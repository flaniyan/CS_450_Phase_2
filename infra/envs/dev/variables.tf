variable "aws_region" { type = string }
variable "artifacts_bucket" { type = string }
variable "image_tag" { 
  type = string 
  default = "latest"
  description = "Docker image tag for the validator service"
}
