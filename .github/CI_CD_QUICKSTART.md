# CI/CD Pipeline Quick Start Guide

Get up and running with the FKS Trading Platform CI/CD pipeline in minutes.

## 🚀 Quick Setup (5 Minutes)

### Step 1: Configure Minimum Secrets (2 min)

Only one secret is **required** to start using CI/CD:

```bash
# Discord notifications (optional but recommended)
gh secret set DISCORD_WEBHOOK -b "YOUR_DISCORD_WEBHOOK_URL"
```

Everything else is optional for initial testing!

### Step 2: Enable Actions (1 min)

1. Go to your repository → **Actions** tab
2. Click "I understand my workflows, go ahead and enable them"
3. Workflows are now active!

### Step 3: Test with a PR (2 min)

```bash
# Create a test branch
git checkout -b test-ci
echo "# Test" >> README.md
git add README.md
git commit -m "test: CI/CD pipeline"
git push origin test-ci

# Open PR on GitHub
gh pr create --title "Test CI/CD" --body "Testing the CI/CD pipeline"
```

Watch the Actions tab - you'll see:
- ✅ Tests running
- ✅ Linting checks
- ✅ Security scans
- ✅ PR comments with results

## 📊 What Runs Automatically

### On Every PR
- **Tests**: Full test suite across Python 3.10-3.13
- **Lint**: Code quality checks (ruff, black, isort, mypy)
- **Security**: Dependency vulnerabilities (pip-audit, bandit)
- **Coverage**: Test coverage report posted as comment
- **Labels**: Auto-label based on changed files

### On Push to Main/Develop
- All of the above, plus:
- **Docker**: Build and push images to Docker Hub (if configured)
- **Deploy**: Update Cloudflare DNS (if configured)
- **Release**: Create GitHub release (on version tags)

### Weekly (Mondays 9 AM UTC)
- **Health Check**: Full project analysis
- **Metrics**: Update PROJECT_STATUS.md
- **Issues**: Auto-create issues for critical problems
- **Reports**: Generate comprehensive health report

## 🎯 Using the Pipeline

### Running Tests Locally First

Always run tests locally before pushing:

```bash
# Quick test
make test

# With coverage
pytest tests/ -v --cov=src --cov-report=html

# Check lint
make lint

# Check security
pip-audit --requirement requirements.txt
```

### Understanding Check Results

#### ✅ Green Check = Passed
All tests passed, code meets quality standards

#### ❌ Red X = Failed  
Click to see details:
- Test failures → Fix broken tests
- Lint errors → Run `make lint` locally
- Security issues → Review artifacts

#### 🟡 Yellow Circle = In Progress
Checks are running, wait for completion

#### ⚪ Gray Circle = Skipped
Check was skipped (e.g., docs-only change)

### Workflow Status on PR

Your PR will show status like this:

```
All checks have passed
✅ test (3.13, ubuntu-latest)
✅ lint
✅ security
✅ docker (skipped)
```

**Merge button enables** when all required checks pass.

## 🔧 Common Tasks

### Fix Failing Tests

```bash
# See what failed in CI
gh run view --log-failed

# Run same tests locally
pytest tests/path/to/test_file.py::test_function -v

# Fix the code, then push
git add .
git commit -m "fix: failing test"
git push
```

### Fix Lint Issues

```bash
# Run all linters
make lint

# Auto-fix formatting
black src/
isort src/

# Check again
ruff check src/

# Commit fixes
git add .
git commit -m "style: fix linting issues"
git push
```

### Address Security Issues

```bash
# Check locally
pip-audit --requirement requirements.txt

# Update vulnerable package
pip install --upgrade <package-name>
pip freeze > requirements.txt

# Commit update
git add requirements.txt
git commit -m "security: update vulnerable dependency"
git push
```

### Trigger Manual Run

```bash
# Via GitHub CLI
gh workflow run ci-cd.yml

# Via GitHub UI
Actions → CI/CD Pipeline → Run workflow
```

## 📈 Viewing Results

### PR Comments
- **Coverage**: Test coverage percentage
- **Health**: Overall project health metrics
- Located at bottom of PR conversation

### Job Summaries
- Click on check name in PR
- View detailed summary with:
  - Coverage breakdown
  - Security findings
  - Lint issues
  - Test results

### Artifacts
- Click workflow run → Artifacts section
- Download:
  - Coverage reports (HTML)
  - Security audit results
  - Lint reports
  - Weekly health reports

## 🎨 Customizing Checks

### Skip Tests for a Commit

```bash
# Add [skip ci] to commit message
git commit -m "docs: update README [skip ci]"
```

### Run Only Specific Tests

Edit your commit to trigger specific workflows:
- Docs changes → Skips lint and test (automatic)
- Framework changes → Shows warning about impact

### Manual Workflow Dispatch

```bash
# CI/CD with custom Python version
gh workflow run ci-cd.yml -f python_version=3.12

# Weekly health check on demand
gh workflow run weekly-health-check.yml
```

## 📊 Monitoring

### Discord Notifications (if configured)

You'll receive:
- 🚀 Workflow started
- ✅ All checks passed
- ❌ Checks failed with details
- 🏷️ PR auto-labeled
- 🐳 Docker image built
- 🚀 Deployment completed

### GitHub Actions Dashboard

View all runs:
```bash
# List recent runs
gh run list --limit 10

# View specific run
gh run view <run-id>

# Watch current run
gh run watch
```

### Weekly Health Reports

Every Monday:
- Check Issues tab for health check issue
- Download artifacts for detailed reports
- Review PROJECT_STATUS.md for updates

## 🚨 Troubleshooting

### "Required status check not passing"
**Solution**: Wait for checks to complete, or click to see failures

### "Workflow not triggered"
**Check**:
1. Workflow is enabled (Actions tab)
2. Push is to correct branch
3. Changes aren't in ignored paths

### "Secret not found"
**Solution**:
1. Add minimum secrets: `gh secret set DISCORD_WEBHOOK`
2. Or remove secret references from workflow

### Tests pass locally but fail in CI
**Common causes**:
- Python version difference (CI uses 3.13)
- Missing dependencies
- Database not seeded
- Environment variable not set

**Debug**:
```bash
# Check CI logs
gh run view --log-failed

# Run with same Python version
pyenv install 3.13
pyenv local 3.13
pytest tests/
```

## 🎯 Next Steps

### Minimum Setup (Start Here)
1. ✅ Enable Actions
2. ✅ Create test PR
3. ✅ Watch checks run
4. ⚠️ Add Discord webhook (optional)

### Full Setup (Production Ready)
1. ✅ Configure all secrets (see SECRETS_SETUP.md)
2. ✅ Enable branch protection (see BRANCH_PROTECTION.md)
3. ✅ Configure Docker Hub
4. ✅ Set up Cloudflare DNS
5. ✅ Enable auto-merge

### Advanced
1. Customize workflow triggers
2. Add deployment environments
3. Set up Codecov
4. Configure Dependabot
5. Add custom checks

## 📚 Additional Resources

- [Workflows Documentation](.github/workflows/README.md)
- [Secrets Setup Guide](SECRETS_SETUP.md)
- [Branch Protection Guide](BRANCH_PROTECTION.md)
- [GitHub Actions Docs](https://docs.github.com/en/actions)

## 💡 Pro Tips

1. **Use [skip ci] wisely**: Only for docs/non-code changes
2. **Check locally first**: Faster than waiting for CI
3. **Enable auto-merge**: Let CI merge when ready
4. **Monitor weekly reports**: Catch issues early
5. **Keep branch updated**: Rebase before merge

## ❓ Need Help?

1. Check workflow logs: `gh run view --log-failed`
2. Review error messages in PR checks
3. Search GitHub Actions documentation
4. Create issue with "ci/cd" label

---

**Remember**: The CI/CD pipeline is here to help, not block. If checks fail, they're catching issues that would cause problems in production. Take time to understand and fix them.

Happy coding! 🚀
