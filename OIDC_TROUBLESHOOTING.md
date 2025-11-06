# OIDC Troubleshooting: "Not authorized to perform sts:AssumeRoleWithWebIdentity"

## Error Analysis

**Error:** `Not authorized to perform sts:AssumeRoleWithWebIdentity`

This error typically means:

1. ✅ The trust policy Action is correct (`sts:AssumeRoleWithWebIdentity`)
2. ❌ But the **subject claim** from GitHub doesn't match the trust policy condition
3. OR the OIDC provider doesn't have the right audience

## Most Likely Cause: Subject Claim Mismatch

The trust policy expects:

```
repo:emsilver987/CS_450_Phase_2:*
```

But GitHub might be sending:

- `repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main` (for push events)
- `repo:emsilver987/CS_450_Phase_2:ref:refs/tags/v1.0` (for tags)
- `repo:emsilver987/CS_450_Phase_2:pull_request` (for PRs)
- `repo:emsilver987/CS_450_Phase_2:workflow_dispatch` (for manual dispatch)

The wildcard `:*` should match these, but let's verify.

## Diagnostic Steps

### Step 1: Check the actual subject claim

I've added a debug step to the workflow. After the next run, check the output of "Debug OIDC context" to see:

- `ref=$GITHUB_REF` (should be `refs/heads/main`)
- `repo=$GITHUB_REPOSITORY` (should be `emsilver987/CS_450_Phase_2`)

The actual subject claim will be: `repo:$GITHUB_REPOSITORY:ref:$GITHUB_REF`

### Step 2: Verify trust policy conditions

The trust policy uses `StringLike` with wildcard, which should work. But let's verify the exact format.

**Current trust policy condition:**

```json
"StringLike": {
  "token.actions.githubusercontent.com:sub": "repo:emsilver987/CS_450_Phase_2:*"
}
```

This should match:

- ✅ `repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main`
- ✅ `repo:emsilver987/CS_450_Phase_2:ref:refs/tags/v1.0`
- ✅ `repo:emsilver987/CS_450_Phase_2:pull_request`
- ✅ `repo:emsilver987/CS_450_Phase_2:workflow_dispatch`

### Step 3: Alternative - Use exact match

If the wildcard isn't working, try an exact match for the main branch:

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
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

Or use multiple conditions for push and workflow_dispatch:

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
          "token.actions.githubusercontent.com:sub": [
            "repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main",
            "repo:emsilver987/CS_450_Phase_2:workflow_dispatch"
          ]
        }
      }
    }
  ]
}
```

## Quick Fix: Try More Permissive Pattern

If StringLike wildcard isn't working, try this pattern:

```json
"StringLike": {
  "token.actions.githubusercontent.com:sub": "repo:emsilver987/CS_450_Phase_2:*"
}
```

But make sure it's in the `Condition` block, not mixed with `StringEquals`.

## Verification Commands

After updating the trust policy, verify:

```bash
# Check current trust policy
aws iam get-role --role-name github-actions-oidc-role \
  --query 'Role.AssumeRolePolicyDocument' --output json | jq .

# Verify OIDC provider
aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn arn:aws:iam::838693051036:oidc-provider/token.actions.githubusercontent.com
```

## Next Steps

1. **Run the workflow again** with the debug step added
2. **Check the "Debug OIDC context" output** to see the actual subject claim
3. **Compare** the subject claim with the trust policy condition
4. **Update trust policy** if there's a mismatch

## Common Issues

### Issue 1: Case sensitivity

- GitHub repo names are case-sensitive
- Make sure `emsilver987/CS_450_Phase_2` matches exactly (check capitalization)

### Issue 2: StringLike vs StringEquals

- `StringLike` with wildcard `:*` should work
- But if it doesn't, try `StringEquals` with exact match first

### Issue 3: Multiple conditions

- Make sure both `aud` and `sub` are in the same `Condition` block
- `StringEquals` for `aud`, `StringLike` for `sub` is valid

## Expected Subject Claims

Based on workflow triggers:

- **Push to main:** `repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main`
- **Manual dispatch:** `repo:emsilver987/CS_450_Phase_2:ref:refs/heads/main` (uses default branch)

The wildcard pattern `repo:emsilver987/CS_450_Phase_2:*` should match both.
