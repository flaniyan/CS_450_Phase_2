# GitHub Secrets Configuration for CD Pipeline

## Required Secrets

The CD pipeline requires the following GitHub repository secrets to be configured:

### Option 1: OIDC (Recommended - More Secure)

1. **AWS_ROLE_TO_ASSUME**
   - Description: ARN of the IAM role that GitHub Actions can assume
   - Example: `arn:aws:iam::838693051036:role/GitHubActionsRole`
   - How to get: Create an IAM role with trust policy for GitHub Actions

### Option 2: Static Credentials (Less Secure)

1. **AWS_ACCESS_KEY_ID**
   - Description: AWS Access Key ID for deployment
   - How to get: Create IAM user with deployment permissions

2. **AWS_SECRET_ACCESS_KEY**
   - Description: AWS Secret Access Key for deployment
   - How to get: Generated when creating IAM user

## Required IAM Permissions

The AWS credentials/role must have permissions for:

### ECR Permissions
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:GetDownloadUrlForLayer`
- `ecr:BatchGetImage`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`
- `ecr:PutImage`

### ECS Permissions
- `ecs:UpdateService`
- `ecs:DescribeServices`
- `ecs:DescribeTasks`
- `ecs:ListTasks`

### Terraform Permissions
- All permissions needed for your infrastructure (S3, DynamoDB, ECS, IAM, etc.)

## How to Configure Secrets

1. Go to your GitHub repository
2. Click on **Settings** tab
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Add each secret with the exact name and value

## Testing the Pipeline

After configuring secrets, the CD pipeline will automatically run on:
- Push to `main` branch
- Manual trigger via GitHub Actions tab

The pipeline will:
1. Build Docker image
2. Push to ECR
3. Update Terraform infrastructure
4. Deploy to ECS
5. Run health checks



