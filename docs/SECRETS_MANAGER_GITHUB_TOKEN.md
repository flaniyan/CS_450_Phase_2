# GitHub Token via AWS Secrets Manager

This document describes how the GitHub token is managed using AWS Secrets Manager to avoid rate limit issues.

## Problem

The GitHub API has strict rate limits:
- **Unauthenticated requests**: 60 requests/hour
- **Authenticated requests**: 5,000 requests/hour

When the system ingests multiple models or performs rating operations, it quickly hits the unauthenticated rate limit, causing errors like:
```
ERROR: GitHub API rate limit exceeded. Reset at: 1763073705
```

## Solution

The GitHub token is now stored in AWS Secrets Manager and automatically injected into the ECS container as an environment variable. This provides:
- **Higher rate limits**: 5,000 requests/hour instead of 60
- **Secure storage**: Token is encrypted at rest
- **No code changes needed**: Token is available as `GITHUB_TOKEN` environment variable

## Setup

### 1. Create the Secret in AWS Secrets Manager

```bash
# Create the secret (replace YOUR_GITHUB_TOKEN with your actual token)
aws secretsmanager create-secret \
  --name acme-github-token \
  --description "GitHub personal access token for API rate limits" \
  --secret-string '{"github_token":"YOUR_GITHUB_TOKEN"}' \
  --region us-east-1
```

Or using the AWS Console:
1. Go to AWS Secrets Manager
2. Click "Store a new secret"
3. Select "Other type of secret"
4. Choose "Plaintext" and enter: `{"github_token":"YOUR_GITHUB_TOKEN"}`
5. Name it: `acme-github-token`
6. Click "Store"

### 2. Get a GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name (e.g., "ACME Model Registry")
4. Select scopes:
   - `public_repo` (for public repositories)
   - `repo` (if you need private repos)
5. Click "Generate token"
6. Copy the token (starts with `ghp_`)

### 3. Update the Secret

If you need to update the token later:

```bash
aws secretsmanager update-secret \
  --secret-id acme-github-token \
  --secret-string '{"github_token":"YOUR_NEW_TOKEN"}' \
  --region us-east-1
```

## Implementation Details

### Terraform Configuration

The ECS module (`infra/modules/ecs/main.tf`) includes:

1. **Data source** to reference the secret:
```terraform
data "aws_secretsmanager_secret" "github_token" {
  name = "acme-github-token"
}
```

2. **Container secret** injection:
```terraform
secrets = [
  {
    name      = "GITHUB_TOKEN"
    valueFrom = "${data.aws_secretsmanager_secret.github_token.arn}:github_token::"
  }
]
```

3. **IAM permissions** for the execution role:
```terraform
{
  Effect = "Allow"
  Action = [
    "secretsmanager:GetSecretValue",
    "secretsmanager:DescribeSecret"
  ]
  Resource = [
    data.aws_secretsmanager_secret.github_token.arn
  ]
}
```

### Code Implementation

The GitHub handler (`src/acmecli/github_handler.py`) automatically:
1. Checks for `GITHUB_TOKEN` environment variable (injected by ECS)
2. Falls back to Secrets Manager if needed (for programmatic access)
3. Falls back to unauthenticated requests if neither is available

## Verification

After deployment, check the logs to verify the token is being used:

```bash
# Should see this in logs:
INFO: GitHub token found - using authenticated requests (5000 req/hour)

# Instead of:
WARNING: GITHUB_TOKEN not set - using unauthenticated requests (60 req/hour)
```

## Troubleshooting

### Token Not Working

1. **Check secret exists**:
```bash
aws secretsmanager describe-secret --secret-id acme-github-token
```

2. **Verify secret value**:
```bash
aws secretsmanager get-secret-value --secret-id acme-github-token --query SecretString --output text
```

3. **Check ECS task definition**:
```bash
aws ecs describe-task-definition --task-definition validator-service --query 'taskDefinition.containerDefinitions[0].secrets'
```

4. **Check IAM permissions**:
```bash
aws iam get-role-policy --role-name ecs-execution-role --policy-name ecs-execution-secrets-policy
```

### Rate Limit Still Hit

- Verify token is valid: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`
- Check token has correct scopes
- Ensure ECS service has been redeployed after secret creation

## Security Notes

- The secret is encrypted at rest using AWS KMS
- Only the ECS execution role can read the secret
- The token is never logged or exposed in error messages
- Rotate the token periodically for security best practices

