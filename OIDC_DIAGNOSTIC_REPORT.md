# GitHub Actions OIDC Authentication Diagnostic Report

## Current Configuration

### 0) Target Information

- **AWS Account ID:** `838693051036`
- **Role ARN:** `arn:aws:iam::838693051036:role/github-actions-oidc-role`
- **Repo:** `emsilver987/CS_450_Phase_2`
- **Branch:** `main` (triggers on push to main)
- **Workflow:** `.github/workflows/cd.yml`

---

### 1) GitHub Actions Side ✅ CORRECT

**Workflow Configuration:**

```yaml
permissions:
  id-token: write  # ✅ Correct
  contents: read   # ✅ Correct

- name: Configure AWS credentials (OIDC)
  uses: aws-actions/configure-aws-credentials@v3
  with:
    aws-region: us-east-1
    role-to-assume: arn:aws:iam::838693051036:role/github-actions-oidc-role
    role-session-name: GitHubActions-CDPipeline
```

**Status:** ✅ Workflow is correctly configured

---

### 2) AWS IAM Side ❌ CRITICAL ERROR FOUND

**Current Trust Policy** (`github-actions-trust-policy.json`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::838693051036:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRole", // ❌ WRONG! Should be sts:AssumeRoleWithWebIdentity
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" // ✅ Correct
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:emsilver987/CS_450_Phase_2:*" // ✅ Correct
        }
      }
    }
  ]
}
```

## 🔴 CRITICAL ISSUE

**Line 9:** `"Action": "sts:AssumeRole"` is **WRONG**

**Should be:** `"Action": "sts:AssumeRoleWithWebIdentity"`

**Why:** OIDC authentication requires `AssumeRoleWithWebIdentity`, not regular `AssumeRole`. Regular `AssumeRole` is for AWS-to-AWS role assumption, not for web identity federation.

---

## 3) Branch/Ref Pattern

**Current pattern:** `repo:emsilver987/CS_450_Phase_2:*` (allows any branch/tag)

**Workflow triggers on:**

- Push to `main` branch
- Manual workflow dispatch

**Expected subject claim:**

- Push to main: `repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main`
- Manual dispatch: `repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main` (uses default branch)

**Status:** ✅ Pattern matches (wildcard `:*` covers both cases)

---

## 4) OIDC Provider Status

**Expected Provider ARN:**

```
arn:aws:iam::838693051036:oidc-provider/token.actions.githubusercontent.com
```

**Required Configuration:**

- **Provider URL:** `https://token.actions.githubusercontent.com`
- **Audience:** `sts.amazonaws.com`
- **Thumbprints:** AWS-managed (automatically updated)

**Action Required:** Verify this provider exists in AWS IAM → Identity providers

---

## 5) Fix Required

### Immediate Fix: Update Trust Policy

Replace the trust policy on the IAM role `github-actions-oidc-role` with:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::838693051036:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:emsilver987/CS_450_Phase_2:*"
        }
      }
    }
  ]
}
```

**Change:** Line 9: `"sts:AssumeRole"` → `"sts:AssumeRoleWithWebIdentity"`

---

## 6) Verification Steps

After fixing the trust policy:

1. **Trigger workflow** (push to main or manual dispatch)
2. **Check "Configure AWS credentials (OIDC)" step** - should succeed
3. **Check "Verify AWS identity" step** - should show:
   ```json
   {
     "UserId": "AROA...:botocore-session-...",
     "Account": "838693051036",
     "Arn": "arn:aws:sts::838693051036:assumed-role/github-actions-oidc-role/GitHubActions-CDPipeline"
   }
   ```

---

## 7) Alternative: More Restrictive Pattern (Optional)

If you want to restrict to only the `main` branch (more secure):

```json
"Condition": {
  "StringEquals": {
    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
    "token.actions.githubusercontent.com:sub": "repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main"
  }
}
```

This prevents the workflow from running on other branches.

---

## Summary

✅ **Workflow:** Correctly configured  
❌ **Trust Policy:** Wrong Action (`sts:AssumeRole` instead of `sts:AssumeRoleWithWebIdentity`)  
✅ **Conditions:** Correct (audience and subject pattern)  
✅ **Repository:** Correct (`emsilver987/CS_450_Phase_2`)

**Fix:** Update the trust policy Action to `sts:AssumeRoleWithWebIdentity` and the OIDC authentication will work.
