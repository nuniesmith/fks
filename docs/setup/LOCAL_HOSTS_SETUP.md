# Local hosts setup for fkstrading.xyz

Use this to route local domains to your running Docker stack via Nginx.

## 1) Edit /etc/hosts

Add these lines to the bottom of /etc/hosts:

```text
127.0.0.1 fkstrading.xyz www.fkstrading.xyz
127.0.0.1 api.fkstrading.xyz data.fkstrading.xyz auth.fkstrading.xyz code.fkstrading.xyz
```

Notes:

- Keep the existing localhost entries as-is. The above lines only add domain aliases to 127.0.0.1.
- This setup is HTTP-only locally. Use http://, not https://.

## 2) Start services

From the repo root:

- To bring everything up: ./start.sh --gpu
- If already up and you changed /etc/hosts, no container restart is needed.

The Nginx gateway uses `config/networking/nginx/simple.conf` and listens on port 80 (`docker-compose.override.yml`).

## 3) Quick checks

You can verify routing without editing /etc/hosts by spoofing the Host header:

- Web (root): `curl -I http://127.0.0.1/health -H 'Host: fkstrading.xyz'`
- API: `curl -I http://127.0.0.1/health -H 'Host: api.fkstrading.xyz'`
- Data: `curl -I http://127.0.0.1/health -H 'Host: data.fkstrading.xyz'`
- Auth: `curl -I http://127.0.0.1/health -H 'Host: auth.fkstrading.xyz'`
- VS Code: `curl -I http://127.0.0.1/health -H 'Host: code.fkstrading.xyz'`

Expect HTTP/1.1 200 OK from each. Alternatively, run scripts/check_routing.sh.

## 4) Troubleshooting

- Browser forces https:
  - Use `http://fkstrading.xyz` (without s). If a previous HSTS entry exists, try a private window or clear HSTS for the domain.
- Nothing resolves to 127.0.0.1:
  - Confirm /etc/hosts lines are present and not shadowed by earlier lines. /etc/hosts overrides DNS.
- 502/404 from a subdomain:
  - Ensure the corresponding service is healthy: api (8000), data (9001), authelia-server (9000), vscode (8080) in the fks-network.
- Port conflicts:
  - Locally we bind only port 80 for Nginx (docker-compose.override.yml). Stop any other service using port 80.

## 5) Optional: local HTTPS

If you need https:// locally, use mkcert to create a local CA and certs for fkstrading.xyz and subdomains, then add 443 server blocks. Current dev flow is HTTP-only to keep it simple.
