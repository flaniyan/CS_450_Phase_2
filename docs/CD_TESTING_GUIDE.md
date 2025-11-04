# CD Pipeline Testing Guide

## 🧪 How to Test the CD Pipeline

### **Step 1: Configure GitHub Secrets**

**Before testing, you MUST configure the GitHub secret:**

1. Go to your GitHub repository: `https://github.com/emsilver987/CS_450_Phase_2`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. **Name**: `AWS_ROLE_TO_ASSUME`
5. **Secret**: `arn:aws:iam::838693051036:role/github-actions-oidc-role`
6. Click **Add secret**

### **Step 2: Test Methods**

#### **Method 1: Push to Main Branch (Automatic Trigger)**
```bash
# Make a small change and push to main
git add .
git commit -m "test: trigger CD pipeline"
git push origin main
```

#### **Method 2: Manual Workflow Dispatch (Recommended for Testing)**
1. Go to GitHub repository → **Actions** tab
2. Click on **CD** workflow
3. Click **Run workflow** button
4. Select branch (usually `main`)
5. Click **Run workflow**

#### **Method 3: Test with a Feature Branch**
```bash
# Create a test branch
git checkout -b test-cd-pipeline
git add .
git commit -m "test: CD pipeline functionality"
git push origin test-cd-pipeline

# Then merge to main to trigger CD
git checkout main
git merge test-cd-pipeline
git push origin main
```

### **Step 3: Monitor the Pipeline**

**Watch the workflow execution:**
1. Go to **Actions** tab in GitHub
2. Click on the running workflow
3. Monitor each step:
   - ✅ Checkout
   - ✅ Cache Terraform plugins
   - ✅ Configure AWS credentials (OIDC)
   - ✅ Verify AWS identity
   - ✅ Login to Amazon ECR
   - ✅ Build, tag, and push image
   - ✅ Setup Terraform
   - ✅ Terraform plan
   - ✅ Terraform apply
   - ✅ Force ECS service update
   - ✅ Wait for ECS service to stabilize

### **Step 4: Verify Deployment**

**Check ECS Service:**
```bash
aws ecs describe-services --cluster validator-cluster --services validator-service
```

**Check ECR Repository:**
```bash
aws ecr describe-images --repository-name validator-service
```

**Test the deployed API:**
```bash
# Test health endpoint
curl https://d2r8ifqdir6hfe.cloudfront.net/api/health

# Test package listing
curl https://d2r8ifqdir6hfe.cloudfront.net/api/packages/list
```

### **Step 5: Troubleshooting**

**If the pipeline fails:**

1. **Check AWS Credentials Error:**
   - Verify `AWS_ROLE_TO_ASSUME` secret is set correctly
   - Check IAM role permissions

2. **Check ECR Push Error:**
   - Verify ECR repository exists
   - Check ECR permissions

3. **Check Terraform Error:**
   - Review Terraform plan output
   - Check for missing variables

4. **Check ECS Update Error:**
   - Verify ECS cluster and service exist
   - Check ECS permissions

### **Step 6: Success Indicators**

**✅ Pipeline Success:**
- All workflow steps complete without errors
- Docker image pushed to ECR with new tag
- Terraform plan and apply succeed
- ECS service updates successfully
- Service stabilizes (healthy tasks)

**✅ Deployment Success:**
- API endpoints respond correctly
- New Docker image is running
- CloudFront serves updated content

### **Step 7: Rollback (If Needed)**

**If deployment fails:**
```bash
# Force ECS to use previous image
aws ecs update-service --cluster validator-cluster --service validator-service --force-new-deployment
```

**Or revert the commit:**
```bash
git revert HEAD
git push origin main
```

## 🎯 Testing Checklist

- [ ] GitHub secret `AWS_ROLE_TO_ASSUME` configured
- [ ] Workflow triggers successfully
- [ ] AWS credentials authenticate
- [ ] Docker image builds and pushes
- [ ] Terraform plan succeeds
- [ ] Terraform apply succeeds
- [ ] ECS service updates
- [ ] Service stabilizes
- [ ] API endpoints work
- [ ] CloudFront serves updated content

## 🚀 Quick Test Command

```bash
# Make a small change and test
echo "# CD Pipeline Test $(date)" >> README.md
git add README.md
git commit -m "test: CD pipeline - $(date)"
git push origin main
```

Then watch the Actions tab for the CD workflow to run!



