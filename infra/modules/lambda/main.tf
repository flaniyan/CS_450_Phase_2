# Minimal Lambda module for performance testing download handler
# Keeps Terraform changes minimal per user requirements

# Lambda IAM Role
resource "aws_iam_role" "lambda_download_role" {
  name = "${var.lambda_function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for Lambda to access S3
resource "aws_iam_role_policy" "lambda_s3_access" {
  name = "${var.lambda_function_name}-s3-policy"
  role = aws_iam_role.lambda_download_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifacts_bucket}",
          "arn:aws:s3:::${var.artifacts_bucket}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:${var.aws_region}:*:accesspoint/*",
          "arn:aws:s3:${var.aws_region}:*:accesspoint/*/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Create a ZIP file for Lambda deployment package
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../../../src/lambda/download_handler.py"
  output_path = "${path.module}/lambda_function.zip"
}

# Lambda Function
resource "aws_lambda_function" "download_handler" {
  filename      = data.archive_file.lambda_zip.output_path
  function_name = var.lambda_function_name
  role          = aws_iam_role.lambda_download_role.arn
  handler       = "download_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = 512

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      S3_ACCESS_POINT_NAME = "cs450-s3"
    }
  }
}

output "lambda_function_arn" {
  value = aws_lambda_function.download_handler.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.download_handler.function_name
}

