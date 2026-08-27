#!/usr/bin/env python3
"""Print this credential's FCM ID, IB ID and account list — once, by hand.

WHY THIS EXISTS
---------------
The read-only positions/PnL reader needs a triple: account_id, fcm_id, ib_id.
The account id is on the prop-firm dashboard; the other two are not shown
anywhere in R|Trader Pro's connection view, and they are not optional — Rithmic
will not build a PnL request without them (verified 2026-08-27: with the order
plant closed, `async_rithmic` fails at protobuf serialisation because
`client.fcm_id` resolves to None).

Every other platform — NinjaTrader, Sierra Chart, Jigsaw, ATAS, R|Trader Pro —
gets them the same way: the ORDER PLANT's login response carries them. That is
why none of those platforms asks you for an FCM. They are not doing something
cleverer; they simply open a plant we do not.

⚠ THIS SCRIPT OPENS THE ORDER PLANT. THE CONNECTOR STILL DOES NOT.
------------------------------------------------------------------
That distinction is the whole design and it is worth being precise about:

  * `fks-state/crates/rithmic-connector` never references `RithmicOrderPlant`
    at all. `read_only: true` / `order_plant_open: false` are CONSTANTS in
    state.rs, asserted in tests. The long-running service that watches your
    market data cannot place an order because the code to do so is not in that
    binary. Running this script does not change one line of that.

  * This is a separate, one-shot operator tool, in the same spirit as
    `rithmic-list-systems.py`. It logs in, reads two strings, and exits. It
    makes NO order-entry calls — no place, no modify, no cancel — and the only
    plant-level methods it touches are login and logout.

Run it once. Paste the values into the webui Settings → Rithmic accounts panel
(or fks/.env). You should never need it again.

USAGE
-----
    # credentials come from the environment, never from argv (argv is visible
    # in `ps` to every user on the box)
    set -a; . ~/github/pine/.env; set +a
    python3 scripts/rithmic-discover-account.py

    # or, if the connector's secrets are the ones you want:
    source scripts/rithmic-secrets-refresh.sh
    python3 scripts/rithmic-discover-account.py

Requires `async-rithmic` (already installed in ~/github/pine/.venv):
    ~/github/pine/.venv/bin/python scripts/rithmic-discover-account.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# The opening range is the one thing on this platform that cannot be recovered
# after the fact — Rithmic does not backfill, so a minute lost here is lost for
# good. ONE SESSION PER CREDENTIAL means this script's login can evict the
# connector's, so it refuses to run anywhere near the window that matters.
BLACKOUT_START = dtime(9, 20)
BLACKOUT_END = dtime(9, 50)


def _blackout_now() -> str | None:
    now = datetime.now(NY)
    if now.weekday() >= 5:
        return None
    if BLACKOUT_START <= now.timetz().replace(tzinfo=None) <= BLACKOUT_END:
        return now.strftime("%H:%M ET")
    return None


def _require_env() -> dict:
    need = ("RITHMIC_USER", "RITHMIC_PASSWORD", "RITHMIC_SYSTEM_NAME")
    missing = [k for k in need if not os.environ.get(k, "").strip()]
    gateway = os.environ.get("RITHMIC_GATEWAY") or os.environ.get("RITHMIC_GATEWAY_URL") or ""
    if not gateway.strip():
        missing.append("RITHMIC_GATEWAY (or RITHMIC_GATEWAY_URL)")
    if missing:
        sys.exit(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + "\n\nSource them first, e.g.:\n"
            "    set -a; . ~/github/pine/.env; set +a"
        )
    return dict(
        user=os.environ["RITHMIC_USER"].strip(),
        password=os.environ["RITHMIC_PASSWORD"],
        system_name=os.environ["RITHMIC_SYSTEM_NAME"].strip(),
        # The client prefixes wss:// itself; strip one if it is already there so
        # both env spellings work.
        url=gateway.strip().removeprefix("wss://").removeprefix("https://"),
        app_name=os.environ.get("RITHMIC_APP_NAME", "fks-discover").strip(),
        app_version=os.environ.get("RITHMIC_APP_VERSION", "1.0.0").strip(),
    )


def _connector_holding() -> str | None:
    """Is the live connector currently holding this credential's session?

    Advisory only — it reads the connector's own /status. If the connector is
    connected, logging in here will very likely evict it, and the operator
    should choose that deliberately rather than discover it from a gap in
    candles_futures tomorrow.
    """
    try:
        import json
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:9094/status", timeout=3) as r:
            s = json.load(r)
        if s.get("connected") and not s.get("killed"):
            return "connected and streaming"
        if s.get("killed"):
            return None  # released — the session is free, which is what we want
    except Exception:
        return None  # not running, or not reachable: nothing to evict
    return None


async def discover(creds: dict) -> int:
    try:
        from async_rithmic import RithmicClient, SysInfraType
    except ImportError:
        sys.exit(
            "async-rithmic is not installed for this interpreter.\n"
            "Try:  ~/github/pine/.venv/bin/python scripts/rithmic-discover-account.py"
        )

    client = RithmicClient(**creds)
    # ORDER_PLANT only. Not the default set — `connect()` with no argument also
    # opens TICKER, which is the plant the live feed holds, and there is no
    # reason to contend with it for a two-string lookup.
    await client.connect(plants=[SysInfraType.ORDER_PLANT])
    try:
        info = client.plants["order"].login_info or {}
        fcm = client.fcm_id
        ib = client.ib_id
        accounts = client.accounts or []

        print()
        print("  ── Rithmic account identifiers ──────────────────────────────")
        print(f"  RITHMIC_FCM_ID      {fcm if fcm else '(not returned)'}")
        print(f"  RITHMIC_IB_ID       {ib if ib else '(not returned)'}")
        print()
        if accounts:
            print(f"  accounts on this login ({len(accounts)}):")
            for a in accounts:
                aid = getattr(a, "account_id", None) or "?"
                print(f"    RITHMIC_ACCOUNT_ID  {aid}")
        else:
            print("  accounts: (none returned)")
        print()

        if not (fcm and ib):
            # Say what was actually received rather than guessing, so a support
            # ticket can quote it.
            keys = sorted(k for k in info if "id" in k.lower() or "name" in k.lower())
            print("  ⚠ The login response did not carry both ids.")
            print(f"    Fields it did return: {keys or '(none)'}")
            print("    Quote that to your prop firm's support and ask for the")
            print("    FCM and IB ids for your account.")
            return 1

        print("  Paste these into the webui: Settings → Rithmic accounts.")
        print("  Positions stay off until account_id, fcm_id AND ib_id are all set.")
        return 0
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--force",
        action="store_true",
        help="run even inside the 09:20-09:50 ET opening-range blackout, or while "
        "the connector is streaming. Both are session-evicting; be sure.",
    )
    args = ap.parse_args()

    when = _blackout_now()
    if when and not args.force:
        sys.exit(
            f"REFUSING: it is {when}, inside the 09:20-09:50 ET opening-range window.\n"
            "One session per credential — this login would evict the market-data\n"
            "feed exactly when today's range is forming, and Rithmic does not\n"
            "backfill. Run it after 09:50, or pass --force if you truly mean it."
        )

    holding = _connector_holding()
    if holding and not args.force:
        sys.exit(
            f"REFUSING: the Rithmic connector is {holding}.\n"
            "Logging in here would take its session. Release it first\n"
            "(webui /futures → Session → RELEASE, or\n"
            " curl -X POST -H \"X-Internal-Token: $TOK\" http://127.0.0.1:9094/kill),\n"
            "then re-run. Pass --force to override."
        )

    creds = _require_env()
    print(f"  system   {creds['system_name']}")
    print(f"  gateway  {creds['url']}")
    print(f"  user     {creds['user']}")
    print("  opening the ORDER plant (read-only; no order-entry calls) …")
    return asyncio.run(discover(creds))


if __name__ == "__main__":
    raise SystemExit(main())
