# FKS Project Management - Quick Start Checklist

Use this to get the dynamic project management system running in **< 30 minutes**.

## ✅ Step 1: Initial Setup (10 minutes)

### Install GitHub CLI
- [ ] Windows: `winget install GitHub.cli`
- [ ] Mac: `brew install gh`
- [ ] Linux: See https://github.com/cli/cli#installation

### Authenticate
```bash
gh auth login
```
- [ ] Select: GitHub.com
- [ ] Protocol: HTTPS
- [ ] Authenticate: via web browser

### Test authentication
```bash
gh auth status
```
- [ ] Should show: "Logged in to github.com as [username]"

## ✅ Step 2: Setup Project Board (10 minutes)

### Create labels and initial issues
```bash
cd c:\Users\jordan\nextcloud\code\repos\fks
python scripts/setup_github_project.py
```

**What this does**:
- [x] Creates 14 standard labels (🔴 critical, ✨ feature, etc.)
- [x] Creates 4 initial issues from PROJECT_STATUS.md
- [ ] Provides instructions for Project board (manual step below)

### Create GitHub Project Board (Manual)
1. [ ] Visit: https://github.com/nuniesmith/fks/projects/new
2. [ ] Click: "New project" → Select "Board" template
3. [ ] Name: "FKS Trading Platform"
4. [ ] Create these columns (drag to reorder):
   - [ ] 📥 Backlog
   - [ ] 🎯 To-Do (This Week)
   - [ ] 🚧 In Progress
   - [ ] 🔍 Review
   - [ ] ✅ Done

5. [ ] Add automation (Project settings):
   - [ ] New issues → Backlog
   - [ ] Issues assigned → To-Do
   - [ ] PR opened → Review
   - [ ] PR merged → Done

6. [ ] Add existing issues to project:
   - [ ] Go to https://github.com/nuniesmith/fks/issues
   - [ ] Select all issues
   - [ ] Add to project: "FKS Trading Platform"

## ✅ Step 3: Configure GitHub Actions (5 minutes)

### Commit workflow files
```bash
git add .github/workflows/project-health-check.yml
git add .github/scripts/update_status.py
git commit -m "Add project health check automation"
git push origin main
```

### Verify workflow runs
1. [ ] Go to: https://github.com/nuniesmith/fks/actions
2. [ ] Should see: "Project Health Check" workflow running
3. [ ] Wait for completion (~2-3 minutes)
4. [ ] Check: PROJECT_STATUS.md updated with latest metrics

### Enable weekly schedule
- [ ] Workflow runs automatically every Monday 9 AM UTC
- [ ] Or trigger manually: Actions tab → "Project Health Check" → "Run workflow"

## ✅ Step 4: First Weekly Review (5 minutes)

### Create reviews directory
```bash
mkdir -p docs/reviews
```

### Copy template
```bash
$date = Get-Date -Format "yyyy-MM-dd"
Copy-Item .github/WEEKLY_REVIEW_TEMPLATE.md docs/reviews/$date.md
```

### Run analyzer
```bash
python scripts/analyze_project.py --summary
```

### Fill in template
1. [ ] Open `docs/reviews/[today's date].md`
2. [ ] Paste analyzer output in "Health Dashboard Summary"
3. [ ] Set this week's sprint goal
4. [ ] Pick 3-5 priorities from PROJECT_STATUS.md
5. [ ] Save and commit

### Commit review
```bash
git add docs/reviews/
git commit -m "Weekly review for $(Get-Date -Format 'yyyy-MM-dd')"
git push
```

## ✅ Step 5: Start Working (Now!)

### Morning routine
1. [ ] Check PROJECT_STATUS.md for "Priority 1: Critical Blockers"
2. [ ] Open GitHub Project board
3. [ ] Pick 1-3 tasks from "To-Do"
4. [ ] Move selected tasks to "In Progress"

### As you work
1. [ ] Update issue with progress comments
2. [ ] Run tests frequently: `pytest tests/ -v`
3. [ ] Commit with issue reference: `Closes #1`

### End of day
1. [ ] Update issue status (comment progress)
2. [ ] Move completed cards to "Done"
3. [ ] Note any blockers in issue comments

## 🎯 Success Verification

### All systems operational when you can:
- [ ] See issues on GitHub with proper labels
- [ ] Access Project board with 5 columns
- [ ] View automated test runs in Actions tab
- [ ] Read updated PROJECT_STATUS.md with latest metrics
- [ ] Have first weekly review committed

## 🆘 Troubleshooting

### "GitHub CLI not found"
```powershell
# Verify installation
gh --version

# If not found, reinstall
winget install GitHub.cli

# Then restart PowerShell
```

### "Permission denied on scripts"
```powershell
# Windows PowerShell execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "Python script errors"
```powershell
# Verify Python version (need 3.11+)
python --version

# Install dependencies
pip install -r requirements.txt

# Try running analyzer
python scripts/analyze_project.py --summary
```

### "Actions workflow not running"
1. Check: https://github.com/nuniesmith/fks/settings/actions
2. Ensure: "Allow all actions and reusable workflows" is enabled
3. Trigger manually: Actions tab → Run workflow

## 📚 Next Steps

### Daily (5-10 min/day)
- Morning: Check PROJECT_STATUS.md + Project board
- During work: Update issues, run tests
- End of day: Move cards, note blockers

### Weekly (15-30 min)
- Friday EOD or Monday AM: Complete weekly review
- Run analyzer: `python scripts/analyze_project.py --summary`
- Reprioritize based on metrics
- Set next week's top 3-5 priorities

### Monthly (30-60 min)
- Review all weekly reviews
- Identify patterns (recurring blockers, velocity trends)
- Update PROJECT_STATUS.md with new goals
- Clean up backlog (archive low-priority items)

## 🎉 You're Done!

System is now operational. Key files:
- **PROJECT_STATUS.md** - Your daily dashboard
- **GitHub Project Board** - Visual task tracker
- **GitHub Actions** - Automated health checks
- **Weekly Reviews** - Track progress over time

**Questions?** See `.github/README.md` for full documentation.

---

**Setup completed**: [Date]  
**First review due**: [Date + 7 days]
