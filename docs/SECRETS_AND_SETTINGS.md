# Secrets and Settings

This repo previously committed sensitive values in `.env`. Those have been removed. Follow this guide to manage secrets safely and expose only non-sensitive settings to the React app.

## Where to put secrets

- Local development: create `.env.local` at repo root. This file is git-ignored.
- Production: use Docker secrets or provider-specific secret managers (e.g., environment variables injected via CI/CD or orchestration).

Never commit secrets to the repo. The `.gitignore` now ignores `.env` variants except example/templates.

## React app and secrets

React builds run in the browser; anything in `VITE_*` envs is public. Do not store API keys or client secrets in the React bundle. Instead:

- Use the in-app Settings page at `/settings` to set non-secret URLs (API base). These are stored in `localStorage` on the client.
- Enter provider API keys in `/settings/providers`. The keys are sent to the server and stored server-side (with optional encryption-at-rest).

## Google OAuth

- Only the public Client ID and redirect URI are used in the client.
- Client secrets must live on the backend. The code exchange should be performed on the server in production.

## Rithmic and other providers

- Do not put provider API keys in committed `.env`. Set them via server admin endpoints or `.env.local` on the server.

## Summary

- Public config: API URLs, feature flags, non-sensitive IDs.
- Private secrets: API keys, passwords, JWT signing secrets—kept in `.env.local` or Docker secrets.
