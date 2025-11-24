resource "aws_s3_bucket" "artifacts" {
  bucket        = var.artifacts_name
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Access point DEFINITION ONLY
resource "aws_s3_access_point" "main" {
  name   = "cs450-s3"
  bucket = aws_s3_bucket.artifacts.id

  # IMPORTANT: Do NOT define policy here.
  # AWS rejects inline policies when block_public_policy = true.
  # Policies must be set via aws_s3control_access_point_policy.

  public_access_block_configuration {
    block_public_acls       = true
    block_public_policy     = false   # MUST be false so policy can attach
    ignore_public_acls      = true
    restrict_public_buckets = true
  }
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.id
}

