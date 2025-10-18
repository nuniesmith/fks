# GitHub Actions Dynamic Workflows - Setup Checklist

## ✅ Pre-Flight Checklist

Use this checklist to ensure your dynamic workflows are properly configured and ready to use.

---

## 1️⃣ Repository Secrets Configuration

Verify all required secrets are set in **Settings → Secrets and variables → Actions**:

### Required for Basic Functionality
- [ ] `GITHUB_TOKEN` - ✅ Automatically provided by GitHub
- [ ] `DISCORD_WEBHOOK` - Discord webhook URL for notifications

### Required for Docker
- [ ] `DOCKER_USERNAME` - Your Docker Hub username
- [ ] `DOCKER_API_TOKEN` - Docker Hub access token (not password)
- [ ] `DOCKER_REPOSITORY` - Your Docker repo (e.g., `username/fks-trading`)

### Required for DNS Updates
- [ ] `CLOUDFLARE_API_TOKEN` - Cloudflare API token with Zone:Edit permissions
- [ ] `CLOUDFLARE_ZONE_ID` - Your domain's zone ID from Cloudflare
- [ ] `PRODUCTION_IP` - Production server IP address
- [ ] `STAGING_IP` - Staging server IP address

### Optional (for enhanced debugging)
- [ ] `ACTIONS_RUNNER_DEBUG` - Set to `true` for verbose logging
- [ ] `ACTIONS_STEP_DEBUG` - Set to `true` for step-level debugging

---

## 2️⃣ Repository Settings

### Actions Permissions

Navigate to **Settings → Actions → General**:

- [ ] **Actions permissions**: Allow all actions and reusable workflows
- [ ] **Workflow permissions**: 
  - [x] Read and write permissions
  - [x] Allow GitHub Actions to create and approve pull requests
- [ ] **Fork pull request workflows**: Choose based on security needs

### Branch Protection (Optional but Recommended)

For `main` branch (**Settings → Branches → Branch protection rules**):

- [ ] Require pull request reviews before merging
- [ ] Require status checks to pass before merging
  - [ ] Add: `test`
  - [ ] Add: `lint`
  - [ ] Add: `security`
- [ ] Require branches to be up to date before merging
- [ ] Do not allow bypassing the above settings

---

## 3️⃣ File Verification

Ensure all new files are present in your repository:

### GitHub Actions
- [ ] `.github/labeler.yml` - PR labeling configuration
- [ ] `.github/workflows/ci-cd.yml` - Main CI/CD pipeline (enhanced)
- [ ] `.github/workflows/notify.yml` - Reusable notification workflow

### Documentation
- [ ] `docs/DYNAMIC_WORKFLOWS.md` - Comprehensive guide
- [ ] `docs/QUICKREF_DYNAMIC_WORKFLOWS.md` - Quick reference
- [ ] `docs/IMPLEMENTATION_SUMMARY.md` - Implementation details
- [ ] `docs/WORKFLOW_VISUAL_GUIDE.md` - Visual diagrams

---

## 4️⃣ Test the Labeling System

### Create a Test PR

```bash
# 1. Create a test branch
git checkout -b test/dynamic-workflows-labeling

# 2. Make docs-only change
echo "# Test Dynamic Workflows" >> docs/TEST_LABELING.md
git add docs/TEST_LABELING.md
git commit -m "Test: docs-only change for labeling"

# 3. Push and create PR
git push origin test/dynamic-workflows-labeling
gh pr create --title "Test: Dynamic workflow labeling" --body "Testing auto-labeling"
```

### Expected Results
- [ ] PR gets `documentation` label automatically
- [ ] `lint` job is skipped
- [ ] `test` job runs normally
- [ ] Discord notification shows new label

### Test Different Label Combinations

```bash
# Test security label
git checkout -b test/security-label
echo "flask==2.3.0" >> requirements.txt
git add requirements.txt
git commit -m "Test: security label trigger"
git push origin test/security-label
gh pr create --title "Test: Security labeling" --body "Should get security + dependencies labels"
```

Expected labels: `security`, `dependencies`

```bash
# Test framework label (critical)
git checkout -b test/framework-label
touch src/framework/test_file.py
git add src/framework/test_file.py
git commit -m "Test: framework label trigger"
git push origin test/framework-label
gh pr create --title "Test: Framework labeling" --body "Should get framework + breaking labels with warnings"
```

Expected: `framework`, `breaking`, ⚠️ warnings in PR

---

## 5️⃣ Test Matrix Strategy

### Verify Multi-Version Testing

1. [ ] Push a code change to trigger full test suite
2. [ ] Go to **Actions** tab → Latest run → `test` job
3. [ ] Verify 5 parallel jobs:
   - [ ] `Run Tests (Python 3.10 on ubuntu-latest)`
   - [ ] `Run Tests (Python 3.11 on ubuntu-latest)`
   - [ ] `Run Tests (Python 3.12 on ubuntu-latest)`
   - [ ] `Run Tests (Python 3.13 on ubuntu-latest)`
   - [ ] `Run Tests (Python 3.13 on windows-latest)`
4. [ ] Confirm Python 3.13 Ubuntu runs slow tests
5. [ ] Confirm coverage upload only from Python 3.13 Ubuntu

---

## 6️⃣ Test Conditional Execution

### Scenario A: Docs-only PR

- [ ] Create PR with only markdown changes
- [ ] Verify `documentation` label applied
- [ ] Verify `lint` job skipped
- [ ] Verify `docker` job skipped
- [ ] Pipeline completes in ~10 minutes (vs ~20 normally)

### Scenario B: WIP PR

- [ ] Create draft PR or PR with "WIP" in filename
- [ ] Verify `wip` label applied
- [ ] Verify `docker` job skipped
- [ ] Verify `update-dns` job skipped

### Scenario C: Security Change

- [ ] Create PR modifying `requirements.txt` or `.env`
- [ ] Verify `security` label applied
- [ ] Verify enhanced security scanning runs
- [ ] Check for bandit and safety reports

---

## 7️⃣ Test Release Automation

### Create Test Release

```bash
# WARNING: Do this on a test branch first!

# 1. Create a test tag
git checkout main
git pull origin main
git tag -a v0.0.1-test -m "Test release automation"

# 2. Push the tag
git push origin v0.0.1-test

# 3. Monitor Actions tab
# Should see:
# - Full test suite runs
# - Docker images built with version tags
# - GitHub release created
# - Changelog auto-generated
# - Discord notification sent
```

### Verify Release Outputs

- [ ] GitHub release created at: `https://github.com/YOUR_USERNAME/fks/releases/tag/v0.0.1-test`
- [ ] Release notes auto-generated with commits
- [ ] Docker images pushed:
  - [ ] `yourrepo:0.0.1-test`
  - [ ] `yourrepo:0.0`
  - [ ] `yourrepo:0`
  - [ ] `yourrepo:main-SHA`
- [ ] Discord notification received

### Clean Up Test Release

```bash
# Delete test tag locally and remotely
git tag -d v0.0.1-test
git push --delete origin v0.0.1-test

# Delete release from GitHub UI or via CLI
gh release delete v0.0.1-test --yes
```

---

## 8️⃣ Test Manual Workflow Trigger

### Via GitHub UI

1. [ ] Go to **Actions** tab
2. [ ] Select **FKS CI/CD Pipeline** workflow
3. [ ] Click **Run workflow** button
4. [ ] Select options:
   - Python version: `3.12`
   - Skip tests: `false`
   - Environment: `staging`
5. [ ] Click **Run workflow**
6. [ ] Verify workflow uses selected Python version
7. [ ] Verify tests run (not skipped)
8. [ ] Verify staging environment targeted

### Via GitHub CLI

```bash
# Trigger with default inputs
gh workflow run ci-cd.yml

# Trigger with custom inputs
gh workflow run ci-cd.yml \
  -f python_version=3.11 \
  -f skip_tests=false \
  -f environment=production
```

---

## 9️⃣ Monitor & Validate

### Check Workflow Runs

```bash
# List recent runs
gh run list --workflow=ci-cd.yml --limit 10

# View specific run
gh run view <RUN_ID>

# Watch live run
gh run watch
```

### Review Metrics

In **Actions** tab, check:

- [ ] Average duration < 20 minutes for full runs
- [ ] Success rate > 95%
- [ ] Path filters working (docs-only PRs faster)
- [ ] Matrix jobs running in parallel

### Verify Cost Optimization

**Settings → Billing → Actions usage**:

- [ ] Compare minutes used before/after implementation
- [ ] Target: 30-40% reduction in minutes consumed
- [ ] Monitor over 2-4 weeks for accurate comparison

---

## 🔟 Documentation Review

Ensure team members can access:

- [ ] **Full guide** (`docs/DYNAMIC_WORKFLOWS.md`) - Comprehensive reference
- [ ] **Quick ref** (`docs/QUICKREF_DYNAMIC_WORKFLOWS.md`) - Common tasks
- [ ] **Visual guide** (`docs/WORKFLOW_VISUAL_GUIDE.md`) - Diagrams
- [ ] **Summary** (`docs/IMPLEMENTATION_SUMMARY.md`) - Implementation details
- [ ] **This checklist** (`docs/SETUP_CHECKLIST.md`) - You are here!

---

## 🚨 Troubleshooting Common Issues

### Issue: Labels not applied to PR

**Symptoms:**
- PR created but no labels appear
- Labeler job succeeds but no changes

**Check:**
1. [ ] `.github/labeler.yml` syntax is valid (use YAML validator)
2. [ ] Workflow has `pull-requests: write` permission
3. [ ] PR is not from a fork (use `pull_request_target` for forks)
4. [ ] Glob patterns match actual file paths

**Test locally:**
```bash
# Check if files match patterns
git diff --name-only HEAD~1 HEAD | grep -E '^(src|tests|docs)/'
```

### Issue: Matrix job fails on specific Python version

**Symptoms:**
- One Python version fails, others pass
- Version-specific import errors

**Debug:**
```bash
# Test locally with specific version
python3.11 -m pytest tests/ -v

# Check installed packages
python3.11 -m pip list
```

**Solution:**
- Add version-specific dependencies to `requirements.txt`
- Update code for compatibility
- Temporarily exclude version from matrix if needed

### Issue: Docker build fails

**Symptoms:**
- Docker job fails with authentication error
- Tags not generated correctly

**Check:**
1. [ ] `DOCKER_USERNAME` and `DOCKER_API_TOKEN` are set
2. [ ] Docker Hub credentials are valid
3. [ ] Repository name in `DOCKER_REPOSITORY` is correct
4. [ ] Dockerfile syntax is valid

**Test locally:**
```bash
docker build -t test:latest -f docker/Dockerfile .
```

### Issue: DNS update fails

**Symptoms:**
- DNS job fails with API errors
- Cloudflare authentication issues

**Check:**
1. [ ] `CLOUDFLARE_API_TOKEN` has Zone:Edit permissions
2. [ ] `CLOUDFLARE_ZONE_ID` is correct
3. [ ] Domain exists in Cloudflare account
4. [ ] API token is not expired

**Test manually:**
```bash
curl -X GET "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json"
```

### Issue: Release creation fails

**Symptoms:**
- Tag pushed but no release created
- Release job skipped

**Check:**
1. [ ] Tag starts with `v` (e.g., `v1.0.0` not `1.0.0`)
2. [ ] Workflow has `contents: write` permission
3. [ ] `GITHUB_TOKEN` has necessary permissions
4. [ ] Tag is on the correct branch

**Verify:**
```bash
# Check tag format
git tag -l "v*"

# Check tag on branch
git tag --contains <TAG_NAME>
```

---

## ✨ Success Criteria

Your dynamic workflows are properly configured when:

- [x] All secrets are set and valid
- [x] Test PRs get auto-labeled correctly
- [x] Matrix tests run in parallel across versions
- [x] Conditional jobs skip when appropriate
- [x] Releases can be created with one `git push`
- [x] Discord notifications work for all events
- [x] Docker images build and push successfully
- [x] DNS updates work for staging/production
- [x] Cost reduction visible in billing (30-40% target)
- [x] Team understands how to use the system

---

## 📚 Next Steps After Setup

1. **Train team members** on label-based workflows
2. **Monitor metrics** for 2-4 weeks to validate savings
3. **Adjust labeler.yml** based on your specific file structure
4. **Add custom labels** for your project's needs
5. **Optimize matrix** if cost is still high
6. **Document team-specific processes** in your wiki

---

## 🆘 Need Help?

- **Full documentation**: `docs/DYNAMIC_WORKFLOWS.md`
- **Visual guide**: `docs/WORKFLOW_VISUAL_GUIDE.md`
- **GitHub Actions docs**: https://docs.github.com/actions
- **Labeler action**: https://github.com/actions/labeler

---

**Setup Checklist for FKS Trading Platform**  
**Version**: 1.0  
**Last Updated**: October 2025  
**Status**: Ready for Production ✅
