# AWS Infrastructure Setup Guide for CS_450_Phase_2

## 🚀 **Current Status: Infrastructure Ready, Deployment Needed**

Based on my analysis, here's the complete AWS setup status:

### ✅ **What's Already Configured:**

#### **1. Terraform Infrastructure (Complete)**
- **S3 Module**: `pkg-artifacts` bucket with SSE-KMS encryption
- **DynamoDB Module**: 5 tables (users, tokens, packages, uploads, downloads) with proper schemas
- **ECS Module**: Fargate cluster with Python 3.12-slim container
- **IAM Module**: Group_106 policy with least-privilege access
- **Networking**: VPC, subnets, security groups, load balancer
- **Monitoring**: CloudWatch logs and metrics

#### **2. Python Services (Complete)**
- **Validator Service**: FastAPI-based package validation
- **Auth Service**: JWT authentication with DynamoDB
- **Package Service**: S3 multipart upload/download management
- **S3 Service**: Existing HuggingFace model handling

### ❌ **What's Missing/Needs Setup:**

#### **1. AWS Account Setup**
- AWS CLI installation
- Terraform installation
- AWS credentials configuration
- Account ID: `838693051036` (referenced in docs)

#### **2. Missing Infrastructure Components**
- **API Gateway**: Not defined in Terraform (mentioned in docs but missing)
- **Lambda Functions**: Not implemented (docs mention Lambda but only ECS exists)
- **KMS Keys**: Referenced but not defined
- **Secrets Manager**: Referenced but not defined
- **CloudWatch Alarms**: Not configured

#### **3. Deployment Pipeline**
- No CI/CD pipeline for AWS deployment
- No automated testing of AWS services
- No environment-specific configurations

## 🛠️ **Step-by-Step AWS Setup**

### **Step 1: Install Prerequisites**

```powershell
# Install AWS CLI
winget install Amazon.AWSCLI

# Install Terraform
winget install HashiCorp.Terraform

# Verify installations
aws --version
terraform --version
```

### **Step 2: Configure AWS Credentials**

```powershell
# Configure AWS credentials
aws configure
# Enter:
# - AWS Access Key ID: [Your access key]
# - AWS Secret Access Key: [Your secret key]
# - Default region: us-east-1
# - Default output format: json

# Verify credentials
aws sts get-caller-identity
```

### **Step 3: Deploy Infrastructure**

```powershell
# Navigate to infrastructure directory
cd CS_450_Phase_2/infra/envs/dev

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var 'aws_region=us-east-1' -var 'artifacts_bucket=pkg-artifacts'

# Apply infrastructure
terraform apply -var 'aws_region=us-east-1' -var 'artifacts_bucket=pkg-artifacts'
```

### **Step 4: Build and Deploy Python Services**

```powershell
# Build validator service Docker image
cd CS_450_Phase_2
docker build -f Dockerfile.validator -t validator-service .

# Tag for ECR (replace with your account ID)
docker tag validator-service:latest 838693051036.dkr.ecr.us-east-1.amazonaws.com/validator-service:latest

# Push to ECR
aws ecr create-repository --repository-name validator-service --region us-east-1
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 838693051036.dkr.ecr.us-east-1.amazonaws.com
docker push 838693051036.dkr.ecr.us-east-1.amazonaws.com/validator-service:latest
```

### **Step 5: Update ECS Task Definition**

```powershell
# Update ECS task definition to use your ECR image
# Edit infra/modules/ecs/main.tf line 26:
# Change: image = "public.ecr.aws/docker/library/python:3.12-slim"
# To: image = "838693051036.dkr.ecr.us-east-1.amazonaws.com/validator-service:latest"

# Reapply Terraform
terraform apply -var 'aws_region=us-east-1' -var 'artifacts_bucket=pkg-artifacts'
```

## 🔧 **Missing Components to Add**

### **1. API Gateway Module**

Create `infra/modules/api-gateway/main.tf`:

```hcl
resource "aws_api_gateway_rest_api" "main_api" {
  name = "acme-api"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_deployment" "main_deployment" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  stage_name  = "prod"
  
  depends_on = [
    aws_api_gateway_method.health,
    aws_api_gateway_integration.health
  ]
}

# Health endpoint
resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_method" "health" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.health.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "health" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.health_lambda.invoke_arn
}
```

### **2. Lambda Functions Module**

Create `infra/modules/lambda/main.tf`:

```hcl
# Health check Lambda
resource "aws_lambda_function" "health_lambda" {
  filename         = "health.zip"
  function_name    = "health-check"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.12"
  timeout         = 30
  
  environment {
    variables = {
      VALIDATOR_SERVICE_URL = var.validator_service_url
    }
  }
}

# Package Lambda
resource "aws_lambda_function" "package_lambda" {
  filename         = "package.zip"
  function_name    = "package-service"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.12"
  timeout         = 60
  
  environment {
    variables = {
      ARTIFACTS_BUCKET = var.artifacts_bucket
      DDB_TABLE_PACKAGES = "packages"
      DDB_TABLE_UPLOADS = "uploads"
    }
  }
}
```

### **3. KMS and Secrets Manager**

Add to `infra/modules/security/main.tf`:

```hcl
# KMS Key for encryption
resource "aws_kms_key" "main_key" {
  description             = "KMS key for ACME project"
  deletion_window_in_days = 7
}

resource "aws_kms_alias" "main_key_alias" {
  name          = "alias/acme-main-key"
  target_key_id = aws_kms_key.main_key.key_id
}

# Secrets Manager for JWT secret
resource "aws_secretsmanager_secret" "jwt_secret" {
  name = "acme-jwt-secret"
  
  kms_key_id = aws_kms_key.main_key.arn
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id = aws_secretsmanager_secret.jwt_secret.id
  secret_string = jsonencode({
    jwt_secret = "your-super-secret-jwt-key-change-this"
  })
}
```

## 🧪 **Testing Strategy**

### **1. Infrastructure Testing**

```powershell
# Test S3 bucket
aws s3 ls s3://pkg-artifacts/

# Test DynamoDB tables
aws dynamodb list-tables

# Test ECS cluster
aws ecs list-clusters

# Test load balancer
aws elbv2 describe-load-balancers
```

### **2. Service Testing**

```powershell
# Get validator service URL
$validator_url = terraform output -raw validator_service_url

# Test health endpoint
curl $validator_url/health

# Test validation endpoint
curl -X POST $validator_url/validate \
  -H "Content-Type: application/json" \
  -d '{"pkg_name":"test","version":"1.0.0","user_id":"test","user_groups":["Group_106"]}'
```

### **3. End-to-End Testing**

```powershell
# 1. Register user
curl -X POST $validator_url/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass","roles":["user"],"groups":["Group_106"]}'

# 2. Login
curl -X POST $validator_url/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}'

# 3. Upload package (using token from login)
curl -X POST $validator_url/init \
  -H "Authorization: Bearer [TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{"pkg_name":"test-pkg","version":"1.0.0"}'
```

## 📊 **Monitoring and Alerts**

### **CloudWatch Alarms**

```hcl
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "validator-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors validator service cpu utilization"
  
  dimensions = {
    ServiceName = aws_ecs_service.validator_service.name
    ClusterName = aws_ecs_cluster.validator_cluster.name
  }
}

resource "aws_cloudwatch_metric_alarm" "high_memory" {
  alarm_name          = "validator-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors validator service memory utilization"
  
  dimensions = {
    ServiceName = aws_ecs_service.validator_service.name
    ClusterName = aws_ecs_cluster.validator_cluster.name
  }
}
```

## 🎯 **Next Steps Priority**

1. **Install AWS CLI and Terraform** (Required)
2. **Configure AWS credentials** (Required)
3. **Deploy basic infrastructure** (S3, DynamoDB, ECS)
4. **Build and deploy Python services**
5. **Add missing components** (API Gateway, Lambda, KMS)
6. **Set up monitoring and alerts**
7. **Create CI/CD pipeline**
8. **Test end-to-end workflows**

The infrastructure is well-designed and ready for deployment. The main blockers are:
- Missing AWS CLI/Terraform installation
- Missing AWS credentials configuration
- Missing API Gateway and Lambda components
- Missing CI/CD pipeline

Once these are addressed, you'll have a fully functional AWS-based package registry system!

