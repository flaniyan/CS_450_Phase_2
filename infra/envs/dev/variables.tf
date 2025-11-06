variable "aws_region" { type = string }
variable "artifacts_bucket" { type = string }
variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Docker image tag for the validator service"
}
variable "aws_account_id" {
  type        = string
  description = "AWS account ID"
}


variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for S3 default encryption used by API policy"
}

variable "jwt_secret_arn" {
  type        = string
  description = "Secrets Manager ARN (or partial) for JWT secret valueFrom"
}
