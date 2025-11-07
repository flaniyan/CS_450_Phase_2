# IAM Policy Issues Summary

## ✅ Current Status

All previously identified IAM policy issues have been resolved.

### Fixes Applied

1. **Added missing S3 multipart upload permissions**
   - Added `s3:CreateMultipartUpload`, `s3:CompleteMultipartUpload`, `s3:UploadPart`, and `s3:UploadPartCopy`.
   - Ensures Lambda can perform the full multipart upload workflow (`create_multipart_upload`, `upload_part_copy`, `complete_multipart_upload`).

2. **Split S3 read/write permissions**
   - Read operations (`s3:GetObject`, `s3:GetObjectTagging`) remain unrestricted by KMS conditions.
   - Write operations (Put/Delete/Multipart) require `aws:kms` encryption.
   - Prevents GetObject failures when reading existing non-KMS objects.

### Updated Policy Snippet

```hcl
resource "aws_iam_policy" "lambda_s3_policy" {
  name = "lambda-s3-packages-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListPackagesPrefix"
        Effect = "Allow"
        Action = ["s3:ListBucket"]
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
```

## 📌 Next Steps

- Run `terraform plan` / `terraform apply` to deploy the updated policies.
- Re-test package upload and download flows.
