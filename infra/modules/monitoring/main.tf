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

# module "s3" {
#   source         = "../../modules/s3"
#   artifacts_name = var.artifacts_bucket
# }

# module "ddb" {
#   source = "../../modules/dynamodb"
# }

module "iam" {
  source            = "../../modules/iam"
  artifacts_bucket  = "pkg-artifacts"
  ddb_tables_arnmap = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
}

module "ecs" {
  source            = "../../modules/ecs"
  artifacts_bucket  = "pkg-artifacts"
  ddb_tables_arnmap = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
}

module "api_gateway" {
  source              = "../../modules/api-gateway"
  artifacts_bucket    = "pkg-artifacts"
  ddb_tables_arnmap   = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
  validator_service_url = module.ecs.validator_service_url
}

module "monitoring" {
  source              = "../../modules/monitoring"
  artifacts_bucket    = "pkg-artifacts"
  ddb_tables_arnmap   = {
    users     = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
    tokens    = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
    packages  = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
    uploads   = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
    downloads = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  }
  validator_service_url = module.ecs.validator_service_url
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
output "api_gateway_url" { value = module.api_gateway.api_gateway_url }
output "kms_key_arn" { value = module.monitoring.kms_key_arn }
output "jwt_secret_arn" { value = module.monitoring.jwt_secret_arn }
output "dashboard_url" { value = module.monitoring.dashboard_url }

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

module "ecs" {
  source            = "../../modules/ecs"
  artifacts_bucket  = module.s3.artifacts_bucket
  ddb_tables_arnmap = module.ddb.arn_map
}

output "artifacts_bucket" { value = module.s3.artifacts_bucket }
output "group106_policy_arn" { value = module.iam.group106_policy_arn }
output "ddb_tables" { value = module.ddb.arn_map }
output "validator_service_url" { value = module.ecs.validator_service_url }
output "validator_cluster_arn" { value = module.ecs.validator_cluster_arn }