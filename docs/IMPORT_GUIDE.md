# Importing Your Project Plan into GitHub Issues

## 🎯 Quick Start (3 Steps)

### 1. Preview Issues (Dry Run)
```powershell
python scripts/import_project_plan.py --dry-run
```

This shows you all issues that will be created **without actually creating them**.

**Output**:
```
🎯 Importing 20 issues to nuniesmith/fks
🔍 DRY RUN MODE - No issues will be created

1. [PHASE 1] Immediate Fixes - Security, Tests, Cleanup
   Labels: 🔴 critical, effort:high, phase:1-immediate
   Milestone: Phase 1: Foundation

2. [P1.1] Security Hardening - Production-Ready Secrets
   Labels: 🔴 critical, 🔒 security, effort:medium, phase:1-immediate

... (18 more)

Total: 20 issues ready to create
```

### 2. Create All Issues
```powershell
python scripts/import_project_plan.py
```

**What Happens**:
- Creates 20 GitHub issues from your 7-phase plan
- Assigns labels automatically (🔴 critical, ✨ feature, etc.)
- Creates milestones (Phase 1-7)
- Links dependencies in issue descriptions
- Formats with markdown, code blocks, checklists

**Progress Output**:
```
🎯 Importing 20 issues to nuniesmith/fks
🚀 CREATING ISSUES

  ✅ Created: [PHASE 1] Immediate Fixes - Security, Tests, Cleanup
  ✅ Created: [P1.1] Security Hardening - Production-Ready Secrets
  ✅ Created: [P1.2] Fix Import Errors - Unblock 20 Failing Tests
  ...
  ✅ Created: [PHASE 7] Future Features - Post-MVP Growth

✅ Summary:
   Created: 20
   Failed: 0

View issues: https://github.com/nuniesmith/fks/issues
```

### 3. Organize in Project Board
```powershell
# Visit your GitHub Project
https://github.com/nuniesmith/fks/projects/1
```

**Manual Steps**:
1. Go to your Project board
2. Click "Add items"
3. Select all newly created issues
4. Drag Phase 1 issues to "To-Do (This Week)"
5. Rest go to "Backlog"

---

## 📋 What Gets Created

### Issue Structure
Each issue includes:
- ✅ **Clear Title** with phase/task number
- 📝 **Detailed Description** with sub-tasks
- 🏷️ **Labels** for priority/effort/phase
- 📊 **Success Criteria** (checkboxes)
- ⏱️ **Effort Estimates** (hours)
- 🔗 **Dependencies** (what must come first)
- 📚 **References** (relevant files/docs)

### 7 Phases Created

#### Phase 1: Immediate Fixes (2-4 weeks)
- **[PHASE 1]** Overview issue
- **[P1.1]** Security Hardening
- **[P1.2]** Fix Import/Test Failures
- **[P1.3]** Code Cleanup

#### Phase 2: Core Development (4-8 weeks)
- **[PHASE 2]** Overview issue
- **[P2.1]** Implement 16 Celery Tasks
- **[P2.2]** Complete RAG System
- **[P2.3]** Web UI and API Polish
- **[P2.4]** Data Sync and Backtesting

#### Phase 3: Testing & QA (Ongoing)
- **[PHASE 3]** Overview issue
- **[P3.1]** Expand Test Suite
- **[P3.2]** CI/CD Pipeline

#### Phase 4: Documentation (2 weeks)
- **[PHASE 4]** Overview issue

#### Phase 5: Deployment (4-6 weeks)
- **[PHASE 5]** Overview issue

#### Phase 6: Optimization (Ongoing)
- **[PHASE 6]** Overview issue

#### Phase 7: Future Features (6+ weeks)
- **[PHASE 7]** Overview issue

---

## 🏷️ Labels Used

Issues are automatically labeled for easy filtering:

### Priority Labels
- 🔴 **critical** - Blocks work, security, deployment
- 🟡 **high** - Core features, high value
- 🟢 **medium** - Improvements, moderate value
- ⚪ **low** - Nice-to-have, future

### Effort Labels
- **effort:low** - <1 day
- **effort:medium** - 1-3 days
- **effort:high** - >3 days

### Phase Labels
- **phase:1-immediate** - Foundation fixes
- **phase:2-core** - Core features
- **phase:3-testing** - Quality assurance
- **phase:4-docs** - Documentation
- **phase:5-deploy** - Production
- **phase:6-optimize** - Performance
- **phase:7-future** - Growth

### Type Labels
- ✨ **feature** - New functionality
- 🐛 **bug** - Fix something broken
- 🔒 **security** - Security hardening
- 🧪 **tests** - Testing related
- 🧹 **tech-debt** - Cleanup/refactoring
- 📚 **documentation** - Docs updates
- ⚙️ **automation** - CI/CD, scripts
- 🚀 **deployment** - Deployment related
- ⚡ **performance** - Optimization

---

## 🎯 Recommended Workflow

### After Import
1. **Review Issues**: Click through to verify content
2. **Create Milestones**: GitHub → Issues → Milestones
   - Phase 1: Foundation (Due: Nov 14, 2025)
   - Phase 2: Core Features (Due: Dec 12, 2025)
   - Phase 3: Quality (Due: Jan 2, 2026)
   - etc.
3. **Add to Project**: Select all issues, add to Project board
4. **Prioritize**: Move Phase 1 to "To-Do", rest to "Backlog"

### Daily Workflow
1. **Morning**: Check "To-Do (This Week)" column
2. **Pick Task**: Select 1-3 issues, move to "In Progress"
3. **Work**: Update issue with progress comments
4. **End of Day**: Move completed to "Done"

### Weekly Review
1. **Run Analyzer**: `python scripts/analyze_project.py --summary`
2. **Check Progress**: How many Phase 1 issues closed?
3. **Reprioritize**: Move urgent items up, less important down
4. **Plan Next Week**: Select 3-5 issues for "To-Do"

---

## 🔧 Customization

### Modify Issues Before Import
Edit `scripts/import_project_plan.py`:

```python
def get_issues(self) -> List[Dict]:
    return [
        {
            "title": "Your Custom Issue Title",
            "body": """
## Description
Your custom content here

## Tasks
- [ ] Task 1
- [ ] Task 2
            """,
            "labels": ["🔴 critical", "effort:high"],
            "milestone": "Phase 1: Foundation"
        },
        # Add more issues...
    ]
```

### Add Custom Labels
Before running import, create labels:

```powershell
gh label create "custom-label" --color "ff0000" --description "My label"
```

### Modify Milestones
After import, adjust milestone dates:

```powershell
gh api repos/nuniesmith/fks/milestones/1 -X PATCH -f due_on='2025-11-14T00:00:00Z'
```

---

## 🆘 Troubleshooting

### Error: "GitHub CLI not authenticated"
```powershell
gh auth login
```

### Error: "Label does not exist"
Run setup script first:
```powershell
python scripts/setup_github_project.py
```

This creates all standard labels.

### Error: "Rate limit exceeded"
GitHub API limits: 5000 req/hr for authenticated users.
Wait 1 hour or use `--dry-run` to preview first.

### Issues Created in Wrong Order
Issues are created sequentially. If you want specific order:
1. Delete unwanted issues: `gh issue delete <number>`
2. Re-run import script

### Want to Delete All Imported Issues
**⚠️ DESTRUCTIVE - BE CAREFUL**
```powershell
# List recent issues
gh issue list --limit 100

# Delete specific issues (one at a time)
gh issue delete 123
gh issue delete 124
# etc.
```

---

## 📊 Example: First Week Workflow

### Monday Morning (10 min)
```powershell
# 1. View Phase 1 issues
gh issue list --label "phase:1-immediate"

# 2. Check your project board
# Visit: https://github.com/nuniesmith/fks/projects/1

# 3. Pick #1.1 (Security) - move to "In Progress"
```

### During Work (As needed)
```powershell
# Update issue with progress
gh issue comment 5 --body "✅ Sub-task 1.1.1 complete - passwords generated"

# Commit with issue reference
git commit -m "Generate secure passwords for production

- Created strong passwords for Postgres, Redis, PgAdmin
- Added .env to .gitignore
- Created .env.example template

Relates to #5"
```

### End of Day (5 min)
```powershell
# Check issue status
gh issue view 5

# If complete, close it
gh issue close 5 --comment "All sub-tasks complete. Security hardening done."

# Move card to "Done" on project board (manual)
```

### Friday Review (15 min)
```powershell
# Run analyzer
python scripts/analyze_project.py --summary

# Check closed issues this week
gh issue list --state closed --label "phase:1-immediate"

# Update PROJECT_STATUS.md with progress
# Plan next week's issues
```

---

## 🎉 After Import

You'll have:
- ✅ **20 structured issues** in GitHub
- ✅ **7 milestone phases** defined
- ✅ **Clear priorities** with labels
- ✅ **Effort estimates** for planning
- ✅ **Dependencies** documented
- ✅ **Success criteria** to track progress

**Your entire 3-6 month roadmap is now in GitHub!**

---

## 📚 Next Steps

1. **Import Issues**: `python scripts/import_project_plan.py`
2. **Create Project Board**: See SETUP_CHECKLIST.md
3. **Start Phase 1**: Pick issue #1.1 or #1.2
4. **Daily Updates**: Comment on issues as you work
5. **Weekly Reviews**: Run analyzer, reprioritize

**Questions?** See `.github/README.md` for full system documentation.

---

**Script**: `scripts/import_project_plan.py`  
**Created**: 2025-10-17  
**Issues**: 20 (7 phases, 13 detailed tasks)
