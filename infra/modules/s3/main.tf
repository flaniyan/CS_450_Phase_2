resource "aws_s3_bucket" "artifacts" {
  bucket        = var.artifacts_name
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# S3 Access Point for secure access to the bucket
resource "aws_s3_access_point" "main" {
  name   = "cs450-s3"
  bucket = aws_s3_bucket.artifacts.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          AWS = aws_iam_role.ecs_task_role.arn
        },
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:AbortMultipartUpload",
          "s3:CreateMultipartUpload",
          "s3:ListMultipartUploadParts",
          "s3:CompleteMultipartUpload"
        ],
        Resource = [
          "${aws_s3_access_point.main.arn}",
          "${aws_s3_access_point.main.arn}/*"
        ]
      }
    ]
  })

  public_access_block_configuration {
    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
  }
}


output "artifacts_bucket" { value = aws_s3_bucket.artifacts.id }
output "access_point_arn" {
  value = aws_s3_access_point.main.arn
}


