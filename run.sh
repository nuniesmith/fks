#!/usr/bin/env bash
# =============================================================================
# FKS — Unified Project Management Script
# =============================================================================
#
# Usage:
#   ./run.sh <command> [flags]
#
# Top-level commands:
#   (no args) / check     clippy + cargo test (Rust)
#   lint                  cargo fmt --check + clippy (no tests)
#   fmt                   Auto-format Rust (cargo fmt)
#   test                  Run all Rust tests
#   all [--demo]          Build images, then start everything
#                         (janus + webui + spawner + monitoring [+ crypto-demo bot])
#   fresh [--demo]        Clean rebuild — stop, rebuild images (incl. postgres),
#                         bootstrap all databases, start everything
#   start [prod]          Env setup → build → start all services (dev or prod)
#   up [prod] [svcs...]   Start services (already built)
#   down [prod] [-v]      Stop services (-v removes volumes)
#   restart [svcs...]     Restart services
#   logs [svc]            Follow service logs
#   status                Show service status
#   health                Health check all services
#   build [svcs...]       Build service images
#   build-redis           Build custom Redis image
#   build-bots            Build the spawnable reference bot images (bots/)
#   setup-env             Generate or validate .env, fill missing secrets, prompt for API keys
#   generate-certs        Generate internal service TLS certs (skips if already present)
#   ssl-local             Force-regenerate internal service TLS certs
#   shell <svc>           Open a shell in a running container
#   clean                 Remove stopped containers and dangling images
#   force-clean           ⚠️  Remove ALL FKS resources including volumes
#   fix-db                Bootstrap all databases (idempotent — safe to re-run)
#   network-cleanup       ⚠️  Fix Docker network conflicts — stops the FULL fks_
#                         stack, removes every fks_* container + fks* network
#                         (prompts y/N; spawner-managed fks-bot-* left running)
#   setup-kernel          Install sysctl tuning (fd limits, net, inotify) — run once per host
#   setup-hosts           Add fkstrading.local entries to /etc/hosts — run once per host
#   diagnose              Show detailed system diagnostics
#   web-hash-password     Generate bcrypt hash for WEB_PASSWORD_HASH
#   tailscale-serve       Expose FKS dashboard via Tailscale HTTPS
#   tailscale-stop        Remove Tailscale HTTPS serve config
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.yml"
PROD_COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"

DC="docker compose -p fks --env-file $ENV_FILE"
DC_RA="docker compose --env-file $ENV_FILE -f $COMPOSE_FILE"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE" 2>/dev/null || true
    set +a
fi
TAILSCALE_IP="${TAILSCALE_IP:-}"

# ---------------------------------------------------------------------------
# Compose profile "state" — private-sibling autodetection
# ---------------------------------------------------------------------------
# advisor + orb-briefing build from the PRIVATE sibling repo ../fks-state and
# are gated behind the compose profile "state" so a fresh host with only the
# public fks repo can still `./run.sh all`. When the sibling checkout exists,
# auto-enable the profile (MERGED into any COMPOSE_PROFILES from .env, not
# overwritten) so behavior on a full checkout is unchanged. Bare
# `docker compose` users without run.sh: set COMPOSE_PROFILES=state in .env.
if [ -d "$SCRIPT_DIR/../fks-state" ]; then
    case ",${COMPOSE_PROFILES:-}," in
        *,state,*) ;; # already listed
        *) COMPOSE_PROFILES="${COMPOSE_PROFILES:+${COMPOSE_PROFILES},}state" ;;
    esac
    export COMPOSE_PROFILES
fi

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log()    { echo -e "${CYAN}[run]${NC} $*"; }
ok()     { echo -e "${GREEN}[  ✓ ]${NC} $*"; }
warn()   { echo -e "${YELLOW}[ warn ]${NC} $*"; }
err()    { echo -e "${RED}[ fail ]${NC} $*"; }
header() { echo -e "${BLUE}===================================================${NC}"; \
           echo -e "${BLUE}  $*${NC}"; \
           echo -e "${BLUE}===================================================${NC}"; }
info()   { echo -e "${BLUE}ℹ $*${NC}"; }

# ---------------------------------------------------------------------------
# Secret generators
# ---------------------------------------------------------------------------

generate_password() {
    openssl rand -base64 48 | tr -d '/+=' | head -c 40 2>/dev/null \
        || python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(40)))"
}

generate_secret() {
    openssl rand -base64 32 | tr -d "=+/\n" | cut -c1-32 2>/dev/null \
        || python3 -c "import secrets; print(secrets.token_urlsafe(24)[:32])"
}

generate_fernet_key() {
    openssl rand -base64 32 | tr '+/' '-_' 2>/dev/null \
        || python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

generate_long_secret() {
    openssl rand -base64 72 | tr -d "=+/\n" | cut -c1-64 2>/dev/null \
        || python3 -c "import secrets; print(secrets.token_urlsafe(48)[:64])"
}

# ---------------------------------------------------------------------------
# Interactive API key prompt
# ---------------------------------------------------------------------------

_prompt_api_keys() {
    local env_file="$1"
    [ -t 0 ] || return 0

    echo ""
    info "Would you like to enter your API keys now?"
    info "  (y) Enter keys interactively — paste each one into the terminal"
    info "  (n) Skip — edit .env manually later"
    echo ""
    printf "  Enter API keys now? [y/N]: "
    local answer=""
    read -r answer
    echo ""

    case "$answer" in
        [yY]|[yY][eE][sS])
            info "Enter each key when prompted (press Enter to skip any)."
            info "Keys are written directly to .env — they never appear in logs."
            echo ""

            _prompt_key() {
                local key="$1" desc="$2" val=""
                printf "  %s (%s): " "$key" "$desc"
                read -r val
                if [ -n "$val" ]; then
                    if grep -q "^${key}=" "$env_file"; then
                        sed -i "s|^${key}=.*|${key}=${val}|" "$env_file"
                    else
                        echo "${key}=${val}" >> "$env_file"
                    fi
                    ok "  Set $key"
                fi
            }

            echo "  ── Required for AI features ──"
            echo ""

            echo "  ── Trading (optional — skip if not trading yet) ──"
            _prompt_key KRAKEN_API_KEY "Kraken API key"
            _prompt_key KRAKEN_API_SECRET "Kraken API secret"
            echo ""

            echo "  ── Market data (optional — features degrade gracefully) ──"
            _prompt_key FINNHUB_API_KEY "Finnhub news key"
            _prompt_key CMC_API_KEY "CoinMarketCap key"
            _prompt_key WHALE_ALERT_API_KEY "Whale Alert key"
            _prompt_key ETHERSCAN_API_KEY "Etherscan key"
            _prompt_key CRYPTOCOMPARE_API_KEY "CryptoCompare key"
            echo ""

            ok "API keys saved to .env"
            ;;
        *)
            info "Skipped — edit .env manually to add API keys later"
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Web password helpers
# ---------------------------------------------------------------------------

_generate_bcrypt_hash() {
    FKS_BCRYPT_PW="$1" python3 -c "
import os, bcrypt
pw = os.environ['FKS_BCRYPT_PW'].encode()
print(bcrypt.hashpw(pw, bcrypt.gensalt()).decode())
" 2>/dev/null || true
}

_prompt_web_password() {
    local env_file="$1"
    local password="" confirm="" hash=""

    [ -t 0 ] || return 0
    grep -q "^WEB_PASSWORD_HASH=.\+" "$env_file" 2>/dev/null && return 0

    echo ""
    info "Set a web dashboard password for WEB_PASSWORD_HASH"
    info "(Press Enter with no input to skip — leaves authentication disabled)"
    echo ""
    printf "  Password : "
    stty -echo 2>/dev/null || true
    read -r password
    stty echo 2>/dev/null || true
    printf "\n"

    if [ -z "$password" ]; then
        warn "No password entered — WEB_PASSWORD_HASH left empty (auth disabled)"
        return 0
    fi

    printf "  Confirm  : "
    stty -echo 2>/dev/null || true
    read -r confirm
    stty echo 2>/dev/null || true
    printf "\n"

    if [ "$password" != "$confirm" ]; then
        warn "Passwords do not match — WEB_PASSWORD_HASH left empty"
        return 0
    fi

    echo ""
    info "Generating bcrypt hash…"
    hash=$(_generate_bcrypt_hash "$password")

    if [ -z "$hash" ]; then
        warn "bcrypt unavailable — set WEB_PASSWORD_HASH manually after: pip install bcrypt"
        warn "  ./run.sh web-hash-password"
        return 0
    fi

    if grep -q "^WEB_PASSWORD_HASH=" "$env_file"; then
        sed -i "s|^WEB_PASSWORD_HASH=.*|WEB_PASSWORD_HASH='${hash}'|" "$env_file"
    else
        echo "WEB_PASSWORD_HASH='${hash}'" >> "$env_file"
    fi
    ok "WEB_PASSWORD_HASH set"
}

# ---------------------------------------------------------------------------
# Tailscale
# ---------------------------------------------------------------------------
get_tailscale_ip() {
    if command -v tailscale >/dev/null 2>&1; then
        local ip
        ip=$(tailscale ip -4 2>/dev/null || true)
        if [ -n "$ip" ]; then echo "$ip"; return; fi
    fi
    warn "Tailscale not available or not connected — Tailscale IP unknown"
    echo ""
}

# ---------------------------------------------------------------------------
# Build pins — clone-layer cache busting for git-clone-built images
# ---------------------------------------------------------------------------
# janus/webui build by cloning a MOVING ref (main). Docker's layer cache can't
# see the remote move, so an unpinned rebuild may silently reuse a stale clone
# and ship old code while reporting success (bit us on oryx 2026-07-06: a
# "rebuild" redeployed a 10-hour-old janus). Resolving the remote head sha
# into JANUS_COMMIT/WEB_COMMIT (compose → REPO_COMMIT build arg) busts the
# clone layer exactly when the remote moves. Best-effort: if ls-remote fails
# the pin stays empty and the build behaves as before (cached — warned).
resolve_build_pins() {
    local janus_repo="${JANUS_REPO:-https://github.com/nuniesmith/janus}"
    local janus_ref="${JANUS_REF:-main}"
    local web_repo="${WEB_REPO:-https://github.com/nuniesmith/fks-web}"
    local web_ref="${WEB_REF:-main}"
    local spawner_repo="${SPAWNER_REPO:-}"
    local spawner_ref="${SPAWNER_REF:-main}"
    if [ -z "${JANUS_COMMIT:-}" ] && [ -n "$janus_repo" ]; then
        JANUS_COMMIT=$(git ls-remote "$janus_repo" "$janus_ref" 2>/dev/null | head -1 | cut -f1)
        export JANUS_COMMIT
    fi
    if [ -z "${WEB_COMMIT:-}" ] && [ -n "$web_repo" ]; then
        WEB_COMMIT=$(git ls-remote "$web_repo" "$web_ref" 2>/dev/null | head -1 | cut -f1)
        export WEB_COMMIT
    fi
    if [ -z "${SPAWNER_COMMIT:-}" ] && [ -n "$spawner_repo" ]; then
        SPAWNER_COMMIT=$(git ls-remote "$spawner_repo" "$spawner_ref" 2>/dev/null | head -1 | cut -f1)
        export SPAWNER_COMMIT
    fi
    if [ -n "${JANUS_COMMIT:-}" ]; then
        info "janus build pinned to ${JANUS_COMMIT:0:9} (${janus_ref})"
    else
        warn "janus build UNPINNED (ls-remote failed?) — clone layer may come from cache"
    fi
    if [ -n "${WEB_COMMIT:-}" ]; then
        info "webui build pinned to ${WEB_COMMIT:0:9} (${web_ref})"
    else
        warn "webui build UNPINNED (ls-remote failed?) — clone layer may come from cache"
    fi
    if [ -n "$spawner_repo" ]; then
        if [ -n "${SPAWNER_COMMIT:-}" ]; then
            info "spawner build pinned to ${SPAWNER_COMMIT:0:9} (${spawner_ref})"
        else
            warn "spawner build UNPINNED (ls-remote failed?) — clone layer may come from cache"
        fi
    fi
    return 0
}

# =============================================================================
# .env management
# =============================================================================

setup_env_file() {
    local env_file="$ENV_FILE"

    if [ ! -f "$env_file" ]; then
        header "Generating .env with secure secrets"

        local ts_ip=""
        ts_ip=$(get_tailscale_ip 2>/dev/null || true)
        if [ -z "$ts_ip" ]; then ts_ip="127.0.0.1"; fi

        local ra_proxy_key
        ra_proxy_key=$(generate_long_secret)

        cat > "$env_file" << EOF
# =============================================================================
# FKS Trading System — Environment
# Generated $(date -u +"%Y-%m-%dT%H:%M:%SZ") by ./run.sh setup-env
# Edit this file to fill in API keys and optional settings.
# Re-run ./run.sh setup-env at any time to fill missing secrets.
# =============================================================================


# =============================================================================
# SECTION 1 — SERVICE SECRETS  (auto-generated — never commit to git)
# =============================================================================

# Compose project name — keeps bare docker-compose in sync with ./run.sh (-p fks).
COMPOSE_PROJECT_NAME=fks

# --- Postgres (shared instance: janus_db + fks_db) ---
POSTGRES_USER=fks_user
POSTGRES_PASSWORD=$(generate_password)
JANUS_DB=janus_db
RUBY_DB=fks_db

# --- Redis ---
REDIS_PASSWORD=$(generate_password)

# --- QuestDB ---
QUESTDB_PG_USER=admin
QUESTDB_PG_PASSWORD=$(generate_password)

# --- Grafana ---
GRAFANA_USER=admin
GRAFANA_PASSWORD=$(generate_password)

# --- Discord webhooks (optional) ---
DISCORD_WEBHOOK_ANALYSIS=
DISCORD_WEBHOOK_GENERAL=
DISCORD_WEBHOOK_SIGNALS=
DISCORD_BOT_TOKEN=

# --- Web dashboard auth ---
WEB_PASSWORD_HASH=
WEB_SESSION_SECRET=$(generate_long_secret)
WEB_SESSION_TTL_DAYS=30

# --- API key encryption (Fernet) ---
API_KEY_ENCRYPTION_SECRET=$(generate_fernet_key)

# --- Internal API key (data service + web endpoints) ---
API_KEY=$(generate_secret)

# --- nginx internal token (nginx → backend trust header) ---
NGINX_INTERNAL_TOKEN=$(generate_secret)

# --- Tailscale (all ports bind to this IP — never the public interface) ---
TAILSCALE_IP=${ts_ip}


# =============================================================================
# SECTION 2 — JANUS (Rust trading engine)
# =============================================================================

EXECUTION_MODE=paper_trading     # paper_trading | live  — NEVER set live without full review
DATA_SOURCE=live
DATA_EXCHANGE=binance
DATA_WS_URL=wss://stream.binance.com:9443/ws
DATA_KLINE_INTERVALS=1m,5m

JANUS_ENABLE_BACKWARD=true
# NEVER autonomous: signals terminate at a human decision point. Keep this
# false unless you fully understand the live order path. This is the deliberate
# second gate, separate from EXECUTION_MODE (paper_trading force-dry-runs in
# code, so live orders need BOTH EXECUTION_MODE=live AND this =true). Matches
# .env.example.
ENABLE_EXECUTION=false

OPTIMIZER_ENABLED=true
OPTIMIZE_ASSETS=BTC,ETH,SOL
OPTIMIZE_INTERVAL=6h
OPTIMIZE_TRIALS=100
OPTIMIZE_HISTORICAL_DAYS=30
OPTIMIZER_INSTANCE_ID=janus-dev

BRAIN_WIRE_KILL_SWITCH=false
BRAIN_AUTO_START_WATCHDOG=true

# --- Trade execution ---
EXECUTION_EXCHANGE=kraken
EXEC_ACCOUNT_TYPE=personal-crypto
EXECUTION_CONNECT_TIMEOUT=10
EXECUTION_REQUEST_TIMEOUT=30
EXECUTION_MAX_RETRIES=3
EXECUTION_RETRY_BACKOFF_MS=100
EXECUTION_DEFAULT_QUANTITY=0.001


# =============================================================================
# SECTION 3 — EXTERNAL API KEYS  (prefer WebUI Settings → API Keys)
# =============================================================================

# --- Broker: Kraken ---
KRAKEN_API_KEY=
KRAKEN_API_SECRET=
ENABLE_KRAKEN_CRYPTO=1

# --- Market data: supplementary ---
FINNHUB_API_KEY=
ALPHA_VANTAGE_API_KEY=

# --- TradingView ---
TV_SESSION_ID=

# --- Copier integration ---
COPIER_URL=


# =============================================================================
# SECTION 4 — ON-CHAIN MONITORING & MARKET DATA  (all optional)
# =============================================================================

WHALE_ALERT_API_KEY=
ETHERSCAN_API_KEY=
SOLSCAN_API_KEY=
CRYPTOCOMPARE_API_KEY=
MEMPOOL_SPACE_URL=https://mempool.space/api

CHAIN_MIN_USD=1000000
CHAIN_POLL_WHALE=30
CHAIN_POLL_MEMPOOL=60
CHAIN_POLL_FLOW=3600

CMC_API_KEY=
CMC_POLL_QUOTES=900
CMC_POLL_GLOBAL=1800
CMC_POLL_FEAR_GREED=1800
CMC_POLL_LISTINGS=21600

# =============================================================================
# SECTION 9 — LOGGING & TIMEZONE
# =============================================================================

LOG_LEVEL=info
PYTHONUNBUFFERED=1
TZ=America/Toronto
EOF
        ok ".env generated with all service secrets (sections 1–9)"
        warn "Review .env and fill in your API keys before going live"

        if [ -f ".gitignore" ] && ! grep -q "^\.env$" .gitignore; then
            echo ".env" >> .gitignore
            info "Added .env to .gitignore"
        fi

        _prompt_api_keys "$env_file"
    fi

    # ── Helpers ──────────────────────────────────────────────────────────────
    _env_get() { grep "^${1}=" "$env_file" | cut -d'=' -f2- | sed 's/#.*//' | tr -d ' ' || true; }
    _env_set() {
        local key="$1" val="$2"
        if grep -q "^${key}=" "$env_file"; then
            sed -i "s|^${key}=.*|${key}=${val}|" "$env_file"
        else
            echo "${key}=${val}" >> "$env_file"
        fi
    }
    _env_del() { sed -i "/^${1}=/d" "$env_file"; }

    local needs_update=false

    # --- Enforce canonical values ---
    local pg_db;  pg_db=$(_env_get JANUS_DB)
    local pg_usr; pg_usr=$(_env_get POSTGRES_USER)
    if [ "$pg_db" != "janus_db" ]; then
        _env_set JANUS_DB janus_db
        warn "Fixed JANUS_DB → janus_db"
        needs_update=true
    fi
    if [ "$pg_usr" != "fks_user" ]; then
        _env_set POSTGRES_USER fks_user
        warn "Fixed POSTGRES_USER → fks_user"
        needs_update=true
    fi

    # --- Migrate stale vars ---
    if grep -q "^RUBY_POSTGRES_USER=" "$env_file"; then
        _env_del RUBY_POSTGRES_USER
        _env_del RUBY_POSTGRES_PASSWORD
        _env_del RUBY_JANUS_DB
        warn "Removed stale RUBY_POSTGRES_* vars"
        needs_update=true
    fi

    if ! grep -q "^RUBY_DB=" "$env_file"; then
        _env_set RUBY_DB fks_db
        warn "Added RUBY_DB=fks_db"
        needs_update=true
    fi

    for stale_var in DATABASE_URL GATEWAY_SECRET_KEY GATEWAY_JWT_SECRET \
                     DATA_SERVICE_JWT_SECRET DATA_SERVICE_JWT_EXPIRY \
                     GF_SECURITY_SECRET_KEY QUESTDB_PASSWORD QUESTDB_USER \
                     DISCORD_NOTIFICATIONS_ENABLED DISCORD_NOTIFY_ON_SIGNAL \
                     DISCORD_NOTIFY_ON_FILL DISCORD_NOTIFY_ON_ERROR \
                     REDDIT_POLL_INTERVAL REAL_ORDERS_ENABLED \
                     EXECUTION_ENDPOINT ENVIRONMENT RUST_LOG RUST_BACKTRACE \
                     CLOUDFLARE_API_KEY; do
        if grep -q "^${stale_var}=" "$env_file"; then
            _env_del "$stale_var"
            warn "Removed stale var: $stale_var"
            needs_update=true
        fi
    done

    # --- Auto-fill missing/empty secrets ---
    _fill_password() {
        local key="$1"; local val; val=$(_env_get "$key")
        if [ -z "$val" ]; then _env_set "$key" "$(generate_password)"; warn "Generated $key"; needs_update=true; fi
    }
    _fill_secret() {
        local key="$1"; local val; val=$(_env_get "$key")
        if [ -z "$val" ]; then _env_set "$key" "$(generate_secret)"; warn "Generated $key"; needs_update=true; fi
    }
    _fill_long() {
        local key="$1"; local val; val=$(_env_get "$key")
        if [ -z "$val" ] || [ "${#val}" -lt 64 ]; then _env_set "$key" "$(generate_long_secret)"; warn "Generated $key (64-char)"; needs_update=true; fi
    }
    _fill_fernet() {
        local key="$1"; local val; val=$(_env_get "$key")
        if [ -z "$val" ]; then _env_set "$key" "$(generate_fernet_key)"; warn "Generated $key (Fernet key)"; needs_update=true; fi
    }

    _fill_password POSTGRES_PASSWORD
    _fill_password REDIS_PASSWORD
    _fill_password QUESTDB_PG_PASSWORD
    _fill_password GRAFANA_PASSWORD
    _fill_secret   API_KEY
    _fill_long     WEB_SESSION_SECRET
    _fill_fernet   API_KEY_ENCRYPTION_SECRET
    _fill_secret   NGINX_INTERNAL_TOKEN

    # --- Tailscale IP auto-detect ---
    local ts_val; ts_val=$(_env_get TAILSCALE_IP)
    if [ -z "$ts_val" ] || [ "$ts_val" = "100.x.x.x" ]; then
        local detected_ts=""
        detected_ts=$(get_tailscale_ip 2>/dev/null || true)
        if [ -n "$detected_ts" ]; then
            _env_set TAILSCALE_IP "$detected_ts"
            warn "Set TAILSCALE_IP=$detected_ts (auto-detected)"
        else
            warn "TAILSCALE_IP not set — using 127.0.0.1 (Tailscale not connected?)"
            _env_set TAILSCALE_IP "127.0.0.1"
        fi
        needs_update=true
    fi

    # --- Docker group GID auto-detect (the spawner's group_add uses it to reach
    #     /var/run/docker.sock; the compose default is host-specific and often wrong) ---
    if [ -z "$(_env_get DOCKER_GID)" ]; then
        local detected_gid=""
        detected_gid=$(getent group docker 2>/dev/null | cut -d: -f3 || true)
        if [ -n "$detected_gid" ]; then
            _env_set DOCKER_GID "$detected_gid"
            warn "Set DOCKER_GID=$detected_gid (host docker group gid — spawner group_add)"
            needs_update=true
        fi
    fi

    for webhook_key in DISCORD_WEBHOOK_ANALYSIS DISCORD_WEBHOOK_GENERAL DISCORD_WEBHOOK_SIGNALS DISCORD_BOT_TOKEN; do
        if ! grep -q "^${webhook_key}=" "$env_file"; then
            echo "${webhook_key}=" >> "$env_file"
            warn "Added ${webhook_key} (empty)"
            needs_update=true
        fi
    done

    # --- Strip inline comments so `docker compose --env-file` sees clean values ---
    # docker compose's env-file parser does NOT strip "KEY=value  # comment" inline
    # comments (bash `source` does — which is why this script itself was unaffected).
    # Left in, the comment text leaks into the value: e.g. an empty `SPAWNER_REPO=
    # # e.g. https://…` becomes the literal git URL "# e.g. https://…" and breaks the
    # spawner/web image build, and empty broker keys become their literal hint text.
    # Secrets are single tokens (no spaces), so "whitespace then #" only ever matches
    # the comment convention — never a value.
    sed -i -E '/^[A-Za-z_][A-Za-z0-9_]*=/ s/[[:space:]]+#.*$//' "$env_file"

    # --- Render alertmanager.yml from template ---
    local tmpl="infrastructure/config/alertmanager/alertmanager.yml.tmpl"
    local dest="infrastructure/config/alertmanager/alertmanager.yml"
    if [ -f "$tmpl" ]; then
        set -a; set +u; source "$env_file"; set -u; set +a
        if command -v envsubst &>/dev/null; then
            envsubst '${DISCORD_WEBHOOK_GENERAL}' < "$tmpl" > "$dest"
        else
            local wh; wh=$(_env_get DISCORD_WEBHOOK_GENERAL)
            sed "s|\${DISCORD_WEBHOOK_GENERAL}|${wh}|g" "$tmpl" > "$dest"
        fi
    fi

    if [ "$needs_update" = true ]; then
        ok ".env updated"
    else
        ok ".env validated — all secrets present"
    fi

    _env_get FINNHUB_API_KEY | grep -q "^$" && warn "FINNHUB_API_KEY is empty" || true
    _env_get KRAKEN_API_KEY  | grep -q "^$" && warn "KRAKEN_API_KEY is empty — live trading disabled" || true
    _prompt_web_password "$env_file"
}

# =============================================================================
# Pre-flight checks
# =============================================================================

preflight_check() {
    header "Pre-flight Checks"
    local errors=0

    if ! docker info > /dev/null 2>&1; then
        err "Docker daemon is not running"; ((errors++))
    else
        ok "Docker daemon is running"
    fi

    if ! docker compose version > /dev/null 2>&1; then
        err "Docker Compose V2 is not available"; ((errors++))
    else
        ok "Docker Compose available"
    fi

    local available_gb
    available_gb=$(df / | tail -1 | awk '{print int($4/1024/1024)}')
    if [ "$available_gb" -lt 10 ]; then
        err "Low disk space: ${available_gb}GB (need ≥ 10GB)"
        # NOT `docker system prune -af --volumes`: that is host-wide and would
        # take the running money bots' images plus every unreferenced volume,
        # including the per-bot fks-bot-state-* state volumes. Suggest the
        # bounded version instead.
        warn "Run: ./run.sh clean   (or: docker image prune -af)"
        ((errors++))
    else
        ok "Disk space: ${available_gb}GB available"
    fi

    local port_ok=true
    for entry in "9000:QuestDB" "6379:Redis"; do
        local port="${entry%:*}" svc="${entry#*:}"
        local ctr
        ctr=$(docker ps --filter "publish=$port" --format "{{.Names}}" 2>/dev/null)
        if [ -n "$ctr" ]; then
            err "Port $port ($svc) already in use by: $ctr"
            port_ok=false
            ((errors++))
        fi
    done
    [ "$port_ok" = true ] && ok "Critical ports are free"

    local orphans
    orphans=$(docker ps -a --filter "name=fks_" --filter "status=exited" --format "{{.Names}}" 2>/dev/null | wc -l)
    [ "$orphans" -gt 0 ] && warn "Found $orphans orphan container(s) — will be cleaned on start"

    if [ $errors -gt 0 ]; then
        err "Pre-flight failed with $errors error(s)"
        info "Run './run.sh diagnose' for details or './run.sh force-clean' to reset"
        return 1
    fi
    ok "Pre-flight passed"
}

# =============================================================================
# CNN model files check
# =============================================================================

ensure_models() {
    local missing=0
    for f in "models/breakout_cnn_best_meta.json" \
             "models/feature_contract.json"; do
        if [ ! -f "$f" ]; then
            err "Missing model file: $f"
            missing=1
        fi
    done
    if [ "$missing" -eq 1 ]; then
        if [ "${EXECUTION_MODE:-paper_trading}" = "live" ]; then
            err "CNN model files missing — cannot start in live execution mode"
            exit 1
        else
            warn "CNN model files missing — ML predictions unavailable until models are present"
            warn "  Train champions in janus (burn-native) or copy model files into ./models/"
        fi
    else
        ok "CNN model files present"
    fi
}

# =============================================================================
# Volume bootstrap
# =============================================================================

ensure_volumes() {
    # Only the volumes declared `external: true` in docker-compose.yml must be
    # pre-created — compose auto-creates every other (project-scoped) volume.
    # These names are matched verbatim (external volumes are NOT project-prefixed),
    # so they must equal the keys in the compose `volumes:` block exactly.
    local external_volumes=(
        prometheus_data
        grafana_data
        alertmanager_data
    )
    local created=0
    for vol in "${external_volumes[@]}"; do
        if ! docker volume inspect "$vol" > /dev/null 2>&1; then
            docker volume create "$vol" > /dev/null
            log "Created volume: $vol"
            created=$((created + 1))
        fi
    done
    if [ "$created" -gt 0 ]; then
        ok "Created $created missing external volume(s)"
    else
        ok "All external volumes present"
    fi
}

# =============================================================================
# Database bootstrap — idempotent
# =============================================================================

_ensure_single_db() {
    local db_name="$1"
    local pg_user="$2"
    local pg_container="$3"

    local exists
    exists=$(docker exec -i "$pg_container" \
        psql -U "$pg_user" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='${db_name}'" 2>/dev/null || true)

    if [ "$exists" = "1" ]; then
        ok "${db_name} database exists"
        return 0
    fi

    log "Creating ${db_name} database ..."
    docker exec -i "$pg_container" \
        psql -U "$pg_user" -d postgres -c \
        "CREATE DATABASE ${db_name}
             WITH OWNER     = ${pg_user}
                  ENCODING  = 'UTF8'
                  LC_COLLATE = 'C'
                  LC_CTYPE   = 'C'
                  TEMPLATE  = template0;" 2>/dev/null

    docker exec -i "$pg_container" \
        psql -U "$pg_user" -d "${db_name}" -c "
            ALTER SCHEMA public OWNER TO ${pg_user};
            GRANT ALL ON SCHEMA public TO ${pg_user};
            GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${pg_user};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
                GRANT ALL PRIVILEGES ON TABLES TO ${pg_user};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
                GRANT ALL PRIVILEGES ON SEQUENCES TO ${pg_user};
            CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";
            CREATE EXTENSION IF NOT EXISTS \"pg_stat_statements\";
        " 2>/dev/null

    ok "${db_name} database created"
}

_wait_for_postgres() {
    local pg_user="${POSTGRES_USER:-fks_user}"
    local pg_container="fks_postgres"
    local retries=15
    while [ "$retries" -gt 0 ]; do
        if docker exec "$pg_container" pg_isready -U "$pg_user" -d "${JANUS_DB:-janus_db}" > /dev/null 2>&1; then
            return 0
        fi
        retries=$(( retries - 1 ))
        sleep 2
    done
    return 1
}

ensure_databases() {
    header "Database Bootstrap"
    local pg_user="${POSTGRES_USER:-fks_user}"
    local pg_container="fks_postgres"
    local janus_db="${JANUS_DB:-janus_db}"
    local fks_db="${RUBY_DB:-fks_db}"

    if ! _wait_for_postgres; then
        warn "postgres not ready after 30s — skipping database bootstrap"
        warn "  Services will retry on their own, but you may see errors."
        warn "  Re-run: ./run.sh fix-db"
        return 0
    fi
    ok "postgres is accepting connections"

    _ensure_single_db "$janus_db" "$pg_user" "$pg_container"
    _ensure_single_db "$fks_db"  "$pg_user" "$pg_container"

    # Apply bot_configs / bot_runs schema (idempotent — uses CREATE TABLE IF NOT EXISTS)
    local bot_sql="infrastructure/config/postgres/09-init-bots.sql"
    if [ -f "$bot_sql" ]; then
        log "Applying bot schema (09-init-bots.sql) ..."
        if docker exec -i "$pg_container" \
            psql -U "$pg_user" \
            -d "$fks_db" \
            -v POSTGRES_USER="$pg_user" \
            -v RUBY_DB="$fks_db" \
            < "$bot_sql" >/dev/null 2>&1; then
            ok "Bot schema applied (bot_configs, bot_runs)"
        else
            warn "Bot schema apply failed — check: ./run.sh logs postgres"
        fi
    fi

    local all_ok=true
    for db in "$janus_db" "$fks_db"; do
        if docker exec -i "$pg_container" \
            psql -U "$pg_user" -d "$db" -tAc "SELECT 1" 2>/dev/null | grep -q "1"; then
            true
        else
            err "  ${db} — cannot connect after creation"
            all_ok=false
        fi
    done

    if [ "$all_ok" = true ]; then
        ok "All databases verified: ${janus_db}, ${fks_db}"
    else
        warn "Some databases failed verification — check postgres logs"
        warn "  ./run.sh logs postgres"
    fi
}

# =============================================================================
# TLS certificate bootstrap
# =============================================================================

ensure_tls_certs() {
    local certs_dir="infrastructure/certs"
    local srv_crt="${certs_dir}/server.crt"
    local srv_key="${certs_dir}/server.key"

    if [ -f "${srv_crt}" ] && [ -f "${srv_key}" ]; then
        if command -v openssl &>/dev/null; then
            local expiry
            expiry=$(openssl x509 -noout -enddate -in "${srv_crt}" 2>/dev/null | cut -d= -f2 || true)
            ok "Internal TLS certs present${expiry:+ (expires: ${expiry})}"
        else
            ok "Internal TLS certs present"
        fi
        return 0
    fi

    if ! command -v openssl &>/dev/null; then
        warn "openssl not found — skipping internal cert generation"
        return 0
    fi

    log "Generating internal self-signed TLS cert in ${certs_dir}/ ..."
    mkdir -p "${certs_dir}"

    if openssl req -x509 -newkey rsa:2048 \
            -keyout "${srv_key}" \
            -out "${srv_crt}" \
            -days 3650 \
            -nodes \
            -subj "/CN=fks-internal/O=FKS Trading/C=CA" \
            2>/dev/null; then
        chmod 600 "${srv_key}"
        ok "Internal TLS cert generated in ${certs_dir}/"
    else
        warn "Internal cert generation failed — non-fatal, continuing"
    fi
}

cmd_ssl_local() {
    local certs_dir="infrastructure/certs"
    local srv_crt="${certs_dir}/server.crt"
    local srv_key="${certs_dir}/server.key"

    header "SSL/TLS — Regenerate Internal Service Certificates"

    if ! command -v openssl &>/dev/null; then
        err "openssl not found — cannot generate TLS certificates"
        exit 1
    fi

    mkdir -p "${certs_dir}"
    log "Generating internal self-signed TLS cert (force) ..."

    if openssl req -x509 -newkey rsa:2048 \
            -keyout "${srv_key}" \
            -out "${srv_crt}" \
            -days 3650 \
            -nodes \
            -subj "/CN=fks-internal/O=FKS Trading/C=CA" \
            2>/dev/null; then
        chmod 600 "${srv_key}"
        ok "Cert written to ${certs_dir}/"
    else
        err "Certificate generation failed"
        exit 1
    fi
}

# =============================================================================
# Build commands
# =============================================================================

cmd_build_redis() {
    header "Building Custom Redis Image"
    if $DC build redis; then
        ok "Redis image built"
    else
        err "Redis build failed"
        return 1
    fi
}

# Build the spawnable reference bot images under bots/. These are NOT part of
# the always-on compose stack — the spawner launches them on demand — so they
# build directly with `docker build` from the repo root. Both are tagged with
# the `fks-bot-` prefix the spawner whitelists (ALLOWED_IMAGE_PREFIX).
cmd_build_bots() {
    header "Building Reference Bot Images"
    # The reference bots moved to the fks-spawner repo in the #196 prune (their
    # crates path-dep ../../crates/crypto-bot-core, so the build CONTEXT is the
    # fks-spawner repo ROOT, not this repo). Build from the sibling checkout.
    local spawner_dir="${SPAWNER_DIR:-$(dirname "$SCRIPT_DIR")/fks-spawner}"
    if [ ! -d "$spawner_dir/bots" ]; then
        err "fks-spawner checkout not found at ${spawner_dir} (set SPAWNER_DIR). The bots live there since #196."
        return 1
    fi
    local rc=0
    local bots=(
        "fks-bot-example:bots/fks-bot-example/Dockerfile"
        "fks-bot-crypto-demo:bots/crypto-demo/Dockerfile"
    )
    for spec in "${bots[@]}"; do
        local tag="${spec%%:*}"
        local dockerfile="${spec#*:}"
        if [ ! -f "$spawner_dir/$dockerfile" ]; then
            err "${tag}: ${dockerfile} not found under ${spawner_dir}"
            rc=1
            continue
        fi
        info "Building ${tag}:latest (context: ${spawner_dir})"
        if docker build -f "$spawner_dir/$dockerfile" -t "${tag}:latest" "$spawner_dir"; then
            ok "${tag}:latest built"
        else
            err "${tag} build failed"
            rc=1
        fi
    done
    [ "$rc" -eq 0 ] && ok "Bot images built — spawn from the WebUI /bots page"
    return "$rc"
}

cmd_build() {
    local mode="${1:-dev}"
    shift || true
    header "Building Images (${mode})"
    resolve_build_pins
    if [ "$mode" = "prod" ]; then
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" build "$@"
    else
        $DC -f "$COMPOSE_FILE" build "$@"
    fi
    ok "Build complete"
}

# =============================================================================
# Start / up / down / restart
# =============================================================================

cmd_all() {
    # --demo also brings up the crypto-demo paper bot (drives the janus brain
    # end-to-end). The Python "Ruby"/Trainer services were removed — this starts
    # the janus-centric stack only.
    local with_demo=false
    while [ $# -gt 0 ]; do
        case "$1" in
            --demo)   with_demo=true; shift ;;
            *)        shift ;;
        esac
    done

    header "FKS — Start Everything"

    setup_env_file
    echo ""

    ensure_models
    echo ""

    log "Stopping any existing FKS containers (removes orphans: old ruby/trainer/etc.)..."
    $DC down --remove-orphans --timeout 10 2>/dev/null || true
    ok "Existing containers stopped"
    echo ""

    preflight_check
    echo ""

    ensure_volumes
    echo ""

    ensure_tls_certs
    echo ""

    # Build the postgres image BEFORE its first start: on a fresh host, `up`
    # would otherwise pull/start a stale image and initialize the data volume
    # without the baked /docker-entrypoint-initdb.d schema scripts — leaving
    # janus_db/fks_db present but EMPTY (initdb only runs on an empty volume,
    # so the later build never gets a second chance). cmd_fresh already does
    # this; cmd_all was the remaining path with the trap.
    log "Building postgres image (bakes the DB init scripts) ..."
    $DC build postgres
    echo ""

    log "Starting postgres for database bootstrap ..."
    $DC up -d postgres 2>/dev/null || true
    sleep 3
    ensure_databases
    echo ""

    local demo_profile=""
    [ "$with_demo" = true ] && demo_profile="--profile demo"
    # A --profile flag OVERRIDES COMPOSE_PROFILES (compose does not merge
    # them), so re-assert the auto-enabled "state" profile alongside demo or
    # advisor/orb-briefing would silently drop out of this build/up.
    if [ -n "$demo_profile" ]; then
        case ",${COMPOSE_PROFILES:-}," in
            *,state,*) demo_profile="$demo_profile --profile state" ;;
        esac
    fi

    resolve_build_pins
    log "Building service images..."
    $DC $demo_profile build
    echo ""

    log "Bringing up all services (core + monitoring${demo_profile:+ + demo bot})..."
    # NOTE: monitoring services (prometheus, grafana, loki, etc.) have no profile
    # in docker-compose.yml so they start with core services by default.
    # janus has no in-tree copy — its image is built by git-cloning JANUS_REPO@JANUS_REF.
    $DC $demo_profile up -d

    echo ""
    log "Waiting for services to initialize ..."
    sleep 10
    _post_start_verify

    local ts_ip
    ts_ip=$(get_tailscale_ip)

    echo ""
    ok "Everything is up (bound to 127.0.0.1 — use localhost on this desktop):"
    echo "    WebUI:        http://localhost:3001   (https://${ts_ip}:3001 via Tailscale)"
    echo "    Janus API:    http://localhost:7000"
    echo "    Grafana:      http://localhost:3000"
    echo "    Prometheus:   http://localhost:9090"
    echo "    QuestDB:      http://localhost:9000"
    echo "    Bot Spawner:  http://localhost:8090"
    [ "$with_demo" = true ] && echo "    Demo bot:     http://localhost:9091/metrics   (fks_bot_* series)"
    echo ""
    info "Logs:   docker compose logs -f                 (one service: ./run.sh logs janus)"
    [ "$with_demo" = true ] && info "Demo:   ./run.sh logs crypto-demo"
    info "Stop:   ./run.sh down"
}

_post_start_verify() {
    local issues=0

    local janus_code
    janus_code=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:7000/health 2>/dev/null || echo "000")
    if [ "$janus_code" = "200" ]; then
        ok "Janus HTTP API healthy"
    else
        warn "Janus HTTP API: HTTP ${janus_code} (may still be starting)"
        issues=$((issues + 1))
    fi

    local webui_code
    webui_code=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:3001/ 2>/dev/null || echo "000")
    if [ "$webui_code" = "200" ]; then
        ok "WebUI (SvelteKit) healthy"
    else
        warn "WebUI: HTTP ${webui_code} (may still be starting)"
        issues=$((issues + 1))
    fi

    local spawner_code
    spawner_code=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8090/health 2>/dev/null || echo "000")
    if [ "$spawner_code" = "200" ]; then
        ok "Bot Spawner healthy"
    else
        warn "Bot Spawner: HTTP ${spawner_code} (may still be starting)"
        issues=$((issues + 1))
    fi

    if [ "$issues" -gt 0 ]; then
        echo ""
        warn "${issues} service(s) may need attention — check with: ./run.sh health"
    else
        echo ""
        ok "All critical services verified"
    fi
}

cmd_fresh() {
    local reset_volumes=false
    local with_demo=false
    while [ $# -gt 0 ]; do
        case "$1" in
            --reset-volumes) reset_volumes=true; shift ;;
            --demo)          with_demo=true; shift ;;
            *)               shift ;;
        esac
    done

    header "FKS — Fresh Start"

    if [ "$reset_volumes" = true ]; then
        warn "⚠️  --reset-volumes will destroy ALL database data, Redis cache, etc."
        echo -n "Type 'yes' to confirm: "
        read -r confirm
        if [ "$confirm" != "yes" ]; then
            info "Cancelled"
            return 0
        fi
    fi

    setup_env_file
    echo ""

    ensure_models
    echo ""

    log "Stopping all FKS containers ..."
    # -v drops the project-scoped named volumes (postgres/redis/questdb/…) on a
    # full reset; the external volumes are removed explicitly below.
    local down_flags="--remove-orphans --timeout 10"
    [ "$reset_volumes" = true ] && down_flags="-v $down_flags"
    $DC down $down_flags 2>/dev/null || true
    ok "All containers stopped"
    echo ""

    if [ "$reset_volumes" = true ]; then
        warn "Removing external data volumes ..."
        for vol in prometheus_data grafana_data alertmanager_data; do
            docker volume rm "$vol" 2>/dev/null && warn "  Removed $vol" || true
        done
        echo ""
    fi

    log "Removing old containers ..."
    # name=fks_ ONLY — this rebuilds the compose stack. The spawner-managed
    # fks-bot-* containers (fks.bot=true) are intentionally NOT swept: they may
    # hold live positions and are the spawner's to stop, not ours.
    docker ps -a --filter "name=fks_" -q | xargs -r docker rm -f 2>/dev/null || true
    ok "Old containers removed"
    echo ""

    log "Pruning dangling images ..."
    docker image prune -f 2>/dev/null || true
    echo ""

    preflight_check
    echo ""

    ensure_volumes
    echo ""

    ensure_tls_certs
    echo ""

    log "Rebuilding postgres image (picks up latest init scripts) ..."
    $DC build postgres
    ok "postgres image rebuilt"
    echo ""

    log "Starting postgres for database bootstrap ..."
    $DC up -d postgres
    sleep 5
    ensure_databases
    echo ""

    local demo_profile=""
    [ "$with_demo" = true ] && demo_profile="--profile demo"
    # A --profile flag OVERRIDES COMPOSE_PROFILES (compose does not merge
    # them), so re-assert the auto-enabled "state" profile alongside demo or
    # advisor/orb-briefing would silently drop out of this build/up.
    if [ -n "$demo_profile" ]; then
        case ",${COMPOSE_PROFILES:-}," in
            *,state,*) demo_profile="$demo_profile --profile state" ;;
        esac
    fi

    resolve_build_pins
    log "Building service images ..."
    $DC $demo_profile build
    echo ""

    log "Bringing up all services${demo_profile:+ + demo bot} ..."
    $DC $demo_profile up -d

    echo ""
    log "Waiting for services to initialize ..."
    sleep 10
    _post_start_verify

    local ts_ip
    ts_ip=$(get_tailscale_ip)

    echo ""
    ok "Fresh start complete (bound to 127.0.0.1 — use localhost on this desktop):"
    echo "    WebUI:        http://localhost:3001   (https://${ts_ip}:3001 via Tailscale)"
    echo "    Janus API:    http://localhost:7000"
    echo "    Grafana:      http://localhost:3000"
    echo "    Prometheus:   http://localhost:9090"
    echo "    QuestDB:      http://localhost:9000"
    echo "    Bot Spawner:  http://localhost:8090"
    [ "$with_demo" = true ] && echo "    Demo bot:     http://localhost:9091/metrics"
    echo ""
    info "Logs:  docker compose logs -f"
    info "Stop:  ./run.sh down"
}

cmd_fix_db() {
    header "FKS — Fix Databases"

    setup_env_file
    echo ""

    local pg_status
    pg_status=$(docker inspect --format='{{.State.Status}}' fks_postgres 2>/dev/null || echo "not-found")

    if [ "$pg_status" != "running" ]; then
        log "Postgres is not running (status: ${pg_status}) — starting it ..."
        ensure_volumes
        $DC up -d postgres
        sleep 5
    fi

    ensure_databases
    echo ""

    ok "Database fix complete"
}

cmd_start() {
    local mode="${1:-dev}"
    shift || true
    header "Starting FKS (${mode} mode)"

    if [ "$mode" = "prod" ]; then
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" down --timeout 10 --remove-orphans 2>/dev/null || true
    else
        $DC -f "$COMPOSE_FILE" down --timeout 10 --remove-orphans 2>/dev/null || true
    fi
    ok "Stopped existing containers"
    echo ""

    preflight_check
    echo ""
    setup_env_file
    echo ""
    ensure_volumes
    echo ""

    if [ "$mode" = "prod" ]; then
        header "Pulling Production Images"
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" pull "$@"
        ok "Images pulled"
        echo ""
        header "Starting Production Services"
        warn "STANDING GUARD: fks_postgres deliberately lags its image tag (see CLAUDE.md)."
        warn "A bare up -d WILL recreate the live ledger DB. Type RECREATE-DB to proceed:"
        read -r _guard && [ "$_guard" = "RECREATE-DB" ] || { err "Refused. Deploy single services by name."; return 1; }
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" up -d "$@"
    else
        $DC -f "$COMPOSE_FILE" build "$@"
        ok "Build complete"
        echo ""
        header "Starting Development Services"
        warn "STANDING GUARD: fks_postgres deliberately lags its image tag (see CLAUDE.md)."
        warn "A bare up -d WILL recreate the live ledger DB. Type RECREATE-DB to proceed:"
        read -r _guard && [ "$_guard" = "RECREATE-DB" ] || { err "Refused. Deploy single services by name."; return 1; }
        $DC -f "$COMPOSE_FILE" up -d "$@"
    fi

    ok "Services started"
    info "Waiting for health checks..."
    sleep 5
    cmd_status "$mode"

    echo ""
    ok "FKS Trading System is ready!"
    echo ""
    info "Access:"
    echo "  Web UI:      http://localhost:3001"
    echo "  Grafana:     http://localhost/grafana/"
    echo "  QuestDB:     http://localhost:9000"
    echo "  Prometheus:  http://localhost:9090"
    echo ""
    info "Logs:   ./run.sh logs"
    info "Health: ./run.sh health"
}

cmd_up() {
    local mode="${1:-dev}"
    shift || true
    ensure_volumes
    echo ""
    if [ "$mode" = "prod" ]; then
        warn "STANDING GUARD: fks_postgres deliberately lags its image tag (see CLAUDE.md)."
        warn "A bare up -d WILL recreate the live ledger DB. Type RECREATE-DB to proceed:"
        read -r _guard && [ "$_guard" = "RECREATE-DB" ] || { err "Refused. Deploy single services by name."; return 1; }
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" up -d "$@"
    else
        warn "STANDING GUARD: fks_postgres deliberately lags its image tag (see CLAUDE.md)."
        warn "A bare up -d WILL recreate the live ledger DB. Type RECREATE-DB to proceed:"
        read -r _guard && [ "$_guard" = "RECREATE-DB" ] || { err "Refused. Deploy single services by name."; return 1; }
        $DC -f "$COMPOSE_FILE" up -d "$@"
    fi
    ok "Services up"
}

cmd_down() {
    local mode="${1:-dev}"
    shift || true
    header "Stopping Services (${mode})"
    if [ "$mode" = "prod" ]; then
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" \
            down "$@" --remove-orphans || true
    else
        $DC -f "$COMPOSE_FILE" \
            down "$@" --remove-orphans || true
    fi
    ok "All services stopped"
}

cmd_restart() {
    local mode="${1:-dev}"
    shift || true
    if [ "$mode" = "prod" ]; then
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" restart "$@"
    else
        $DC -f "$COMPOSE_FILE" restart "$@"
    fi
    ok "Restarted"
}

cmd_logs() {
    local mode="${1:-dev}"
    shift || true
    if [ "$mode" = "prod" ]; then
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" logs -f "$@"
    else
        $DC -f "$COMPOSE_FILE" logs -f "$@"
    fi
}

# Every container this operator cares about: the compose STACK (name=fks_)
# PLUS the spawner-launched bots (label fks.bot=true, named fks-bot-*), which
# live outside the compose file and so are invisible to `compose ps` and to a
# bare `name=fks_` filter. READ-ONLY visibility only. Destructive commands
# (fresh / force-clean / network-cleanup) deliberately DO NOT use this — they
# scope to name=fks_ so they rebuild the stack WITHOUT sweeping the bots, which
# are lifecycle-managed by the spawner and may hold LIVE positions. run.sh must
# never rm -f a money bot out from under the spawner.
fks_visible_containers() {
    {
        docker ps -a --filter "name=fks_"          --format '{{.Names}}' 2>/dev/null
        docker ps -a --filter "label=fks.bot=true" --format '{{.Names}}' 2>/dev/null
    } | sort -u
}

cmd_status() {
    local mode="${1:-dev}"
    if [ "$mode" = "prod" ]; then
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" ps
    else
        $DC -f "$COMPOSE_FILE" ps
    fi

    # `compose ps` shows only stack services; the spawner-managed bots are not
    # in the compose file. Surface them so `status` is the whole picture.
    local bots
    bots=$(docker ps -a --filter "label=fks.bot=true" \
             --format '{{.Names}}\t{{.Status}}\t{{.Label "fks.mode"}}' 2>/dev/null)
    if [ -n "$bots" ]; then
        printf '\nSpawner-managed bots (not in compose):\n'
        printf '%s\n' "$bots" | while IFS=$'\t' read -r name st mode_lbl; do
            printf '  %-28s %-22s [%s]\n' "$name" "$st" "${mode_lbl:-?}"
        done
    fi
}

# =============================================================================
# Health
# =============================================================================

cmd_health() {
    header "Service Health"
    local any_unhealthy=false

    local containers
    containers=$(fks_visible_containers)
    while IFS= read -r ctr; do
        [ -z "$ctr" ] && continue
        local label="${ctr#fks_}"
        local state
        state=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \
                "$ctr" 2>/dev/null || echo "not-found")
        local running
        running=$(docker inspect --format='{{.State.Status}}' "$ctr" 2>/dev/null || echo "unknown")
        case "$state" in
            healthy)        ok  "$label — healthy" ;;
            no-healthcheck)
                if [ "$running" = "running" ]; then
                    info "$label — running (no healthcheck)"
                else
                    warn "$label — $running (no healthcheck)"
                fi
                ;;
            starting)       warn "$label — starting…" ;;
            *)
                if [ "$running" != "running" ]; then
                    warn "$label — $running"
                else
                    err  "$label — $state"; any_unhealthy=true
                fi
                ;;
        esac
    done <<< "$containers"

    # FIX: expanded HTTP endpoint checks covering all key services
    echo ""
    info "HTTP endpoint checks:"
    local http_ok=true
    for entry in \
        "http://localhost:3001/:webui" \
        "http://localhost:7000/health:janus" \
        "http://localhost:9094/health:alertmanager-discord-bridge" \
        "http://localhost:8090/health:bot-spawner" \
        "http://localhost:16686/:jaeger"; do
        local url="${entry%:*}" label="${entry##*:}"
        local http_code
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$url" 2>/dev/null || echo "000")
        if [ "$http_code" = "200" ]; then
            ok  "$label — HTTP 200 ($url)"
        else
            warn "$label — HTTP $http_code ($url)"
            http_ok=false
        fi
    done

    echo ""
    info "Database connectivity:"
    local pg_state
    pg_state=$(docker inspect --format='{{.State.Health.Status}}' fks_postgres 2>/dev/null || echo "not-found")
    case "$pg_state" in
        healthy)   ok  "postgres: healthy" ;;
        not-found) warn "postgres: container not found (is the stack up?)" ;;
        *)         warn "postgres: $pg_state"; any_unhealthy=true ;;
    esac

    [ "$any_unhealthy" = true ] || [ "$http_ok" = false ] && return 1 || return 0
}

# =============================================================================
# Check / Lint / Fmt / Test  (local — no Docker required)
# =============================================================================

cmd_check() {
    header "Full Check — Rust"
    local errors=0

    cmd_lint_rust    || ((errors++))
    echo ""
    cmd_test_rust    || ((errors++))

    echo ""
    if [ "$errors" -gt 0 ]; then
        err "$errors stage(s) failed"
        return 1
    fi
    ok "All checks passed ✨"
}

# ── Rust ────────────────────────────────────────────────────────────────────

cmd_lint_rust() {
    header "Rust — cargo clippy"
    local rc=0

    log "cargo fmt --check..."
    if cargo fmt --all -- --check; then
        ok "cargo fmt check passed"
    else
        warn "cargo fmt: files need formatting — run './run.sh fmt' to fix"
        rc=1
    fi

    log "cargo clippy..."
    if cargo clippy --workspace --all-targets -- -D warnings; then
        ok "cargo clippy passed"
    else
        err "cargo clippy found warnings/errors"
        rc=1
    fi

    return $rc
}

cmd_test_rust() {
    header "Rust — cargo test"
    local errors=0

    if cargo test --workspace; then
        ok "cargo test passed"
    else
        err "cargo test failed"
        ((errors++))
    fi

    local _has_gpu=0
    local _has_nvcc=0

    if command -v nvidia-smi >/dev/null 2>&1 && \
       nvidia-smi --query-gpu=name --format=csv,noheader &>/dev/null; then
        _has_gpu=1
    fi

    if command -v nvcc >/dev/null 2>&1; then
        _has_nvcc=1
    elif [ -x /usr/local/cuda/bin/nvcc ]; then
        export PATH="/usr/local/cuda/bin:$PATH"
        _has_nvcc=1
    fi

    if [ "$_has_gpu" -eq 1 ] && [ "$_has_nvcc" -eq 1 ]; then
        local gpu nvcc_ver
        gpu="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
        nvcc_ver="$(nvcc --version 2>/dev/null | grep 'release' | awk '{print $NF}' | tr -d ,)"
        header "Rust — cargo test (janus-neuromorphic, CUDA) [${gpu} / nvcc ${nvcc_ver}]"
        if cargo test -p janus-neuromorphic --features cuda; then
            ok "neuromorphic CUDA tests passed"
        else
            err "neuromorphic CUDA tests failed"
            ((errors++))
        fi
    elif [ "$_has_gpu" -eq 1 ] && [ "$_has_nvcc" -eq 0 ]; then
        warn "GPU detected but nvcc not found — skipping neuromorphic CUDA tests"
        warn "Install the CUDA toolkit to enable them:"
        warn "  sudo apt-get install cuda-toolkit-12-8"
        warn "  export PATH=/usr/local/cuda/bin:\$PATH"
    else
        info "No CUDA GPU detected — skipping neuromorphic CUDA test pass"
    fi

    return $errors
}

# ── Format (write mode) ─────────────────────────────────────────────────────

cmd_fmt() {
    header "Auto-format — Rust"

    log "cargo fmt..."
    cargo fmt --all && ok "cargo fmt done" || warn "cargo fmt had issues"

    ok "Formatting complete"
}

# ── Convenience aliases ──────────────────────────────────────────────────────

cmd_lint() {
    header "Lint — Rust"
    cmd_lint_rust
}

cmd_test_all() {
    header "Test — Rust"
    cmd_test_rust
}

# =============================================================================
# Shell
# =============================================================================

cmd_shell() {
    local mode="${1:-dev}"
    local svc="${2:-data}"
    if [ "$mode" = "prod" ]; then
        $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" exec "$svc" bash \
            || $DC -f "$COMPOSE_FILE" -f "$PROD_COMPOSE_FILE" exec "$svc" sh
    else
        $DC -f "$COMPOSE_FILE" exec "$svc" bash \
            || $DC -f "$COMPOSE_FILE" exec "$svc" sh
    fi
}

# =============================================================================
# Cleanup
# =============================================================================

cmd_clean() {
    header "Cleaning Docker Resources + Build Caches"
    # `docker container prune -f` is HOST-WIDE and unconfirmed. A spawner-managed
    # bot sits in the exited state in several normal situations (crashed
    # overnight with no restart policy, stopped for a key rotation, awaiting
    # auto_prune), and this command's name and header both read as routine
    # housekeeping — so the operator gets no signal that a money bot is about to
    # be hard-removed out from under the spawner, losing its container and
    # leaving its bot_runs row open.
    #
    # label!= keeps the intent (clear stopped containers) while making the
    # money bots unreachable from here. Stopping a bot remains the spawner's job.
    local spared
    spared=$(docker ps -a --filter "label=fks.bot=true" --filter "status=exited" \
               --format '{{.Names}}' 2>/dev/null)
    docker container prune -f --filter "label!=fks.bot=true"
    docker image prune -f
    ok "Cleaned stopped containers and dangling images"
    if [ -n "$spared" ]; then
        warn "Spared stopped bot container(s) — remove via the spawner, not here:"
        printf '%s\n' "$spared" | sed 's/^/    /'
    fi
    log "Cleaning Python build caches..."
    find . -name ".mypy_cache"   -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "__pycache__"   -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".ruff_cache"   -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.egg-info"    -type d -exec rm -rf {} + 2>/dev/null || true
    ok "Cleaned Python caches (.mypy_cache, __pycache__, .pytest_cache, .ruff_cache, *.egg-info)"
}

cmd_force_clean() {
    header "⚠️  Force Clean — Removing ALL FKS Resources"
    warn "This will destroy all FKS containers, images, volumes."
    echo -n "Type 'yes' to confirm: "
    read -r confirm
    if [ "$confirm" != "yes" ]; then
        info "Cancelled"
        return
    fi

    $DC -f "$COMPOSE_FILE" \
        down --volumes --remove-orphans --timeout 5 2>/dev/null || true

    # Stack only (name=fks_). The spawner-managed fks-bot-* containers are NOT
    # torn down here — a blanket rm -f on a live-money bot skips its graceful
    # shutdown. Stop those via the spawner. Report any left running so a "force
    # clean" that leaves a bot alive isn't a silent surprise.
    docker ps -a --filter "name=fks_" -q | xargs -r docker rm -f || true
    docker images --filter "reference=nuniesmith/fks*" -q | xargs -r docker rmi -f || true
    docker images --filter "reference=fks:*" -q          | xargs -r docker rmi -f || true
    docker network ls --filter "name=fks" -q | xargs -r docker network rm || true
    docker network prune -f || true

    local spared
    spared=$(docker ps --filter "label=fks.bot=true" --format '{{.Names}}' 2>/dev/null)
    if [ -n "$spared" ]; then
        warn "Spawner-managed bots left RUNNING (stop via the spawner, not here):"
        printf '%s\n' "$spared" | sed 's/^/    /'
    fi

    ok "Force clean complete"
}

cmd_network_cleanup() {
    header "Network Cleanup"
    # No prior confirmation existed here (2026-08-04 audit finding) even though
    # this is a full-stack teardown, not a scoped network fix: it runs
    # `compose down` on the WHOLE stack, force-removes every fks_* container,
    # and removes/prunes every fks* Docker network. Scoped to name=fks_ only —
    # see cmd_force_clean / fks_visible_containers above — so spawner-managed
    # money bots (fks-bot-*) are never rm -f'd here, but every OTHER FKS
    # service stops. Guard it the same way the postgres RECREATE-DB prompt
    # (cmd_start/cmd_up) does: warn, then require explicit input, default no.
    warn "This stops the FULL fks_ stack (docker compose down), force-removes"
    warn "every fks_* container, and removes/prunes every fks* Docker network —"
    warn "not a scoped fix. Spawner-managed bots (fks-bot-*) are left alone,"
    warn "but every other FKS service (janus, webui, postgres, redis, ...) stops."
    printf "Continue? [y/N]: "
    read -r _confirm
    case "$_confirm" in
        y|Y|yes|YES) ;;
        *) err "Refused."; return 1 ;;
    esac
    $DC -f "$COMPOSE_FILE" down --remove-orphans --timeout 5 2>/dev/null || true
    # Stack only — see cmd_force_clean: never rm -f a spawner-managed money bot.
    docker ps -a --filter "name=fks_" -q | xargs -r docker rm -f || true
    docker network ls --filter "name=fks" -q | xargs -r docker network rm || true
    docker network prune -f || true
    ok "Network cleanup complete"
}

cmd_setup_kernel() {
    header "Host Kernel Tuning (sysctl)"
    local conf_src="infrastructure/config/99-fks.sysctl.conf"
    local conf_dst="/etc/sysctl.d/99-fks.conf"

    if [ ! -f "$conf_src" ]; then
        err "Config not found: $conf_src"
        return 1
    fi

    info "Installing $conf_src → $conf_dst"
    if sudo cp "$conf_src" "$conf_dst"; then
        ok "Config installed"
    else
        err "sudo cp failed — re-run with sudo or copy manually:"
        info "  sudo cp $conf_src $conf_dst"
        return 1
    fi

    info "Applying settings (sudo sysctl --system)..."
    sudo sysctl --system 2>&1 | grep -E "fks|file-max|somaxconn|overcommit|inotify" || true

    echo ""
    ok "Kernel parameters applied:"
    for key in fs.file-max net.core.somaxconn vm.overcommit_memory \
                fs.inotify.max_user_instances fs.inotify.max_user_watches; do
        local val; val=$(sysctl -n "$key" 2>/dev/null || echo "unknown")
        echo "  $key = $val"
    done
    echo ""
    info "Settings will persist across reboots via $conf_dst"
}

# FIX: cmd_setup_hosts moved OUT of the case block (it was previously defined
# inside the case/esac which is invalid bash) and typo `"w` on ok() line fixed.
cmd_setup_hosts() {
    header "Setup /etc/hosts — fkstrading.local"

    local entry="127.0.0.1 fkstrading.local"

    if grep -qF "fkstrading.local" /etc/hosts; then
        ok "/etc/hosts already has fkstrading.local entry"
        return 0
    fi

    if echo "$entry" | sudo tee -a /etc/hosts > /dev/null; then
        ok "Added '${entry}' to /etc/hosts"
    else
        warn "Failed to update /etc/hosts (requires sudo privileges)"
        return 1
    fi
}

cmd_diagnose() {
    header "System Diagnostics"
    echo "Docker version:"; docker version --format 'Client: {{.Client.Version}}  Server: {{.Server.Version}}' 2>/dev/null || docker version
    echo ""
    echo "Running containers:"; docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "FKS images:"; docker images --filter "reference=nuniesmith/fks*" --filter "reference=fks:*"
    echo ""
    echo "Volumes:"; docker volume ls --filter "name=fks"
    echo ""
    echo "Networks:"; docker network ls --filter "name=fks"
    echo ""
    echo "Port usage (selected):"
    for port in 80 3000 3001 5432 6379 7000 7001 8090 8812 9000 9009 9090 9091 9093 16686 6333; do
        local owner; owner=$(ss -tlnp 2>/dev/null | grep ":${port} " | awk '{print $NF}' | head -1 || true)
        [ -n "$owner" ] && echo "  :$port — $owner" || true
    done
    echo ""
    echo "Disk:"; df -h /
}

# =============================================================================
# web-hash-password
# =============================================================================

cmd_web_hash_password() {
    header "Generate Web Dashboard Password Hash"
    echo ""
    info "Generates a bcrypt hash to set as WEB_PASSWORD_HASH in .env"
    echo ""

    local password=""
    if [ -t 0 ]; then
        printf "Enter password: "
        stty -echo 2>/dev/null || true
        read -r password
        stty echo 2>/dev/null || true
        echo ""
        echo ""
        printf "Confirm password: "
        stty -echo 2>/dev/null || true
        local confirm=""
        read -r confirm
        stty echo 2>/dev/null || true
        echo ""
        if [ "$password" != "$confirm" ]; then
            err "Passwords do not match"
            exit 1
        fi
    else
        read -r password
    fi

    if [ -z "$password" ]; then
        err "Password cannot be empty"
        exit 1
    fi

    local hash
    hash=$(_generate_bcrypt_hash "$password")

    if [ -n "$hash" ]; then
        echo ""
        ok "Password hash generated:"
        echo ""
        echo "    WEB_PASSWORD_HASH=${hash}"
        echo ""
        info "Add the line above to your .env file, or run:"
        info "  ./run.sh setup-env   (prompts for password automatically)"
    else
        err "Failed to generate hash — install bcrypt: pip install bcrypt"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# tailscale-serve
# ---------------------------------------------------------------------------
cmd_tailscale_serve() {
    header "Tailscale Serve — Expose Dashboard"

    if ! command -v tailscale &>/dev/null; then
        err "tailscale CLI not found"
        exit 1
    fi
    if ! tailscale status &>/dev/null; then
        err "Tailscale daemon is not running"
        exit 1
    fi

    local target_port="3001"
    while [ $# -gt 0 ]; do
        case "$1" in
            --port) target_port="${2:-8080}"; shift 2 ;;
            *)      shift ;;
        esac
    done

    local ts_url
    ts_url="$(tailscale serve status 2>/dev/null | grep -o 'https://[^ ]*' | head -1 || true)"
    [ -z "$ts_url" ] && ts_url="https://<your-tailscale-host>"

    log "Configuring Tailscale HTTPS → :${target_port}..."
    tailscale serve --https=443 off 2>/dev/null || true
    tailscale serve --bg --https=443 "http://127.0.0.1:${target_port}"

    echo ""
    ok "Tailscale serve configured"
    echo ""
    echo -e "  ${GREEN}● Dashboard URL:${NC} ${ts_url}  →  :${target_port}"
    echo -e "  (Accessible from any device on your tailnet)"
    echo -e "  Run 'tailscale serve status' to verify"
    echo ""
    tailscale serve status
}

# ---------------------------------------------------------------------------
# tailscale-stop
# ---------------------------------------------------------------------------
cmd_tailscale_stop() {
    header "Tailscale Serve — Remove Config"

    if ! command -v tailscale &>/dev/null; then
        err "tailscale CLI not found"
        exit 1
    fi

    tailscale serve --https=443 off 2>/dev/null && \
        ok "Tailscale HTTPS serve removed" || \
        warn "Nothing to remove (or already gone)"

    echo ""
    tailscale serve status 2>/dev/null || echo "  (no serve config)"
}

# =============================================================================
# Usage
# =============================================================================

show_usage() {
    cat << EOF

${CYAN}FKS — Unified Management Script${NC}

${BLUE}Usage:${NC} ./run.sh <command> [options]

${BLUE}Quick start:${NC}
  ./run.sh                        Run full check (clippy + cargo test)
  ./run.sh all                    Build everything and start the janus stack
  ./run.sh all --demo             Same, plus the crypto-demo paper bot (end-to-end)
  ./run.sh fresh                  Clean rebuild — stop, rebuild all, bootstrap DBs, start
  ./run.sh fresh --reset-volumes  ⚠️  Same as fresh but wipes all data volumes first
  ./run.sh fresh --demo           Fresh rebuild + start the demo bot

${BLUE}Service management:${NC}
  ./run.sh start [prod]           Env setup → build → start
  ./run.sh up [prod] [svcs...]    Start (already built) services
  ./run.sh down [prod] [-v]       Stop services  (-v removes volumes)
  ./run.sh restart [svcs...]      Restart services
  ./run.sh logs [svc]             Follow logs (all services or one)
  ./run.sh status                 Show container status
  ./run.sh health                 Health check all services

${BLUE}Build:${NC}
  ./run.sh build [prod] [svcs...] Build images
  ./run.sh build-redis            Build custom Redis image
  ./run.sh build-bots             Build the spawnable reference bot images

${BLUE}Environment:${NC}
  ./run.sh setup-env              Generate or validate .env, fill secrets, prompt for API keys

${BLUE}Code quality (local — no Docker):${NC}
  ./run.sh check                  Full check: clippy + cargo test (Rust)
  ./run.sh lint                   cargo fmt --check + clippy (no tests)
  ./run.sh test                   cargo test
  ./run.sh fmt                    Auto-format Rust (cargo fmt)
  ./run.sh lint-rust              Cargo fmt --check + clippy only
  ./run.sh test-rust              cargo test only

${BLUE}Utilities:${NC}
  ./run.sh fix-db                 Bootstrap all databases (idempotent — safe to re-run)
  ./run.sh shell <svc>            Open shell in a container
  ./run.sh web-hash-password      Generate bcrypt hash for WEB_PASSWORD_HASH
  ./run.sh clean                  Remove stopped containers + dangling images
  ./run.sh force-clean            ⚠️  Remove ALL FKS resources + volumes
  ./run.sh network-cleanup        ⚠️  Fix Docker network conflicts — stops the FULL
                                   fks_ stack + removes every fks_* container and
                                   fks* network (prompts y/N; fks-bot-* untouched)
  ./run.sh diagnose               Detailed system diagnostics
  ./run.sh help                   Show this message

${BLUE}Tailscale:${NC}
  ./run.sh tailscale-serve [--port N]   Expose dashboard via Tailscale HTTPS (default: :3001)
  ./run.sh tailscale-stop               Remove Tailscale HTTPS serve config

${BLUE}Host setup (run once):${NC}
  ./run.sh setup-kernel           Install sysctl tuning (fd limits, net, inotify)
  ./run.sh setup-hosts            Add fkstrading.local to /etc/hosts
  ./run.sh generate-certs         Generate internal TLS certs
  ./run.sh ssl-local              Force-regenerate internal TLS certs

${BLUE}Examples:${NC}
  ./run.sh                        # Run all checks (default action)
  ./run.sh check                  # Same as above
  ./run.sh fmt                    # Auto-format everything
  ./run.sh lint                   # Lint only (no tests)
  ./run.sh test                   # Tests only (no lint)
  ./run.sh all                    # Full build + start (first time)
  ./run.sh all --demo             # Full build + start + crypto-demo paper bot
  ./run.sh fresh                  # Clean rebuild + DB bootstrap (fix broken state)
  ./run.sh fix-db                 # Just fix missing databases (no rebuild)
  ./run.sh start                  # Env → build → up (dev)
  ./run.sh start prod             # Env → pull → up (prod)
  ./run.sh logs janus             # Follow janus logs
  ./run.sh down -v                # Stop and remove volumes
EOF
}

# =============================================================================
# needs_docker — returns 1 for commands that don't need Docker
# =============================================================================

needs_docker() {
    case "$1" in
        # FIX: added setup-env — safe to run without Docker (just edits .env)
        check|lint|test|fmt|lint-rust|test-rust|\
        setup-env|web-hash-password|\
        tailscale-serve|tailscale-stop|help|--help|-h|"")
            return 1 ;;
        *)
            return 0 ;;
    esac
}

# =============================================================================
# Main
# =============================================================================

main() {
    if [ $# -lt 1 ]; then
        cmd_check
        exit $?
    fi

    local command="$1"

    if needs_docker "$command" "${2:-}"; then
        if ! docker info > /dev/null 2>&1; then
            err "Docker is not running"
            exit 1
        fi
        if ! docker compose version > /dev/null 2>&1; then
            err "Docker Compose V2 is not available"
            exit 1
        fi
    fi

    shift || true

    # ── prod prefix: ./run.sh prod <command> ────────────────────────────────
    local mode="dev"
    if [ "$command" = "prod" ]; then
        mode="prod"
        command="${1:-start}"
        shift || true
    fi

    # ── Dispatch ─────────────────────────────────────────────────────────────
    case $command in
        all)                cmd_all "$@" ;;
        fresh)              cmd_fresh "$@" ;;
        fix-db)             cmd_fix_db ;;
        start)              cmd_start "$mode" "$@" ;;
        up)                 cmd_up "$mode" "$@" ;;
        stop|down)          cmd_down "$mode" "$@" ;;
        restart)            cmd_restart "$mode" "$@" ;;
        logs)               cmd_logs "$mode" "$@" ;;
        status|ps)          cmd_status "$mode" ;;
        health)             cmd_health ;;
        build)              cmd_build "$mode" "$@" ;;
        build-redis)        cmd_build_redis ;;
        build-bots)         cmd_build_bots ;;
        setup-env)          setup_env_file ;;
        generate-certs)     ensure_tls_certs ;;
        ssl-local)          cmd_ssl_local "$@" ;;
        shell|exec)         cmd_shell "$mode" "$@" ;;
        web-hash-password)  cmd_web_hash_password ;;
        check)              cmd_check ;;
        lint)               cmd_lint ;;
        test)               cmd_test_all ;;
        fmt|format)         cmd_fmt ;;
        lint-rust)          cmd_lint_rust ;;
        test-rust)          cmd_test_rust ;;
        tailscale-serve)    cmd_tailscale_serve "$@" ;;
        tailscale-stop)     cmd_tailscale_stop ;;
        clean)              cmd_clean ;;
        force-clean)        cmd_force_clean ;;
        network-cleanup)    cmd_network_cleanup ;;
        setup-kernel)       cmd_setup_kernel ;;
        setup-hosts)        cmd_setup_hosts ;;      # FIX: function now properly defined above main()
        diagnose|diag)      cmd_diagnose ;;
        help|--help|-h)     show_usage ;;

        *)
            err "Unknown command: $command"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
