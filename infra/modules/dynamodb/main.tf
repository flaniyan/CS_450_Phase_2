locals {
  tables = {
    users     = { hash_key = "user_id" }
    tokens    = { hash_key = "token_id", ttl_attr = "exp_ts" }
    packages  = { hash_key = "pkg_key" }
    uploads   = { hash_key = "upload_id" }
    downloads = { hash_key = "event_id" }
  }
}

resource "aws_dynamodb_table" "this" {
  for_each      = local.tables
  name          = each.key
  billing_mode  = "PAY_PER_REQUEST"
  hash_key      = each.value.hash_key
  attribute {
    name = each.value.hash_key
    type = "S"
  }
  ttl {
    enabled        = try(each.value.ttl_attr != null, false)
    attribute_name = try(each.value.ttl_attr, null)
  }
}

output "arn_map" { value = { for k, t in aws_dynamodb_table.this : k => t.arn } }


