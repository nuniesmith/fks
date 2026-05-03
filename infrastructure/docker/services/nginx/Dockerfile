# =============================================================================
# FKS Nginx Dockerfile
# =============================================================================
# Bakes all nginx configuration into the image. In production, Tailscale
# terminates TLS via `tailscale serve` — nginx serves HTTP only on port 80.
# For local dev, fkstrading.local.conf provides optional HTTPS via a
# self-signed or mkcert certificate.
#
# Build: docker build -t nuniesmith/fks:nginx -f infrastructure/docker/services/nginx/Dockerfile .
# =============================================================================

FROM nginx:alpine AS base

# Install required tools
RUN apk add --no-cache \
    curl \
    openssl \
    && rm -rf /var/cache/apk/*

# =============================================================================
# Production Stage
# =============================================================================
FROM base AS production

# Create directories
RUN mkdir -p /etc/nginx/conf.d \
    /etc/nginx/snippets \
    /etc/nginx/ssl \
    /etc/letsencrypt \
    /var/www/certbot \
    /var/log/nginx \
    /var/cache/nginx

# Copy nginx configuration files
COPY infrastructure/config/nginx/nginx.conf /etc/nginx/nginx.conf
COPY infrastructure/config/nginx/conf.d/ /etc/nginx/conf.d/
# Note: snippets/ was removed during INFRA-B cleanup (was empty, contained only .gitkeep)

# Tailscale handles all external TLS — nginx serves HTTP only on port 80.
# No SSL certs needed in the image.
RUN mkdir -p /etc/nginx/ssl

# Copy entrypoint script
COPY infrastructure/docker/services/nginx/entrypoint.sh /docker-entrypoint.d/99-fks-init.sh
RUN chmod +x /docker-entrypoint.d/99-fks-init.sh

# Set proper permissions
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx && \
    chmod -R 755 /etc/nginx

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost/health > /dev/null || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
