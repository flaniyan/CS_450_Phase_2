# Fix OIDC Authentication Issue

## Problem
The IAM role trust policy has the wrong repository name (`flaniyan/CS_450_Phase_2` instead of `emsilver987/CS_450_Phase_2`).

## Solution

### Option 1: Update IAM Role Trust Policy (Recommended)

Run this AWS CLI command to update the role:

```bash
aws iam update-assume-role-policy \
  --role-name github-actions-oidc-role \
  --policy-document file://github-actions-trust-policy.json
```

### Option 2: Use the Setup Script

If the OIDC provider or role doesn't exist, run:

```bash
chmod +x setup-oidc.sh
./setup-oidc.sh emsilver987 CS_450_Phase_2
```

### Option 3: Manual AWS Console Update

1. Go to AWS IAM Console → Roles
2. Find `github-actions-oidc-role`
3. Click "Trust relationships" tab
4. Click "Edit trust policy"
5. Replace the content with the updated `github-actions-trust-policy.json` content
6. Save changes

## Verify

After updating, test the workflow again. You should see:
```
Authenticated as assumedRoleId AROA4GRQALKOCAEH4X22V:GitHubActions-CDPipeline
```

Instead of the error.

