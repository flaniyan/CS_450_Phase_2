data "aws_iam_policy_document" "validator_ddb_min_rw" {
  statement {
    sid    = "DDBRead"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem", "dynamodb:BatchGetItem",
      "dynamodb:Query", "dynamodb:Scan", "dynamodb:DescribeTable"
    ]
    resources = [
      "arn:aws:dynamodb:us-east-1:838693051036:table/packages",
      "arn:aws:dynamodb:us-east-1:838693051036:table/packages/index/*"
    ]
  }

  # validator updates status/metrics fields
  statement {
    sid       = "DDBUpdateOnly"
    effect    = "Allow"
    actions   = ["dynamodb:UpdateItem"]
    resources = ["arn:aws:dynamodb:us-east-1:838693051036:table/packages"]
  }
}

resource "aws_iam_policy" "validator_ddb_min_rw_managed" {
  name   = "validator-ddb-min-rw"
  policy = data.aws_iam_policy_document.validator_ddb_min_rw.json
}


# Validator — S3 RO

data "aws_iam_policy_document" "validator_s3_inputs_ro" {
  # List only within validator/inputs/
  statement {
    sid       = "ListValidatorInputs"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::pkg-artifacts"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["validator/inputs/*"]
    }
  }

  # Read only under validator/inputs/
  statement {
    sid       = "ReadValidatorInputs"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectTagging"]
    resources = ["arn:aws:s3:::pkg-artifacts/validator/inputs/*"]
  }
}

resource "aws_iam_policy" "validator_s3_inputs_ro_managed" {
  name   = "validator-s3-inputs-ro"
  policy = data.aws_iam_policy_document.validator_s3_inputs_ro.json
}

# Validator — KMS (decrypt-only via S3)
resource "aws_iam_policy" "validator_kms_s3_ro_managed" {
  name = "validator-kms-s3-ro"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "KMSViaS3Service"
        Effect = "Allow",
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey*"
        ],
        Resource = [
          module.monitoring.kms_key_arn,
          "arn:aws:kms:us-east-1:838693051036:key/ffc50d00-4db1-4676-a63a-c7c1e286abfc"
        ],
        Condition = { StringEquals = { "kms:ViaService" = "s3.us-east-1.amazonaws.com" } }
      },
      {
        Sid    = "KMSDirectAccess"
        Effect = "Allow",
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey*"
        ],
        Resource = [
          module.monitoring.kms_key_arn,
          "arn:aws:kms:us-east-1:838693051036:key/ffc50d00-4db1-4676-a63a-c7c1e286abfc"
        ]
      }
    ]
  })
}

# Attach policies to the Validator task role
resource "aws_iam_role_policy_attachment" "validator_attach_ddb" {
  role       = aws_iam_role.validator_task.name
  policy_arn = aws_iam_policy.validator_ddb_min_rw_managed.arn
}

resource "aws_iam_role_policy_attachment" "validator_attach_s3" {
  role       = aws_iam_role.validator_task.name
  policy_arn = aws_iam_policy.validator_s3_inputs_ro_managed.arn
}

resource "aws_iam_role_policy_attachment" "validator_attach_kms" {
  role       = aws_iam_role.validator_task.name
  policy_arn = aws_iam_policy.validator_kms_s3_ro_managed.arn
}

# Validator — Secrets Manager (JWT secret)
resource "aws_iam_policy" "validator_secrets_jwt_ro_managed" {
  name = "validator-secrets-jwt-ro"
  
  lifecycle {
    create_before_destroy = true
  }
  
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ],
        Resource = module.monitoring.jwt_secret_arn
      },
      {
        Effect = "Allow",
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey*"
        ],
        Resource = module.monitoring.kms_key_arn,
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.us-east-1.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "validator_attach_secrets" {
  role       = aws_iam_role.validator_task.name
  policy_arn = aws_iam_policy.validator_secrets_jwt_ro_managed.arn
}
