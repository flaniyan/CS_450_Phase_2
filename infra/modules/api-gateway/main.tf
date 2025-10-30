variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "validator_service_url" { type = string }
variable "aws_region" { 
  type    = string 
  default = "us-east-1"
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

resource "aws_api_gateway_resource" "rate" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "rate"
}

resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "upload"
}

resource "aws_api_gateway_resource" "lineage" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "lineage"
}

resource "aws_api_gateway_resource" "size_cost" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "size-cost"
}

resource "aws_api_gateway_resource" "ingest" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "ingest"
}

resource "aws_api_gateway_resource" "download" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_rest_api.main_api.root_resource_id
  path_part   = "download"
}

resource "aws_api_gateway_resource" "download_model_id" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.download.id
  path_part   = "{model_id}"
}

resource "aws_api_gateway_resource" "download_model_id_version" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.download_model_id.id
  path_part   = "{version}"
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

# /artifact/byName/{name}
resource "aws_api_gateway_resource" "artifact_byname" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact.id
  path_part   = "byName"
}

resource "aws_api_gateway_resource" "artifact_byname_name" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact_byname.id
  path_part   = "{name}"
}

# /artifact/byRegEx
resource "aws_api_gateway_resource" "artifact_byregex" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  parent_id   = aws_api_gateway_resource.artifact.id
  path_part   = "byRegEx"
}

# ===== METHODS AND INTEGRATIONS =====

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

# GET /health/components
resource "aws_api_gateway_method" "health_components_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.health_components.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.querystring.windowMinutes"    = false
    "method.request.querystring.includeTimeline"  = false
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

# DELETE /reset
resource "aws_api_gateway_method" "reset_delete" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.reset.id
  http_method   = "DELETE"
  authorization = "NONE"

  request_parameters = {
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "reset_delete" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.reset.id
  http_method = aws_api_gateway_method.reset_delete.http_method

  integration_http_method = "DELETE"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/reset"

  request_parameters = {
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
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

# GET /rate
resource "aws_api_gateway_method" "rate_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.rate.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "rate_get" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.rate.id
  http_method = aws_api_gateway_method.rate_get.http_method

  integration_http_method = "GET"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/rate"
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

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS /rate
resource "aws_api_gateway_method" "rate_options" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.rate.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "rate_options" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.rate.id
  http_method = aws_api_gateway_method.rate_options.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "rate_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.rate.id
  http_method = aws_api_gateway_method.rate_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "rate_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.rate.id
  http_method = aws_api_gateway_method.rate_options.http_method
  status_code = aws_api_gateway_method_response.rate_options_200.status_code

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

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
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

# GET /artifacts/{artifact_type}/{id}
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
  uri                     = "${var.validator_service_url}/artifacts/{artifact_type}/{id}"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# PUT /artifacts/{artifact_type}/{id}
resource "aws_api_gateway_method" "artifact_type_id_put" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_type_id.id
  http_method   = "PUT"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_type_id_put" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id.id
  http_method = aws_api_gateway_method.artifact_type_id_put.http_method

  integration_http_method = "PUT"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifacts/{artifact_type}/{id}"

  request_parameters = {
    "integration.request.path.artifact_type"     = "method.request.path.artifact_type"
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
}

# DELETE /artifacts/{artifact_type}/{id}
resource "aws_api_gateway_method" "artifact_type_id_delete" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_type_id.id
  http_method   = "DELETE"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.artifact_type"     = true
    "method.request.path.id"                = true
    "method.request.header.X-Authorization" = true
  }
}

resource "aws_api_gateway_integration" "artifact_type_id_delete" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id
  resource_id = aws_api_gateway_resource.artifact_type_id.id
  http_method = aws_api_gateway_method.artifact_type_id_delete.http_method

  integration_http_method = "DELETE"
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifacts/{artifact_type}/{id}"

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
  type                    = "HTTP_PROXY"
  uri                     = "${var.validator_service_url}/artifact/model/{id}/rate"

  request_parameters = {
    "integration.request.path.id"                = "method.request.path.id"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
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

# GET /artifact/byName/{name}
resource "aws_api_gateway_method" "artifact_byname_name_get" {
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  resource_id   = aws_api_gateway_resource.artifact_byname_name.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.name"              = true
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
    "integration.request.path.name"              = "method.request.path.name"
    "integration.request.header.X-Authorization" = "method.request.header.X-Authorization"
  }
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

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ===== API GATEWAY DEPLOYMENT =====

resource "aws_api_gateway_deployment" "main_deployment" {
  rest_api_id = aws_api_gateway_rest_api.main_api.id

  triggers = {
    redeployment = sha1(jsonencode([
      # Resources
      aws_api_gateway_resource.health.id,
      aws_api_gateway_resource.health_components.id,
      aws_api_gateway_resource.artifacts.id,
      aws_api_gateway_resource.reset.id,
      aws_api_gateway_resource.authenticate.id,
      aws_api_gateway_resource.tracks.id,
      aws_api_gateway_resource.admin.id,
      aws_api_gateway_resource.directory.id,
      aws_api_gateway_resource.rate.id,
      aws_api_gateway_resource.upload.id,
      aws_api_gateway_resource.lineage.id,
      aws_api_gateway_resource.size_cost.id,
      aws_api_gateway_resource.ingest.id,
      aws_api_gateway_resource.download.id,
      aws_api_gateway_resource.download_model_id.id,
      aws_api_gateway_resource.download_model_id_version.id,
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
      aws_api_gateway_resource.artifact_byname.id,
      aws_api_gateway_resource.artifact_byname_name.id,
      aws_api_gateway_resource.artifact_byregex.id,
      # Methods
      aws_api_gateway_method.health_get.id,
      aws_api_gateway_method.health_components_get.id,
      aws_api_gateway_method.artifacts_post.id,
      aws_api_gateway_method.reset_delete.id,
      aws_api_gateway_method.authenticate_put.id,
      aws_api_gateway_method.tracks_get.id,
      aws_api_gateway_method.admin_get.id,
      aws_api_gateway_method.directory_get.id,
      aws_api_gateway_method.rate_get.id,
      aws_api_gateway_method.upload_get.id,
      aws_api_gateway_method.upload_post.id,
      aws_api_gateway_method.admin_options.id,
      aws_api_gateway_method.directory_options.id,
      aws_api_gateway_method.rate_options.id,
      aws_api_gateway_method.upload_options.id,
      aws_api_gateway_method.artifact_type_post.id,
      aws_api_gateway_method.artifact_type_id_get.id,
      aws_api_gateway_method.artifact_type_id_put.id,
      aws_api_gateway_method.artifact_type_id_delete.id,
      aws_api_gateway_method.artifact_type_id_cost_get.id,
      aws_api_gateway_method.artifact_type_id_audit_get.id,
      aws_api_gateway_method.artifact_model_id_rate_get.id,
      aws_api_gateway_method.artifact_model_id_lineage_get.id,
      aws_api_gateway_method.artifact_model_id_license_check_post.id,
      aws_api_gateway_method.artifact_byname_name_get.id,
      aws_api_gateway_method.artifact_byregex_post.id,
      # Integrations
      aws_api_gateway_integration.health_get.id,
      aws_api_gateway_integration.health_components_get.id,
      aws_api_gateway_integration.artifacts_post.id,
      aws_api_gateway_integration.reset_delete.id,
      aws_api_gateway_integration.authenticate_put.id,
      aws_api_gateway_integration.tracks_get.id,
      aws_api_gateway_integration.artifact_type_post.id,
      aws_api_gateway_integration.artifact_type_id_get.id,
      aws_api_gateway_integration.artifact_type_id_put.id,
      aws_api_gateway_integration.artifact_type_id_delete.id,
      aws_api_gateway_integration.artifact_type_id_cost_get.id,
      aws_api_gateway_integration.artifact_type_id_audit_get.id,
      aws_api_gateway_integration.artifact_model_id_rate_get.id,
      aws_api_gateway_integration.artifact_model_id_lineage_get.id,
      aws_api_gateway_integration.artifact_model_id_license_check_post.id,
      aws_api_gateway_integration.artifact_byname_name_get.id,
      aws_api_gateway_integration.artifact_byregex_post.id,
    ]))
  }

  depends_on = [
    aws_api_gateway_integration.health_get,
    aws_api_gateway_integration.health_components_get,
    aws_api_gateway_integration.artifacts_post,
    aws_api_gateway_integration.reset_delete,
    aws_api_gateway_integration.authenticate_put,
    aws_api_gateway_integration.tracks_get,
    aws_api_gateway_integration.admin_get,
    aws_api_gateway_integration.directory_get,
    aws_api_gateway_integration.rate_get,
    aws_api_gateway_integration.upload_get,
    aws_api_gateway_integration.upload_post,
    aws_api_gateway_integration.admin_options,
    aws_api_gateway_integration.directory_options,
    aws_api_gateway_integration.rate_options,
    aws_api_gateway_integration.upload_options,
    aws_api_gateway_integration.artifact_type_post,
    aws_api_gateway_integration.artifact_type_id_get,
    aws_api_gateway_integration.artifact_type_id_put,
    aws_api_gateway_integration.artifact_type_id_delete,
    aws_api_gateway_integration.artifact_type_id_cost_get,
    aws_api_gateway_integration.artifact_type_id_audit_get,
    aws_api_gateway_integration.artifact_model_id_rate_get,
    aws_api_gateway_integration.artifact_model_id_lineage_get,
    aws_api_gateway_integration.artifact_model_id_license_check_post,
    aws_api_gateway_integration.artifact_byname_name_get,
    aws_api_gateway_integration.artifact_byregex_post,
    aws_api_gateway_integration_response.artifacts_options_200,
    aws_api_gateway_integration_response.artifact_type_options_200,
    aws_api_gateway_integration_response.authenticate_options_200,
    aws_api_gateway_integration_response.artifact_byregex_options_200,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "main_stage" {
  deployment_id = aws_api_gateway_deployment.main_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.main_api.id
  stage_name    = "prod"

  tags = {
    Name        = "acme-api-prod"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
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

resource "aws_iam_policy" "lambda_policy" {
  name = "lambda-package-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:CreateMultipartUpload",
          "s3:AbortMultipartUpload",
          "s3:CompleteMultipartUpload",
          "s3:UploadPart",
          "s3:UploadPartCopy"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifacts_bucket}",
          "arn:aws:s3:::${var.artifacts_bucket}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = values(var.ddb_tables_arnmap)
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
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
    health                = "${aws_api_gateway_stage.main_stage.invoke_url}/health"
    health_components     = "${aws_api_gateway_stage.main_stage.invoke_url}/health/components"
    artifacts             = "${aws_api_gateway_stage.main_stage.invoke_url}/artifacts"
    reset                 = "${aws_api_gateway_stage.main_stage.invoke_url}/reset"
    authenticate          = "${aws_api_gateway_stage.main_stage.invoke_url}/authenticate"
    tracks                = "${aws_api_gateway_stage.main_stage.invoke_url}/tracks"
    artifact_create       = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/{artifact_type}"
    artifact_get          = "${aws_api_gateway_stage.main_stage.invoke_url}/artifacts/{artifact_type}/{id}"
    artifact_rate         = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/model/{id}/rate"
    artifact_cost         = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/{artifact_type}/{id}/cost"
    artifact_lineage      = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/model/{id}/lineage"
    artifact_license      = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/model/{id}/license-check"
    artifact_audit        = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/{artifact_type}/{id}/audit"
    artifact_by_name      = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/byName/{name}"
    artifact_by_regex     = "${aws_api_gateway_stage.main_stage.invoke_url}/artifact/byRegEx"
  }
  description = "Map of all API endpoints"
}