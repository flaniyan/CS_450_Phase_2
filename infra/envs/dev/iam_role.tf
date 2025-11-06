# IAM Task Roles for ECS Services
# 
# Note: Based on architecture analysis, there are two services in code:
# 1. API Service (Main API - package CRUD, authentication, frontend)
# 2. Validator Service (Validation, download history)
#
# Currently, only ONE ECS service is deployed (misnamed "validator-service" but runs Main API).
# If you're deploying TWO separate services, create both roles.
# If you're keeping ONE service, you can skip api_task and attach API policies to validator_task.

# API Task Role
# Used by the Main API service for package management operations
resource "aws_iam_role" "api_task" {
  name = "api-task-role-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = {
    Name        = "api-task-role-dev"
    Environment = "dev"
    Service     = "api"
  }
}

# Validator Task Role
# Used by the Validator service for validation and download history
resource "aws_iam_role" "validator_task" {
  name = "validator-task-role-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = {
    Name        = "validator-task-role-dev"
    Environment = "dev"
    Service     = "validator"
  }
}

