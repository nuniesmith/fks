#!/usr/bin/env python3
"""Regression guard for auth-chain M1/M7 — webui login CSRF origin.

Background
----------
The webui (SvelteKit + adapter-node) is fronted by nginx, which is fronted by
tailscale. tailscale terminates TLS and forwards a *plaintext* request to nginx,
which `listen 80;` only ("ssl":"off"). Every webui-bound nginx location stamps
`proxy_set_header X-Forwarded-Proto $scheme;` — and because nginx received a
plaintext connection, $scheme == "http". So the header value that actually
reaches the webui is ALWAYS `x-forwarded-proto: http`, regardless of the https
URL the browser used.

SvelteKit's built-in form-action CSRF check (csrf.checkOrigin, default ON)
compares the browser's `Origin` header (https://<tailnet-host>) against the app
origin adapter-node computes. adapter-node's get_origin():

    protocol = normalise_header(PROTOCOL_HEADER, headers[PROTOCOL_HEADER]) || 'https'
    host     = normalise_header(HOST_HEADER, headers[HOST_HEADER]) || headers['host']
    origin   = f"{protocol}://{host}"

If PROTOCOL_HEADER=x-forwarded-proto is set, `protocol` resolves to nginx's
poisoned "http", the app origin becomes http://<host>, it mismatches the
browser's https://<host>, and the login POST 403s ("Cross-site POST form
submissions are forbidden") — the operator cannot log in via the documented
tailnet HTTPS access path.

The fix (M1/M7): leave PROTOCOL_HEADER UNSET so adapter-node defaults the scheme
to "https" (the true external scheme, since tailscale always terminates TLS),
and keep HOST_HEADER=host. Do NOT pin ORIGIN (adapter-node then ignores
HOST_HEADER and re-introduces the localhost:3001 mismatch).

This test parses the real docker-compose.yml webui env, replicates get_origin()
exactly under the headers nginx actually delivers, and asserts the computed app
origin equals the browser origin — i.e. the login POST is NOT 403'd.

Runs offline (no docker, no stack). Exit 0 = pass.
"""
from __future__ import annotations

import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.yml"

# The documented access path: browser loads the tailnet host over HTTPS.
TAILNET_HOST = "oryx.tailfef10.ts.net"
BROWSER_ORIGIN = f"https://{TAILNET_HOST}"

# Headers as they ACTUALLY arrive at fks_webui:3000 behind nginx (conf: every
# webui location sets `X-Forwarded-Proto $scheme` and nginx is HTTP-only, so the
# webui sees "http"; Host is passed through as $host = the tailnet hostname).
INBOUND_HEADERS = {
    "x-forwarded-proto": "http",
    "host": TAILNET_HOST,
    "x-real-ip": "100.64.0.9",
}


def webui_env(compose_path: pathlib.Path) -> dict[str, str]:
    doc = yaml.safe_load(compose_path.read_text())
    svc = doc["services"]["webui"]
    env = svc.get("environment", [])
    out: dict[str, str] = {}
    if isinstance(env, dict):
        for k, v in env.items():
            out[k] = "" if v is None else str(v)
    else:
        for item in env:
            k, sep, v = str(item).partition("=")
            if sep:
                out[k] = v
    return out


def normalise_header(name: str, value):
    """Port of adapter-node's normalise_header (handler.js)."""
    if not name:  # empty PROTOCOL_HEADER/HOST_HEADER => header lookup disabled
        return None
    if isinstance(value, list):
        if not value:
            return None
        if len(value) == 1:
            return value[0]
        raise ValueError(f"Multiple values for {name}")
    return value


def get_origin(env: dict[str, str], headers: dict[str, str]) -> str:
    """Port of adapter-node get_origin() + the ORIGIN short-circuit.

    handler.js: `base: origin || get_origin(req.headers)` where
    `origin = parse_origin(env('ORIGIN', undefined))`.
    """
    static_origin = env.get("ORIGIN", "").strip()
    if static_origin:
        return static_origin.rstrip("/")

    protocol_header = env.get("PROTOCOL_HEADER", "").lower()
    host_header = env.get("HOST_HEADER", "").lower()

    protocol = normalise_header(protocol_header, headers.get(protocol_header)) or "https"
    host = normalise_header(host_header, headers.get(host_header)) or headers.get("host")
    if not host:
        raise ValueError("Could not determine host")
    return f"{protocol}://{host}"


def main() -> int:
    if not COMPOSE.exists():
        print(f"FAIL: compose not found at {COMPOSE}", file=sys.stderr)
        return 2

    env = webui_env(COMPOSE)
    computed = get_origin(env, INBOUND_HEADERS)

    print(f"webui ORIGIN          = {env.get('ORIGIN', '<unset>')!r}")
    print(f"webui PROTOCOL_HEADER = {env.get('PROTOCOL_HEADER', '<unset>')!r}")
    print(f"webui HOST_HEADER     = {env.get('HOST_HEADER', '<unset>')!r}")
    print(f"browser Origin        = {BROWSER_ORIGIN}")
    print(f"computed app origin   = {computed}")

    if computed != BROWSER_ORIGIN:
        print(
            "\nFAIL (M1/M7): app origin != browser origin — SvelteKit form CSRF "
            "will 403 the login POST on the tailnet HTTPS path.\n"
            "  Fix: leave PROTOCOL_HEADER UNSET (adapter-node defaults to https) "
            "and keep HOST_HEADER=host; do not pin ORIGIN.",
            file=sys.stderr,
        )
        return 1

    # Guard the specific footgun explicitly for a clear failure message.
    if env.get("PROTOCOL_HEADER", "").lower() == "x-forwarded-proto":
        print(
            "\nFAIL (M1/M7): PROTOCOL_HEADER=x-forwarded-proto reads nginx's "
            "$scheme=http and bricks login. Remove it.",
            file=sys.stderr,
        )
        return 1

    print("\nPASS: login POST origin check succeeds on the tailnet HTTPS path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
