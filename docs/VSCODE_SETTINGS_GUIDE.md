# VS Code Settings for FKS Trading Platform

## Overview

The `.vscode/settings.json` file configures VS Code for optimal Python development with Django, testing, linting, and formatting.

## Key Configurations

### Python Environment

```json
"python.defaultInterpreterPath": "/home/jordan/.venv/fks-trading/bin/python"
```

- Points to your WSL virtual environment at `~/.venv/fks-trading`
- Automatically activates when you open a Python file
- Works across VS Code terminal sessions

**Verify it's working:**
1. Open any `.py` file
2. Check bottom-right corner - should show: `Python 3.13.8 64-bit ('.venv/fks-trading')`
3. If wrong, click it and select `/home/jordan/.venv/fks-trading/bin/python`

### Code Formatting

**Black** is configured with 100-character line length:
- Auto-formats on save
- Organizes imports automatically
- Matches `ruff.toml` configuration

**Shortcuts:**
- `Ctrl+Shift+I` - Format document
- `Ctrl+Shift+O` - Organize imports

### Linting

Three linters enabled:
1. **Pylint** - Comprehensive Python linting
2. **Flake8** - Style guide enforcement
3. **MyPy** - Type checking

All run on save and show errors inline.

### Testing (pytest)

Configured for pytest with auto-discovery:

```json
"python.testing.pytestArgs": [
  "tests",
  "-v",
  "--tb=short"
]
```

**Using Test Explorer:**
1. Click Testing icon in sidebar (beaker icon)
2. VS Code auto-discovers tests in `tests/` directory
3. Click play button to run individual tests
4. Green checkmark = pass, red X = fail

**Keyboard shortcuts:**
- `Ctrl+; Ctrl+A` - Run all tests
- `Ctrl+; Ctrl+F` - Run failed tests
- `Ctrl+; Ctrl+L` - Run last test run

### Django Support

```json
"python.analysis.extraPaths": ["${workspaceFolder}/src"]
```

- Adds `src/` to Python path for imports
- Enables autocomplete for Django models, views, forms
- Recognizes Django template tags in HTML files

**Environment file:**
```json
"python.envFile": "${workspaceFolder}/.env"
```

Loads `.env` automatically for database credentials, API keys, etc.

### Pylance (IntelliSense)

Advanced type checking and autocomplete:

```json
"python.analysis.typeCheckingMode": "basic"
```

**Features:**
- Auto-imports when you use undefined names
- Function parameter hints
- Return type hints (inlay hints)
- Go to definition (`F12`)
- Find all references (`Shift+F12`)

**Performance:**
- `diagnosticMode: workspace` - Checks all files, not just open ones
- Catches errors before you run code

### File Exclusions

Hidden from file explorer and search:
- `__pycache__/` - Python bytecode
- `*.pyc` - Compiled Python files
- `.pytest_cache/` - Test cache
- `.mypy_cache/` - Type checking cache
- `.ruff_cache/` - Linter cache
- `*.egg-info/` - Package metadata
- `logs/` - Log files

**Why?** Keeps workspace clean and search fast.

### Auto-Save

```json
"files.autoSave": "afterDelay",
"files.autoSaveDelay": 1000
```

Saves files 1 second after you stop typing. Prevents lost work during WSL crashes.

### Line Endings

```json
"files.eol": "\n"
```

Uses Unix-style line endings (LF) instead of Windows (CRLF). Required for:
- Docker containers
- Git on WSL
- Shell scripts

## Terminal Configuration

```json
"terminal.integrated.defaultProfile.windows": "Ubuntu (WSL)"
```

New terminals open in WSL Ubuntu by default.

**Environment variables:**
```json
"terminal.integrated.env.linux": {
  "PYTHONPATH": "${workspaceFolder}/src"
}
```

Sets `PYTHONPATH` so you can import from `src/` in terminal.

## Language-Specific Settings

### Markdown
- Word wrap enabled
- Auto-format on save
- Suggestions enabled

### JSON/JSONC
- Auto-format on save
- Built-in formatter

### YAML
- 2-space indentation (Docker Compose, GitHub Actions)
- Advanced auto-indent

### Dockerfile
- Syntax highlighting
- Auto-formatting

## GitHub Copilot

```json
"github.copilot.enable": {
  "python": true,
  "yaml": true,
  "markdown": true
}
```

Copilot enabled for:
- ✅ Python code
- ✅ YAML (Docker, CI/CD)
- ✅ Markdown (docs)
- ❌ Plaintext (disabled to reduce noise)

## Jupyter Notebooks

```json
"jupyter.askForKernelRestart": false,
"notebook.output.textLineLimit": 500
```

- Auto-restart kernel without prompting
- Show up to 500 lines of output (useful for ML training logs)

## Recommended Extensions

These settings work best with:

### Essential
- **Python** (`ms-python.python`) - Core Python support
- **Pylance** (`ms-python.vscode-pylance`) - Fast IntelliSense
- **Black Formatter** (`ms-python.black-formatter`) - Code formatting
- **isort** (`ms-python.isort`) - Import sorting

### Django
- **Django** (`batisteo.vscode-django`) - Template syntax, snippets
- **Django Template** - Syntax highlighting for `.html` files

### Testing
- **Python Test Explorer** - Visual test runner

### Docker
- **Docker** (`ms-azuretools.vscode-docker`) - Dockerfile, Compose support

### Git
- **GitLens** (`eamodio.gitlens`) - Advanced Git features

### Utilities
- **Better Comments** - Color-coded comments
- **Error Lens** - Inline error messages
- **Todo Tree** - Find TODO comments

## Troubleshooting

### Python Interpreter Not Found

**Problem:** VS Code shows "Python interpreter not set"

**Solution:**
1. Press `Ctrl+Shift+P`
2. Type "Python: Select Interpreter"
3. Choose `/home/jordan/.venv/fks-trading/bin/python`

### Linting Not Working

**Problem:** No red squiggles for errors

**Solution:**
```bash
# Activate venv and install linting tools
source ~/.venv/fks-trading/bin/activate
pip install pylint flake8 mypy black isort
```

### Tests Not Discovered

**Problem:** Test Explorer shows "No tests found"

**Solution:**
1. Check pytest is installed: `pip list | grep pytest`
2. Reload window: `Ctrl+Shift+P` → "Developer: Reload Window"
3. Check `pytest.ini` exists in project root

### Import Errors (Django Models)

**Problem:** `from src.core.models import Trade` shows error

**Solution:**
1. Verify `PYTHONPATH` in terminal:
   ```bash
   echo $PYTHONPATH
   # Should include: /mnt/c/Users/jordan/nextcloud/code/repos/fks/src
   ```
2. Reload window
3. Check `.env` file exists

### Auto-Format Not Working

**Problem:** Save doesn't format code

**Solution:**
1. Check Black is installed: `pip list | grep black`
2. Open Command Palette (`Ctrl+Shift+P`)
3. Run "Format Document" manually
4. Check for format errors in Output panel

## Custom Keybindings

Add to `.vscode/keybindings.json`:

```json
[
  {
    "key": "ctrl+shift+t",
    "command": "python.execInTerminal"
  },
  {
    "key": "ctrl+shift+r",
    "command": "python.testing.runCurrentFile"
  }
]
```

## Performance Tips

### For Large Projects

If VS Code is slow:

```json
"python.analysis.diagnosticMode": "openFilesOnly",
"files.watcherExclude": {
  "**/logs/**": true,
  "**/.venv/**": true
}
```

### For Slow Tests

```json
"python.testing.autoTestDiscoverOnSaveEnabled": false
```

Manually trigger test discovery instead of on every save.

## Quick Reference

| Task | Shortcut |
|------|----------|
| Command Palette | `Ctrl+Shift+P` |
| Quick Open File | `Ctrl+P` |
| Format Document | `Ctrl+Shift+I` |
| Organize Imports | `Ctrl+Shift+O` |
| Go to Definition | `F12` |
| Find References | `Shift+F12` |
| Rename Symbol | `F2` |
| Run All Tests | `Ctrl+; Ctrl+A` |
| Run Python File | `Ctrl+Shift+T` (if keybinding added) |
| Toggle Terminal | `Ctrl+`` |

## Environment Check

Verify settings are working:

```bash
# 1. Activate venv
source ~/.venv/fks-trading/bin/activate

# 2. Check Python
python --version
# Should show: Python 3.13.8 (or 3.12.x if you migrated)

# 3. Check linters installed
pip list | grep -E "(black|pylint|flake8|mypy|isort)"

# 4. Check pytest
pytest --version

# 5. Test imports
python -c "import sys; print(sys.path)" | grep src
```

All should work correctly with the settings.json configuration.

## Next Steps

1. **Install recommended extensions** (VS Code will prompt)
2. **Reload window** to apply settings: `Ctrl+Shift+P` → "Reload Window"
3. **Select Python interpreter** if not auto-detected
4. **Run tests** to verify configuration: Click Testing icon
5. **Start coding!** Settings will auto-format, lint, and test

---

**File Location**: `.vscode/settings.json`
**Last Updated**: October 18, 2025
**Python Version**: 3.13.8 (or 3.12.x recommended)
**Virtual Env**: `~/.venv/fks-trading`
