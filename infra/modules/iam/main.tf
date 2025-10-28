variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }

resource "aws_iam_policy" "group106_policy" {
  name = "group106_project_policy"
  policy = jsonencode({
    Version : "2012-10-17",
    Statement : [
      {
        Effect : "Allow",
        Action : [
          "s3:PutObject",
          "s3:GetObject",
          "s3:AbortMultipartUpload",
          "s3:CreateMultipartUpload",
          "s3:ListBucketMultipartUploads",
          "s3:ListBucket"
        ],
        Resource : [
          "arn:aws:s3:::${var.artifacts_bucket}",
          "arn:aws:s3:::${var.artifacts_bucket}/packages/*",
          "arn:aws:s3:::${var.artifacts_bucket}/validators/*"
        ]
      },
      {
        Effect : "Allow",
        Action : ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query"],
        Resource : values(var.ddb_tables_arnmap)
      }
    ]
  })
}

output "group106_policy_arn" { value = aws_iam_policy.group106_policy.arn }


