#!/usr/bin/env python3
"""Report where docker-compose.yml's defaults disagree with the live .env.

WHY THIS EXISTS. An external review found `ORB_PLAN_TIME` defaulting to 10:00
in compose while the deployment ran 09:47. Because every other session's plan
is derived from the lag that implies, a rebuild from a clean checkout would
have fired BOTH futures plans thirteen minutes late — and on 2026-08-31 gold
broke its real low at 08:35, so a late plan is not a cosmetic difference.

The general problem: "it works on the box" and "the repository describes what
is on the box" are different claims, and nothing checked the second one.

WHAT IT DOES NOT DO: judge. Three kinds of difference are EXPECTED and are
bucketed rather than flagged —

  secret          credentials belong in .env and must never have a compose
                  default. A difference here is correct.
  safe-off        compose deliberately defaults dangerous things OFF
                  (ENABLE_EXECUTION, RITHMIC_ENABLED, ...). A live "on" is the
                  operator's decision, not drift.
  per-deployment  account ids, broker logins, host paths — one box's truth.

What is left is behavioural drift: values that SHOULD agree and do not.

  ⚠ VALUES ARE NEVER PRINTED. Only key names and compose-side defaults. This
  script exists partly because an ad-hoc version of it dumped live secrets —
  the Rithmic password, Discord webhooks and DB passwords — into a terminal on
  2026-09-02. Masking is not a nicety here; it is the reason this is a
  committed script instead of a one-liner someone retypes from memory.

Usage:  scripts/compose-env-drift.py [--compose FILE] [--env FILE]
Exit:   0 no behavioural drift · 1 drift found · 2 could not read inputs
"""

from __future__ import annotations

import argparse
import re
import sys

# A key is treated as secret on NAME alone. Deliberately broad: a false
# positive costs one line of output, a false negative prints a credential.
SECRET = re.compile(r"PASSWORD|TOKEN|SECRET|_KEY$|KEY$|WEBHOOK|CREDENTIAL|DSN|PASS$")

# Compose defaults these OFF on purpose. Running them on is an operator
# decision; reporting it as drift would train the reader to ignore this tool.
SAFE_OFF = {
    "ENABLE_EXECUTION",
    "RITHMIC_ENABLED",
    "JANUS_AUTO_START",
    "EDGE_DECAY_ENABLED",
    "JANUS_EXPERIENCE_ENABLED",
    "JANUS_TRAIN_FROM_QDRANT",
    "JANUS_TRAIN_SCHEDULE_ENABLED",
    "REQUIRE_INTERNAL_TOKEN",
    "JANUS_GATE_METRICS_REDIS",
    "SPOT_LIVE",
}

# One box's truth: broker identity, host paths, instance names. A shared
# default would be wrong for everyone else.
PER_DEPLOYMENT = {
    "RITHMIC_ACCOUNT_ID",
    "RITHMIC_USER",
    "RITHMIC_FCM_ID",
    "RITHMIC_IB_ID",
    "RITHMIC_STARTING_EQUITY",
    "RITHMIC_GATEWAY_URL",
    "RITHMIC_GATEWAY_ALT_URL",
    "FKS_TEXTFILE_DIR",
    "OPTIMIZER_INSTANCE_ID",
    "SPAWNER_REPO",
    "EXEC_ACCOUNT_TYPE",
    "NET_WORTH_BOT_CADENCE_SECS",
    # Account-size dependent (4,500 on a 150k eval, less on a smaller one). A
    # shared default would be wrong for everyone else, and empty is the SAFE
    # state: the connector then claims no floor at all and the briefing
    # publishes no size, rather than sizing against someone else's account.
    "RITHMIC_TRAILING_DD",
}


def parse_env(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def parse_defaults(path: str) -> dict[str, str]:
    """Every `${VAR:-default}` in the compose file."""
    with open(path, encoding="utf-8") as fh:
        return dict(re.findall(r"\$\{([A-Z0-9_]+):-([^}]*)\}", fh.read()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compose", default="docker-compose.yml")
    ap.add_argument("--env", default=".env")
    args = ap.parse_args()

    try:
        env = parse_env(args.env)
        defaults = parse_defaults(args.compose)
    except OSError as e:
        print(f"could not read inputs: {e}", file=sys.stderr)
        return 2

    drift, secret, safe_off, per_dep = [], [], [], []
    for key, live in sorted(env.items()):
        if key not in defaults or defaults[key] == live:
            continue
        if SECRET.search(key):
            secret.append(key)
        elif key in SAFE_OFF:
            safe_off.append(key)
        elif key in PER_DEPLOYMENT:
            per_dep.append(key)
        else:
            drift.append(key)

    print(f"{len(defaults)} compose defaults · {len(env)} live vars\n")
    print(f"  expected differences: {len(secret)} secret, "
          f"{len(safe_off)} safe-off, {len(per_dep)} per-deployment")

    if not drift:
        print("\n  no behavioural drift — the repository reproduces this deployment")
        return 0

    print(f"\n  BEHAVIOURAL DRIFT ({len(drift)}) — these should agree and do not:")
    for key in drift:
        # compose-side default only. The live value is never printed.
        print(f"    {key:34} compose default = {defaults[key]!r}")
    print("\n  Either align the compose default, or add the key to SAFE_OFF /")
    print("  PER_DEPLOYMENT above with a reason. Silence is not an option:")
    print("  a default nobody reconciles is a deployment nobody can rebuild.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
