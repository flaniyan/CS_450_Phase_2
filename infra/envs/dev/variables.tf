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
  default     = "838693051036"
}
variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for encryption (optional, will look up via alias if not provided)"
  default     = ""
}
