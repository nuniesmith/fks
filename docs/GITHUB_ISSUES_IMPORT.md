# GitHub Issues Import Guide

This guide walks you through importing all 19 FKS development tasks as GitHub issues.

## Prerequisites

### 1. Install GitHub CLI

If you don't have GitHub CLI installed:

**Ubuntu/Debian (WSL):**
```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

**Or via snap:**
```bash
sudo snap install gh
```

### 2. Authenticate with GitHub

```bash
gh auth login
```

Follow the prompts:
- Choose: **GitHub.com**
- Protocol: **HTTPS** (recommended) or **SSH**
- Authenticate: **Login with a web browser** (easiest)
- Copy the one-time code and paste it in your browser

Verify authentication:
```bash
gh auth status
```

## Import Process

### Step 1: Review the Script

The import script is located at: `scripts/import_github_issues.sh`

It will create:
- **7 milestones** (one for each phase)
- **19 issues** (with detailed hour-by-hour breakdowns)
- **Labels** for impact, urgency, effort, and phase

### Step 2: Dry Run (Optional)

To see what will be created without actually creating issues, review the script:

```bash
cat scripts/import_github_issues.sh | less
```

### Step 3: Run the Import

Execute the script:

```bash
./scripts/import_github_issues.sh
```

The script will:
1. Check if `gh` CLI is installed and authenticated
2. Create 7 phase milestones
3. Create 19 issues with full details
4. Apply appropriate labels and milestones

**Expected output:**
```
=== FKS GitHub Issues Import ===
This will create 19 issues across 7 phases

✓ GitHub CLI ready

Creating milestones...
✓ Milestones created

=== Phase 1: Immediate Fixes ===
Creating: Security Hardening
Creating: Fix Import/Test Failures
Creating: Code Cleanup
✓ Phase 1 issues created

[... continues for all phases ...]

================================
✅ GitHub Issues Import Complete!
================================

Summary:
  • Phase 1: 3 issues (Immediate Fixes)
  • Phase 2: 4 issues (Core Development)
  • Phase 3: 2 issues (Testing & QA)
  • Phase 4: 2 issues (Documentation)
  • Phase 5: 2 issues (Deployment & Monitoring)
  • Phase 6: 3 issues (Optimization & Maintenance)
  • Phase 7: 3 issues (Future Features)

Total: 19 issues created
```

### Step 4: Verify Issues Created

View all created issues:

```bash
gh issue list --limit 100
```

View issues by milestone:

```bash
gh issue list --milestone "Phase 1: Immediate Fixes"
gh issue list --milestone "Phase 2: Core Development"
# ... etc
```

View issues by label:

```bash
gh issue list --label "impact:high"
gh issue list --label "phase:1"
gh issue list --label "effort:high"
```

## Working with Issues

### Start Working on an Issue

```bash
# View issue details
gh issue view <issue-number>

# Assign to yourself
gh issue edit <issue-number> --add-assignee @me

# Create branch and start work
gh issue develop <issue-number> --checkout
```

### Track Progress

```bash
# List your assigned issues
gh issue list --assignee @me

# Filter by state
gh issue list --state open
gh issue list --state closed

# Close an issue
gh issue close <issue-number> --comment "Completed implementation and tests"
```

### Add to GitHub Project

If you have a GitHub Project board:

```bash
# List your projects
gh project list

# Add issue to project
gh issue edit <issue-number> --add-project "<project-name>"
```

## Issue Structure

Each issue includes:

### Metadata
- **Phase**: Which development phase (1-7)
- **Impact**: High/Medium/Low (business value)
- **Urgency**: High/Medium/Low (time sensitivity)
- **Effort**: High/Medium/Low (hours required)
- **Dependencies**: Related issues to complete first

### Hour-by-Hour Breakdown
Detailed steps for each hour of work, including:
- Specific tasks to accomplish
- Files to modify
- Commands to run
- Testing procedures
- Verification steps

### Verification Checklist
- [ ] Checkbox items to confirm completion
- Tests to run
- Metrics to achieve
- Documentation to update

### Notes
- Tips and best practices
- Common pitfalls to avoid
- References to relevant documentation

## Labels Explained

### Impact Labels
- `impact:high` - Critical features, security, or blocking issues
- `impact:medium` - Important but not blocking
- `impact:low` - Nice-to-have improvements

### Urgency Labels
- `urgency:high` - Needs immediate attention
- `urgency:medium` - Important but can wait
- `urgency:low` - Future work

### Effort Labels
- `effort:high` - 10+ hours of work
- `effort:medium` - 5-10 hours of work
- `effort:low` - <5 hours of work

### Phase Labels
- `phase:1` through `phase:7` - Development phases

## Troubleshooting

### "gh: command not found"
Install GitHub CLI (see Prerequisites above)

### "authentication required"
Run: `gh auth login`

### "milestone already exists" errors
This is normal if re-running the script. Existing milestones won't be duplicated.

### Issues not appearing
Check repository permissions. Run:
```bash
gh repo view
```

### Too many issues at once
You can modify the script to create issues in batches by commenting out phases.

## Next Steps

After importing:

1. **Review issues**: `gh issue list --limit 50`
2. **Assign priorities**: Add to project board or assign to yourself
3. **Start Phase 1**: Begin with Security Hardening (#1)
4. **Track progress**: Update issue status as you work
5. **Close completed**: Close issues with summary comments

## Additional Resources

- [GitHub CLI Manual](https://cli.github.com/manual/)
- [GitHub Issues Guide](https://docs.github.com/en/issues)
- [GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- FKS docs: `docs/PROJECT_MANAGEMENT_SUMMARY.md`

## Workflow Example

```bash
# 1. View Phase 1 issues
gh issue list --milestone "Phase 1: Immediate Fixes"

# 2. Pick first issue and view details
gh issue view 1

# 3. Assign to yourself and create branch
gh issue edit 1 --add-assignee @me
gh issue develop 1 --checkout

# 4. Work through hour-by-hour breakdown
# ... make changes ...

# 5. Commit and push
git add .
git commit -m "Complete security hardening (Issue #1)"
git push

# 6. Close issue with summary
gh issue close 1 --comment "✅ Completed:
- Updated all passwords
- Removed external port exposure  
- Configured rate limiting
- Passed pip-audit

All verification items complete."

# 7. Move to next issue
gh issue view 2
```

---

**Total Development Time**: ~120 hours across 14-22 weeks  
**Current Status**: Ready to import and begin Phase 1  
**Last Updated**: October 22, 2025
