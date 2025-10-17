# Generate htpasswd file for nginx basic auth
# Usage: bash generate_htpasswd.sh

#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}FKS Trading - Nginx Authentication Setup${NC}"
echo "=========================================="

# Check if htpasswd is installed
if ! command -v htpasswd &> /dev/null; then
    echo -e "${RED}htpasswd not found. Installing apache2-utils...${NC}"
    sudo apt-get update && sudo apt-get install -y apache2-utils
fi

# Create nginx directory if it doesn't exist
mkdir -p ./nginx

# Create htpasswd file for admin access
echo -e "\n${YELLOW}Creating admin user for nginx basic auth...${NC}"
read -p "Enter admin username: " ADMIN_USER
htpasswd -c ./nginx/.htpasswd "$ADMIN_USER"

echo -e "\n${GREEN}Admin user created successfully!${NC}"

# Option to add more users
while true; do
    read -p "Do you want to add another user? (y/n) " yn
    case $yn in
        [Yy]* )
            read -p "Enter username: " USERNAME
            htpasswd ./nginx/.htpasswd "$USERNAME"
            echo -e "${GREEN}User added successfully!${NC}"
            ;;
        [Nn]* )
            break
            ;;
        * ) echo "Please answer yes or no.";;
    esac
done

echo -e "\n${GREEN}Authentication file created at: ./nginx/.htpasswd${NC}"
echo -e "${YELLOW}Make sure to mount this file in your nginx container!${NC}"
