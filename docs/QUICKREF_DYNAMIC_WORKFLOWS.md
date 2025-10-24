# Quick Reference: Dynamic GitHub Actions

## 🏷️ Label-Triggered Behaviors

| Label | Action Taken |
|-------|--------------|
| `documentation` | Skip lint job |
| `security` | Always run security scan |
| `framework` | Add critical review warning |
| `breaking` | Add breaking change warning |
| `wip` | Skip Docker build and deployment |
| `docker` | Force Docker build on PR |

## 🧪 Test Matrix

```yaml
# Runs 5 parallel test jobs:
- Python 3.10 on Ubuntu
- Python 3.11 on Ubuntu
- Python 3.12 on Ubuntu
- Python 3.13 on Ubuntu (+ slow tests + coverage)
- Python 3.13 on Windows
```

## 🚀 Creating a Release

```bash
# 1. Tag the commit
git tag -a v1.0.0 -m "Release version 1.0.0"

# 2. Push the tag
git push origin v1.0.0

# 3. Pipeline automatically:
#    ✅ Runs all tests
#    ✅ Builds versioned Docker images
#    ✅ Creates GitHub release with changelog
#    ✅ Notifies via Discord
```

## 🎛️ Manual Workflow Trigger

GitHub UI → Actions → FKS CI/CD Pipeline → Run workflow

**Options:**
- Python version: 3.10, 3.11, 3.12, or 3.13
- Skip tests: Yes/No
- Environment: staging or production

## 📁 Files Created

```
.github/
├── labeler.yml              # PR labeling rules
└── workflows/
    ├── ci-cd.yml            # Enhanced main pipeline
    └── notify.yml           # Reusable notification workflow
docs/
└── DYNAMIC_WORKFLOWS.md     # Full documentation
```

## 🔧 Key Improvements

### Before
- ❌ Static single-version testing
- ❌ All jobs run on every change
- ❌ Manual labeling required
- ❌ No release automation

### After
- ✅ Multi-version Python testing (3.10-3.13)
- ✅ Smart conditional execution
- ✅ Automatic PR labeling
- ✅ One-command releases
- ✅ Path-based triggers
- ✅ Matrix strategy for parallel tests
- ✅ Windows compatibility testing

## ⚠️ Important Notes

1. **Framework changes** trigger critical review warnings
2. **WIP PRs** skip Docker builds automatically
3. **Docs-only changes** skip lint job to save time
4. **Security changes** always run full security scan
5. **Version tags** (`v*`) trigger automatic releases
6. **Slow tests** only run on Python 3.13 Ubuntu

## 🔗 Related Commands

```bash
# View workflow runs
gh run list --workflow=ci-cd.yml

# Check PR labels
gh pr view <PR_NUMBER> --json labels

# Create pre-release
git tag -a v1.0.0-rc1 -m "Release candidate 1"
git push origin v1.0.0-rc1

# Test path filters locally (requires act CLI)
act pull_request --workflows .github/workflows/ci-cd.yml
```

## 📊 Cost Optimization

**Old approach:** ~20 min pipeline on every push  
**New approach:**
- Docs-only: ~2 min (skip lint/tests)
- WIP PRs: ~10 min (skip Docker)
- Full pipeline: ~18 min (matrix parallelization)

**Estimated savings:** 30-40% on GitHub Actions minutes

---

**Full Documentation:** See `docs/DYNAMIC_WORKFLOWS.md`
