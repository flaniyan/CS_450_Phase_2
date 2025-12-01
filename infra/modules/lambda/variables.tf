# Variables for Lambda module

variable "artifacts_bucket" {
  type        = string
  description = "S3 bucket name for artifacts"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "lambda_function_name" {
  type        = string
  description = "Name of the Lambda function"
  default     = "model-download-handler"
}

