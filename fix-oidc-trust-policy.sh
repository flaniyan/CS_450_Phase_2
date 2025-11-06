#!/bin/bash
# Fix OIDC Trust Policy for GitHub Actions
# Run this script to update the IAM role trust policy

set -e

ACCOUNT_ID="838693051036"
ROLE_NAME="github-actions-oidc-role"
TRUST_POLICY_FILE="github-actions-trust-policy.json"

echo "🔧 Updating IAM role trust policy for OIDC authentication..."
echo "Role: $ROLE_NAME"
echo "Account: $ACCOUNT_ID"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ Error: AWS CLI not configured or credentials not set"
    echo "Run: aws configure"
    exit 1
fi

# Check if trust policy file exists
if [ ! -f "$TRUST_POLICY_FILE" ]; then
    echo "❌ Error: Trust policy file not found: $TRUST_POLICY_FILE"
    exit 1
fi

# Verify the fix is in the file
if ! grep -q "sts:AssumeRoleWithWebIdentity" "$TRUST_POLICY_FILE"; then
    echo "❌ Error: Trust policy file still has wrong Action"
    echo "Expected: sts:AssumeRoleWithWebIdentity"
    echo "Please update github-actions-trust-policy.json first"
    exit 1
fi

# Update the trust policy
echo "📝 Updating trust policy..."
aws iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document "file://$TRUST_POLICY_FILE"

echo ""
echo "✅ Trust policy updated successfully!"
echo ""
echo "🔍 Verifying the update..."
aws iam get-role \
    --role-name "$ROLE_NAME" \
    --query 'Role.AssumeRolePolicyDocument' \
    --output json | jq .

echo ""
echo "✅ Next steps:"
echo "1. Push a commit to main branch or trigger workflow manually"
echo "2. Check the 'Configure AWS credentials (OIDC)' step in GitHub Actions"
echo "3. Verify 'aws sts get-caller-identity' succeeds in the workflow"

