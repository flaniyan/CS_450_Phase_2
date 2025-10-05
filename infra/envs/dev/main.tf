terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "s3" {
  source         = "../../modules/s3"
  artifacts_name = var.artifacts_bucket
}

module "ddb" {
  source = "../../modules/dynamodb"
}

module "iam" {
  source            = "../../modules/iam"
  artifacts_bucket  = module.s3.artifacts_bucket
  ddb_tables_arnmap = module.ddb.arn_map
}

output "artifacts_bucket" { value = module.s3.artifacts_bucket }
output "group106_policy_arn" { value = module.iam.group106_policy_arn }
output "ddb_tables" { value = module.ddb.arn_map }
