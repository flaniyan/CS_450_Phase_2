variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "validator_service_url" { type = string }

# API Gateway
resource "aws_api_gateway_rest_api" "main_api" {
  name = "acme-api"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }
  
  tags = {
    Name        = "acme-api"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

# API Gateway Resources
resource "aws_api_gateway_resource" "api" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "api"
}

resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.api.id
  path_part   = "health"
}

resource "aws_api_gateway_resource" "packages" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.api.id
  path_part   = "packages"
}

resource "aws_api_gateway_resource" "auth" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.api.id
  path_part   = "auth"
}

# Health endpoint
resource "aws_api_gateway_method" "health_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.health.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "health_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  
  integration_http_method = "GET"
  type                   = "HTTP_PROXY"
  uri                    = "${var.validator_service_url}/health"
}

# Packages endpoints
resource "aws_api_gateway_method" "packages_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.packages.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "packages_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.packages.id
  http_method = aws_api_gateway_method.packages_get.http_method
  
  integration_http_method = "GET"
  type                   = "HTTP_PROXY"
  uri                    = "${var.validator_service_url}/packages"
}

# Auth endpoints
resource "aws_api_gateway_resource" "auth_login" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "login"
}

resource "aws_api_gateway_method" "auth_login_post" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_login_post" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.auth_login_post.http_method
  
  integration_http_method = "POST"
  type                   = "HTTP_PROXY"
  uri                    = "${var.validator_service_url}/login"
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "main_deployment" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  
  depends_on = [
    aws_api_gateway_integration.health_get,
    aws_api_gateway_integration.packages_get,
    aws_api_gateway_integration.auth_login_post
  ]
  
  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "main_stage" {
  deployment_id = aws_api_gateway_deployment.main_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  stage_name    = "prod"
  
  tags = {
    Name        = "acme-api-prod"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

# Lambda Functions for additional functionality
# resource "aws_lambda_function" "package_lambda" {
#   filename         = "package_lambda.zip"
#   function_name    = "package-service"
#   role            = aws_iam_role.lambda_role.arn
#   handler         = "lambda_function.lambda_handler"
#   runtime         = "python3.12"
#   timeout         = 60
#   
#   environment {
#     variables = {
#       ARTIFACTS_BUCKET = var.artifacts_bucket
#       DDB_TABLE_PACKAGES = "packages"
#       DDB_TABLE_UPLOADS = "uploads"
#       DDB_TABLE_USERS = "users"
#       DDB_TABLE_TOKENS = "tokens"
#       VALIDATOR_SERVICE_URL = var.validator_service_url
#     }
#   }
#   
#   tags = {
#     Name        = "package-service"
#     Environment = "dev"
#     Project     = "CS_450_Phase_2"
#   }
# }

# Lambda IAM Role
resource "aws_iam_role" "lambda_role" {
  name = "lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
  
  tags = {
    Name        = "lambda-execution-role"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "lambda_policy" {
  name = "lambda-package-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:CreateMultipartUpload",
          "s3:AbortMultipartUpload",
          "s3:CompleteMultipartUpload",
          "s3:UploadPart",
          "s3:UploadPartCopy"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifacts_bucket}",
          "arn:aws:s3:::${var.artifacts_bucket}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = values(var.ddb_tables_arnmap)
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

output "api_gateway_url" {
  value = "https://${aws_api_gateway_rest_api.main_api.id}.execute-api.us-east-1.amazonaws.com/${aws_api_gateway_stage.main_stage.stage_name}"
}

output "api_gateway_id" {
  value = aws_api_gateway_rest_api.main_api.id
}

# output "lambda_function_arn" {
#   value = aws_lambda_function.package_lambda.arn
# }
