#!/bin/bash
# Script to create or update the GitHub token secret in AWS Secrets Manager
# Usage: ./setup-github-token-secret.sh YOUR_GITHUB_TOKEN

set -e

SECRET_NAME="acme-github-token"
REGION="us-east-1"

if [ -z "$1" ]; then
    echo "Usage: $0 <GITHUB_TOKEN>"
    echo "Example: $0 ghp_xxxxxxxxxxxxxxxxxxxx"
    exit 1
fi

GITHUB_TOKEN="$1"

# Validate token format
if [[ ! "$GITHUB_TOKEN" =~ ^(ghp_|github_pat_) ]]; then
    echo "Warning: Token doesn't start with 'ghp_' or 'github_pat_'. Are you sure it's valid?"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create JSON secret string
SECRET_JSON=$(cat <<EOF
{
  "github_token": "$GITHUB_TOKEN"
}
EOF
)

# Check if secret exists
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Secret '$SECRET_NAME' already exists. Updating..."
    aws secretsmanager update-secret \
        --secret-id "$SECRET_NAME" \
        --secret-string "$SECRET_JSON" \
        --region "$REGION"
    echo "✅ Secret updated successfully!"
else
    echo "Creating new secret '$SECRET_NAME'..."
    aws secretsmanager create-secret \
        --name "$SECRET_NAME" \
        --description "GitHub personal access token for API rate limits (5000 req/hour)" \
        --secret-string "$SECRET_JSON" \
        --region "$REGION"
    echo "✅ Secret created successfully!"
fi

echo ""
echo "Next steps:"
echo "1. Redeploy the ECS service to pick up the new secret:"
echo "   aws ecs update-service --cluster validator-cluster --service validator-service --force-new-deployment"
echo ""
echo "2. Verify the token is being used by checking logs:"
echo "   aws logs tail /ecs/validator-service --follow | grep -i github"

