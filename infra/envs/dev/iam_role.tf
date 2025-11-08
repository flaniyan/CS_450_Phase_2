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

