# Virtual Environment Setup - WSL

## Location
The Python virtual environment is installed **outside** the project directory in your WSL home:
```
~/.venvs/fks/
```

This keeps the project directory clean and prevents the large venv from being synced with Nextcloud.

## Activation

### Quick Activation (Recommended)
```bash
source ~/activate-fks.sh
```

This will:
- Activate the virtual environment
- Navigate to the project directory
- Show helpful information about available commands

### Manual Activation
```bash
source ~/.venvs/fks/bin/activate
cd /mnt/c/Users/jordan/Nextcloud/code/repos/fks
```

## Deactivation
```bash
deactivate
```

## Python Version
```
Python 3.12.3
```

## Installation Details

### Initial Setup
```bash
# Install venv package
sudo apt install -y python3.12-venv

# Create virtual environment
python3 -m venv ~/.venvs/fks

# Activate
source ~/.venvs/fks/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt
```

### Verify Installation
```bash
source ~/.venvs/fks/bin/activate
python --version  # Should show Python 3.12.3
which python      # Should show /home/jordan/.venvs/fks/bin/python
pip list          # Shows all installed packages
```

## Benefits

1. **Clean Project Directory** - No large `venv/` folder cluttering the project
2. **No Sync Issues** - Virtual environment not synced with Nextcloud
3. **Persistent** - Survives project clones and moves
4. **Standard Location** - Follows common Python conventions (`~/.venvs/`)
5. **Easy Management** - Can manage multiple venvs in one place

## Common Commands

### With Virtual Environment Active
```bash
# Install a package
pip install <package-name>

# Update requirements.txt
pip freeze > requirements.txt

# Run tests
pytest tests/ -v

# Run linting
make lint

# Start Django shell
python manage.py shell

# Run development server (in Docker)
make up
```

## Troubleshooting

### Virtual Environment Not Found
```bash
# Recreate it
python3 -m venv ~/.venvs/fks
source ~/.venvs/fks/bin/activate
pip install -r requirements.txt
```

### Wrong Python Version
```bash
# Check Python version
python --version

# If wrong, deactivate and recreate
deactivate
rm -rf ~/.venvs/fks
python3 -m venv ~/.venvs/fks
source ~/.venvs/fks/bin/activate
```

### Missing Packages
```bash
# Ensure venv is activated
source ~/.venvs/fks/bin/activate

# Reinstall requirements
pip install -r requirements.txt
```

### Permission Issues
```bash
# The venv should be owned by your user
ls -ld ~/.venvs/fks
# Should show: drwxr-xr-x ... jordan jordan ...

# If not, fix permissions
sudo chown -R jordan:jordan ~/.venvs/fks
```

## Integration with VS Code

To use this virtual environment in VS Code:

1. Open VS Code
2. Press `Ctrl+Shift+P`
3. Type "Python: Select Interpreter"
4. Choose "Enter interpreter path..."
5. Enter: `/home/jordan/.venvs/fks/bin/python`

Alternatively, create `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "/home/jordan/.venvs/fks/bin/python",
    "python.terminal.activateEnvironment": true
}
```

## Multiple Environments

You can create additional virtual environments for different projects:
```bash
# Create another venv
python3 -m venv ~/.venvs/other-project

# Activate it
source ~/.venvs/other-project/bin/activate
```

All venvs live in `~/.venvs/` for easy management.

## Backup and Restore

### Backup (requirements.txt is sufficient)
```bash
# The requirements.txt file is all you need
# It's already in the repository
```

### Restore
```bash
# Create fresh venv
python3 -m venv ~/.venvs/fks
source ~/.venvs/fks/bin/activate
pip install -r requirements.txt
```

## Notes

- The virtual environment is **not** included in git (and shouldn't be)
- The `requirements.txt` file tracks all dependencies
- Use `pip freeze` to update `requirements.txt` after installing new packages
- The venv is specific to the WSL environment (not shared with Windows)

---

**Created**: October 21, 2025
**Python Version**: 3.12.3
**Location**: `~/.venvs/fks/`
**Activation Script**: `~/activate-fks.sh`
