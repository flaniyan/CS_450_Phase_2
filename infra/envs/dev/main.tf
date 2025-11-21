terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  backend "s3" {
    bucket         = "pkg-artifacts"
    key            = "terraform/state"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  artifacts_bucket = "pkg-artifacts"
  ddb_tables_arnmap = {
    users     = "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/users"
    tokens    = "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/tokens"
    packages  = "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/packages"
    uploads   = "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/uploads"
    downloads = "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/downloads"
    artifacts = "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/artifacts"
  }
}

# module "s3" {
#   source         = "../../modules/s3"
#   artifacts_name = var.artifacts_bucket
# }

module "ddb" {
  source = "../../modules/dynamodb"
}

module "monitoring" {
  source                = "../../modules/monitoring"
  artifacts_bucket      = local.artifacts_bucket
  validator_service_url = "http://placeholder"
  ddb_tables_arnmap     = local.ddb_tables_arnmap
}

module "iam" {
  source            = "../../modules/iam"
  artifacts_bucket  = local.artifacts_bucket
  ddb_tables_arnmap = local.ddb_tables_arnmap
}

module "ecs" {
  source            = "../../modules/ecs"
  artifacts_bucket  = local.artifacts_bucket
  image_tag         = var.image_tag
  ddb_tables_arnmap = local.ddb_tables_arnmap
  kms_key_arn       = module.monitoring.kms_key_arn
}

module "api_gateway" {
  source                = "../../modules/api-gateway"
  artifacts_bucket      = local.artifacts_bucket
  validator_service_url = module.ecs.validator_service_url
  kms_key_arn           = module.monitoring.kms_key_arn
  ddb_tables_arnmap     = local.ddb_tables_arnmap
}

# Extract ALB DNS name from the validator service URL (e.g., "http://validator-lb-xxx.elb.amazonaws.com" -> "validator-lb-xxx.elb.amazonaws.com")
module "cloudfront" {
  source       = "../../modules/cloudfront"
  alb_dns_name = replace(replace(module.ecs.validator_service_url, "http://", ""), "https://", "")
  aws_region   = var.aws_region
}

output "artifacts_bucket" { value = local.artifacts_bucket }
output "group106_policy_arn" { value = module.iam.group106_policy_arn }
output "ddb_tables" { value = local.ddb_tables_arnmap }
output "validator_service_url" { value = module.ecs.validator_service_url }
output "validator_cluster_arn" { value = module.ecs.validator_cluster_arn }
output "ecr_repository_url" { value = module.ecs.ecr_repository_url }
output "cloudfront_url" { value = module.cloudfront.cloudfront_url }
output "cloudfront_domain_name" { value = module.cloudfront.cloudfront_domain_name }
output "cloudfront_distribution_id" { value = module.cloudfront.cloudfront_distribution_id }