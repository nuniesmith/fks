# GitHub Actions Workflows

This directory contains automated workflows for the FKS Trading Platform CI/CD pipeline.

## Workflows

### 1. CI/CD Pipeline (`ci-cd.yml`)
**Triggers**: Push to main/develop, Pull Requests, Tags, Manual dispatch

Comprehensive build, test, and deployment pipeline with the following stages:

#### Stages
- **Notify Start**: Discord notification when workflow begins
- **Label PR**: Auto-label pull requests based on changed files
- **Test**: Run test suite across multiple Python versions (3.10-3.13) and OS (Ubuntu, Windows)
  - PostgreSQL + TimescaleDB service
  - Redis service
  - Pytest with coverage reporting
  - Coverage comments on PRs
  - Codecov integration
- **Lint**: Code quality checks (strict for critical errors)
  - Ruff linting (fails on critical E/F rules)
  - Black formatting (informational)
  - isort import sorting (informational)
  - mypy type checking (informational)
- **Security**: Security vulnerability scanning
  - pip-audit for dependency vulnerabilities
  - Bandit for code security issues
  - Safety check (legacy)
- **Docker**: Build and push Docker images
  - Multi-platform support
  - Tag management (branch, semver, sha, latest)
  - Docker Hub integration
- **Release**: Create GitHub releases on version tags
  - Auto-generate release notes
  - Include Docker image tags
- **DNS Update**: Update Cloudflare DNS for deployments
  - Production and staging environments
  - Automatic domain configuration
- **Notify Completion**: Final status summary

#### Key Features
- ✅ Test failures block PR merge
- ✅ Coverage reports posted to PRs
- ✅ Critical lint errors block merge
- ✅ Security scans with detailed reports
- ✅ Docker image caching for faster builds
- ✅ Discord notifications for all stages
- ✅ Comprehensive job summaries

### 2. Weekly Health Check (`weekly-health-check.yml`)
**Triggers**: Schedule (Mondays 9 AM UTC), Manual dispatch

Automated weekly analysis with auto-commit functionality.

#### Features
- Runs full test suite with coverage
- Security audit (pip-audit)
- Lint checking (ruff)
- Type checking (mypy)
- Project metrics analysis
- Auto-updates PROJECT_STATUS.md
- Auto-commits changes (with [skip ci])
- Creates/updates GitHub issue for critical findings
- Generates comprehensive weekly report
- 30-day artifact retention

#### Artifacts Generated
- `coverage.json` - Test coverage data
- `htmlcov/` - HTML coverage report
- `security-audit.json` - Security vulnerabilities
- `lint-report.json` - Linting issues
- `mypy-report/` - Type checking results
- `metrics.json` - Project metrics
- `weekly-report.md` - Summary report

#### Critical Issue Detection
Automatically creates/updates GitHub issue when:
- Security vulnerabilities found
- Test pass rate < 80%
- Legacy imports detected

### 3. Project Health Check (`project-health-check.yml`)
**Triggers**: Push, Pull Request, Schedule (Mondays 9 AM), Manual dispatch

Quick health check for PRs and regular monitoring.

#### Features
- Fast test execution (no slow tests)
- Security audit
- Lint check
- Type check
- Project metrics
- PR comments with health summary
- Updates PROJECT_STATUS.md

## Configuration

### Required Secrets
- `GITHUB_TOKEN` - Automatically provided by GitHub
- `DISCORD_WEBHOOK` - Discord webhook URL for notifications
- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_API_TOKEN` - Docker Hub API token
- `DOCKER_REPOSITORY` - Docker Hub repository name
- `CLOUDFLARE_API_TOKEN` - Cloudflare API token
- `CLOUDFLARE_ZONE_ID` - Cloudflare zone ID
- `PRODUCTION_IP` - Production server IP
- `STAGING_IP` - Staging server IP

### Required Permissions
Workflows need the following permissions:
- `contents: write` - For auto-commit and releases
- `pull-requests: write` - For PR comments and labels
- `issues: write` - For creating health check issues

## Usage

### Running Tests Locally
```bash
# Full test suite
make test

# With coverage
pytest tests/ -v --cov=src --cov-report=html

# Unit tests only
pytest tests/ -m "unit"

# Skip slow tests
pytest tests/ -m "not slow"
```

### Running Linters Locally
```bash
# All linters
make lint

# Individual tools
ruff check src/
black --check src/
isort --check-only src/
mypy src/ --ignore-missing-imports
```

### Running Security Checks Locally
```bash
# Dependency audit
pip-audit --requirement requirements.txt

# Code security
bandit -r src/

# Combined
make security-check
```

### Running Health Analysis Locally
```bash
# Generate metrics
python scripts/analyze_project.py --summary

# Update status file
python .github/scripts/update_status.py
```

## Workflow Dispatch Parameters

### CI/CD Pipeline
- `python_version` - Python version to test (3.10-3.13, default: 3.13)
- `skip_tests` - Skip test execution (default: false)
- `environment` - Target environment (staging/production, default: staging)

### Weekly Health Check
- `commit_changes` - Auto-commit PROJECT_STATUS.md updates (default: true)

## Branch Protection Rules

Recommended branch protection for `main` and `develop`:
- ✅ Require status checks to pass:
  - `test` (Python 3.13, ubuntu-latest)
  - `lint`
  - `security`
- ✅ Require branches to be up to date
- ✅ Require review from code owners
- ⚠️ Do not require Docker build (runs after merge)

## Troubleshooting

### Tests Failing in CI but Pass Locally
- Check Python version matches (CI uses 3.13)
- Verify PostgreSQL and Redis are running in CI
- Check environment variables in workflow
- Review test logs in workflow artifacts

### Lint Blocking PRs
- Run `make lint` locally to see issues
- Only critical E/F rules block (syntax errors, undefined names)
- Formatting and style issues are informational only

### Security Scan Failures
- Review pip-audit report in artifacts
- Update vulnerable dependencies
- Add exceptions for false positives (see pip-audit docs)

### Weekly Auto-Commit Not Working
- Check workflow permissions (needs `contents: write`)
- Verify PROJECT_STATUS.md changed
- Look for [skip ci] in commit message
- Check workflow logs for git errors

## Monitoring

All workflows provide:
- Real-time Discord notifications
- Detailed job summaries in GitHub UI
- Downloadable artifacts for offline analysis
- PR comments for quick feedback

## Future Enhancements

Planned improvements:
- [ ] Parallel test execution for faster CI
- [ ] Deployment to staging/production
- [ ] Performance regression testing
- [ ] E2E testing with Playwright
- [ ] Dependency update automation (Dependabot)
- [ ] Code quality trends tracking
- [ ] Slack integration option

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Pytest Documentation](https://docs.pytest.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [pip-audit Documentation](https://pypi.org/project/pip-audit/)
