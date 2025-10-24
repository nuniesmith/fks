#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

clear

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                                ║${NC}"
echo -e "${CYAN}║        FKS Trading Platform - Nginx SSL Setup Script          ║${NC}"
echo -e "${CYAN}║                    fkstrading.xyz                              ║${NC}"
echo -e "${CYAN}║                                                                ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
DOMAIN="fkstrading.xyz"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}📋 Setup Options:${NC}"
echo -e "  ${GREEN}1)${NC} Generate self-signed SSL certificate (Quick start)"
echo -e "  ${GREEN}2)${NC} Setup Let's Encrypt SSL certificate (Production)"
echo -e "  ${GREEN}3)${NC} Just start services (certificates already exist)"
echo -e "  ${GREEN}4)${NC} View current status"
echo ""
read -p "Select option (1-4): " -n 1 -r
echo ""

case $REPLY in
    1)
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}  Option 1: Self-Signed SSL Certificate${NC}"
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        
        # Check if OpenSSL is installed
        if ! command -v openssl &> /dev/null; then
            echo -e "${RED}❌ OpenSSL is not installed${NC}"
            echo -e "${YELLOW}Install with: apt-get install openssl${NC}"
            exit 1
        fi
        
        # Run the self-signed cert generation script
        bash ./scripts/generate-self-signed-cert.sh
        
        echo ""
        echo -e "${YELLOW}Starting Docker services...${NC}"
        docker compose up -d
        
        echo ""
        echo -e "${GREEN}✅ Services started with self-signed certificate${NC}"
        sleep 3
        docker compose ps
        
        echo ""
        echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║                     Setup Complete! ✅                         ║${NC}"
        echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${GREEN}Access your application:${NC}"
        echo -e "  • HTTP:  ${BLUE}http://fkstrading.xyz${NC} (redirects to HTTPS)"
        echo -e "  • HTTPS: ${BLUE}https://fkstrading.xyz${NC}"
        echo -e "  • Flower: ${BLUE}https://fkstrading.xyz/flower/${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  Browser Security Warning:${NC}"
        echo -e "  Self-signed certificates will show a browser warning"
        echo -e "  Click 'Advanced' → 'Proceed to fkstrading.xyz (unsafe)'"
        echo ""
        echo -e "${GREEN}To upgrade to Let's Encrypt:${NC}"
        echo -e "  ${CYAN}bash scripts/upgrade-to-letsencrypt.sh${NC}"
        echo ""
        ;;
        
    2)
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}  Option 2: Let's Encrypt SSL Certificate${NC}"
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        
        # Check if running as root
        if [ "$EUID" -ne 0 ]; then 
            echo -e "${RED}❌ Let's Encrypt setup requires root privileges${NC}"
            echo -e "${YELLOW}Please run with sudo:${NC}"
            echo -e "  ${CYAN}sudo bash scripts/setup-nginx-ssl.sh${NC}"
            exit 1
        fi
        
        # Check DNS
        echo -e "${YELLOW}Checking DNS configuration...${NC}"
        DOMAIN_IP=$(dig +short ${DOMAIN} | tail -n1)
        
        if [ -z "$DOMAIN_IP" ]; then
            echo -e "${RED}❌ Domain ${DOMAIN} does not resolve${NC}"
            echo -e "${YELLOW}Please configure your DNS first:${NC}"
            echo -e "  A     fkstrading.xyz     → 100.114.87.27"
            echo -e "  A     www               → 100.114.87.27"
            exit 1
        fi
        
        echo -e "${GREEN}✅ Domain resolves to: ${DOMAIN_IP}${NC}"
        echo ""
        
        # Start services first
        echo -e "${YELLOW}Starting Docker services...${NC}"
        docker compose up -d
        sleep 5
        
        # Run Let's Encrypt setup
        bash ./scripts/upgrade-to-letsencrypt.sh
        ;;
        
    3)
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}  Option 3: Start Services${NC}"
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        
        # Check if SSL certificates exist
        if [ ! -f "./nginx/ssl/${DOMAIN}.crt" ] || [ ! -f "./nginx/ssl/${DOMAIN}.key" ]; then
            echo -e "${RED}❌ SSL certificates not found${NC}"
            echo -e "${YELLOW}Please generate certificates first (option 1 or 2)${NC}"
            exit 1
        fi
        
        echo -e "${YELLOW}Starting Docker services...${NC}"
        docker compose up -d
        
        sleep 3
        echo ""
        echo -e "${GREEN}✅ Services started${NC}"
        docker compose ps
        
        echo ""
        echo -e "${GREEN}Access your application:${NC}"
        echo -e "  • HTTPS: ${BLUE}https://fkstrading.xyz${NC}"
        echo ""
        ;;
        
    4)
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}  Option 4: Current Status${NC}"
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        
        # Check Docker services
        echo -e "${BLUE}Docker Services:${NC}"
        docker compose ps
        echo ""
        
        # Check SSL certificates
        echo -e "${BLUE}SSL Certificates:${NC}"
        if [ -f "./nginx/ssl/${DOMAIN}.crt" ]; then
            echo -e "  ${GREEN}✅${NC} Certificate found: ./nginx/ssl/${DOMAIN}.crt"
            
            # Check certificate details
            ISSUER=$(openssl x509 -in "./nginx/ssl/${DOMAIN}.crt" -noout -issuer | sed 's/issuer=//')
            EXPIRES=$(openssl x509 -in "./nginx/ssl/${DOMAIN}.crt" -noout -enddate | sed 's/notAfter=//')
            
            echo -e "  Issuer: ${ISSUER}"
            echo -e "  Expires: ${EXPIRES}"
            
            if [[ $ISSUER == *"Let's Encrypt"* ]]; then
                echo -e "  Type: ${GREEN}Let's Encrypt (Trusted)${NC}"
            else
                echo -e "  Type: ${YELLOW}Self-Signed (Browser warning)${NC}"
            fi
        else
            echo -e "  ${RED}❌${NC} No certificate found"
            echo -e "  Generate with option 1 or 2"
        fi
        echo ""
        
        # Check DNS
        echo -e "${BLUE}DNS Configuration:${NC}"
        DOMAIN_IP=$(dig +short ${DOMAIN} | tail -n1)
        WWW_IP=$(dig +short www.${DOMAIN} | tail -n1)
        
        if [ -n "$DOMAIN_IP" ]; then
            echo -e "  ${GREEN}✅${NC} ${DOMAIN} → ${DOMAIN_IP}"
        else
            echo -e "  ${RED}❌${NC} ${DOMAIN} does not resolve"
        fi
        
        if [ -n "$WWW_IP" ]; then
            echo -e "  ${GREEN}✅${NC} www.${DOMAIN} → ${WWW_IP}"
        else
            echo -e "  ${YELLOW}⚠️${NC}  www.${DOMAIN} does not resolve"
        fi
        echo ""
        
        # Test connectivity
        echo -e "${BLUE}Connectivity Test:${NC}"
        if curl -k -s -o /dev/null -w "%{http_code}" https://localhost | grep -q "200\|301\|302"; then
            echo -e "  ${GREEN}✅${NC} Local HTTPS responding"
        else
            echo -e "  ${RED}❌${NC} Local HTTPS not responding"
        fi
        echo ""
        ;;
        
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Useful Commands:${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  View logs:           ${YELLOW}docker compose logs -f nginx${NC}"
echo -e "  Restart services:    ${YELLOW}docker compose restart${NC}"
echo -e "  Stop services:       ${YELLOW}docker compose down${NC}"
echo -e "  Test Nginx config:   ${YELLOW}docker compose exec nginx nginx -t${NC}"
echo -e "  Reload Nginx:        ${YELLOW}docker compose exec nginx nginx -s reload${NC}"
echo -e "  SSL cert details:    ${YELLOW}openssl x509 -in nginx/ssl/${DOMAIN}.crt -text -noout${NC}"
echo ""
