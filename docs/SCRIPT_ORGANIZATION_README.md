# FKS Trading Systems - Script Organization

## 📁 Complete Script Structure

All scripts have been organized into logical directories for better maintainability and clarity.

## 🗂️ Directory Structure

```
scripts/
├── automation/          # Automated update and monitoring scripts
├── deployment/          # Deployment and infrastructure scripts
├── environment/         # Environment setup and configuration
├── orchestration/       # System orchestration and startup scripts
├── services/           # Individual service management scripts
├── testing/            # Testing and validation scripts
├── maintenance/        # Cleanup and maintenance scripts
├── build/              # Build and compilation scripts
├── docker/             # Docker-related scripts
├── k8s/               # Kubernetes deployment scripts
├── utils/             # Utility and helper scripts
└── core/              # Core system scripts
```

## 📋 Script Categories

### 🤖 Automation (`scripts/automation/`)
**Purpose**: Automated monitoring, updates, and CI/CD processes

- **`auto_update.sh`** - Main auto-update script for GitHub integration
- **`check_auto_update.sh`** - Status monitoring and health checks
- **`test_auto_update.sh`** - Test script for auto-update functionality

**Usage:**
```bash
# Run auto-update
./scripts/automation/auto_update.sh

# Check status
./scripts/automation/check_auto_update.sh

# Test functionality
./scripts/automation/test_auto_update.sh
```

### 🏗️ Deployment (`scripts/deployment/`)
**Purpose**: Infrastructure deployment and server management

- **`github-actions/`** - GitHub Actions workflow scripts
- **`staged/`** - Multi-stage deployment processes
- **`tools/`** - Deployment utilities and troubleshooting
- **`manual/`** - Manual deployment scripts
- **`linode/`** - Linode-specific infrastructure scripts

### 🔧 Environment (`scripts/environment/`)
**Purpose**: Environment setup and configuration management

- **`activate_env.sh`** - Activate conda environment with GPU detection
- **`deactivate_env.sh`** - Deactivate conda environment

**Usage:**
```bash
# Activate environment
source scripts/environment/activate_env.sh

# Deactivate environment
source scripts/environment/deactivate_env.sh
```

### 🎭 Orchestration (`scripts/orchestration/`)
**Purpose**: System-wide orchestration and startup management

- **`start.sh`** - Main system startup with Docker orchestration
- **`run.sh`** - Enhanced orchestrator with Docker Hub integration

**Usage:**
```bash
# Start the system
./scripts/orchestration/start.sh

# Run with orchestration
./scripts/orchestration/run.sh
```

### 🔌 Services (`scripts/services/`)
**Purpose**: Individual service management and startup

- **`start_rithmic.sh`** - Rithmic service startup script

**Usage:**
```bash
# Start Rithmic service (test environment)
./scripts/services/start_rithmic.sh test

# Start Rithmic service (live environment)
./scripts/services/start_rithmic.sh live
```

### 🧪 Testing (`scripts/testing/`)
**Purpose**: Test scripts and validation tools

- **`test_rithmic_integration.py`** - Rithmic integration testing

**Usage:**
```bash
# Run Rithmic integration tests
python scripts/testing/test_rithmic_integration.py
```

### 🧽 Maintenance (`scripts/maintenance/`)
**Purpose**: System cleanup and maintenance tasks

- **`cleanup-now.sh`** - Immediate server cleanup
- **`cleanup-servers.sh`** - Interactive server cleanup

**Usage:**
```bash
# Quick cleanup
LINODE_CLI_TOKEN=your_token ./scripts/maintenance/cleanup-now.sh

# Interactive cleanup
LINODE_CLI_TOKEN=your_token ./scripts/maintenance/cleanup-servers.sh
```

## 🔗 Quick Access Scripts

For backward compatibility and ease of use, create symbolic links in the project root:

```bash
# Create convenience links
ln -sf scripts/orchestration/start.sh start.sh
ln -sf scripts/orchestration/run.sh run.sh
ln -sf scripts/services/start_rithmic.sh start_rithmic.sh
ln -sf scripts/automation/auto_update.sh auto_update.sh
```

## 📊 Migration Summary

### Scripts Moved:
- `activate_env.sh` → `scripts/environment/activate_env.sh`
- `deactivate_env.sh` → `scripts/environment/deactivate_env.sh`
- `auto_update.sh` → `scripts/automation/auto_update.sh`
- `check_auto_update.sh` → `scripts/automation/check_auto_update.sh`
- `test_auto_update.sh` → `scripts/automation/test_auto_update.sh`
- `start_rithmic.sh` → `scripts/services/start_rithmic.sh`
- `start.sh` → `scripts/orchestration/start.sh`
- `run.sh` → `scripts/orchestration/run.sh`
- `cleanup-now.sh` → `scripts/maintenance/cleanup-now.sh`
- `cleanup-servers.sh` → `scripts/maintenance/cleanup-servers.sh`
- `test_rithmic_integration.py` → `scripts/testing/test_rithmic_integration.py`

### Benefits:
- **Improved Organization**: Scripts are logically grouped by function
- **Better Maintainability**: Easier to find and modify specific scripts
- **Enhanced Documentation**: Clear purpose and usage for each category
- **Reduced Clutter**: Clean project root directory
- **Consistent Structure**: Follows established patterns from deployment scripts

## 🔧 Path Updates Required

### GitHub Actions Workflows
Update any workflow files that reference the moved scripts:

```yaml
# Old path
- name: Run auto update
  run: ./auto_update.sh

# New path  
- name: Run auto update
  run: ./scripts/automation/auto_update.sh
```

### Docker Compose Files
Update any docker-compose references:

```yaml
# Old path
command: ./start.sh

# New path
command: ./scripts/orchestration/start.sh
```

### Cron Jobs
Update cron job paths:

```bash
# Old path
*/5 * * * * /home/jordan/fks/auto_update.sh

# New path
*/5 * * * * /home/jordan/fks/scripts/automation/auto_update.sh
```

## 🎯 Next Steps

1. **Update References**: Search for and update all references to moved scripts
2. **Create Symlinks**: Add convenience symlinks for frequently used scripts
3. **Test Functionality**: Verify all scripts work from their new locations
4. **Update Documentation**: Update any additional documentation referencing old paths
5. **CI/CD Integration**: Update GitHub Actions workflows with new paths

## 🔍 Verification Commands

```bash
# List all scripts in new locations
find scripts/ -name "*.sh" -type f | sort

# Check for any remaining scripts in root
ls -la *.sh 2>/dev/null || echo "No scripts remaining in root"

# Verify script permissions
find scripts/ -name "*.sh" -type f -exec ls -la {} \;
```

---

**Organization completed**: $(date)
**Total scripts organized**: 11 scripts moved to appropriate directories
**New directory structure**: 7 specialized script categories
