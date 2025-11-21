variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "validator_service_url" { type = string }
variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for S3 encryption"
}

# API Gateway
resource "aws_api_gateway_rest_api" "main_api" {
  name = "acme-api"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name        = "acme-api"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

# ===== ROOT LEVEL RESOURCES =====

# GET / (root path)
resource "aws_api_gateway_method" "root_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "root_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_rest_api.main_api.root_resource_id
  http_method = aws_api_gateway_method.root_get.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "root_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_rest_api.main_api.root_resource_id
  http_method = aws_api_gateway_method.root_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Content-Type" = true
  }
}

resource "aws_api_gateway_integration_response" "root_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_rest_api.main_api.root_resource_id
  http_method = aws_api_gateway_method.root_get.http_method
  status_code = aws_api_gateway_method_response.root_get_200.status_code

  depends_on = [aws_api_gateway_integration.root_get]

  response_parameters = {
    "method.response.header.Content-Type" = "'application/json'"
  }

  response_templates = {
    "application/json" = jsonencode({
      message = "ACME Registry API"
      version = "1.0.0"
      endpoints = {
        health                  = "/health"
        health_components       = "/health/components"
        authenticate            = "/authenticate"
        artifacts               = "/artifacts"
        reset                   = "/reset"
        artifact_by_type_and_id = "/artifact/{artifact_type}/{id}"
        artifact_by_type        = "/artifact/{artifact_type}"
        artifact_by_name        = "/artifact/byName/{name}"
        artifact_by_regex       = "/artifact/byRegEx"
        artifact_cost           = "/artifact/{artifact_type}/{id}/cost"
        artifact_audit          = "/artifact/{artifact_type}/{id}/audit"
        model_rate              = "/artifact/model/{id}/rate"
        model_lineage           = "/artifact/model/{id}/lineage"
        model_license_check     = "/artifact/model/{id}/license-check"
        model_download          = "/artifact/model/{id}/download"
        artifact_ingest         = "/artifact/ingest"
        artifact_directory      = "/artifact/directory"
        upload                  = "/upload"
        admin                   = "/admin"
        directory               = "/directory"
      }
    })
  }
}

# NOTE: The /{proxy+} resource exists in AWS but should be removed
# as it intercepts requests before specific routes can match.
# To remove it:
# 1. Delete it manually from AWS Console, OR
# 2. Import it: terraform import 'module.api_gateway.aws_api_gateway_resource.proxy[0]' <rest_api_id>/<resource_id>
# 3. Then Terraform will delete it on next apply
# resource "aws_api_gateway_resource" "proxy" {
#   count       = 0  # Set to 0 to remove, or 1 to import then remove
#   rest_api_id = aws_api_gateway_rest_api.main_api.id
#   parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
#   path_part   = "{proxy+}"
# }

resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_resource" "health_components" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.health.id
  path_part   = "components"
}

resource "aws_api_gateway_resource" "artifacts" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "artifacts"
}

# /artifacts/{artifact_type} (plural - matches OpenAPI spec)
resource "aws_api_gateway_resource" "artifacts_type" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifacts.id
  path_part   = "{artifact_type}"
}

# /artifacts/{artifact_type}/{id} (plural - matches OpenAPI spec)
resource "aws_api_gateway_resource" "artifacts_type_id" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifacts_type.id
  path_part   = "{id}"
}

resource "aws_api_gateway_resource" "reset" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "reset"
}

resource "aws_api_gateway_resource" "authenticate" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "authenticate"
}

resource "aws_api_gateway_resource" "package" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "package"
}

resource "aws_api_gateway_resource" "package_id" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.package.id
  path_part   = "{id}"
}

resource "aws_api_gateway_resource" "package_id_rate" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.package_id.id
  path_part   = "rate"
}

resource "aws_api_gateway_resource" "tracks" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "tracks"
}

resource "aws_api_gateway_resource" "admin" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "admin"
}

resource "aws_api_gateway_resource" "directory" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "directory"
}

resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "upload"
}

# ===== /artifact RESOURCES =====

resource "aws_api_gateway_resource" "artifact" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "artifact"
}

# /artifact/{artifact_type}
resource "aws_api_gateway_resource" "artifact_type" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact.id
  path_part   = "{artifact_type}"
}

# /artifact/{artifact_type}/{id}
resource "aws_api_gateway_resource" "artifact_type_id" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_type.id
  path_part   = "{id}"
}

# /artifact/{artifact_type}/{id}/cost
resource "aws_api_gateway_resource" "artifact_type_id_cost" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_type_id.id
  path_part   = "cost"
}

# /artifact/{artifact_type}/{id}/audit
resource "aws_api_gateway_resource" "artifact_type_id_audit" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_type_id.id
  path_part   = "audit"
}

# /artifact/model/{id}/rate
resource "aws_api_gateway_resource" "artifact_model" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact.id
  path_part   = "model"
}

resource "aws_api_gateway_resource" "artifact_model_id" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_model.id
  path_part   = "{id}"
}

resource "aws_api_gateway_resource" "artifact_model_id_rate" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_model_id.id
  path_part   = "rate"
}

# /artifact/model/{id}/lineage
resource "aws_api_gateway_resource" "artifact_model_id_lineage" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_model_id.id
  path_part   = "lineage"
}

# /artifact/model/{id}/license-check
resource "aws_api_gateway_resource" "artifact_model_id_license_check" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_model_id.id
  path_part   = "license-check"
}

# /artifact/model/{id}/upload
resource "aws_api_gateway_resource" "artifact_model_id_upload" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_model_id.id
  path_part   = "upload"
}

# /artifact/model/{id}/download
resource "aws_api_gateway_resource" "artifact_model_id_download" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_model_id.id
  path_part   = "download"
}

# /artifact/ingest
resource "aws_api_gateway_resource" "artifact_ingest" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact.id
  path_part   = "ingest"
}

# /artifact/directory
resource "aws_api_gateway_resource" "artifact_directory" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact.id
  path_part   = "directory"
}

# /artifact/byName/{name}
resource "aws_api_gateway_resource" "artifact_byname" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact.id
  path_part   = "byName"
}

resource "aws_api_gateway_resource" "artifact_byname_name" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_byname.id
  path_part   = "{proxy+}"
}

# /artifact/byRegEx
resource "aws_api_gateway_resource" "artifact_byregex" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact.id
  path_part   = "byRegEx"
}

# ===== METHODS AND INTEGRATIONS =====

# GET /artifact
resource "aws_api_gateway_method" "artifact_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "artifact_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact.id
  http_method = aws_api_gateway_method.artifact_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact"
}

# GET /health
resource "aws_api_gateway_method" "health_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.health.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "health_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/health"
}

# Method responses for GET /health
resource "aws_api_gateway_method_response" "health_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for GET /health
resource "aws_api_gateway_integration_response" "health_get_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.health.id
  http_method       = aws_api_gateway_method.health_get.http_method
  status_code       = aws_api_gateway_method_response.health_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.health_get,
    aws_api_gateway_method_response.health_get_200,
  ]
}

# GET /health/components
resource "aws_api_gateway_method" "health_components_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.health_components.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.querystring.windowMinutes"   = false
    "method.request.querystring.includeTimeline" = false
  }
}

resource "aws_api_gateway_integration" "health_components_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.health_components.id
  http_method = aws_api_gateway_method.health_components_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/health/components"

  request_parameters = {
    "integration.request.querystring.windowMinutes"   = "method.request.querystring.windowMinutes"
    "integration.request.querystring.includeTimeline" = "method.request.querystring.includeTimeline"
  }
}

# Method responses for GET /health/components
resource "aws_api_gateway_method_response" "health_components_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.health_components.id
  http_method = aws_api_gateway_method.health_components_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for GET /health/components
resource "aws_api_gateway_integration_response" "health_components_get_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.health_components.id
  http_method       = aws_api_gateway_method.health_components_get.http_method
  status_code       = aws_api_gateway_method_response.health_components_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.health_components_get,
    aws_api_gateway_method_response.health_components_get_200,
  ]
}

# POST /artifacts
resource "aws_api_gateway_method" "artifacts_post" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifacts.id
  http_method   = "POST"
  authorization = "NONE"

  request_parameters = {
    "method.request.header.X-Authorization" = true
    "method.request.querystring.offset"     = false
  }
}

resource "aws_api_gateway_integration" "artifacts_post" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts.id
  http_method = aws_api_gateway_method.artifacts_post.http_method

  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifacts"

  request_parameters = {
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
    "integration.request.querystring.offset"     = "method.request.querystring.offset"
  }
}

# Method responses for POST /artifacts
resource "aws_api_gateway_method_response" "artifacts_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts.id
  http_method = aws_api_gateway_method.artifacts_post.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.offset" = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_post_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts.id
  http_method = aws_api_gateway_method.artifacts_post.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_post_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts.id
  http_method = aws_api_gateway_method.artifacts_post.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_post_413" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts.id
  http_method = aws_api_gateway_method.artifacts_post.http_method
  status_code = "413"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for POST /artifacts
resource "aws_api_gateway_integration_response" "artifacts_post_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts.id
  http_method       = aws_api_gateway_method.artifacts_post.http_method
  status_code       = aws_api_gateway_method_response.artifacts_post_200.status_code
  selection_pattern = "200"

  response_parameters = {
    "method.response.header.offset" = "integration.response.header.offset"
  }

  depends_on = [
    aws_api_gateway_integration.artifacts_post,
    aws_api_gateway_method_response.artifacts_post_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_post_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts.id
  http_method       = aws_api_gateway_method.artifacts_post.http_method
  status_code       = aws_api_gateway_method_response.artifacts_post_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifacts_post,
    aws_api_gateway_method_response.artifacts_post_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_post_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts.id
  http_method       = aws_api_gateway_method.artifacts_post.http_method
  status_code       = aws_api_gateway_method_response.artifacts_post_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifacts_post,
    aws_api_gateway_method_response.artifacts_post_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_post_413" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts.id
  http_method       = aws_api_gateway_method.artifacts_post.http_method
  status_code       = aws_api_gateway_method_response.artifacts_post_413.status_code
  selection_pattern = "413"

  depends_on = [
    aws_api_gateway_integration.artifacts_post,
    aws_api_gateway_method_response.artifacts_post_413,
  ]
}

# DELETE /reset (matches spec)
resource "aws_api_gateway_method" "reset_delete" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.reset.id
  http_method   = "DELETE"
  authorization = "NONE"

  request_parameters = {
    "method.request.header.X-Authorization" = false
  }
}

resource "aws_api_gateway_integration" "reset_delete" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.reset.id
  http_method = aws_api_gateway_method.reset_delete.http_method

  integration_http_method = "DELETE"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/reset"
}

resource "aws_api_gateway_method_response" "reset_delete_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.reset.id
  http_method = aws_api_gateway_method.reset_delete.http_method
  status_code = "200"
}

resource "aws_api_gateway_integration_response" "reset_delete_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.reset.id
  http_method = aws_api_gateway_method.reset_delete.http_method
  status_code = aws_api_gateway_method_response.reset_delete_200.status_code

  depends_on = [aws_api_gateway_integration.reset_delete]
}

# Method responses for DELETE /reset
resource "aws_api_gateway_method_response" "reset_delete_401" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.reset.id
  http_method = aws_api_gateway_method.reset_delete.http_method
  status_code = "401"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "reset_delete_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.reset.id
  http_method = aws_api_gateway_method.reset_delete.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for DELETE /reset
resource "aws_api_gateway_integration_response" "reset_delete_401" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.reset.id
  http_method       = aws_api_gateway_method.reset_delete.http_method
  status_code       = aws_api_gateway_method_response.reset_delete_401.status_code
  selection_pattern = "401"

  depends_on = [
    aws_api_gateway_integration.reset_delete,
    aws_api_gateway_method_response.reset_delete_401,
  ]
}

resource "aws_api_gateway_integration_response" "reset_delete_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.reset.id
  http_method       = aws_api_gateway_method.reset_delete.http_method
  status_code       = aws_api_gateway_method_response.reset_delete_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.reset_delete,
    aws_api_gateway_method_response.reset_delete_403,
  ]
}

# PUT /authenticate
resource "aws_api_gateway_method" "authenticate_put" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.authenticate.id
  http_method   = "PUT"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "authenticate_put" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.authenticate.id
  http_method = aws_api_gateway_method.authenticate_put.http_method

  integration_http_method = "PUT"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/authenticate"
}

# Method responses for PUT /authenticate
resource "aws_api_gateway_method_response" "authenticate_put_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.authenticate.id
  http_method = aws_api_gateway_method.authenticate_put.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "authenticate_put_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.authenticate.id
  http_method = aws_api_gateway_method.authenticate_put.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for PUT /authenticate
resource "aws_api_gateway_integration_response" "authenticate_put_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.authenticate.id
  http_method       = aws_api_gateway_method.authenticate_put.http_method
  status_code       = aws_api_gateway_method_response.authenticate_put_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.authenticate_put,
    aws_api_gateway_method_response.authenticate_put_200,
  ]
}

resource "aws_api_gateway_integration_response" "authenticate_put_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.authenticate.id
  http_method       = aws_api_gateway_method.authenticate_put.http_method
  status_code       = aws_api_gateway_method_response.authenticate_put_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.authenticate_put,
    aws_api_gateway_method_response.authenticate_put_400,
  ]
}

# GET /package/{id}
resource "aws_api_gateway_method" "package_id_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.package_id.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "package_id_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id.id
  http_method = aws_api_gateway_method.package_id_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP"
  uri                     = "${var.validator_service_url}/package/{id}"

  request_parameters = {
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }

  passthrough_behavior = "WHEN_NO_MATCH"
}

resource "aws_api_gateway_method_response" "package_id_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id.id
  http_method = aws_api_gateway_method.package_id_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "package_id_get_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id.id
  http_method = aws_api_gateway_method.package_id_get.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "package_id_get_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id.id
  http_method = aws_api_gateway_method.package_id_get.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "package_id_get_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id.id
  http_method = aws_api_gateway_method.package_id_get.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "package_id_get_500" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id.id
  http_method = aws_api_gateway_method.package_id_get.http_method
  status_code = "500"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "package_id_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id.id
  http_method = aws_api_gateway_method.package_id_get.http_method
  status_code = aws_api_gateway_method_response.package_id_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.package_id_get,
    aws_api_gateway_method_response.package_id_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "package_id_get_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.package_id.id
  http_method       = aws_api_gateway_method.package_id_get.http_method
  status_code       = aws_api_gateway_method_response.package_id_get_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.package_id_get,
    aws_api_gateway_method_response.package_id_get_400,
  ]
}

resource "aws_api_gateway_integration_response" "package_id_get_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.package_id.id
  http_method       = aws_api_gateway_method.package_id_get.http_method
  status_code       = aws_api_gateway_method_response.package_id_get_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.package_id_get,
    aws_api_gateway_method_response.package_id_get_403,
  ]
}

resource "aws_api_gateway_integration_response" "package_id_get_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.package_id.id
  http_method       = aws_api_gateway_method.package_id_get.http_method
  status_code       = aws_api_gateway_method_response.package_id_get_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.package_id_get,
    aws_api_gateway_method_response.package_id_get_404,
  ]
}

resource "aws_api_gateway_integration_response" "package_id_get_500" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.package_id.id
  http_method       = aws_api_gateway_method.package_id_get.http_method
  status_code       = aws_api_gateway_method_response.package_id_get_500.status_code
  selection_pattern = "500"

  depends_on = [
    aws_api_gateway_integration.package_id_get,
    aws_api_gateway_method_response.package_id_get_500,
  ]
}

# GET /tracks
resource "aws_api_gateway_method" "tracks_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.tracks.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "tracks_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.tracks.id
  http_method = aws_api_gateway_method.tracks_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/tracks"
}

# Method responses for GET /tracks
resource "aws_api_gateway_method_response" "tracks_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.tracks.id
  http_method = aws_api_gateway_method.tracks_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "tracks_get_500" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.tracks.id
  http_method = aws_api_gateway_method.tracks_get.http_method
  status_code = "500"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for GET /tracks
resource "aws_api_gateway_integration_response" "tracks_get_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.tracks.id
  http_method       = aws_api_gateway_method.tracks_get.http_method
  status_code       = aws_api_gateway_method_response.tracks_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.tracks_get,
    aws_api_gateway_method_response.tracks_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "tracks_get_500" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.tracks.id
  http_method       = aws_api_gateway_method.tracks_get.http_method
  status_code       = aws_api_gateway_method_response.tracks_get_500.status_code
  selection_pattern = "500"

  depends_on = [
    aws_api_gateway_integration.tracks_get,
    aws_api_gateway_method_response.tracks_get_500,
  ]
}

# GET /admin
resource "aws_api_gateway_method" "admin_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.admin.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "admin_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.admin.id
  http_method = aws_api_gateway_method.admin_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/admin"
}

# GET /directory
resource "aws_api_gateway_method" "directory_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.directory.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "directory_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.directory.id
  http_method = aws_api_gateway_method.directory_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/directory"
}


# GET /upload
resource "aws_api_gateway_method" "upload_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.upload.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "upload_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.upload.id
  http_method = aws_api_gateway_method.upload_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/upload"
}

# POST /upload
resource "aws_api_gateway_method" "upload_post" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.upload.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "upload_post" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.upload.id
  http_method = aws_api_gateway_method.upload_post.http_method

  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/upload"

  content_handling     = "CONVERT_TO_BINARY"
  passthrough_behavior = "WHEN_NO_MATCH"
}

# OPTIONS /admin
resource "aws_api_gateway_method" "admin_options" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.admin.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "admin_options" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.admin.id
  http_method = aws_api_gateway_method.admin_options.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "admin_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.admin.id
  http_method = aws_api_gateway_method.admin_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "admin_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.admin.id
  http_method = aws_api_gateway_method.admin_options.http_method
  status_code = aws_api_gateway_method_response.admin_options_200.status_code

  depends_on = [aws_api_gateway_integration.admin_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS /directory
resource "aws_api_gateway_method" "directory_options" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.directory.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "directory_options" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.directory.id
  http_method = aws_api_gateway_method.directory_options.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "directory_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.directory.id
  http_method = aws_api_gateway_method.directory_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "directory_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.directory.id
  http_method = aws_api_gateway_method.directory_options.http_method
  status_code = aws_api_gateway_method_response.directory_options_200.status_code

  depends_on = [aws_api_gateway_integration.directory_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}


# OPTIONS /upload
resource "aws_api_gateway_method" "upload_options" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.upload.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "upload_options" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.upload.id
  http_method = aws_api_gateway_method.upload_options.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "upload_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.upload.id
  http_method = aws_api_gateway_method.upload_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "upload_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.upload.id
  http_method = aws_api_gateway_method.upload_options.http_method
  status_code = aws_api_gateway_method_response.upload_options_200.status_code

  depends_on = [aws_api_gateway_integration.upload_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# GET /artifact/{artifact_type}
resource "aws_api_gateway_method" "artifact_type_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_type.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_type_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/{artifact_type}"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# POST /artifact/{artifact_type}
resource "aws_api_gateway_method" "artifact_type_post" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_type.id
  http_method   = "POST"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_type_post" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_post.http_method

  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/{artifact_type}"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# Method responses for POST /artifact/{artifact_type}
resource "aws_api_gateway_method_response" "artifact_type_post_201" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_post.http_method
  status_code = "201"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_post_202" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_post.http_method
  status_code = "202"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_post_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_post.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_post_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_post.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_post_409" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_post.http_method
  status_code = "409"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_post_424" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_post.http_method
  status_code = "424"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for POST /artifact/{artifact_type}
resource "aws_api_gateway_integration_response" "artifact_type_post_201" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type.id
  http_method       = aws_api_gateway_method.artifact_type_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_post_201.status_code
  selection_pattern = "201"

  depends_on = [
    aws_api_gateway_integration.artifact_type_post,
    aws_api_gateway_method_response.artifact_type_post_201,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_post_202" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type.id
  http_method       = aws_api_gateway_method.artifact_type_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_post_202.status_code
  selection_pattern = "202"

  depends_on = [
    aws_api_gateway_integration.artifact_type_post,
    aws_api_gateway_method_response.artifact_type_post_202,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_post_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type.id
  http_method       = aws_api_gateway_method.artifact_type_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_post_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifact_type_post,
    aws_api_gateway_method_response.artifact_type_post_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_post_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type.id
  http_method       = aws_api_gateway_method.artifact_type_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_post_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifact_type_post,
    aws_api_gateway_method_response.artifact_type_post_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_post_409" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type.id
  http_method       = aws_api_gateway_method.artifact_type_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_post_409.status_code
  selection_pattern = "409"

  depends_on = [
    aws_api_gateway_integration.artifact_type_post,
    aws_api_gateway_method_response.artifact_type_post_409,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_post_424" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type.id
  http_method       = aws_api_gateway_method.artifact_type_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_post_424.status_code
  selection_pattern = "424"

  depends_on = [
    aws_api_gateway_integration.artifact_type_post,
    aws_api_gateway_method_response.artifact_type_post_424,
  ]
}

# GET /artifacts/{artifact_type}/{id} (plural - matches OpenAPI spec)
resource "aws_api_gateway_method" "artifacts_type_id_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifacts_type_id.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifacts_type_id_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifacts/{artifact_type}/{id}"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# PUT /artifacts/{artifact_type}/{id} (plural - matches OpenAPI spec)
resource "aws_api_gateway_method" "artifacts_type_id_put" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifacts_type_id.id
  http_method   = "PUT"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifacts_type_id_put" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_put.http_method

  integration_http_method = "PUT"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifacts/{artifact_type}/{id}"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# Method responses for PUT /artifacts/{artifact_type}/{id}
resource "aws_api_gateway_method_response" "artifacts_type_id_put_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_put.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_put_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_put.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_put_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_put.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_put_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_put.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for PUT /artifacts/{artifact_type}/{id}
resource "aws_api_gateway_integration_response" "artifacts_type_id_put_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_put.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_put_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_put,
    aws_api_gateway_method_response.artifacts_type_id_put_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_put_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_put.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_put_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_put,
    aws_api_gateway_method_response.artifacts_type_id_put_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_put_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_put.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_put_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_put,
    aws_api_gateway_method_response.artifacts_type_id_put_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_put_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_put.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_put_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_put,
    aws_api_gateway_method_response.artifacts_type_id_put_404,
  ]
}

# DELETE /artifacts/{artifact_type}/{id} (plural - matches OpenAPI spec)
resource "aws_api_gateway_method" "artifacts_type_id_delete" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifacts_type_id.id
  http_method   = "DELETE"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifacts_type_id_delete" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_delete.http_method

  integration_http_method = "DELETE"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifacts/{artifact_type}/{id}"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# Method responses for DELETE /artifacts/{artifact_type}/{id}
resource "aws_api_gateway_method_response" "artifacts_type_id_delete_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_delete.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_delete_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_delete.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_delete_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_delete.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_delete_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_delete.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for DELETE /artifacts/{artifact_type}/{id}
resource "aws_api_gateway_integration_response" "artifacts_type_id_delete_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_delete.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_delete_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_delete,
    aws_api_gateway_method_response.artifacts_type_id_delete_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_delete_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_delete.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_delete_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_delete,
    aws_api_gateway_method_response.artifacts_type_id_delete_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_delete_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_delete.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_delete_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_delete,
    aws_api_gateway_method_response.artifacts_type_id_delete_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_delete_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_delete.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_delete_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_delete,
    aws_api_gateway_method_response.artifacts_type_id_delete_404,
  ]
}

# Method responses for GET /artifacts/{artifact_type}/{id}
resource "aws_api_gateway_method_response" "artifacts_type_id_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_get_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_get.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_get_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_get.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifacts_type_id_get_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts_type_id.id
  http_method = aws_api_gateway_method.artifacts_type_id_get.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for GET /artifacts/{artifact_type}/{id}
resource "aws_api_gateway_integration_response" "artifacts_type_id_get_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_get.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_get,
    aws_api_gateway_method_response.artifacts_type_id_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_get_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_get.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_get_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_get,
    aws_api_gateway_method_response.artifacts_type_id_get_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_get_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_get.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_get_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_get,
    aws_api_gateway_method_response.artifacts_type_id_get_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifacts_type_id_get_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifacts_type_id.id
  http_method       = aws_api_gateway_method.artifacts_type_id_get.http_method
  status_code       = aws_api_gateway_method_response.artifacts_type_id_get_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifacts_type_id_get,
    aws_api_gateway_method_response.artifacts_type_id_get_404,
  ]
}

# GET /artifact/{artifact_type}/{id} (singular - also supported by backend)
resource "aws_api_gateway_method" "artifact_type_id_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_type_id.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_type_id_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id.id
  http_method = aws_api_gateway_method.artifact_type_id_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/{artifact_type}/{id}"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# GET /artifact/{artifact_type}/{id}/cost
resource "aws_api_gateway_method" "artifact_type_id_cost_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
    "method.request.querystring.dependency" = false
  }
}

resource "aws_api_gateway_integration" "artifact_type_id_cost_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method = aws_api_gateway_method.artifact_type_id_cost_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/{artifact_type}/{id}/cost"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
    "integration.request.querystring.dependency" = "method.request.querystring.dependency"
  }
}

# Method responses for GET /artifact/{artifact_type}/{id}/cost
resource "aws_api_gateway_method_response" "artifact_type_id_cost_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_id_cost_get_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_id_cost_get_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_id_cost_get_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_id_cost_get_500" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code = "500"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for GET /artifact/{artifact_type}/{id}/cost
resource "aws_api_gateway_integration_response" "artifact_type_id_cost_get_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method       = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_cost_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_cost_get,
    aws_api_gateway_method_response.artifact_type_id_cost_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_id_cost_get_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method       = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_cost_get_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_cost_get,
    aws_api_gateway_method_response.artifact_type_id_cost_get_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_id_cost_get_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method       = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_cost_get_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_cost_get,
    aws_api_gateway_method_response.artifact_type_id_cost_get_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_id_cost_get_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method       = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_cost_get_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_cost_get,
    aws_api_gateway_method_response.artifact_type_id_cost_get_404,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_id_cost_get_500" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_cost.id
  http_method       = aws_api_gateway_method.artifact_type_id_cost_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_cost_get_500.status_code
  selection_pattern = "500"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_cost_get,
    aws_api_gateway_method_response.artifact_type_id_cost_get_500,
  ]
}

# GET /artifact/{artifact_type}/{id}/audit
resource "aws_api_gateway_method" "artifact_type_id_audit_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_type_id_audit_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method = aws_api_gateway_method.artifact_type_id_audit_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/{artifact_type}/{id}/audit"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# Method responses for GET /artifact/{artifact_type}/{id}/audit
resource "aws_api_gateway_method_response" "artifact_type_id_audit_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method = aws_api_gateway_method.artifact_type_id_audit_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_id_audit_get_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method = aws_api_gateway_method.artifact_type_id_audit_get.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_id_audit_get_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method = aws_api_gateway_method.artifact_type_id_audit_get.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_type_id_audit_get_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method = aws_api_gateway_method.artifact_type_id_audit_get.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for GET /artifact/{artifact_type}/{id}/audit
resource "aws_api_gateway_integration_response" "artifact_type_id_audit_get_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method       = aws_api_gateway_method.artifact_type_id_audit_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_audit_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_audit_get,
    aws_api_gateway_method_response.artifact_type_id_audit_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_id_audit_get_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method       = aws_api_gateway_method.artifact_type_id_audit_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_audit_get_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_audit_get,
    aws_api_gateway_method_response.artifact_type_id_audit_get_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_id_audit_get_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method       = aws_api_gateway_method.artifact_type_id_audit_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_audit_get_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_audit_get,
    aws_api_gateway_method_response.artifact_type_id_audit_get_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_type_id_audit_get_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_type_id_audit.id
  http_method       = aws_api_gateway_method.artifact_type_id_audit_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_type_id_audit_get_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifact_type_id_audit_get,
    aws_api_gateway_method_response.artifact_type_id_audit_get_404,
  ]
}

# GET /artifact/model/{id}/rate
resource "aws_api_gateway_method" "artifact_model_id_rate_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_model_id_rate_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method = aws_api_gateway_method.artifact_model_id_rate_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP"
  uri                     = "${var.validator_service_url}/artifact/model/{id}/rate"

  request_parameters = {
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }

  passthrough_behavior = "WHEN_NO_MATCH"
}

# Method responses for /artifact/model/{id}/rate
resource "aws_api_gateway_method_response" "artifact_model_id_rate_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_rate_get_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_rate_get_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_rate_get_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_rate_get_500" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code = "500"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for /artifact/model/{id}/rate
resource "aws_api_gateway_integration_response" "artifact_model_id_rate_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code = aws_api_gateway_method_response.artifact_model_id_rate_get_200.status_code

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_rate_get,
    aws_api_gateway_method_response.artifact_model_id_rate_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_rate_get_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method       = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_rate_get_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_rate_get,
    aws_api_gateway_method_response.artifact_model_id_rate_get_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_rate_get_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method       = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_rate_get_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_rate_get,
    aws_api_gateway_method_response.artifact_model_id_rate_get_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_rate_get_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method       = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_rate_get_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_rate_get,
    aws_api_gateway_method_response.artifact_model_id_rate_get_404,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_rate_get_500" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_rate.id
  http_method       = aws_api_gateway_method.artifact_model_id_rate_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_rate_get_500.status_code
  selection_pattern = "500"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_rate_get,
    aws_api_gateway_method_response.artifact_model_id_rate_get_500,
  ]
}

# GET /package/{id}/rate
resource "aws_api_gateway_method" "package_id_rate_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.package_id_rate.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "package_id_rate_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id_rate.id
  http_method = aws_api_gateway_method.package_id_rate_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP"
  uri                     = "${var.validator_service_url}/package/{id}/rate"

  request_parameters = {
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }

  passthrough_behavior = "WHEN_NO_MATCH"
}

# Method responses for /package/{id}/rate
resource "aws_api_gateway_method_response" "package_id_rate_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id_rate.id
  http_method = aws_api_gateway_method.package_id_rate_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "package_id_rate_get_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id_rate.id
  http_method = aws_api_gateway_method.package_id_rate_get.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "package_id_rate_get_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id_rate.id
  http_method = aws_api_gateway_method.package_id_rate_get.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "package_id_rate_get_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id_rate.id
  http_method = aws_api_gateway_method.package_id_rate_get.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "package_id_rate_get_500" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id_rate.id
  http_method = aws_api_gateway_method.package_id_rate_get.http_method
  status_code = "500"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for /package/{id}/rate
resource "aws_api_gateway_integration_response" "package_id_rate_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.package_id_rate.id
  http_method = aws_api_gateway_method.package_id_rate_get.http_method
  status_code = aws_api_gateway_method_response.package_id_rate_get_200.status_code

  depends_on = [
    aws_api_gateway_integration.package_id_rate_get,
    aws_api_gateway_method_response.package_id_rate_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "package_id_rate_get_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.package_id_rate.id
  http_method       = aws_api_gateway_method.package_id_rate_get.http_method
  status_code       = aws_api_gateway_method_response.package_id_rate_get_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.package_id_rate_get,
    aws_api_gateway_method_response.package_id_rate_get_400,
  ]
}

resource "aws_api_gateway_integration_response" "package_id_rate_get_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.package_id_rate.id
  http_method       = aws_api_gateway_method.package_id_rate_get.http_method
  status_code       = aws_api_gateway_method_response.package_id_rate_get_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.package_id_rate_get,
    aws_api_gateway_method_response.package_id_rate_get_403,
  ]
}

resource "aws_api_gateway_integration_response" "package_id_rate_get_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.package_id_rate.id
  http_method       = aws_api_gateway_method.package_id_rate_get.http_method
  status_code       = aws_api_gateway_method_response.package_id_rate_get_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.package_id_rate_get,
    aws_api_gateway_method_response.package_id_rate_get_404,
  ]
}

resource "aws_api_gateway_integration_response" "package_id_rate_get_500" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.package_id_rate.id
  http_method       = aws_api_gateway_method.package_id_rate_get.http_method
  status_code       = aws_api_gateway_method_response.package_id_rate_get_500.status_code
  selection_pattern = "500"

  depends_on = [
    aws_api_gateway_integration.package_id_rate_get,
    aws_api_gateway_method_response.package_id_rate_get_500,
  ]
}

# GET /artifact/model/{id}/lineage
resource "aws_api_gateway_method" "artifact_model_id_lineage_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_model_id_lineage_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method = aws_api_gateway_method.artifact_model_id_lineage_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/model/{id}/lineage"

  request_parameters = {
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# Method responses for GET /artifact/model/{id}/lineage
resource "aws_api_gateway_method_response" "artifact_model_id_lineage_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method = aws_api_gateway_method.artifact_model_id_lineage_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_lineage_get_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method = aws_api_gateway_method.artifact_model_id_lineage_get.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_lineage_get_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method = aws_api_gateway_method.artifact_model_id_lineage_get.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_lineage_get_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method = aws_api_gateway_method.artifact_model_id_lineage_get.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for GET /artifact/model/{id}/lineage
resource "aws_api_gateway_integration_response" "artifact_model_id_lineage_get_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method       = aws_api_gateway_method.artifact_model_id_lineage_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_lineage_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_lineage_get,
    aws_api_gateway_method_response.artifact_model_id_lineage_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_lineage_get_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method       = aws_api_gateway_method.artifact_model_id_lineage_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_lineage_get_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_lineage_get,
    aws_api_gateway_method_response.artifact_model_id_lineage_get_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_lineage_get_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method       = aws_api_gateway_method.artifact_model_id_lineage_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_lineage_get_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_lineage_get,
    aws_api_gateway_method_response.artifact_model_id_lineage_get_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_lineage_get_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_lineage.id
  http_method       = aws_api_gateway_method.artifact_model_id_lineage_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_lineage_get_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_lineage_get,
    aws_api_gateway_method_response.artifact_model_id_lineage_get_404,
  ]
}

# POST /artifact/model/{id}/license-check
resource "aws_api_gateway_method" "artifact_model_id_license_check_post" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method   = "POST"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_model_id_license_check_post" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method = aws_api_gateway_method.artifact_model_id_license_check_post.http_method

  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/model/{id}/license-check"

  request_parameters = {
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# Method responses for POST /artifact/model/{id}/license-check
resource "aws_api_gateway_method_response" "artifact_model_id_license_check_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_license_check_post_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_license_check_post_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_license_check_post_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_model_id_license_check_post_502" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code = "502"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for POST /artifact/model/{id}/license-check
resource "aws_api_gateway_integration_response" "artifact_model_id_license_check_post_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method       = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_license_check_post_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_license_check_post,
    aws_api_gateway_method_response.artifact_model_id_license_check_post_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_license_check_post_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method       = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_license_check_post_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_license_check_post,
    aws_api_gateway_method_response.artifact_model_id_license_check_post_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_license_check_post_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method       = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_license_check_post_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_license_check_post,
    aws_api_gateway_method_response.artifact_model_id_license_check_post_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_license_check_post_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method       = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_license_check_post_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_license_check_post,
    aws_api_gateway_method_response.artifact_model_id_license_check_post_404,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_model_id_license_check_post_502" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_model_id_license_check.id
  http_method       = aws_api_gateway_method.artifact_model_id_license_check_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_model_id_license_check_post_502.status_code
  selection_pattern = "502"

  depends_on = [
    aws_api_gateway_integration.artifact_model_id_license_check_post,
    aws_api_gateway_method_response.artifact_model_id_license_check_post_502,
  ]
}

# POST /artifact/model/{id}/upload
resource "aws_api_gateway_method" "artifact_model_id_upload_post" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_model_id_upload.id
  http_method   = "POST"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_model_id_upload_post" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_upload.id
  http_method = aws_api_gateway_method.artifact_model_id_upload_post.http_method

  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/model/{id}/upload"

  request_parameters = {
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# GET /artifact/model/{id}/download
resource "aws_api_gateway_method" "artifact_model_id_download_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_model_id_download.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_model_id_download_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_model_id_download.id
  http_method = aws_api_gateway_method.artifact_model_id_download_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/model/{id}/download"

  request_parameters = {
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# GET /artifact/ingest
resource "aws_api_gateway_method" "artifact_ingest_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_ingest.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "artifact_ingest_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_ingest.id
  http_method = aws_api_gateway_method.artifact_ingest_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/ingest"
}

# POST /artifact/ingest
resource "aws_api_gateway_method" "artifact_ingest_post" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_ingest.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "artifact_ingest_post" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_ingest.id
  http_method = aws_api_gateway_method.artifact_ingest_post.http_method

  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/ingest"
}

# GET /artifact/directory
resource "aws_api_gateway_method" "artifact_directory_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_directory.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "artifact_directory_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_directory.id
  http_method = aws_api_gateway_method.artifact_directory_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/directory"
}

# GET /artifact/byName/{name}
resource "aws_api_gateway_method" "artifact_byname_name_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_byname_name.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy"              = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_byname_name_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byname_name.id
  http_method = aws_api_gateway_method.artifact_byname_name_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/byName/{name}"

  request_parameters = {
    "integration.request.path.name"              = "method.request.path.proxy"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# Method responses for /artifact/byName/{name}
resource "aws_api_gateway_method_response" "artifact_byname_name_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byname_name.id
  http_method = aws_api_gateway_method.artifact_byname_name_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_byname_name_get_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byname_name.id
  http_method = aws_api_gateway_method.artifact_byname_name_get.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_byname_name_get_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byname_name.id
  http_method = aws_api_gateway_method.artifact_byname_name_get.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_byname_name_get_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byname_name.id
  http_method = aws_api_gateway_method.artifact_byname_name_get.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for /artifact/byName/{name}
resource "aws_api_gateway_integration_response" "artifact_byname_name_get_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_byname_name.id
  http_method       = aws_api_gateway_method.artifact_byname_name_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_byname_name_get_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifact_byname_name_get,
    aws_api_gateway_method_response.artifact_byname_name_get_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_byname_name_get_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_byname_name.id
  http_method       = aws_api_gateway_method.artifact_byname_name_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_byname_name_get_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifact_byname_name_get,
    aws_api_gateway_method_response.artifact_byname_name_get_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_byname_name_get_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_byname_name.id
  http_method       = aws_api_gateway_method.artifact_byname_name_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_byname_name_get_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifact_byname_name_get,
    aws_api_gateway_method_response.artifact_byname_name_get_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_byname_name_get_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_byname_name.id
  http_method       = aws_api_gateway_method.artifact_byname_name_get.http_method
  status_code       = aws_api_gateway_method_response.artifact_byname_name_get_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifact_byname_name_get,
    aws_api_gateway_method_response.artifact_byname_name_get_404,
  ]
}

# POST /artifact/byRegEx
resource "aws_api_gateway_method" "artifact_byregex_post" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_byregex.id
  http_method   = "POST"
  authorization = "NONE"

  request_parameters = {
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_byregex_post" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byregex.id
  http_method = aws_api_gateway_method.artifact_byregex_post.http_method

  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/byRegEx"

  request_parameters = {
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# Method responses for POST /artifact/byRegEx
resource "aws_api_gateway_method_response" "artifact_byregex_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byregex.id
  http_method = aws_api_gateway_method.artifact_byregex_post.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_byregex_post_400" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byregex.id
  http_method = aws_api_gateway_method.artifact_byregex_post.http_method
  status_code = "400"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_byregex_post_403" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byregex.id
  http_method = aws_api_gateway_method.artifact_byregex_post.http_method
  status_code = "403"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_method_response" "artifact_byregex_post_404" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byregex.id
  http_method = aws_api_gateway_method.artifact_byregex_post.http_method
  status_code = "404"

  response_models = {
    "application/json" = "Empty"
  }
}

# Integration responses for POST /artifact/byRegEx
resource "aws_api_gateway_integration_response" "artifact_byregex_post_200" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_byregex.id
  http_method       = aws_api_gateway_method.artifact_byregex_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_byregex_post_200.status_code
  selection_pattern = "200"

  depends_on = [
    aws_api_gateway_integration.artifact_byregex_post,
    aws_api_gateway_method_response.artifact_byregex_post_200,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_byregex_post_400" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_byregex.id
  http_method       = aws_api_gateway_method.artifact_byregex_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_byregex_post_400.status_code
  selection_pattern = "400"

  depends_on = [
    aws_api_gateway_integration.artifact_byregex_post,
    aws_api_gateway_method_response.artifact_byregex_post_400,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_byregex_post_403" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_byregex.id
  http_method       = aws_api_gateway_method.artifact_byregex_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_byregex_post_403.status_code
  selection_pattern = "403"

  depends_on = [
    aws_api_gateway_integration.artifact_byregex_post,
    aws_api_gateway_method_response.artifact_byregex_post_403,
  ]
}

resource "aws_api_gateway_integration_response" "artifact_byregex_post_404" {
  rest_api_id       = aws_api_gateway_rest_api.main_api.id
  resource_id       = aws_api_gateway_resource.artifact_byregex.id
  http_method       = aws_api_gateway_method.artifact_byregex_post.http_method
  status_code       = aws_api_gateway_method_response.artifact_byregex_post_404.status_code
  selection_pattern = "404"

  depends_on = [
    aws_api_gateway_integration.artifact_byregex_post,
    aws_api_gateway_method_response.artifact_byregex_post_404,
  ]
}

# ===== CORS CONFIGURATION =====

# CORS for /artifacts
resource "aws_api_gateway_method" "artifacts_options" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifacts.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "artifacts_options" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts.id
  http_method = aws_api_gateway_method.artifacts_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "artifacts_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts.id
  http_method = aws_api_gateway_method.artifacts_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "artifacts_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifacts.id
  http_method = aws_api_gateway_method.artifacts_options.http_method
  status_code = aws_api_gateway_method_response.artifacts_options_200.status_code

  depends_on = [aws_api_gateway_integration.artifacts_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# CORS for /artifact/{artifact_type}
resource "aws_api_gateway_method" "artifact_type_options" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_type.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "artifact_type_options" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "artifact_type_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "artifact_type_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type.id
  http_method = aws_api_gateway_method.artifact_type_options.http_method
  status_code = aws_api_gateway_method_response.artifact_type_options_200.status_code

  depends_on = [aws_api_gateway_integration.artifact_type_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# CORS for /authenticate
resource "aws_api_gateway_method" "authenticate_options" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.authenticate.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "authenticate_options" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.authenticate.id
  http_method = aws_api_gateway_method.authenticate_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "authenticate_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.authenticate.id
  http_method = aws_api_gateway_method.authenticate_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "authenticate_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.authenticate.id
  http_method = aws_api_gateway_method.authenticate_options.http_method
  status_code = aws_api_gateway_method_response.authenticate_options_200.status_code

  depends_on = [aws_api_gateway_integration.authenticate_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'PUT,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# CORS for /artifact/byRegEx
resource "aws_api_gateway_method" "artifact_byregex_options" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_byregex.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "artifact_byregex_options" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byregex.id
  http_method = aws_api_gateway_method.artifact_byregex_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "artifact_byregex_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byregex.id
  http_method = aws_api_gateway_method.artifact_byregex_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "artifact_byregex_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_byregex.id
  http_method = aws_api_gateway_method.artifact_byregex_options.http_method
  status_code = aws_api_gateway_method_response.artifact_byregex_options_200.status_code

  depends_on = [aws_api_gateway_integration.artifact_byregex_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ===== API GATEWAY DEPLOYMENT =====

resource "aws_api_gateway_deployment" "main_deployment" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id

  depends_on = [
    aws_api_gateway_method.root_get,
    aws_api_gateway_integration.root_get,
    aws_api_gateway_method_response.root_get_200,
    aws_api_gateway_integration_response.root_get_200,
    aws_api_gateway_integration.health_get,
    aws_api_gateway_integration.health_components_get,
    aws_api_gateway_integration.artifact_get,
    aws_api_gateway_integration.artifacts_post,
    aws_api_gateway_integration.reset_delete,
    aws_api_gateway_integration.authenticate_put,
    aws_api_gateway_integration.package_id_get,
    aws_api_gateway_integration.tracks_get,
    aws_api_gateway_integration.admin_get,
    aws_api_gateway_integration.directory_get,
    aws_api_gateway_integration.upload_get,
    aws_api_gateway_integration.upload_post,
    aws_api_gateway_integration.admin_options,
    aws_api_gateway_integration.directory_options,
    aws_api_gateway_integration.upload_options,
    aws_api_gateway_integration.artifact_type_post,
    aws_api_gateway_integration.artifacts_type_id_get,
    aws_api_gateway_integration.artifacts_type_id_put,
    aws_api_gateway_integration.artifacts_type_id_delete,
    aws_api_gateway_integration.artifact_type_id_get,
    aws_api_gateway_integration.artifact_type_id_cost_get,
    aws_api_gateway_integration.artifact_type_id_audit_get,
    aws_api_gateway_integration.artifact_model_id_rate_get,
    aws_api_gateway_integration.package_id_rate_get,
    aws_api_gateway_integration.artifact_model_id_lineage_get,
    aws_api_gateway_integration.artifact_model_id_license_check_post,
    aws_api_gateway_integration.artifact_model_id_upload_post,
    aws_api_gateway_integration.artifact_model_id_download_get,
    aws_api_gateway_integration.artifact_ingest_get,
    aws_api_gateway_integration.artifact_ingest_post,
    aws_api_gateway_integration.artifact_directory_get,
    aws_api_gateway_integration.artifact_byname_name_get,
    aws_api_gateway_integration_response.artifact_byname_name_get_200,
    aws_api_gateway_integration_response.artifact_byname_name_get_400,
    aws_api_gateway_integration_response.artifact_byname_name_get_403,
    aws_api_gateway_integration_response.artifact_byname_name_get_404,
    aws_api_gateway_integration.artifact_byregex_post,
    aws_api_gateway_integration_response.package_id_get_200,
    aws_api_gateway_integration_response.package_id_get_400,
    aws_api_gateway_integration_response.package_id_get_403,
    aws_api_gateway_integration_response.package_id_get_404,
    aws_api_gateway_integration_response.package_id_get_500,
    aws_api_gateway_integration_response.artifact_model_id_rate_get_200,
    aws_api_gateway_integration_response.artifact_model_id_rate_get_400,
    aws_api_gateway_integration_response.artifact_model_id_rate_get_403,
    aws_api_gateway_integration_response.artifact_model_id_rate_get_404,
    aws_api_gateway_integration_response.artifact_model_id_rate_get_500,
    aws_api_gateway_integration_response.package_id_rate_get_200,
    aws_api_gateway_integration_response.package_id_rate_get_400,
    aws_api_gateway_integration_response.package_id_rate_get_403,
    aws_api_gateway_integration_response.package_id_rate_get_404,
    aws_api_gateway_integration_response.package_id_rate_get_500,
    aws_api_gateway_integration_response.artifacts_options_200,
    aws_api_gateway_integration_response.artifact_type_options_200,
    aws_api_gateway_integration_response.authenticate_options_200,
    aws_api_gateway_integration_response.artifact_byregex_options_200,
  ]

  triggers = {
    redeployment = sha1(jsonencode([
      timestamp(), # Force redeployment when any change is made
      # Resources
      aws_api_gateway_resource.health.id,
      aws_api_gateway_resource.health_components.id,
      aws_api_gateway_resource.artifacts.id,
      aws_api_gateway_resource.artifacts_type.id,
      aws_api_gateway_resource.artifacts_type_id.id,
      aws_api_gateway_resource.reset.id,
      aws_api_gateway_resource.authenticate.id,
      aws_api_gateway_resource.package.id,
      aws_api_gateway_resource.package_id.id,
      aws_api_gateway_resource.package_id_rate.id,
      aws_api_gateway_resource.tracks.id,
      aws_api_gateway_resource.admin.id,
      aws_api_gateway_resource.directory.id,
      aws_api_gateway_resource.upload.id,
      aws_api_gateway_resource.artifact.id,
      aws_api_gateway_resource.artifact_type.id,
      aws_api_gateway_resource.artifact_type_id.id,
      aws_api_gateway_resource.artifact_type_id_cost.id,
      aws_api_gateway_resource.artifact_type_id_audit.id,
      aws_api_gateway_resource.artifact_model.id,
      aws_api_gateway_resource.artifact_model_id.id,
      aws_api_gateway_resource.artifact_model_id_rate.id,
      aws_api_gateway_resource.artifact_model_id_lineage.id,
      aws_api_gateway_resource.artifact_model_id_license_check.id,
      aws_api_gateway_resource.artifact_model_id_upload.id,
      aws_api_gateway_resource.artifact_model_id_download.id,
      aws_api_gateway_resource.artifact_ingest.id,
      aws_api_gateway_resource.artifact_directory.id,
      aws_api_gateway_resource.artifact_byname.id,
      aws_api_gateway_resource.artifact_byname_name.id,
      aws_api_gateway_resource.artifact_byregex.id,
      # Methods
      aws_api_gateway_method.health_get.id,
      aws_api_gateway_method.health_components_get.id,
      aws_api_gateway_method.artifact_get.id,
      aws_api_gateway_method.artifacts_post.id,
      aws_api_gateway_method.reset_delete.id,
      aws_api_gateway_method.authenticate_put.id,
      aws_api_gateway_method.tracks_get.id,
      aws_api_gateway_method.admin_get.id,
      aws_api_gateway_method.directory_get.id,
      aws_api_gateway_method.upload_get.id,
      aws_api_gateway_method.upload_post.id,
      aws_api_gateway_method.admin_options.id,
      aws_api_gateway_method.directory_options.id,
      aws_api_gateway_method.upload_options.id,
      aws_api_gateway_method.artifact_type_post.id,
      aws_api_gateway_method.artifact_get.id,
      aws_api_gateway_method.artifact_type_get.id,
      aws_api_gateway_method.artifacts_type_id_get.id,
      aws_api_gateway_method.artifacts_type_id_put.id,
      aws_api_gateway_method.artifacts_type_id_delete.id,
      aws_api_gateway_method.artifact_type_id_get.id,
      aws_api_gateway_method.artifact_type_id_cost_get.id,
      aws_api_gateway_method.artifact_type_id_audit_get.id,
      aws_api_gateway_method.artifact_model_id_rate_get.id,
      aws_api_gateway_method.package_id_rate_get.id,
      aws_api_gateway_method.artifact_model_id_lineage_get.id,
      aws_api_gateway_method.artifact_model_id_license_check_post.id,
      aws_api_gateway_method.artifact_model_id_upload_post.id,
      aws_api_gateway_method.artifact_model_id_download_get.id,
      aws_api_gateway_method.artifact_ingest_get.id,
      aws_api_gateway_method.artifact_ingest_post.id,
      aws_api_gateway_method.artifact_directory_get.id,
      aws_api_gateway_method.artifact_byname_name_get.id,
      aws_api_gateway_method_response.artifact_byname_name_get_200.id,
      aws_api_gateway_method_response.artifact_byname_name_get_400.id,
      aws_api_gateway_method_response.artifact_byname_name_get_403.id,
      aws_api_gateway_method_response.artifact_byname_name_get_404.id,
      aws_api_gateway_method.artifact_byregex_post.id,
      aws_api_gateway_method.package_id_get.id,
      aws_api_gateway_method_response.package_id_get_200.id,
      aws_api_gateway_method_response.package_id_get_400.id,
      aws_api_gateway_method_response.package_id_get_403.id,
      aws_api_gateway_method_response.package_id_get_404.id,
      aws_api_gateway_method_response.package_id_get_500.id,
      aws_api_gateway_method.root_get.id,
      # Integrations
      aws_api_gateway_integration.root_get.id,
      aws_api_gateway_integration.health_get.id,
      aws_api_gateway_integration.health_components_get.id,
      aws_api_gateway_integration.artifact_get.id,
      aws_api_gateway_integration.artifacts_post.id,
      aws_api_gateway_integration.reset_delete.id,
      aws_api_gateway_integration.authenticate_put.id,
      aws_api_gateway_integration.package_id_get.id,
      aws_api_gateway_integration.tracks_get.id,
      aws_api_gateway_integration.artifact_type_get.id,
      aws_api_gateway_integration.artifact_type_post.id,
      aws_api_gateway_integration.artifact_type_id_get.id,
      aws_api_gateway_integration.artifacts_type_id_get.id,
      aws_api_gateway_integration.artifacts_type_id_put.id,
      aws_api_gateway_integration.artifacts_type_id_delete.id,
      aws_api_gateway_integration.artifact_type_id_cost_get.id,
      aws_api_gateway_integration.artifact_type_id_audit_get.id,
      aws_api_gateway_integration.artifact_model_id_rate_get.id,
      aws_api_gateway_integration.package_id_rate_get.id,
      aws_api_gateway_integration.artifact_model_id_lineage_get.id,
      aws_api_gateway_integration.artifact_model_id_license_check_post.id,
      aws_api_gateway_integration.artifact_model_id_upload_post.id,
      aws_api_gateway_integration.artifact_model_id_download_get.id,
      aws_api_gateway_integration.artifact_ingest_get.id,
      aws_api_gateway_integration.artifact_ingest_post.id,
      aws_api_gateway_integration.artifact_directory_get.id,
      aws_api_gateway_integration.artifact_byname_name_get.id,
      aws_api_gateway_integration.artifact_byregex_post.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/apigateway/acme-api"
  retention_in_days = 7

  tags = {
    Name        = "acme-api-gateway-logs"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "main_stage" {
  deployment_id = aws_api_gateway_deployment.main_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  stage_name    = "prod"

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  xray_tracing_enabled = true

  tags = {
    Name        = "acme-api-prod"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

# Enable execution logging for all methods
resource "aws_api_gateway_method_settings" "main_stage_all_methods" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  stage_name  = aws_api_gateway_stage.main_stage.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = "INFO"
    data_trace_enabled = true
  }

  depends_on = [aws_api_gateway_stage.main_stage]
}

# ===== LAMBDA IAM ROLE AND POLICIES =====

resource "aws_iam_role" "lambda_role" {
  name = "lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name        = "lambda-execution-role"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda S3 Policy
resource "aws_iam_policy" "lambda_s3_policy" {
  name = "lambda-s3-packages-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListPackagesPrefix"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = ["arn:aws:s3:::${var.artifacts_bucket}"]
        Condition = {
          StringLike = {
            "s3:prefix" = ["packages/*"]
          }
        }
      },
      {
        Sid    = "ReadPackages"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectTagging"
        ]
        Resource = ["arn:aws:s3:::${var.artifacts_bucket}/packages/*"]
      },
      {
        Sid    = "WritePackagesWithKMS"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectTagging",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts",
          "s3:CreateMultipartUpload",
          "s3:CompleteMultipartUpload",
          "s3:UploadPart",
          "s3:UploadPartCopy"
        ]
        Resource = ["arn:aws:s3:::${var.artifacts_bucket}/packages/*"]
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      }
    ]
  })
}

# Lambda DynamoDB Policy 
resource "aws_iam_policy" "lambda_ddb_policy" {
  name = "lambda-ddb-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:BatchGetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:DescribeTable"
        ]
        Resource = [
          for table_arn in values(var.ddb_tables_arnmap) : table_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:BatchGetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:DescribeTable"
        ]
        Resource = [
          for table_arn in values(var.ddb_tables_arnmap) : "${table_arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = values(var.ddb_tables_arnmap)
      }
    ]
  })
}

# Lambda KMS Policy
resource "aws_iam_policy" "lambda_kms_policy" {
  name = "lambda-kms-s3-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:DescribeKey"
      ]
      Resource = var.kms_key_arn
      Condition = {
        StringEquals = {
          "kms:ViaService" = "s3.${var.aws_region}.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_s3_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_s3_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_ddb_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_ddb_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_kms_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_kms_policy.arn
}

# ===== API GATEWAY CLOUDWATCH LOGGING =====

# IAM Role for API Gateway CloudWatch Logs
resource "aws_iam_role" "api_gateway_cloudwatch_role" {
  name = "api-gateway-cloudwatch-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "apigateway.amazonaws.com"
      }
    }]
  })

  tags = {
    Name        = "api-gateway-cloudwatch-logs-role"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch_logs" {
  role       = aws_iam_role.api_gateway_cloudwatch_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# Grant API Gateway permission to write logs
resource "aws_api_gateway_account" "api_gateway_account" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch_role.arn
}

# ===== OUTPUTS =====

output "api_gateway_url" {
  value       = "https://${aws_api_gateway_rest_api.main_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.main_stage.stage_name}"
  description = "The URL of the API Gateway"
}

output "api_gateway_id" {
  value       = aws_api_gateway_rest_api.main_api.id
  description = "The ID of the API Gateway REST API"
}

output "api_gateway_invoke_url" {
  value       = aws_api_gateway_stage.main_stage.invoke_url
  description = "The invoke URL for the API Gateway stage"
}

output "api_endpoints" {
  value = {
    health             = "${aws_api_gateway_stage.main_stage.invoke_url}/health"
    health_components  = "${aws_api_gateway_stage.main_stage.invoke_url}/health/components"
    artifacts          = "${aws_api_gateway_stage.main_stage.invoke_url}/artifacts"
    reset              = "${aws_api_gateway_stage.main_stage.invoke_url}/reset"
    authenticate       = "${aws_api_gateway_stage.main_stage.invoke_url}/authenticate"
    tracks             = "${aws_api_gateway_stage.main_stage.invoke_url}/tracks"
    artifact_ingest    = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/ingest"
    artifact_directory = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/directory"
    artifact_create    = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/{artifact_type}"
    artifact_rate      = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/model/{id}/rate"
    artifact_cost      = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/{artifact_type}/{id}/cost"
    artifact_lineage   = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/model/{id}/lineage"
    artifact_license   = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/model/{id}/license-check"
    artifact_upload    = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/model/{id}/upload"
    artifact_download  = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/model/{id}/download"
    artifact_audit     = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/{artifact_type}/{id}/audit"
    artifact_by_name   = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/byName/{name}"
    artifact_by_regex  = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/byRegEx"
  }
  description = "Map of all API endpoints"
}