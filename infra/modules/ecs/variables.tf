variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "image_tag" { 
  type = string 
  default = "latest"
  description = "Docker image tag for the validator service"
}
variable "validator_kms_key_id" {
  type        = string
  description = "KMS CMK ARN used to encrypt validator temp artifacts"
}
