#!/usr/bin/env python3
"""botsync — sync bots/*.yaml into the fks spawner, then exit.

One-shot container (restart: "no"), runs on every `docker compose up`:
  1. Waits for the spawner to be reachable (compose already gates on healthy).
  2. Upserts each YAML file via POST /configs (idempotent, keyed by `name`).
  3. For configs with `autostart: true` that aren't running, POSTs a respawn.

Env:
  SPAWNER_URL           spawner base URL (default http://fks_bot_spawner:8090)
  NGINX_INTERNAL_TOKEN  sent as X-Internal-Token (spawner auth)
  BOTS_DIR              where the YAML files live (default /bots)
"""

import glob
import os
import re
import sys

import requests
import yaml

SPAWNER_URL = os.environ.get("SPAWNER_URL", "http://fks_bot_spawner:8090").rstrip("/")
TOKEN = os.environ.get("NGINX_INTERNAL_TOKEN", "")
BOTS_DIR = os.environ.get("BOTS_DIR", "/bots")

# Deployment-level keys: consumed here, never sent to the spawner.
LOCAL_KEYS = ("autostart", "description")


def headers():
    h = {"Content-Type": "application/json"}
    if TOKEN:
        h["X-Internal-Token"] = TOKEN
    return h


def template(value):
    """Expand ${VAR} / ${VAR:-default} from the environment (recursive)."""
    if isinstance(value, dict):
        return {k: template(v) for k, v in value.items()}
    if isinstance(value, list):
        return [template(v) for v in value]
    if not isinstance(value, str):
        return value

    def repl(m):
        var, default = m.group(1), m.group(2)
        return os.environ.get(var, default if default is not None else "")

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}", repl, value)


def is_running(bot_id):
    """True if a container with the spawner's fks.bot_id label is running.

    Returns False if no such container exists or none is running, None if
    the check itself failed (fail safe: don't respawn blindly)."""
    try:
        r = requests.get(f"{SPAWNER_URL}/containers", headers=headers(), timeout=10)
        r.raise_for_status()
        containers = r.json().get("containers", [])
    except requests.RequestException as e:
        print(f"botsync: WARN — container list failed: {e}")
        return None
    except ValueError as e:
        print(f"botsync: WARN — bad container list JSON: {e}")
        return None
    matches = [
        c for c in containers
        if c.get("bot_id") == bot_id or c.get("name") == f"fks-bot-{bot_id}"
    ]
    if not matches:
        return False
    return any(c.get("state") == "running" for c in matches)


def main():
    files = sorted(
        glob.glob(os.path.join(BOTS_DIR, "*.yaml"))
        + glob.glob(os.path.join(BOTS_DIR, "*.yml"))
    )
    if not files:
        print(f"botsync: no bot definitions in {BOTS_DIR} — nothing to do")
        return 0

    try:
        requests.get(f"{SPAWNER_URL}/health", timeout=10).raise_for_status()
    except requests.RequestException as e:
        print(f"botsync: ERROR — spawner not reachable at {SPAWNER_URL}: {e}")
        return 1

    failed = 0
    for path in files:
        fname = os.path.basename(path)
        try:
            with open(path) as f:
                cfg = yaml.safe_load(f)
        except Exception as e:  # noqa: BLE001 — report and continue
            print(f"botsync: ERROR — cannot parse {fname}: {e}")
            failed += 1
            continue
        if not isinstance(cfg, dict) or not cfg.get("name"):
            print(f"botsync: ERROR — {fname} has no 'name' key, skipping")
            failed += 1
            continue

        bot_name = cfg["name"]
        autostart = bool(cfg.get("autostart", False))
        payload = template(
            {k: v for k, v in cfg.items() if k not in LOCAL_KEYS}
        )
        try:
            requests.post(
                f"{SPAWNER_URL}/configs", json=payload, headers=headers(), timeout=15
            ).raise_for_status()
            print(f"botsync: upserted '{bot_name}'")
        except requests.RequestException as e:
            print(f"botsync: ERROR — upsert '{bot_name}' failed: {e}")
            failed += 1
            continue

        if autostart:
            running = is_running(cfg.get("bot_id") or bot_name)
            if running is False:
                try:
                    requests.post(
                        f"{SPAWNER_URL}/configs/{bot_name}/respawn",
                        headers=headers(),
                        timeout=30,
                    ).raise_for_status()
                    print(f"botsync: respawned '{bot_name}' (autostart)")
                except requests.RequestException as e:
                    print(f"botsync: ERROR — respawn '{bot_name}' failed: {e}")
                    failed += 1
            elif running is None:
                print(
                    f"botsync: WARN — could not determine status of "
                    f"'{bot_name}', leaving it alone"
                )
            else:
                print(f"botsync: '{bot_name}' already running")

    if failed:
        print(f"botsync: done with {failed} error(s)")
        return 1
    print("botsync: all bot definitions synced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
