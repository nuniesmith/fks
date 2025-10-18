# Branch Protection Configuration Guide

This guide explains how to configure branch protection rules to ensure code quality and prevent breaking changes.

## Recommended Protection Rules

### For `main` Branch (Production)

#### 1. Require Pull Request Reviews
- ✅ **Required number of approvals**: 1
- ✅ **Dismiss stale reviews**: When new commits are pushed
- ✅ **Require review from Code Owners**: Enable if you have CODEOWNERS file
- ⚠️ **Require approval from someone other than the last pusher**: Recommended for teams

#### 2. Require Status Checks
Select these checks to pass before merging:
- ✅ `test (3.13, ubuntu-latest)` - Main test suite
- ✅ `lint` - Code quality checks
- ✅ `security` - Security scanning
- ⚠️ `test (3.11, ubuntu-latest)` - Optional: Python 3.11 compatibility
- ⚠️ `test (3.12, ubuntu-latest)` - Optional: Python 3.12 compatibility
- ❌ `docker` - Don't require (runs after merge on main)

**Configuration**:
- ✅ **Require branches to be up to date**: Prevents merge conflicts
- ✅ **Require status checks to pass**: Ensures quality standards

#### 3. Additional Protection
- ✅ **Require conversation resolution**: All comments must be resolved
- ✅ **Require linear history**: Prevent merge commits (use squash/rebase)
- ⚠️ **Include administrators**: Apply rules to admins too
- ✅ **Allow force pushes**: Disabled
- ✅ **Allow deletions**: Disabled

### For `develop` Branch (Staging)

#### 1. Require Pull Request Reviews
- ✅ **Required number of approvals**: 1 (can be same as main)
- ⚠️ **Dismiss stale reviews**: Optional for faster iteration
- ❌ **Require review from Code Owners**: Less strict than main

#### 2. Require Status Checks
Select these checks to pass:
- ✅ `test (3.13, ubuntu-latest)` - Main test suite
- ✅ `lint` - Code quality checks
- ⚠️ `security` - Optional: Can be less strict than main
- ❌ Other Python versions - Not required for develop

**Configuration**:
- ✅ **Require branches to be up to date**: Yes
- ✅ **Require status checks to pass**: Yes

#### 3. Additional Protection
- ⚠️ **Require conversation resolution**: Optional
- ❌ **Require linear history**: Allow merge commits for flexibility
- ❌ **Include administrators**: Allow admins to bypass for hotfixes
- ✅ **Allow force pushes**: Disabled
- ✅ **Allow deletions**: Disabled

## Setting Up Branch Protection

### Via GitHub Web UI

1. **Navigate to Settings**
   - Go to your repository on GitHub
   - Click "Settings" in the top menu
   - Click "Branches" in the left sidebar

2. **Add Rule for `main`**
   - Click "Add rule" or "Add branch protection rule"
   - Enter branch name pattern: `main`
   - Configure protection as described above
   - Click "Create" or "Save changes"

3. **Add Rule for `develop`**
   - Click "Add rule" again
   - Enter branch name pattern: `develop`
   - Configure protection as described above
   - Click "Create" or "Save changes"

### Via GitHub CLI

```bash
# Install GitHub CLI if not installed
# https://cli.github.com

# Authenticate
gh auth login

# Enable branch protection for main
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  -H "Accept: application/vnd.github.v3+json" \
  -f required_status_checks='{"strict":true,"contexts":["test (3.13, ubuntu-latest)","lint","security"]}' \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1}' \
  -f restrictions=null \
  -f required_linear_history=true \
  -f allow_force_pushes=false \
  -f allow_deletions=false

# Enable branch protection for develop
gh api repos/{owner}/{repo}/branches/develop/protection \
  --method PUT \
  -H "Accept: application/vnd.github.v3+json" \
  -f required_status_checks='{"strict":true,"contexts":["test (3.13, ubuntu-latest)","lint"]}' \
  -f enforce_admins=false \
  -f required_pull_request_reviews='{"dismiss_stale_reviews":false,"require_code_owner_reviews":false,"required_approving_review_count":1}' \
  -f restrictions=null \
  -f allow_force_pushes=false \
  -f allow_deletions=false
```

Replace `{owner}` and `{repo}` with your GitHub username and repository name.

## Status Check Names

The CI/CD pipeline creates these status checks:

### Always Run
- `notify-start` - Workflow initialization
- `label-pr` - Auto-labeling (for PRs only)
- `test (3.10, ubuntu-latest)` - Python 3.10 tests
- `test (3.11, ubuntu-latest)` - Python 3.11 tests
- `test (3.12, ubuntu-latest)` - Python 3.12 tests
- `test (3.13, ubuntu-latest)` - Python 3.13 tests (primary)
- `test (3.13, windows-latest)` - Windows compatibility
- `lint` - Code quality checks
- `security` - Security scanning
- `notify-completion` - Workflow summary

### Conditional Runs
- `docker` - Only after tests pass, not on docs-only changes
- `create-release` - Only on version tags (v*)
- `update-dns` - Only on push to main/develop
- `analyze` - Project health check (separate workflow)

## Verifying Protection Rules

After setting up, verify the rules are working:

1. **Create a test branch**
   ```bash
   git checkout -b test-protection
   git push origin test-protection
   ```

2. **Open a PR to main**
   - Create a PR from test-protection to main
   - Check that status checks appear
   - Verify you cannot merge until checks pass

3. **Test failing checks**
   - Add code that fails linting
   - Push and verify PR is blocked
   - Fix the code and verify PR becomes mergeable

## Bypassing Protection (Emergencies Only)

If you need to bypass protection for a critical hotfix:

1. **Temporarily disable protection**
   - Settings → Branches → Edit rule
   - Uncheck "Include administrators"
   - Make emergency changes
   - Re-enable protection immediately

2. **Alternative: Use admin privileges**
   - Some rules allow admin override
   - Use "Merge without waiting for requirements"
   - Document reason in PR description

⚠️ **Warning**: Only bypass protection for critical production issues. Always re-enable protection after emergency changes.

## Workflow Integration

The CI/CD workflows are designed to work with branch protection:

### Merge Strategies
- **Squash and merge**: Recommended for main (clean history)
- **Rebase and merge**: Alternative for main (preserves commits)
- **Merge commit**: Allowed for develop (full history)

### Auto-Merge
Enable auto-merge for PRs that pass all checks:
```bash
# For a specific PR
gh pr merge --auto --squash <pr-number>

# Enable in PR settings
- Check "Enable auto-merge"
- Select merge method
- PR merges automatically when checks pass
```

## Common Issues

### "Required status check not available"
**Cause**: Status check name doesn't match workflow job name  
**Fix**: 
1. Check exact job name in workflow file
2. Run workflow once to register the check
3. Update branch protection rule with correct name

### "This branch has not been deployed"
**Cause**: Deployment check is enabled but not configured  
**Fix**: 
1. Disable deployment protection if not using deployments
2. Or configure deployment workflows

### "Review required" but can't request review
**Cause**: No reviewers configured or wrong permissions  
**Fix**:
1. Add CODEOWNERS file or
2. Manually request reviewers on PR or
3. Adjust protection settings

### Checks not running on PR
**Cause**: Workflow trigger doesn't match PR  
**Fix**:
1. Check workflow `on: pull_request` section
2. Verify paths-ignore isn't excluding your changes
3. Check workflow is enabled in Actions tab

## Best Practices

1. **Start Strict**: Enable all protections initially
2. **Adjust Based on Team**: Relax rules that slow down legitimate work
3. **Monitor Bypasses**: Track when/why protection is bypassed
4. **Document Exceptions**: Keep notes on why certain rules are disabled
5. **Review Regularly**: Audit protection settings quarterly

## Testing Branch Protection

Before applying to main/develop, test on a feature branch:

```bash
# Create test branch
git checkout -b test-bp-rules
git push origin test-bp-rules

# Apply same rules as main
# Settings → Branches → Add rule for "test-bp-rules"

# Test with a PR
git checkout -b feature-test
# Make changes
git push origin feature-test
# Open PR to test-bp-rules
# Verify all checks run and block as expected
```

## Reference Links

- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Required Status Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)
- [GitHub CLI](https://cli.github.com/manual/gh_api)
- [CODEOWNERS File](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
