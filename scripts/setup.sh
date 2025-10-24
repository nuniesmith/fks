#!/bin/bash
# setup.sh - Script to install prerequisites for TA-Lib and create venv

# Update packages
sudo apt-get update

# Install build essentials and wget if not present
sudo apt-get install -y build-essential wget python3.12-venv

# Download and install TA-Lib C library
cd /tmp
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
sudo ldconfig

# Create virtual environment and install requirements
cd /path/to/your/project  # Replace with your project path
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt