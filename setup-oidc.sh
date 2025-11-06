#!/bin/bash
# Script to set up OIDC provider and IAM role for GitHub Actions
# Usage: ./setup-oidc.sh <github-org-or-username> <repository-name>

set -e

GITHUB_ORG="${1:-emsilver987}"
REPO_NAME="${2:-CS_450_Phase_2}"
AWS_ACCOUNT_ID="838693051036"
AWS_REGION="us-east-1"
ROLE_NAME="github-actions-oidc-role"
OIDC_PROVIDER_URL="https://token.actions.githubusercontent.com"
OIDC_PROVIDER_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

echo "Setting up OIDC for GitHub Actions..."
echo "Repository: ${GITHUB_ORG}/${REPO_NAME}"
echo ""

# Step 1: Create OIDC Provider (if it doesn't exist)
echo "Step 1: Checking/Creating OIDC Provider..."
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "${OIDC_PROVIDER_ARN}" 2>/dev/null; then
    echo "OIDC Provider already exists"
else
    echo "Creating OIDC Provider..."
    # Get thumbprint
    THUMBPRINT=$(echo | openssl s_client -servername token.actions.githubusercontent.com -showcerts -connect token.actions.githubusercontent.com:443 2>/dev/null | openssl x509 -fingerprint -noout | sed 's/://g' | sed 's/.*=\(.*\)/\1/')
    
    aws iam create-open-id-connect-provider \
        --url "${OIDC_PROVIDER_URL}" \
        --client-id-list sts.amazonaws.com \
        --thumbprint-list "${THUMBPRINT}" \
        --tags Key=Name,Value=GitHubActionsOIDC
    
    echo "OIDC Provider created successfully"
fi

# Step 2: Create trust policy
echo ""
echo "Step 2: Creating trust policy..."
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_PROVIDER_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${REPO_NAME}:*"
        }
      }
    }
  ]
}
EOF
)

echo "$TRUST_POLICY" > /tmp/trust-policy.json
echo "Trust policy created:"
cat /tmp/trust-policy.json
echo ""

# Step 3: Create or update IAM role
echo "Step 3: Creating/Updating IAM Role..."
if aws iam get-role --role-name "${ROLE_NAME}" 2>/dev/null; then
    echo "Role exists, updating trust policy..."
    aws iam update-assume-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-document file:///tmp/trust-policy.json
    echo "Trust policy updated"
else
    echo "Creating new role..."
    aws iam create-role \
        --role-name "${ROLE_NAME}" \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --description "Role for GitHub Actions OIDC authentication"
    echo "Role created"
fi

# Step 4: Attach necessary policies (you may need to adjust these)
echo ""
echo "Step 4: Attaching policies..."
# Attach AdministratorAccess for now (you should restrict this based on your needs)
aws iam attach-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess 2>/dev/null || echo "Policy may already be attached or you may need to attach specific policies"

echo ""
echo "✅ OIDC setup complete!"
echo ""
echo "Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
echo "Repository pattern: repo:${GITHUB_ORG}/${REPO_NAME}:*"
echo ""
echo "Next steps:"
echo "1. Verify the role ARN in your GitHub Actions workflow matches: arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
echo "2. Make sure your GitHub repository is: ${GITHUB_ORG}/${REPO_NAME}"
echo "3. Test the workflow!"

