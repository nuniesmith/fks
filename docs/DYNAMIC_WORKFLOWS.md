# Dynamic GitHub Actions Workflows - Implementation Guide

## Overview
This document explains the dynamic workflow features implemented in the FKS Trading Platform CI/CD pipeline, including automatic PR labeling, matrix strategies, conditional execution, and release automation.

## 📋 Table of Contents
1. [Automatic PR Labeling](#automatic-pr-labeling)
2. [Matrix Strategy Testing](#matrix-strategy-testing)
3. [Conditional Job Execution](#conditional-job-execution)
4. [Dynamic Release Creation](#dynamic-release-creation)
5. [Path Filters](#path-filters)
6. [Workflow Dispatch Inputs](#workflow-dispatch-inputs)
7. [Best Practices](#best-practices)

---

## 🏷️ Automatic PR Labeling

### Configuration: `.github/labeler.yml`

The labeler automatically applies labels to PRs based on changed files using glob patterns.

### Implemented Labels

| Label | Triggers On | Pipeline Impact |
|-------|-------------|-----------------|
| `documentation` | `docs/**`, `*.md` | Skips lint job to save resources |
| `code` | `src/**/*.py` (excluding tests) | Enforces full test suite |
| `framework` | `src/framework/**` | **Critical**: Adds warnings about 26 external imports |
| `security` | `requirements.txt`, `.env`, `docker-compose.yml`, etc. | Triggers enhanced security scanning |
| `tests` | `tests/**` | Ensures test coverage reports |
| `database` | `src/core/database/**`, migrations | Careful review required |
| `trading` | `src/trading/**` | Validates trading logic tests |
| `rag` | `src/rag/**`, GPU configs | GPU-specific tests |
| `web` | `src/web/**`, templates, static files | UI/UX review |
| `docker` | `docker/**`, Dockerfiles | Triggers Docker build |
| `celery` | Task files, Celery configs | Task validation |
| `wip` | Draft PRs, files with "WIP" | Skips Docker build and deployment |
| `breaking` | Core models, settings, framework | Requires major review |

### Usage in Workflows

```yaml
label-pr:
  outputs:
    all-labels: ${{ steps.labeler.outputs.all-labels }}
    new-labels: ${{ steps.labeler.outputs.new-labels }}

# Use in other jobs
docker:
  needs: [label-pr]
  if: |
    !contains(needs.label-pr.outputs.all-labels, 'wip') &&
    (github.event_name != 'pull_request' || contains(needs.label-pr.outputs.all-labels, 'docker'))
```

### Special Warnings

#### Framework Changes
When `framework` label is applied:
```
⚠️ Framework layer modified! This requires Phase 9D analysis due to 26 external imports.
```
A GitHub step summary is added with critical review requirements.

#### Breaking Changes
When `breaking` label is applied:
```
⚠️ Breaking changes detected! Major review required.
```

---

## 🧪 Matrix Strategy Testing

### Multi-Version Python Testing

The `test` job now runs across multiple Python versions and operating systems:

```yaml
strategy:
  fail-fast: false  # Continue testing other versions if one fails
  matrix:
    python-version: ['3.11', '3.12', '3.13']
    os: [ubuntu-latest]
    include:
      # Add Windows testing for main Python version
      - python-version: '3.13'
        os: windows-latest
      # Test older Python on Ubuntu only
      - python-version: '3.10'
        os: ubuntu-latest
```

### Test Matrix Breakdown

| Python Version | Operating System | Test Suite |
|----------------|------------------|------------|
| 3.10 | Ubuntu | Unit + Integration (not slow) |
| 3.11 | Ubuntu | Unit + Integration (not slow) |
| 3.12 | Ubuntu | Unit + Integration (not slow) |
| 3.13 | Ubuntu | **Full suite** (unit + integration + slow) |
| 3.13 | Windows | Unit + Integration (not slow) |

### Benefits
- ✅ Catches version-specific bugs early
- ✅ Ensures compatibility with Python 3.10-3.13
- ✅ Windows compatibility testing for main version
- ✅ Parallel execution saves time
- ✅ `fail-fast: false` ensures all versions are tested

### Selective Coverage
Only Python 3.13 on Ubuntu runs:
- Slow tests (`-m "slow"`)
- Coverage uploads to Codecov

---

## ⚙️ Conditional Job Execution

### Path-Based Triggers

The workflow only runs on relevant file changes:

```yaml
on:
  push:
    paths:
      - 'src/**'
      - 'tests/**'
      - 'docker/**'
      - 'requirements*.txt'
      - '.github/workflows/**'
      - '!docs/**'  # Ignore docs-only changes
  pull_request:
    paths-ignore:
      - 'docs/**'
      - '*.md'
      - 'scripts/docs/**'
```

### Label-Based Conditionals

#### Lint Job
Skips on documentation-only PRs:
```yaml
lint:
  if: |
    always() && 
    needs.notify-start.result == 'success' &&
    (github.event_name != 'pull_request' || !contains(needs.label-pr.outputs.all-labels, 'documentation'))
```

#### Security Job
Always runs on security-related changes:
```yaml
security:
  if: |
    always() && 
    needs.notify-start.result == 'success' &&
    (contains(needs.label-pr.outputs.all-labels, 'security') || 
     github.event_name == 'push' || 
     github.event_name == 'workflow_dispatch')
```

#### Docker Job
Skips on WIP PRs and docs-only changes:
```yaml
docker:
  if: |
    always() &&
    needs.test.result == 'success' &&
    needs.lint.result == 'success' &&
    !contains(needs.label-pr.outputs.all-labels, 'wip') &&
    (github.event_name != 'pull_request' || contains(needs.label-pr.outputs.all-labels, 'docker'))
```

### Branch-Specific Logic

DNS updates only on main/develop:
```yaml
update-dns:
  if: (github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop') && github.event_name == 'push'
```

---

## 🎉 Dynamic Release Creation

### Version Tag Triggers

Releases are automatically created when pushing tags:

```yaml
on:
  push:
    tags: ['v*']  # Triggers on v1.0.0, v2.1.0-rc1, etc.
```

### Release Job

```yaml
create-release:
  if: startsWith(github.ref, 'refs/tags/v')
  steps:
    - name: Extract version from tag
      id: version
      run: |
        VERSION=${GITHUB_REF#refs/tags/v}
        echo "version=$VERSION" >> $GITHUB_OUTPUT
    
    - name: Generate release notes
      run: |
        # Get previous tag
        PREV_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo "")
        
        # Generate changelog from commits
        git log $PREV_TAG..HEAD --pretty=format:"- %s (%h)" --no-merges
    
    - name: Create GitHub Release
      uses: softprops/action-gh-release@v1
      with:
        prerelease: ${{ contains(steps.version.outputs.version, 'rc') || contains(steps.version.outputs.version, 'beta') }}
```

### Docker Image Tagging

Release tags automatically create properly versioned Docker images:

```yaml
tags: |
  type=ref,event=branch
  type=ref,event=pr
  type=semver,pattern={{version}}        # v1.2.3 → 1.2.3
  type=semver,pattern={{major}}.{{minor}} # v1.2.3 → 1.2
  type=semver,pattern={{major}}          # v1.2.3 → 1
  type=sha,prefix={{branch}}-
  type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}
```

### Creating a Release

```bash
# Tag the commit
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# Pipeline automatically:
# 1. Runs all tests
# 2. Builds Docker images with version tags
# 3. Creates GitHub release with changelog
# 4. Sends Discord notification
```

### Pre-release Detection

Versions containing `rc` or `beta` are marked as pre-releases:
- `v1.0.0-rc1` → Pre-release ✅
- `v2.0.0-beta.1` → Pre-release ✅
- `v1.0.0` → Full release ✅

---

## 🛤️ Path Filters

### When to Use

Path filters optimize CI/CD by:
1. **Reducing costs** - Skip irrelevant jobs
2. **Faster feedback** - Only run necessary tests
3. **Resource efficiency** - Don't waste GitHub Actions minutes

### Current Implementation

```yaml
on:
  push:
    paths:
      - 'src/**'           # Application code
      - 'tests/**'         # Test files
      - 'docker/**'        # Docker configs
      - 'requirements*.txt' # Dependencies
      - '.github/workflows/**' # Workflow changes
      - '!docs/**'         # Ignore documentation
```

### Path Ignore Pattern

```yaml
pull_request:
  paths-ignore:
    - 'docs/**'
    - '*.md'
    - 'scripts/docs/**'
```

**Effect**: PRs that only change documentation won't trigger the full pipeline.

---

## 🎛️ Workflow Dispatch Inputs

### Manual Workflow Triggers

```yaml
workflow_dispatch:
  inputs:
    python_version:
      description: 'Python version to test'
      required: false
      default: '3.13'
      type: choice
      options: ['3.10', '3.11', '3.12', '3.13']
    
    skip_tests:
      description: 'Skip test execution'
      required: false
      type: boolean
      default: false
    
    environment:
      description: 'Target environment'
      required: false
      type: choice
      default: 'staging'
      options: ['staging', 'production']
```

### Using Inputs

```yaml
env:
  PYTHON_VERSION: ${{ inputs.python_version || '3.13' }}

test:
  if: ${{ !inputs.skip_tests }}
```

### Manual Trigger via GitHub UI

1. Go to **Actions** tab
2. Select **FKS CI/CD Pipeline** workflow
3. Click **Run workflow**
4. Select options:
   - Python version for testing
   - Skip tests (for urgent deployments)
   - Target environment

---

## 📊 Best Practices

### 1. Labeling Strategy

**DO:**
- ✅ Use descriptive, hierarchical labels
- ✅ Combine labels for complex changes (e.g., `code` + `security`)
- ✅ Review auto-applied labels in PR description

**DON'T:**
- ❌ Manually add labels that conflict with auto-labeling
- ❌ Ignore framework/breaking change warnings
- ❌ Push to main without proper labels

### 2. Matrix Testing

**DO:**
- ✅ Test main Python version (3.13) across all platforms
- ✅ Use `fail-fast: false` to see all failures
- ✅ Run expensive tests only on one matrix combination

**DON'T:**
- ❌ Test every version on every OS (cost explosion)
- ❌ Use `fail-fast: true` in development
- ❌ Duplicate test logic across matrix combinations

### 3. Conditional Execution

**DO:**
- ✅ Check `needs.*.result` before running dependent jobs
- ✅ Use `always()` for notification jobs
- ✅ Combine multiple conditions with proper precedence

**DON'T:**
- ❌ Skip security checks based on labels alone
- ❌ Over-optimize - some jobs should always run
- ❌ Create circular dependencies between jobs

### 4. Release Management

**DO:**
- ✅ Follow semantic versioning (`v1.2.3`)
- ✅ Use annotated tags (`git tag -a`)
- ✅ Generate meaningful release notes

**DON'T:**
- ❌ Push tags without testing
- ❌ Create releases from feature branches
- ❌ Use arbitrary version numbers

### 5. Path Filters

**DO:**
- ✅ Use negative patterns (`!docs/**`) to exclude
- ✅ Combine with label conditionals for flexibility
- ✅ Test path filters locally before pushing

**DON'T:**
- ❌ Over-filter - security checks should always run
- ❌ Ignore `.github/workflows/**` changes
- ❌ Assume filters apply to manual triggers

---

## 🔍 Debugging Workflows

### Common Issues

#### 1. Job Skipped Unexpectedly
**Symptom**: Job shows "Skipped" in Actions tab

**Check:**
```yaml
# Review the if condition
if: |
  always() && 
  needs.notify-start.result == 'success'
```

**Solution**: Add `always()` or adjust conditions

#### 2. Labels Not Applied
**Symptom**: PR doesn't get auto-labeled

**Check:**
- Verify `.github/labeler.yml` syntax
- Ensure `label-pr` job has `pull-requests: write` permission
- Check glob patterns match actual file paths

**Test locally:**
```bash
# Install act CLI
# Run workflow locally
act pull_request
```

#### 3. Matrix Job Failures
**Symptom**: One matrix combination fails silently

**Solution:**
- Use `fail-fast: false` to see all failures
- Check job names include matrix variables: `Run Tests (Python ${{ matrix.python-version }})`

#### 4. Path Filters Not Working
**Symptom**: Workflow triggers on ignored files

**Check:**
- Path filters don't apply to `workflow_dispatch`
- Use `paths-ignore` for simple exclusions
- Combine with label conditions for complex logic

### Enable Debug Logging

Add secrets to repository:
- `ACTIONS_RUNNER_DEBUG`: `true`
- `ACTIONS_STEP_DEBUG`: `true`

---

## 📈 Metrics & Monitoring

### Pipeline Efficiency

Track these metrics in Actions tab:

| Metric | Target | Current |
|--------|--------|---------|
| Average pipeline duration | < 15 min | Monitor |
| Success rate | > 95% | Monitor |
| Cost per workflow run | < $0.10 | Monitor |
| False positive rate | < 5% | Monitor |

### Label Usage Analytics

Monitor which labels are most common:
```bash
gh pr list --state all --json labels --jq '.[] | .labels[].name' | sort | uniq -c | sort -rn
```

### Test Coverage Trends

Track coverage over time via Codecov:
- Overall project coverage
- Per-file coverage
- Coverage by Python version

---

## 🚀 Future Enhancements

### Planned Features

1. **Dynamic Test Selection**
   - Analyze changed files
   - Run only affected tests
   - Reduce test execution time by 50%

2. **Environment-Specific Matrices**
   - Staging: Python 3.13 only
   - Production: Full matrix
   - Cost optimization

3. **Custom Label Actions**
   - `performance`: Run benchmark suite
   - `migration`: Extra database checks
   - `hotfix`: Expedited approval process

4. **Advanced Release Automation**
   - Auto-update CHANGELOG.md
   - Generate upgrade guides
   - Notify stakeholders via multiple channels

5. **Reusable Workflows**
   - Extract common patterns
   - Share across multiple repos
   - Organization-wide standards

---

## 📚 References

- [GitHub Actions Documentation](https://docs.github.com/actions)
- [actions/labeler](https://github.com/actions/labeler)
- [Workflow Syntax](https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions)
- [Matrix Strategies](https://docs.github.com/actions/using-jobs/using-a-matrix-for-your-jobs)
- [Conditional Execution](https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idif)

---

## 🆘 Support

For questions or issues:
1. Check workflow run logs in Actions tab
2. Review this documentation
3. Test changes in a fork first
4. Ask in team Discord #ci-cd channel

---

**Last Updated**: October 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready
