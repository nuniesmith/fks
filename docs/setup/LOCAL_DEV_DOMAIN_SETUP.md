# Local Dev Domains (fkstrading.test)

Use a dev-only domain with subdomains to mirror prod routing:

- fkstrading.test → SPA via nginx
- api.fkstrading.test → API service (optional direct)
- data.fkstrading.test → Data service (optional direct)
- auth.fkstrading.test → Authentik UI/API

## 1) Hosts file

Add entries to /etc/hosts:

127.0.0.1 fkstrading.test api.fkstrading.test data.fkstrading.test auth.fkstrading.test

Tip: Keep .test TLD (ICANN reserved). If you need HTTPS locally, use mkcert and enable SSL in nginx later.

## 2) Nginx config

The nginx image processes /etc/nginx/templates. We added dev-multi.conf.template which is enabled by default when present. Ensure the container gets BASE_DOMAIN=fkstrading.test:

- In docker-compose.yml (nginx -> environment):

  BASE_DOMAIN: fkstrading.test

The template proxies:

- / → web:3000 (Vite dev server)
- /api → api:8000
- /data → data:9001
- /ws → api:8000 (WebSocket)
- auth.$BASE_DOMAIN → authelia-server:9000

## 3) React env

File: src/web/react/.env.development

- VITE_API_BASE_URL=<http://fkstrading.test/api>
- VITE_WS_BASE_URL=<ws://fkstrading.test/ws>
- VITE_AUTHELIA_URL=<http://auth.fkstrading.test>
- VITE_AUTHELIA_CLIENT_ID=your-client-id

Vite HMR is set to use fkstrading.test so hot reload works behind nginx.

## 4) Authentik application

In Authentik (<http://auth.fkstrading.test>):

- Application → Your SPA client (OIDC, PKCE)
- Redirect URIs: <http://fkstrading.test/auth/callback>
- Scopes: openid, profile, email, groups
- Optional: add groups claim to ID/access token

## 5) Run

- Start backend services (api, data, authelia)
- Start web dev server (npm run dev from repo root or web folder)
- Browse <http://fkstrading.test>

Troubleshooting:

- If white screen, check browser console and nginx logs (docker logs fks_nginx)
- For 401s, confirm Authentik client/redirect URI and VITE_AUTHELIA_* values
- For WS, check /ws proxy and CORS in API
