# GitHub Project Integration Guide

## Overview

This guide explains how to sync your FKS repository with GitHub Projects for automated task management. The system automatically adds issues and PRs to your project board, routes them based on labels, and keeps everything organized.

---

## 📋 Table of Contents

1. [Initial Setup](#initial-setup)
2. [Automatic Syncing](#automatic-syncing)
3. [Bulk Import from CSV](#bulk-import-from-csv)
4. [Label-Based Routing](#label-based-routing)
5. [Project Automation](#project-automation)
6. [API Integration](#api-integration)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 Initial Setup

### Step 1: Create GitHub Project

1. Go to your profile: `https://github.com/YOUR_USERNAME?tab=projects`
2. Click **New project**
3. Choose **Board** or **Table** view
4. Name it: `FKS Development`
5. Click **Create project**

### Step 2: Link Repository to Project

#### Method A: Via Repository (Recommended)

1. Go to `https://github.com/YOUR_USERNAME/fks`
2. Click **Projects** tab
3. Click **Link a project**
4. Search for "FKS Development"
5. Click to link

#### Method B: Via Project Settings

1. Open your FKS Development project
2. Click ⚙️ **Settings** (top-right menu)
3. Under **Manage access**, add the repository
4. Select **fks** repository

### Step 3: Configure Workflow

Update `.github/workflows/sync-to-project.yml`:

```yaml
env:
  PROJECT_NUMBER: 1  # Change this to YOUR project number
```

**Finding your project number:**
- Go to your project URL: `https://github.com/users/YOUR_USERNAME/projects/NUMBER`
- The `NUMBER` at the end is what you need

### Step 4: Verify Permissions

**Repository Settings → Actions → General**:
- ✅ **Workflow permissions**: Read and write permissions
- ✅ **Allow GitHub Actions to create and approve pull requests**

---

## 🔄 Automatic Syncing

### What Gets Synced Automatically

The workflow automatically adds to your project when:

| Event | Action Taken |
|-------|--------------|
| New issue opened | Add to project immediately |
| Issue reopened | Re-add to project |
| Issue labeled | Add and route by priority |
| Issue assigned | Add and assign in project |
| PR opened | Add to project |
| PR ready for review | Add if draft was converted |
| PR labeled | Add and categorize |

### Testing Automatic Sync

```bash
# 1. Create test issue
gh issue create --title "Test: Auto-sync" --body "Testing project sync"

# 2. Check Actions tab
# Should see "Sync Issues and PRs to Project" workflow running

# 3. Verify in project
# Issue should appear in your project board within 30 seconds
```

### Manual Sync (Bulk Add All Existing Items)

For existing open issues/PRs not yet in the project:

**Via GitHub UI:**
1. Go to **Actions** tab
2. Select **Sync Issues and PRs to Project**
3. Click **Run workflow**
4. Check ✅ **Sync all existing open issues/PRs**
5. Click **Run workflow**

**Via CLI:**
```bash
gh workflow run sync-to-project.yml -f sync_existing=true
```

This will add ALL open issues and PRs to the project.

---

## 📥 Bulk Import from CSV

### Method 1: Using GitHub CLI (Recommended)

**Step 1: Prepare CSV file**

Create `tasks.csv`:
```csv
title,body,labels,assignee
Fix login bug,"Users can't login after update",bug;security,yourusername
Add dark mode,"Implement dark theme",enhancement,
Update README,"Add installation steps",documentation,yourusername
```

**Step 2: Import script**

Create `import-tasks.sh`:
```bash
#!/bin/bash

# Read CSV and create issues
tail -n +2 tasks.csv | while IFS=, read -r title body labels assignee; do
    # Build command
    CMD="gh issue create --title \"$title\" --body \"$body\" --repo YOUR_USERNAME/fks"
    
    # Add labels if present
    if [ -n "$labels" ]; then
        IFS=';' read -ra LABEL_ARRAY <<< "$labels"
        for label in "${LABEL_ARRAY[@]}"; do
            CMD="$CMD --label \"$label\""
        done
    fi
    
    # Add assignee if present
    if [ -n "$assignee" ]; then
        CMD="$CMD --assignee \"$assignee\""
    fi
    
    # Execute
    eval $CMD
    echo "Created: $title"
    sleep 1  # Rate limiting
done

echo "Import complete! Issues will auto-add to project."
```

**Step 3: Run import**
```bash
chmod +x import-tasks.sh
./import-tasks.sh
```

### Method 2: Using Python Script

```python
#!/usr/bin/env python3
import csv
import requests
import time

GITHUB_TOKEN = "ghp_YOUR_TOKEN_HERE"
REPO_OWNER = "YOUR_USERNAME"
REPO_NAME = "fks"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

with open('tasks.csv', 'r') as file:
    reader = csv.DictReader(file)
    for row in reader:
        # Create issue
        data = {
            "title": row['title'],
            "body": row['body'],
            "labels": row['labels'].split(';') if row['labels'] else [],
        }
        
        if row['assignee']:
            data['assignees'] = [row['assignee']]
        
        response = requests.post(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues",
            headers=headers,
            json=data
        )
        
        if response.status_code == 201:
            print(f"✓ Created: {row['title']}")
        else:
            print(f"✗ Failed: {row['title']} - {response.status_code}")
        
        time.sleep(1)  # Rate limiting

print("Import complete! Check your project board.")
```

### Method 3: Using GitHub GraphQL API

For direct project item creation (advanced):

```bash
# Get project ID
gh api graphql -f query='
  query {
    user(login: "YOUR_USERNAME") {
      projectV2(number: 1) {
        id
      }
    }
  }
'

# Add item to project
gh api graphql -f query='
  mutation {
    addProjectV2ItemById(input: {
      projectId: "PROJECT_ID"
      contentId: "ISSUE_NODE_ID"
    }) {
      item {
        id
      }
    }
  }
'
```

---

## 🏷️ Label-Based Routing

The workflow automatically routes items based on labels:

### Priority Mapping

| Label | Priority | Action |
|-------|----------|--------|
| `breaking` | P0 - Critical | Auto-comment + high priority |
| `security` | P0 - Critical | Auto-comment + high priority |
| `bug` | P1 - High | Add to "To Do" |
| `enhancement` | P2 - Medium | Add to "Backlog" |
| `documentation` | P3 - Low | Add to "Documentation" |

### Custom Priority Assignment

Edit `.github/workflows/sync-to-project.yml`:

```yaml
const priorityMap = {
  'breaking': 'P0 - Critical',
  'security': 'P0 - Critical',
  'bug': 'P1 - High',
  'enhancement': 'P2 - Medium',
  'documentation': 'P3 - Low',
  'your-custom-label': 'Your Priority'  # Add custom mappings
};
```

### Status Automation

**In Project Settings → Workflows**, add:

1. **Auto-archive closed items**
   - When: Item is closed
   - Then: Set status to "Done"

2. **Auto-move assigned items**
   - When: Item is assigned
   - Then: Set status to "In Progress"

3. **Auto-move labeled items**
   - When: Label is "in-review"
   - Then: Set status to "In Review"

---

## ⚙️ Project Automation

### Built-in GitHub Project Automations

#### Setup Default Workflows

1. Open your project
2. Click ⚙️ menu → **Workflows**
3. Enable these workflows:

**Auto-add to project:**
```
When: Issue or PR is opened
Filters: repo:YOUR_USERNAME/fks is:open
Then: Add to project
```

**Item closed:**
```
When: Item is closed
Then: Set status to "Done"
```

**Pull request merged:**
```
When: PR is merged
Then: Set status to "Done", Archive item
```

### Custom Field Automation

**Add custom fields to your project:**

1. Click **+** in table view
2. Add fields:
   - **Priority** (Single select): P0, P1, P2, P3
   - **Estimate** (Number): Story points
   - **Sprint** (Text): Sprint name
   - **Category** (Single select): Backend, Frontend, DevOps, Docs

**Auto-populate fields** (via workflow):
```yaml
- name: Set custom fields
  uses: actions/github-script@v7
  with:
    script: |
      // GraphQL mutation to update project field
      const query = `
        mutation {
          updateProjectV2ItemFieldValue(input: {
            projectId: "PROJECT_ID"
            itemId: "ITEM_ID"
            fieldId: "FIELD_ID"
            value: {singleSelectOptionId: "OPTION_ID"}
          }) {
            projectV2Item {
              id
            }
          }
        }
      `;
```

---

## 🔌 API Integration

### Get Project and Item IDs

```bash
# Get project ID
gh api graphql -f query='
query {
  user(login: "YOUR_USERNAME") {
    projectV2(number: 1) {
      id
      title
      fields(first: 10) {
        nodes {
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
    }
  }
}'
```

### Add Item to Project

```bash
# Create issue first
ISSUE_ID=$(gh issue create --title "Test" --body "Test" --repo YOUR_USERNAME/fks --json id --jq '.id')

# Add to project
gh api graphql -f query="
mutation {
  addProjectV2ItemById(input: {
    projectId: \"YOUR_PROJECT_ID\"
    contentId: \"$ISSUE_ID\"
  }) {
    item {
      id
    }
  }
}"
```

### Update Item Fields

```bash
gh api graphql -f query='
mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: "PROJECT_ID"
    itemId: "ITEM_ID"
    fieldId: "PRIORITY_FIELD_ID"
    value: {singleSelectOptionId: "P0_OPTION_ID"}
  }) {
    projectV2Item {
      id
    }
  }
}'
```

### Bulk Operations Script

```python
import requests

def get_all_items(project_id, token):
    """Get all items in project"""
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100) {
            nodes {
              id
              content {
                ... on Issue {
                  number
                  title
                  state
                }
              }
            }
          }
        }
      }
    }
    """
    # Execute query and return items

def update_item_field(item_id, field_id, value, token):
    """Update a project item field"""
    mutation = """
    mutation($itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: "PROJECT_ID"
        itemId: $itemId
        fieldId: $fieldId
        value: $value
      }) {
        projectV2Item {
          id
        }
      }
    }
    """
    # Execute mutation
```

---

## 🔧 Troubleshooting

### Issue: Items not adding to project

**Symptoms:**
- Workflow runs successfully
- No items appear in project

**Solutions:**

1. **Check project number:**
   ```bash
   # Verify project URL
   https://github.com/users/YOUR_USERNAME/projects/NUMBER
   ```

2. **Verify permissions:**
   - Settings → Actions → Workflow permissions: **Read and write**

3. **Check project visibility:**
   - Project must be public or workflow needs project token

4. **Manual add test:**
   ```bash
   gh project item-add PROJECT_NUMBER --owner YOUR_USERNAME --url https://github.com/YOUR_USERNAME/fks/issues/1
   ```

### Issue: Permission denied errors

**Error:** `Resource not accessible by integration`

**Solution:**
```yaml
permissions:
  issues: write
  pull-requests: write
  contents: read
  # Add this if using organization project:
  # project: write  # Requires organization-level PAT
```

### Issue: Bulk import rate limiting

**Error:** `API rate limit exceeded`

**Solution:**
```bash
# Add delays in import script
sleep 2  # Wait 2 seconds between requests

# Or use authenticated requests (higher limit)
gh auth login
```

### Issue: GraphQL mutation fails

**Error:** `Field 'addProjectV2ItemById' doesn't exist`

**Solution:**
- Ensure using Projects V2 (not classic)
- Update GitHub CLI: `gh extension upgrade gh-project`
- Verify token scopes include `project`

### Issue: Custom fields not updating

**Checklist:**
1. Get field IDs: `gh project field-list PROJECT_NUMBER`
2. Get option IDs for select fields
3. Use correct value format:
   - Single select: `{singleSelectOptionId: "ID"}`
   - Number: `{number: 42}`
   - Text: `{text: "value"}`

---

## 📊 Best Practices

### 1. Project Structure

**Recommended views:**
- **Board**: For sprint planning (Backlog → To Do → In Progress → Review → Done)
- **Table**: For detailed tracking (all fields visible)
- **Roadmap**: For timeline visualization (requires date fields)

### 2. Label Strategy

Align labels with project fields:
- `priority-*` labels → Priority field
- `status-*` labels → Status column
- `type-*` labels → Category field

### 3. Automation Rules

**Start simple:**
1. Auto-add new items ✅
2. Auto-close done items ✅
3. Add complexity gradually

**Avoid:**
- Over-automating (can create conflicts)
- Circular rules (A triggers B triggers A)

### 4. Bulk Import

**Before importing:**
- Clean up CSV (remove duplicates)
- Test with 5 items first
- Check labels exist in repo
- Verify assignees are valid

**After importing:**
- Run sync workflow to add to project
- Manually verify 5-10 items
- Adjust automation rules if needed

### 5. Performance

**For large projects (100+ items):**
- Use table view for editing
- Filter views by sprint/milestone
- Archive completed items regularly
- Use GraphQL API for bulk operations

---

## 🚀 Advanced Use Cases

### Scenario 1: Multi-Repository Project

Track issues across multiple repos:

```yaml
# In each repo's workflow
on:
  issues:
    types: [opened]

jobs:
  add-to-shared-project:
    steps:
      - uses: actions/add-to-project@v0.5.0
        with:
          project-url: https://github.com/orgs/YOUR_ORG/projects/1
          github-token: ${{ secrets.ORG_PROJECT_TOKEN }}
```

### Scenario 2: Sprint Automation

Auto-assign sprints based on creation date:

```yaml
- name: Assign to current sprint
  run: |
    # Get current sprint (e.g., "2025-W42")
    SPRINT=$(date +%Y-W%V)
    # Update project field via API
```

### Scenario 3: External Tool Integration

Sync from Trello/Jira:

```bash
# Export from Trello (CSV)
# Import to GitHub (script)
# Auto-add to project (workflow)
```

---

## 📚 Additional Resources

- **Official Docs**: https://docs.github.com/en/issues/planning-and-tracking-with-projects
- **API Reference**: https://docs.github.com/en/graphql/reference/mutations#addprojectv2itembyid
- **actions/add-to-project**: https://github.com/actions/add-to-project
- **GitHub CLI Projects**: https://cli.github.com/manual/gh_project

---

**FKS GitHub Project Integration**  
**Version**: 1.0  
**Last Updated**: October 2025  
**Status**: Production Ready ✅
