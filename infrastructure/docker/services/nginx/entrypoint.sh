#!/bin/sh
# =============================================================================
# FKS Nginx Entrypoint Script
# =============================================================================
# In production, Tailscale terminates TLS via `tailscale serve` — nginx only
# serves HTTP on port 80.  No SSL certificates are needed at the nginx layer.
#
# For local development, fkstrading.local.conf provides optional HTTPS using
# either a mkcert/ssl-local cert or a baked-in self-signed fallback.
# =============================================================================

# Don't exit on error - we want to continue even if symlinks fail
set +e

echo "=== FKS Nginx Initialization ==="

# ---------------------------------------------------------------------------
# Inject NGINX_INTERNAL_TOKEN into nginx conf files.
# Tailscale handles all external TLS — nginx serves HTTP only on port 80.
# envsubst replaces ${NGINX_INTERNAL_TOKEN} placeholders so the internal
# trust header is set correctly without hardcoding it in conf files.
# ---------------------------------------------------------------------------
_fks_token="${NGINX_INTERNAL_TOKEN:-nginx-internal-fks}"
for _fks_conf in /etc/nginx/conf.d/*.conf; do
    [ -f "$_fks_conf" ] || continue
    if grep -qF 'NGINX_INTERNAL_TOKEN' "$_fks_conf" 2>/dev/null; then
        NGINX_INTERNAL_TOKEN="$_fks_token" \
            envsubst '${NGINX_INTERNAL_TOKEN}' \
                < "$_fks_conf" > "${_fks_conf}.tmp" \
            && mv "${_fks_conf}.tmp" "$_fks_conf" \
            || rm -f "${_fks_conf}.tmp"
    fi
done
unset _fks_token _fks_conf

# Re-enable exit on error for nginx validation
set -e

# Validate nginx configuration
echo "Validating nginx configuration..."
if nginx -t 2>/dev/null; then
    echo "✓ Nginx configuration is valid"
else
    echo "✗ Nginx configuration error - check logs"
    nginx -t
fi

echo "=== FKS Nginx Ready ==="
