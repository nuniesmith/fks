# Git Hooks

This directory contains custom git hooks for the FKS project.

## Available Hooks

### pre-commit

Runs markdown linting on staged `.md` files before allowing commits.

#### Installation

```bash
# Install the hook
cp .git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Or use git config to set hooks path (applies to all hooks)
git config core.hooksPath .git-hooks
```

#### Usage

The hook will run automatically when you commit. If markdown linting fails:

1. Fix the errors: `markdownlint --fix <file>`
2. Stage the fixed files: `git add <file>`
3. Commit again

Or bypass the hook (not recommended):

```bash
git commit --no-verify
```

## Requirements

- `markdownlint-cli` - Install with: `npm install -g markdownlint-cli`

## Configuration

Markdown linting rules are configured in `.markdownlintrc` at the repository root.
