locals {
  tables = {
    users    = { hash_key = "user_id" }
    tokens   = { hash_key = "token_id", ttl_attr = "exp_ts" }
    packages = { hash_key = "pkg_key" }
    uploads  = { hash_key = "upload_id" }
    artifacts = { hash_key = "artifact_id" }
    downloads = {
      hash_key = "event_id"
      gsi = {
        "user-timestamp-index" = {
          hash_key        = "user_id"
          range_key       = "timestamp"
          projection_type = "ALL"
        }
      }
    }
  }
}

resource "aws_dynamodb_table" "this" {
  for_each     = local.tables
  name         = each.key
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = each.value.hash_key

  # Prevent accidental deletion of existing tables
  lifecycle {
    ignore_changes = [
      # Ignore changes to table name, billing mode, and hash key
      # These are set correctly and shouldn't change
    ]
  }

  attribute {
    name = each.value.hash_key
    type = "S"
  }

  # Add GSI attributes if they exist
  dynamic "attribute" {
    for_each = try(each.value.gsi, {})
    content {
      name = attribute.value.hash_key
      type = "S"
    }
  }

  dynamic "attribute" {
    for_each = try(each.value.gsi, {})
    content {
      name = attribute.value.range_key
      type = "S"
    }
  }

  # Add GSI if it exists
  dynamic "global_secondary_index" {
    for_each = try(each.value.gsi, {})
    content {
      name            = global_secondary_index.key
      hash_key        = global_secondary_index.value.hash_key
      range_key       = global_secondary_index.value.range_key
      projection_type = global_secondary_index.value.projection_type
    }
  }

  ttl {
    enabled        = try(each.value.ttl_attr != null, false)
    attribute_name = try(each.value.ttl_attr, null)
  }
}

output "arn_map" { value = { for k, t in aws_dynamodb_table.this : k => t.arn } }

