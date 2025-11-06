# OIDC Complete Diagnostic Checklist

## 0) Target Information

- **AWS Account ID:** `838693051036`
- **Role ARN:** `arn:aws:iam::838693051036:role/github-actions-oidc-role`
- **Repo (owner/name):** `emsilver987/CS_450_Phase_2`
- **Branch or ref that runs deploy:** `main` (triggers on push to main branch and manual workflow_dispatch)
- **Workflow file path:** `.github/workflows/cd.yml`

---

## 1) GitHub Actions Side (Token Issuance) ✅

### 1.1 Workflow YAML Configuration

**Top-level permissions:**

```yaml
permissions:
  id-token: write # ✅ Correct
  contents: read # ✅ Correct
  actions: read
  pull-requests: read
```

**Job-level permissions:**

```yaml
permissions:
  id-token: write # ✅ Correct
  contents: read # ✅ Correct
```

**OIDC credentials step:**

```yaml
- name: Configure AWS credentials (OIDC)
  uses: aws-actions/configure-aws-credentials@v3
  with:
    aws-region: us-east-1
    role-to-assume: arn:aws:iam::838693051036:role/github-actions-oidc-role
    role-session-name: GitHubActions-CDPipeline
```

**Status:** ✅ All permissions correctly configured

### 1.2 Debug OIDC Context Step

**Recommended addition to workflow:**

```yaml
- name: Debug OIDC context
  run: |
    echo "ref=$GITHUB_REF"
    echo "ref_name=$GITHUB_REF_NAME"
    echo "repo=$GITHUB_REPOSITORY"
    echo "actor=$GITHUB_ACTOR"
    echo "event_name=$GITHUB_EVENT_NAME"
    echo "workflow_ref=$GITHUB_WORKFLOW_REF"
```

**Expected values when running on main:**

- `ref=refs/heads/main`
- `ref_name=main`
- `repo=emsilver987/CS_450_Phase_2`
- `actor=<github-username>`
- `event_name=push` or `workflow_dispatch`
- `workflow_ref=emsilver987/CS_450_Phase_2/.github/workflows/cd.yml@refs/heads/main`

**Action Required:** Add this step to workflow and run once to capture actual values

### 1.3 Verify AWS Identity Step

**Current configuration:**

```yaml
- name: Verify AWS identity
  shell: bash
  run: aws sts get-caller-identity
```

**Expected output (when OIDC works):**

```json
{
  "UserId": "AROA...:botocore-session-...",
  "Account": "838693051036",
  "Arn": "arn:aws:sts::838693051036:assumed-role/github-actions-oidc-role/GitHubActions-CDPipeline"
}
```

**Status:** ✅ Step exists in workflow

---

## 2) AWS IAM Side (Trust + Policies) ✅

### 2.1 GitHub OIDC Provider ✅ EXISTS

**Provider ARN:** `arn:aws:iam::838693051036:oidc-provider/token.actions.githubusercontent.com`

**Provider Details:**

```json
{
  "Url": "token.actions.githubusercontent.com",
  "ClientIDList": ["sts.amazonaws.com"],
  "ThumbprintList": ["6938fd4d98bab03faadb97b34396831e3780aea1"],
  "CreateDate": "2025-10-22T18:12:49.104000+00:00"
}
```

**Status:** ✅ Provider exists with correct audience (`sts.amazonaws.com`)

### 2.2 Trust Policy ✅ CORRECT

**Current Trust Policy (from AWS):**

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

**Verification:**

- ✅ `Action`: `sts:AssumeRoleWithWebIdentity` (correct)
- ✅ `Principal.Federated`: Correct OIDC provider ARN
- ✅ `Condition.StringEquals.aud`: `sts.amazonaws.com` (correct)
- ✅ `Condition.StringLike.sub`: `repo:emsilver987/CS_450_Phase_2:*` (matches repo; wildcard allows all branches/tags)

**Status:** ✅ Trust policy is correctly configured

### 2.3 Attached Policies

**Attached Managed Policies:**

1. `AmazonAPIGatewayAdministrator`
2. `AmazonEC2ContainerRegistryFullAccess`
3. `AmazonEC2FullAccess`
4. `IAMFullAccess`
5. `SecretsManagerReadWrite`
6. `AmazonECS_FullAccess`
7. `CloudWatchFullAccess`
8. `AWSKeyManagementServicePowerUser`
9. `AmazonDynamoDBFullAccess`
10. `AmazonS3FullAccess`

**Inline Policies:** None

**Note:** These permissions are sufficient for the deployment workflow. The trust policy is the critical piece for OIDC authentication.

---

## 3) Branch/Ref Patterns ✅

**Workflow triggers:**

- ✅ Push to `main` branch
- ✅ Manual `workflow_dispatch`

**Expected subject claims:**

- Push to main: `repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main`
- Manual dispatch: `repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main` (uses default branch)

**Trust policy pattern:**

- `repo:emsilver987/CS_450_Phase_2:*` (wildcard matches all branches/tags)

**Status:** ✅ Pattern matches - wildcard `:*` covers both push and manual dispatch triggers

---

## 4) Local Validations ✅

### 4.1 OIDC Provider List

```bash
$ aws iam list-open-id-connect-providers
{
    "OpenIDConnectProviderList": [
        {
            "Arn": "arn:aws:iam::838693051036:oidc-provider/token.actions.githubusercontent.com"
        }
    ]
}
```

**Status:** ✅ Provider exists

### 4.2 OIDC Provider Details

```bash
$ aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn arn:aws:iam::838693051036:oidc-provider/token.actions.githubusercontent.com
{
    "Url": "token.actions.githubusercontent.com",
    "ClientIDList": ["sts.amazonaws.com"],
    "ThumbprintList": ["6938fd4d98bab03faadb97b34396831e3780aea1"],
    "CreateDate": "2025-10-22T18:12:49.104000+00:00"
}
```

**Status:** ✅ Provider correctly configured with audience `sts.amazonaws.com`

### 4.3 Role Trust Policy

```bash
$ aws iam get-role --role-name github-actions-oidc-role --query 'Role.AssumeRolePolicyDocument' --output json
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

**Status:** ✅ Trust policy matches expected configuration

---

## 5) Success Criteria ✅

### Checklist

1. ✅ **Workflow shows `id-token: write`** - Configured at both workflow and job level
2. ✅ **Runs `configure-aws-credentials@v3`** - Using correct role ARN
3. ✅ **OIDC provider exists** - `token.actions.githubusercontent.com` with audience `sts.amazonaws.com`
4. ✅ **Trust policy contains `sts:AssumeRoleWithWebIdentity`** - Correct Action
5. ✅ **Trust policy has correct Principal** - OIDC provider ARN
6. ✅ **Trust policy has correct audience condition** - `sts.amazonaws.com`
7. ✅ **Trust policy subject pattern matches** - `repo:emsilver987/CS_450_Phase_2:*` (wildcard)
8. ⏳ **`aws sts get-caller-identity` succeeds** - Pending workflow test
9. ✅ **No fallback to static credentials** - `USE_OIDC: "true"` prevents fallback

**Overall Status:** ✅ **8/9 criteria met** (pending workflow test)

---

## 6) Recommended Workflow Enhancements

### Add Debug Step

Add this step **before** "Configure AWS credentials (OIDC)":

```yaml
- name: Debug OIDC context
  run: |
    echo "ref=$GITHUB_REF"
    echo "ref_name=$GITHUB_REF_NAME"
    echo "repo=$GITHUB_REPOSITORY"
    echo "actor=$GITHUB_ACTOR"
    echo "event_name=$GITHUB_EVENT_NAME"
    echo "workflow_ref=$GITHUB_WORKFLOW_REF"
```

This will help diagnose any future issues by showing the exact subject claim values.

---

## 7) Final Verification

### Next Steps

1. **Add debug step** to workflow (optional but recommended)
2. **Trigger workflow** (push to main or manual dispatch)
3. **Verify success:**
   - "Configure AWS credentials (OIDC)" step should succeed
   - "Verify AWS identity" step should show assumed role ARN
   - No errors about assume role failures

### Expected Workflow Output

**Success indicators:**

```
Configure AWS credentials (OIDC)
✓ Successfully assumed role

Verify AWS identity
{
  "UserId": "AROA...",
  "Account": "838693051036",
  "Arn": "arn:aws:sts::838693051036:assumed-role/github-actions-oidc-role/GitHubActions-CDPipeline"
}
```

**If it fails:**

- Check the exact error message
- Verify the subject claim matches the trust policy pattern
- Ensure OIDC provider thumbprint is current (AWS updates these automatically)

---

## Summary

✅ **All configuration is correct:**

- Workflow permissions: ✅
- OIDC provider: ✅
- Trust policy: ✅ (fixed from `sts:AssumeRole` to `sts:AssumeRoleWithWebIdentity`)
- Role ARN: ✅
- Subject pattern: ✅

**The OIDC setup should now work correctly.** The trust policy fix (changing Action to `sts:AssumeRoleWithWebIdentity`) was the critical issue that has been resolved.

---

**Last Updated:** After trust policy fix  
**Status:** Ready for testing
