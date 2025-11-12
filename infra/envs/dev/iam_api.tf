data "aws_iam_policy_document" "api_ddb_rw" {
  statement {
    effect  = "Allow"
    actions = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:DescribeTable"]
    resources = [
      "arn:aws:dynamodb:us-east-1:838693051036:table/packages",
      "arn:aws:dynamodb:us-east-1:838693051036:table/packages/index/*"
    ]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem"]
    resources = ["arn:aws:dynamodb:us-east-1:838693051036:table/packages"]
  }
}

resource "aws_iam_policy" "api_ddb_rw_managed" {
  name   = "api-ddb-rw-dev"
  policy = data.aws_iam_policy_document.api_ddb_rw.json
}

# API Service - S3 Policy
data "aws_iam_policy_document" "api_s3_packages_rw" {
  # List only within packages/ prefix
  statement {
    sid       = "ListPackagesPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::pkg-artifacts"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["packages/*"]
    }
  }

  # Read/Write only under packages/
  statement {
    sid    = "RWPackagesWithKMS"
    effect = "Allow"
    actions = [
      "s3:GetObject", "s3:GetObjectTagging",
      "s3:PutObject", "s3:PutObjectTagging",
      "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts", "s3:DeleteObject"
    ]
    resources = ["arn:aws:s3:::pkg-artifacts/packages/*"]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }
}

resource "aws_iam_policy" "api_s3_packages_rw_managed" {
  name   = "api-s3-packages-rw-dev"
  policy = data.aws_iam_policy_document.api_s3_packages_rw.json
}

# API Service - KMS Policy (required for S3 KMS encryption)
resource "aws_iam_policy" "api_kms_s3_managed" {
  name = "api-kms-s3-dev"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:DescribeKey"
      ],
      Resource = module.monitoring.kms_key_arn,
      Condition = {
        StringEquals = {
          "kms:ViaService" = "s3.us-east-1.amazonaws.com"
        }
      }
    }]
  })
}

# Attach policies to API task role
resource "aws_iam_role_policy_attachment" "api_attach_ddb" {
  role       = aws_iam_role.api_task.name
  policy_arn = aws_iam_policy.api_ddb_rw_managed.arn
}

resource "aws_iam_role_policy_attachment" "api_attach_s3" {
  role       = aws_iam_role.api_task.name
  policy_arn = aws_iam_policy.api_s3_packages_rw_managed.arn
}

resource "aws_iam_role_policy_attachment" "api_attach_kms" {
  role       = aws_iam_role.api_task.name
  policy_arn = aws_iam_policy.api_kms_s3_managed.arn
}