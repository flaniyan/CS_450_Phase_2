# How to Trigger GitHub Actions Workflow

## ⚠️ IMPORTANT: Update IAM Role First!

**Before triggering the workflow, you MUST update the IAM role in AWS:**

```bash
aws iam update-assume-role-policy \
  --role-name github-actions-oidc-role \
  --policy-document file://github-actions-trust-policy.json
```

## Method 1: Manual Trigger (Easiest)

1. Go to: https://github.com/emsilver987/CS_450_Phase_2/actions
2. Click **"CD"** workflow in the left sidebar
3. Click **"Run workflow"** button (top right)
4. Select branch: **`main`**
5. Click **"Run workflow"**

## Method 2: Push to Main Branch

```bash
# Make sure you're on main branch
git checkout main

# Pull latest changes
git pull origin main

# Merge your changes (if on a different branch)
git merge cd_fixes

# Push to trigger workflow
git push origin main
```

## Method 3: Make a Small Commit

```bash
# Make a small change (like updating a comment)
echo "# Updated" >> README.md

# Commit and push
git add README.md
git commit -m "chore: trigger CD pipeline"
git push origin main
```

## Verify Workflow is Running

1. Go to Actions tab
2. You should see a new workflow run
3. Click on it to see the progress
4. Check the "Configure AWS credentials (OIDC)" step - it should now succeed!

## Expected Output

After fixing the IAM role, you should see:
```
✅ Authenticated as assumedRoleId AROA4GRQALKOCAEH4X22V:GitHubActions-CDPipeline
```

Instead of the error.

