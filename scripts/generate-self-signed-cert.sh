#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Self-Signed SSL Certificate Generator for FKS Trading   ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
DOMAIN="fkstrading.xyz"
SSL_DIR="./nginx/ssl"
CERT_FILE="${SSL_DIR}/${DOMAIN}.crt"
KEY_FILE="${SSL_DIR}/${DOMAIN}.key"
DAYS_VALID=365

# Create SSL directory if it doesn't exist
mkdir -p "${SSL_DIR}"

echo -e "${YELLOW}Generating self-signed SSL certificate for ${DOMAIN}...${NC}"
echo ""

# Generate self-signed certificate
openssl req -x509 -nodes -days ${DAYS_VALID} \
    -newkey rsa:2048 \
    -keyout "${KEY_FILE}" \
    -out "${CERT_FILE}" \
    -subj "/C=US/ST=State/L=City/O=FKS Trading/OU=IT/CN=${DOMAIN}/emailAddress=admin@${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN},DNS:www.${DOMAIN},DNS:localhost,IP:127.0.0.1"

# Set proper permissions
chmod 600 "${KEY_FILE}"
chmod 644 "${CERT_FILE}"

echo -e "${GREEN}✅ SSL certificate generated successfully!${NC}"
echo ""
echo -e "${GREEN}Certificate details:${NC}"
echo -e "  Domain: ${DOMAIN}"
echo -e "  Certificate: ${CERT_FILE}"
echo -e "  Private Key: ${KEY_FILE}"
echo -e "  Valid for: ${DAYS_VALID} days"
echo ""

# Verify the certificate
echo -e "${YELLOW}Certificate Information:${NC}"
openssl x509 -in "${CERT_FILE}" -noout -subject -dates -issuer

echo ""
echo -e "${GREEN}✅ Self-signed certificate setup complete!${NC}"
echo ""
echo -e "${YELLOW}⚠️  Important Notes:${NC}"
echo -e "  1. This is a self-signed certificate - browsers will show a security warning"
echo -e "  2. Users will need to accept the security exception"
echo -e "  3. For production, use the upgrade-to-letsencrypt.sh script"
echo -e "  4. Let's Encrypt certificates are free and trusted by all browsers"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo -e "  1. Start Nginx: ${YELLOW}docker compose up -d nginx${NC}"
echo -e "  2. Test HTTPS: ${YELLOW}https://fkstrading.xyz${NC}"
echo -e "  3. Upgrade to Let's Encrypt when ready"
echo ""
