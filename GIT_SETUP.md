# Git Setup Instructions

## Step 1: Install Git

### Windows Installation Options:

**Option A: Using winget (Recommended)**
```powershell
# Open PowerShell as Administrator
winget install --id Git.Git -e --source winget
```

**Option B: Manual Installation**
1. Download Git from: https://git-scm.com/download/win
2. Run the installer with default settings
3. Restart PowerShell after installation

**Option C: Using Chocolatey**
```powershell
choco install git
```

## Step 2: Verify Installation

```powershell
git --version
# Should show: git version 2.x.x
```

## Step 3: Configure Git (First Time Only)

```powershell
# Set your name and email
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Verify configuration
git config --list
```

## Step 4: Initialize Repository

```powershell
# Navigate to your project folder
cd "C:\Users\dhaka\OneDrive\Documents\meesho_sales_app"

# Initialize Git repository
git init

# Check status
git status
```

## Step 5: Make Initial Commit

```powershell
# Stage all files (respects .gitignore)
git add .

# Create initial commit
git commit -m "Initial commit: Meesho Sales Dashboard with Git version control"

# View commit history
git log --oneline
```

## Step 6: Daily Workflow

### Before Making Changes
```powershell
# Check current status
git status

# View what changed
git diff
```

### After Making Changes
```powershell
# Stage specific files
git add filename.py

# Or stage all changes
git add .

# Commit with descriptive message
git commit -m "feat: Add new analytics feature"

# View history
git log --oneline -5
```

### Undo Changes (Safety Net!)

```powershell
# Discard uncommitted changes to a file
git checkout -- filename.py

# Restore file from previous commit
git restore filename.py

# Undo last commit (keep changes)
git reset --soft HEAD~1

# View file from previous commit
git show HEAD:filename.py

# Restore entire project to specific commit
git reset --hard <commit-hash>
```

## Step 7: Create Branches (Advanced)

```powershell
# Create and switch to new branch
git checkout -b feature/modularization

# Make changes and commit
git add .
git commit -m "Work in progress on modularization"

# Switch back to main branch
git checkout main

# Merge feature branch
git merge feature/modularization

# Delete feature branch
git branch -d feature/modularization
```

## Step 8: Remote Repository (Optional)

### GitHub Setup
```powershell
# Create repository on GitHub.com first, then:

# Add remote
git remote add origin https://github.com/yourusername/meesho-sales-app.git

# Push to GitHub
git push -u origin main

# Pull latest changes
git pull origin main
```

## Common Commands Cheat Sheet

| Command | Purpose |
|---------|---------|
| `git status` | Show current status |
| `git add .` | Stage all changes |
| `git commit -m "message"` | Save changes |
| `git log` | View history |
| `git diff` | See what changed |
| `git checkout -- file` | Discard changes |
| `git reset --hard HEAD` | Discard all changes |
| `git show HEAD:file` | View file from last commit |
| `git branch` | List branches |
| `git checkout -b name` | Create new branch |

## Best Practices

1. **Commit Often**: Small, focused commits are better than large ones
2. **Write Good Messages**: Use descriptive commit messages
3. **Use Branches**: Create branches for experimental features
4. **Check Status**: Always run `git status` before committing
5. **Review Changes**: Use `git diff` to review what you're committing

## Commit Message Convention

```
feat: Add new feature
fix: Fix bug
docs: Update documentation
refactor: Refactor code
test: Add tests
chore: Maintenance tasks
```

## Emergency Recovery

If you mess up and need to restore your project:

```powershell
# List all commits
git log --oneline

# Restore to specific commit
git reset --hard <commit-hash>

# Or go back 1 commit
git reset --hard HEAD~1

# Or go back 5 commits
git reset --hard HEAD~5
```

## Next Steps

After installing Git:
1. Run through Steps 3-5 above
2. Git will now protect your code
3. You can safely experiment knowing you can always go back

---

**Note**: Once Git is set up, your code will be safe from accidental deletions or corruptions. You'll be able to restore any previous version of your files.
