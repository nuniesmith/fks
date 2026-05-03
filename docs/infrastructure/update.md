Yes, absolutely — and honestly for a solo homelab setup like FKS, this is a great simplification. You're already using Tailscale as your VPN mesh for all server access, so you can lean into it much harder and drop Authelia entirely.

Here are the three options, from simplest to most granular:

---

## Option A — Tailscale as the Auth Layer (Recommended for Solo)

Since it's just you, the simplest approach: **bind all services to the Tailscale interface only**. Being on the tailnet *is* the authentication. No login portal needed at all.

In your Nginx config, instead of listening on `0.0.0.0`, bind to your Tailscale IP:

```nginx
# infrastructure/config/nginx/nginx.conf
server {
    listen 100.x.x.x:80;   # Your Tailscale IP
    listen 100.x.x.x:443 ssl;
    # ... rest of config, NO auth_request to Authelia
}
```

Or use `tailscale serve` to front everything — Tailscale itself terminates HTTPS and proxies to your services:

```bash
tailscale serve --bg http://localhost:8080  # Web dashboard
tailscale serve --bg http://localhost:3000  # Grafana
```

This means the services are **never reachable** without being on your tailnet. You can gut the entire Authelia compose service, its Redis session store, its config files, and the `auth_request` directives from Nginx.

---

## Option B — `tailscale/nginx-auth` Sidecar

If you want to keep Nginx as the entry point but replace Authelia's `auth_request` with Tailscale identity validation, run the official `tailscale/nginx-auth` container:

```yaml
# docker-compose.yml addition
tailscale-auth:
  image: ghcr.io/tailscale/tailscale-nginx-auth:latest
  volumes:
    - /var/run/tailscale/tailscaled.sock:/var/run/tailscale/tailscaled.sock
  restart: unless-stopped
```

Then swap Authelia's `auth_request` in Nginx:

```nginx
# Before (Authelia)
auth_request /authelia;

# After (Tailscale)
auth_request /_tailscale_auth;
location = /_tailscale_auth {
    proxy_pass http://tailscale-auth:8080;
    proxy_set_header Remote-Addr $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

This gives you per-request identity validation using your Tailscale node identity — useful if you ever add other tailnet members (e.g., giving a friend read-only Grafana access).

---

## Option C — Tailscale as OIDC Provider

Tailscale can act as an OIDC identity provider (available on Personal/Pro plans). You'd configure Authelia or any OIDC-compatible app to use `https://your-tailnet.ts.net` as the issuer. This is the most enterprise-y path and is overkill for your use case.

---

## What to Remove

Once you go with Option A or B, you can cut from the stack:
- The `authelia` service and its image
- The `authelia-redis` session store (if separate from your main Redis)
- `infrastructure/config/authelia/` config directory
- All `auth_request` and `error_page 401` blocks from Nginx
- `AUTH_` related env vars from `.env`

For FKS as a solo trading platform you own entirely, **Option A is the right call** — it removes an entire auth layer with zero loss of security (Tailscale's WireGuard is stronger than a web login portal anyway).

How can i do option A, this would seperate user space from the services, the services will still be able to reach out external for apis and such and then keeps the user space clean and using tailscale. I always have tailscale running on the host computers, and prod server right now is oryx with is deployed with ci-cd.

Then its trimming the fat and focued on our two apps fks_janus and fks_ruby and all the service containers

Let me pull the actual compose and nginx configs so the advice is concrete.Good — I can see the full picture now. Let me also grab the nginx config.Good, I have everything I need. The compose file tells the full story — I can see the empty `# AUTH` section where Authelia used to live, the `authelia_users` volume still mounted into `ruby` and `data`, and all service ports bound to `0.0.0.0`. Here's the complete plan.

---

## The Architecture After This Change

```
[You, on tailnet]
      ↓ HTTPS via Tailscale
[Oryx — tailscale serve]
      ↓ proxies to 127.0.0.1:80
[fks_nginx — bound to loopback only]
      ↓ internal Docker network (fks-network)
[fks_janus] [fks_ruby] [grafana] [etc.]
      ↓ outbound via eth0 (host NAT)
[Kraken / Binance / Massive / Rithmic APIs]
```

Services can still reach external APIs freely. The Tailscale interface (`ts0`) and the main NIC (`eth0`) are completely separate — Docker's NAT routes egress through `eth0` regardless. Tailscale only controls who can reach the front door.

---

## Step 1 — Bind Everything to Loopback in docker-compose.yml

Right now every port is `"HOST:CONTAINER"` which binds to `0.0.0.0`. Change them all to `"127.0.0.1:HOST:CONTAINER"`. This is the core of Option A — services are unreachable from the network, only from localhost (where `tailscale serve` will proxy).

The ports section of each service becomes:

```yaml
# nginx — the ONLY entry point
nginx:
  ports:
    - "127.0.0.1:80:80"
    - "127.0.0.1:443:443"

# All internal services — loopback only (for local debugging if needed)
# If you never need to hit these directly, remove the ports: block entirely
postgres:
  ports:
    - "127.0.0.1:5432:5432"

redis:
  ports:
    - "127.0.0.1:6379:6379"

questdb:
  ports:
    - "127.0.0.1:9000:9000"
    - "127.0.0.1:9009:9009"
    - "127.0.0.1:8812:8812"
    - "127.0.0.1:9003:9003"

janus:
  ports:
    - "127.0.0.1:9051:50051"
    - "127.0.0.1:7000:8080"
    - "127.0.0.1:9092:9092"

ruby:
  ports:
    - "127.0.0.1:8050:8000"
    - "127.0.0.1:8080:8080"

charting:
  ports:
    - "127.0.0.1:8003:8003"
```

Anything in the monitoring stack (grafana `:3000`, prometheus `:9090`, alertmanager `:9093`, jaeger `:16686`, loki `:3100`) gets the same treatment or you just remove the `ports:` blocks entirely since nginx already proxies them.

---

## Step 2 — Remove the Authelia Cruft

The `# AUTH` section is already empty, but the artifacts are still embedded. Three things to clean:

**In `ruby` service, remove:**
```yaml
# Remove this env var
- AUTHELIA_USERS_FILE=/config/authelia/users_database.yml

# Remove this volume mount
- authelia_users:/config/authelia:rw
```

**In `data` service (split profile), same removals.**

**At the bottom of the compose, remove the volume:**
```yaml
volumes:
  # Delete this line:
  authelia_users:
```

---

## Step 3 — Set Up `tailscale serve` on Oryx

SSH into Oryx and run this once:

```bash
# Serve HTTP → nginx loopback, with Tailscale handling HTTPS
tailscale serve --bg http://localhost:80

# Verify it's active
tailscale serve status
```

Tailscale will provision a cert for your node's MagicDNS name (e.g. `oryx.your-tailnet.ts.net`) and terminate HTTPS. You hit `https://oryx.your-tailnet.ts.net` from any of your tailnet machines and it proxies to nginx on loopback.

If you want subpath routing (e.g. grafana on a separate port exposed cleanly), you can do:
```bash
tailscale serve --bg --set-path /grafana http://localhost:3000
```

But in your case nginx already handles all the routing, so one serve pointing to port 80 is enough.

---

## Step 4 — Update the CI/CD Deploy Step

Your CI/CD already uses Tailscale for SSH access to Oryx (you have `TAILSCALE_OAUTH_CLIENT_ID` / `TAILSCALE_OAUTH_SECRET` in GitHub Secrets). The only addition is making sure `tailscale serve` persists across deploys. Add this to your deploy workflow after the `docker compose up` step:

```yaml
- name: Ensure tailscale serve is active
  run: |
    tailscale serve status | grep -q "localhost:80" || \
      tailscale serve --bg http://localhost:80
```

That's idempotent — it only sets it up if it's not already running. The `--bg` flag makes it persistent across tailscale restarts.

---

## What Gets Removed vs What Stays

**Removed entirely:**
- Authelia service + its Redis session store (if you had one)
- `authelia_users` volume
- `AUTHELIA_USERS_FILE` env vars
- `auth_request` directives in nginx config
- Any `error_page 401` / Authelia redirect rules in nginx

**Stays exactly as-is:**
- All of `fks-network` (internal Docker networking unchanged)
- nginx as the internal router between services
- All SSL cert handling (Tailscale replaces this for the user-facing side, but keep the Cloudflare origin cert for `fkstrading.xyz` if you still want the public domain to work — just don't expose it to non-tailnet users)
- Every service's internal communication (fks_janus → fks_ruby, etc.)

---

## One Gotcha — Cloudflare / `fkstrading.xyz`

Your README mentions `fkstrading.xyz` with a Cloudflare Origin Certificate stored in GitHub Secrets. If you want that public domain to still work for anything (webhooks, TradingView callbacks, etc.), you have two paths:

1. **Keep it but firewall it** — leave the Cloudflare proxy in front, which means traffic arriving at Oryx is always from Cloudflare's IPs. Add a UFW rule that only allows 80/443 from [Cloudflare's IP ranges](https://www.cloudflare.com/ips/) plus the Tailscale CIDR `100.64.0.0/10`.

2. **Go full tailnet** — remove the public domain entirely, use only `oryx.your-tailnet.ts.net`. For TradingView webhooks you'd need a separate lightweight public endpoint (e.g. a tiny VPS or Cloudflare Worker that validates and forwards into your tailnet).

For a solo trading platform with no external webhook needs, option 2 is cleaner. If your TradingView Pine Script or Rithmic callbacks need to reach in, option 1 is the safer path.

Let me grab the CI/CD workflow first.Can't access the workflow files directly, but from the README I have everything I need — the secrets list, the deploy chain, and the `ssl-renew.yml`. Here's the complete picture.

---

## What Changes Across the Whole Stack

### Secrets to Delete from GitHub

These are dead weight going forward — remove them from your repo Settings → Secrets:

```
CF_ORIGIN_CERT
CF_ORIGIN_KEY
CLOUDFLARE_API_KEY
CLOUDFLARE_ZONE_ID
```

`TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_SECRET` stay — you still need those for the Actions runner to join the tailnet during CI.

---

### Delete `ssl-renew.yml` Entirely

That workflow exists solely to push the Cloudflare cert. With full Tailscale, it's obsolete.

---

### Nginx — Strip SSL, HTTP Only

Tailscale terminates HTTPS before traffic even reaches nginx. So nginx becomes a plain HTTP router on port 80 with no cert config at all. In your nginx Dockerfile or baked config, the server block simplifies to:

```nginx
server {
    listen 80;
    server_name _;

    # Web dashboard
    location / {
        proxy_pass http://fks_ruby:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Data API
    location /api/ {
        proxy_pass http://fks_ruby:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE — needs buffering off
    location /api/stream {
        proxy_pass http://fks_ruby:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding on;
    }

    # Janus HTTP API
    location /janus/ {
        proxy_pass http://fks_janus:8080/;
    }

    # Grafana
    location /grafana/ {
        proxy_pass http://fks_grafana:3000/;
    }

    # Prometheus
    location /prometheus/ {
        proxy_pass http://fks_prometheus:9090/;
    }

    # Jaeger
    location /jaeger/ {
        proxy_pass http://fks_jaeger:16686/;
    }

    # Charting
    location /charts/ {
        proxy_pass http://fks_charting:8003/;
    }
}
```

No `ssl_certificate`, no `listen 443`, no `certbot_www` volume. Nginx just routes — Tailscale owns TLS.

---

### docker-compose.yml Changes

**Nginx — remove SSL volumes and port 443:**
```yaml
nginx:
  ports:
    - "127.0.0.1:80:80"   # loopback only, no 443
  volumes:
    # DELETE BOTH of these:
    # - ssl_certs:/etc/letsencrypt-volume:ro
    # - certbot_www:/var/www/certbot:ro
    - /dev/null:/etc/nginx/conf.d/default.conf:ro  # keep this one
  environment:
    - API_KEY=${API_KEY:-}
    # DELETE:
    # - SSL_DOMAIN=${SSL_DOMAIN:-fkstrading.xyz}
```

**All other services — loopback bind** (as covered in the previous message). The key ones:

```yaml
postgres:
  ports:
    - "127.0.0.1:5432:5432"

redis:
  ports:
    - "127.0.0.1:6379:6379"

janus:
  ports:
    - "127.0.0.1:7000:8080"
    - "127.0.0.1:9051:50051"
    - "127.0.0.1:9092:9092"

ruby:
  ports:
    - "127.0.0.1:8050:8000"
    - "127.0.0.1:8080:8080"
```

**Remove the `ssl_certs` and `certbot_www` volumes** from the bottom `volumes:` block.

**Remove Authelia artifacts** from `ruby` and `data`:
```yaml
# Delete from ruby environment:
- AUTHELIA_USERS_FILE=/config/authelia/users_database.yml

# Delete from ruby volumes:
- authelia_users:/config/authelia:rw

# Delete the volume at the bottom:
authelia_users:
```

---

### CI/CD Deploy Workflow

The current deploy chain is `Tailscale → DNS → SSL → SSH → Health checks`. The new chain drops DNS and SSL steps entirely and adds a `tailscale serve` step after bringing the stack up. Your deploy job becomes:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Connect to Tailscale
        uses: tailscale/github-action@v2
        with:
          oauth-client-id: ${{ secrets.TAILSCALE_OAUTH_CLIENT_ID }}
          oauth-secret: ${{ secrets.TAILSCALE_OAUTH_SECRET }}
          tags: tag:ci

      - name: Deploy to Oryx
        env:
          SSH_KEY: ${{ secrets.PROD_SSH_KEY }}
        run: |
          echo "$SSH_KEY" > /tmp/deploy_key
          chmod 600 /tmp/deploy_key

          ssh -i /tmp/deploy_key \
              -o StrictHostKeyChecking=no \
              -p ${{ secrets.PROD_SSH_PORT }} \
              ${{ secrets.PROD_SSH_USER }}@${{ secrets.PROD_TAILSCALE_IP }} \
              'bash -s' << 'ENDSSH'

            set -e
            cd /opt/fks   # or wherever you deploy

            # Pull latest images
            docker compose pull

            # Bring up the stack
            docker compose up -d --remove-orphans

            # Wait for nginx to be healthy
            timeout 60 bash -c 'until curl -sf http://127.0.0.1:80/health; do sleep 2; done'

            # Ensure tailscale serve is routing HTTPS → nginx
            # Idempotent — no-op if already configured
            tailscale serve status 2>/dev/null | grep -q "127.0.0.1:80" \
              || tailscale serve --bg http://127.0.0.1:80

            echo "✅ Deploy complete"
            echo "🌐 Accessible at: $(tailscale status --json | python3 -c 'import json,sys; n=json.load(sys.stdin); print([v["DNSName"] for v in n["Peer"].values() if "oryx" in v.get("HostName","").lower()] or [n["Self"]["DNSName"]])')"

          ENDSSH

      - name: Run health checks
        run: |
          ssh -i /tmp/deploy_key \
              -o StrictHostKeyChecking=no \
              -p ${{ secrets.PROD_SSH_PORT }} \
              ${{ secrets.PROD_SSH_USER }}@${{ secrets.PROD_TAILSCALE_IP }} \
              'curl -sf http://127.0.0.1:7000/health && \
               curl -sf http://127.0.0.1:8050/health && \
               echo "All health checks passed"'

      - name: Notify Discord
        if: always()
        uses: Ilshidur/action-discord@master
        env:
          DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_ACTIONS }}
        with:
          args: "FKS deploy ${{ job.status }} — ${{ github.sha }}"
```

The `tailscale serve` line is fully idempotent — if it's already set up from a previous deploy, the `grep -q` short-circuits it.

---

### One-Time Setup on Oryx

The very first time (before CI/CD runs this), SSH in manually and run:

```bash
# Enable HTTPS proxy — Tailscale auto-provisions the cert for oryx.<tailnet>.ts.net
tailscale serve --bg http://127.0.0.1:80

# Confirm
tailscale serve status
# Should show:
# https://oryx.your-tailnet.ts.net (Tailscale HTTPS)
# |-- / proxy http://127.0.0.1:80
```

After that every CI/CD run just checks it's still there and moves on. You access everything at `https://oryx.your-tailnet.ts.net` from any of your tailnet machines (Sullivan, Freddy, your laptop) — no password, no portal, just WireGuard.
