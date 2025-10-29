# Quick Fix: GitHub CLI Installation

## 🚀 Option 1: Install in WSL (Recommended for this workflow)

Since you're running the script in WSL, install GitHub CLI there:

```bash
# Update package list
sudo apt update

# Install GitHub CLI
type -p curl >/dev/null || sudo apt install curl -y
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh -y

# Verify installation
gh --version
```

### Authenticate
```bash
gh auth login
```

**Select**:
- GitHub.com
- HTTPS
- Authenticate via web browser

### Test it works
```bash
gh auth status
```

### Run import script
```bash
python3 scripts/import_project_plan.py --dry-run
```

---

## 🪟 Option 2: Install in Windows PowerShell

If you prefer running from PowerShell instead:

```powershell
# Install with winget (Windows 11/10)
winget install --id GitHub.cli

# Or download manually from: https://cli.github.com/

# Restart PowerShell after install

# Verify
gh --version

# Authenticate
gh auth login

# Run script (in PowerShell)
cd C:\Users\jordan\nextcloud\code\repos\fks
python scripts/import_project_plan.py --dry-run
```

---

## 🔧 Alternative: Use Manual Import (No GitHub CLI)

If you can't install GitHub CLI right now, I can create a web-based import method:

```bash
# Generate JSON file with all issues
python3 scripts/generate_issues_json.py

# Then manually create issues via GitHub web UI
# Or use GitHub API with curl
```

Would you like me to create this alternative script?

---

## ✅ After Installation

Once `gh` is installed and authenticated:

```bash
# 1. Preview issues (dry run)
python3 scripts/import_project_plan.py --dry-run

# 2. Import all issues
python3 scripts/import_project_plan.py

# 3. View on GitHub
https://github.com/nuniesmith/fks/issues
```

---

## 🆘 Troubleshooting

### "gh: command not found" after install
```bash
# WSL: Restart terminal or
source ~/.bashrc

# Windows: Restart PowerShell
```

### "gh auth login" fails
```bash
# Try with token instead
gh auth login --with-token < ~/.github-token
```

### Permission denied
```bash
# WSL might need sudo
sudo gh auth login
```

---

## 📚 What's Next?

1. **Install `gh`** using Option 1 (WSL) above
2. **Authenticate**: `gh auth login`
3. **Run script**: `python3 scripts/import_project_plan.py --dry-run`
4. **Import issues**: Remove `--dry-run` flag
5. **Organize on board**: Add to GitHub Project

**Questions?** The script will guide you through each step!
