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

# module "s3" {
#   source         = "../../modules/s3"
#   artifacts_name = var.artifacts_bucket
# }

# module "ddb" {
#   source = "../../modules/dynamodb"
# }

module "iam" {
  source           = "../../modules/iam"
  artifacts_bucket = "pkg-artifacts"
  ddb_tables_arnmap = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
}

module "ecs" {
  source                  = "../../modules/ecs"
  artifacts_bucket        = "pkg-artifacts"
  image_tag               = var.image_tag
  validator_task_role_arn = aws_iam_role.validator_task.arn
  jwt_secret_arn          = var.jwt_secret_arn
  ddb_tables_arnmap = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
}

module "monitoring" {
  source                = "../../modules/monitoring"
  artifacts_bucket      = "pkg-artifacts"
  validator_service_url = module.ecs.validator_service_url
  ddb_tables_arnmap = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
}

module "api_gateway" {
  source                = "../../modules/api-gateway"
  artifacts_bucket      = "pkg-artifacts"
  validator_service_url = module.ecs.validator_service_url
  kms_key_arn           = module.monitoring.kms_key_arn
  ddb_tables_arnmap = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
}

output "artifacts_bucket" { value = "pkg-artifacts" }
output "group106_policy_arn" { value = module.iam.group106_policy_arn }
output "ddb_tables" {
  value = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
}
output "validator_service_url" { value = module.ecs.validator_service_url }
output "validator_cluster_arn" { value = module.ecs.validator_cluster_arn }
output "ecr_repository_url" { value = module.ecs.ecr_repository_url }
