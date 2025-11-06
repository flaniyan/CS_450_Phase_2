#!/bin/bash
# Update OIDC Trust Policy with explicit pattern matching
# This fixes the "Not authorized" error

set -e

ROLE_NAME="github-actions-oidc-role"
TRUST_POLICY_FILE="github-actions-trust-policy.json"

echo "🔧 Updating IAM role trust policy..."
echo ""

# Update the trust policy
aws iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document "file://$TRUST_POLICY_FILE"

echo ""
echo "✅ Trust policy updated!"
echo ""
echo "📋 Current trust policy:"
aws iam get-role \
    --role-name "$ROLE_NAME" \
    --query 'Role.AssumeRolePolicyDocument' \
    --output json | jq .

echo ""
echo "🔍 Next: Run the workflow and check 'Debug OIDC context' output"
echo "   Compare the subject claim with the trust policy pattern"

