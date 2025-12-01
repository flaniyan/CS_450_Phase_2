data "aws_iam_policy_document" "api_ddb_rw" {
  statement {
    effect  = "Allow"
    actions = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:DescribeTable"]
    resources = [
      "arn:aws:dynamodb:us-east-1:838693051036:table/packages",
      "arn:aws:dynamodb:us-east-1:838693051036:table/packages/index/*",
      "arn:aws:dynamodb:us-east-1:838693051036:table/artifacts"
    ]
  }
  statement {
    effect  = "Allow"
    actions = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem"]
    resources = [
      "arn:aws:dynamodb:us-east-1:838693051036:table/packages",
      "arn:aws:dynamodb:us-east-1:838693051036:table/artifacts"
    ]
  }
}

resource "aws_iam_policy" "api_ddb_rw_managed" {
  name   = "api-ddb-rw-dev"
  policy = data.aws_iam_policy_document.api_ddb_rw.json
}

# API Service - S3 Policy
data "aws_iam_policy_document" "api_s3_packages_rw" {
  # S3 Access Point permissions - required when using access points
  statement {
    sid    = "AccessPointPermissions"
    effect = "Allow"
    actions = [
      "s3:GetAccessPoint",
      "s3:ListAccessPoint"
    ]
    resources = ["arn:aws:s3:us-east-1:838693051036:accesspoint/cs450-s3"]
  }

  # List bucket (must use bucket ARN, not access point ARN)
  statement {
    sid     = "ListAccessPoint"
    effect  = "Allow"
    actions = ["s3:ListBucket"]
    resources = [
      "arn:aws:s3:::pkg-artifacts"
    ]
  }

  # List bucket with prefix conditions for direct bucket access
  statement {
    sid       = "ListPackagesPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::pkg-artifacts"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["packages/*", "models/*"]
    }
  }

  # Read/Write objects through access point (models and packages)
  statement {
    sid    = "RWAccessPointObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectTagging",
      "s3:PutObject",
      "s3:PutObjectTagging",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
      "s3:CreateMultipartUpload",
      "s3:CompleteMultipartUpload",
      "s3:UploadPart"
    ]
    resources = [
      "arn:aws:s3:us-east-1:838693051036:accesspoint/cs450-s3/*",
      "arn:aws:s3:::pkg-artifacts/models/*",
      "arn:aws:s3:::pkg-artifacts/packages/*"
    ]
  }

  # Fallback: Read/Write only under packages/ (for backward compatibility)
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
    Statement = [
      {
        Sid    = "KMSViaS3Service"
        Effect = "Allow",
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ],
        Resource = [
          module.monitoring.kms_key_arn,
          "arn:aws:kms:us-east-1:838693051036:key/ffc50d00-4db1-4676-a63a-c7c1e286abfc"
        ],
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.us-east-1.amazonaws.com"
          }
        }
      },
      {
        Sid    = "KMSDirectAccess"
        Effect = "Allow",
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ],
        Resource = [
          module.monitoring.kms_key_arn,
          "arn:aws:kms:us-east-1:838693051036:key/ffc50d00-4db1-4676-a63a-c7c1e286abfc"
        ]
      }
    ]
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

# API Service - Lambda Invoke Policy (for performance testing compute backend switching)
resource "aws_iam_policy" "api_lambda_invoke_managed" {
  name = "api-lambda-invoke-dev"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          module.lambda.lambda_function_arn,
          "${module.lambda.lambda_function_arn}:*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_attach_lambda" {
  role       = aws_iam_role.api_task.name
  policy_arn = aws_iam_policy.api_lambda_invoke_managed.arn
}