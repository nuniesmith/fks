#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║    Upgrade to Let's Encrypt SSL Certificates (Certbot)    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
DOMAIN="fkstrading.xyz"
EMAIL="admin@${DOMAIN}"
WEBROOT="/var/www/certbot"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Please run as root or with sudo${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Pre-flight checks...${NC}"
echo ""

# Check if domain resolves to this server
echo -e "${BLUE}Checking DNS resolution for ${DOMAIN}...${NC}"
DOMAIN_IP=$(dig +short ${DOMAIN} | tail -n1)
SERVER_IP=$(curl -s ifconfig.me)

if [ -z "$DOMAIN_IP" ]; then
    echo -e "${RED}❌ Domain ${DOMAIN} does not resolve to any IP${NC}"
    echo -e "${YELLOW}Please configure your DNS records first${NC}"
    exit 1
fi

echo -e "  Domain IP: ${DOMAIN_IP}"
echo -e "  Server IP: ${SERVER_IP}"

if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
    echo -e "${YELLOW}⚠️  Warning: Domain IP doesn't match server IP${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install certbot if not installed
if ! command -v certbot &> /dev/null; then
    echo -e "${YELLOW}Installing certbot...${NC}"
    apt-get update
    apt-get install -y certbot python3-certbot-nginx
fi

# Backup current SSL certificates
echo -e "${YELLOW}Backing up current SSL certificates...${NC}"
BACKUP_DIR="./nginx/ssl/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"
cp -r ./nginx/ssl/*.crt ./nginx/ssl/*.key "${BACKUP_DIR}/" 2>/dev/null || true
echo -e "${GREEN}✅ Backup created: ${BACKUP_DIR}${NC}"
echo ""

# Create webroot directory
mkdir -p "${WEBROOT}"

# Update Nginx configuration to use Let's Encrypt paths
echo -e "${YELLOW}Updating Nginx configuration...${NC}"
NGINX_CONF="./nginx/conf.d/fkstrading.xyz.conf"

# Comment out self-signed cert paths and uncomment Let's Encrypt paths
sed -i.bak \
    -e 's|ssl_certificate /etc/nginx/ssl/|#ssl_certificate /etc/nginx/ssl/|' \
    -e 's|ssl_certificate_key /etc/nginx/ssl/|#ssl_certificate_key /etc/nginx/ssl/|' \
    -e 's|#ssl_certificate /etc/letsencrypt/|ssl_certificate /etc/letsencrypt/|' \
    -e 's|#ssl_certificate_key /etc/letsencrypt/|ssl_certificate_key /etc/letsencrypt/|' \
    "${NGINX_CONF}"

# Reload Nginx to serve ACME challenge
echo -e "${YELLOW}Reloading Nginx...${NC}"
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload

# Obtain Let's Encrypt certificate
echo -e "${YELLOW}Obtaining Let's Encrypt certificate...${NC}"
echo -e "${BLUE}Email: ${EMAIL}${NC}"
echo -e "${BLUE}Domain: ${DOMAIN}, www.${DOMAIN}${NC}"
echo ""

certbot certonly \
    --webroot \
    --webroot-path="${WEBROOT}" \
    --email "${EMAIL}" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d "${DOMAIN}" \
    -d "www.${DOMAIN}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Let's Encrypt certificate obtained successfully!${NC}"
    
    # Copy certificates to nginx volume
    cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "./nginx/ssl/${DOMAIN}.crt"
    cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "./nginx/ssl/${DOMAIN}.key"
    
    # Set proper permissions
    chmod 644 "./nginx/ssl/${DOMAIN}.crt"
    chmod 600 "./nginx/ssl/${DOMAIN}.key"
    
    # Reload Nginx
    echo -e "${YELLOW}Reloading Nginx with new certificates...${NC}"
    docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           SSL Certificate Upgrade Complete! ✅             ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Certificate details:${NC}"
    echo -e "  Domain: ${DOMAIN}"
    echo -e "  Issuer: Let's Encrypt"
    echo -e "  Valid for: 90 days"
    echo -e "  Auto-renewal: Configured"
    echo ""
    echo -e "${GREEN}Certificate locations:${NC}"
    echo -e "  Certificate: /etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
    echo -e "  Private Key: /etc/letsencrypt/live/${DOMAIN}/privkey.pem"
    echo ""
    echo -e "${YELLOW}Important:${NC}"
    echo -e "  • Let's Encrypt certificates expire every 90 days"
    echo -e "  • Set up auto-renewal: ${YELLOW}certbot renew --dry-run${NC}"
    echo -e "  • Add to crontab: ${YELLOW}0 0,12 * * * certbot renew --quiet${NC}"
    echo ""
    echo -e "${GREEN}Test your site:${NC}"
    echo -e "  • ${BLUE}https://fkstrading.xyz${NC}"
    echo -e "  • ${BLUE}https://www.ssllabs.com/ssltest/analyze.html?d=fkstrading.xyz${NC}"
    echo ""
else
    echo -e "${RED}❌ Failed to obtain Let's Encrypt certificate${NC}"
    echo -e "${YELLOW}Restoring backup configuration...${NC}"
    mv "${NGINX_CONF}.bak" "${NGINX_CONF}"
    docker compose exec nginx nginx -s reload
    exit 1
fi

# Setup auto-renewal
echo -e "${YELLOW}Setting up auto-renewal...${NC}"
cat > /etc/cron.d/certbot-renew << EOF
# Certbot renewal for fkstrading.xyz
0 0,12 * * * root certbot renew --quiet --deploy-hook "docker compose -f $(pwd)/docker-compose.yml exec nginx nginx -s reload"
EOF

echo -e "${GREEN}✅ Auto-renewal configured${NC}"
echo ""
