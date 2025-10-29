# Install Python 3.13 on Ubuntu 24.04

## Quick Install (Run in WSL Terminal)

```bash
# 1. Update system packages
sudo apt update

# 2. Add deadsnakes PPA (provides newer Python versions)
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# 3. Install Python 3.13 and essential packages
sudo apt install -y \
    python3.13 \
    python3.13-venv \
    python3.13-dev

# 4. Verify installation
python3.13 --version

# 5. Install pip for Python 3.13
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.13

# 6. (Optional) Set Python 3.13 as alternative
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 2
```

## Or Use the Script

```bash
# Run the automated installation script
cd /mnt/c/Users/jordan/nextcloud/code/repos/fks
bash scripts/install_python313.sh
```

## After Installation

### Create New Virtual Environment with Python 3.13

```bash
# Remove old venv (if you want to upgrade)
rm -rf ~/.venv/fks-trading

# Create new venv with Python 3.13
python3.13 -m venv ~/.venv/fks-trading

# Activate it
source ~/.venv/fks-trading/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt
```

### Switch Default Python Version (Optional)

```bash
# See available versions
sudo update-alternatives --config python3

# Select Python 3.13 from the menu
```

## Check Python Versions

```bash
# System Python
python3 --version

# Specific version
python3.13 --version

# In virtual environment
source ~/.venv/fks-trading/bin/activate
python --version
```

## Troubleshooting

### If deadsnakes PPA doesn't have 3.13 yet

Python 3.13 was released in October 2024, so it should be available. If not:

```bash
# Build from source (takes 5-10 minutes)
sudo apt install -y build-essential zlib1g-dev libncurses5-dev \
    libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev \
    libsqlite3-dev wget libbz2-dev

cd /tmp
wget https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tgz
tar -xf Python-3.13.0.tgz
cd Python-3.13.0
./configure --enable-optimizations
make -j $(nproc)
sudo make altinstall  # altinstall doesn't replace python3
```

### Verify Installation

```bash
python3.13 --version
python3.13 -m pip --version
python3.13 -m venv --help
```
