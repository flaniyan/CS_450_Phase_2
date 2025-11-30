# ECS task role ARN is now obtained from the ECS module output

# Access point policy (MUST be separate)
resource "aws_s3control_access_point_policy" "cs450_s3_policy" {
  # Use the actual ARN from the access point resource
  access_point_arn = module.s3.access_point_arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEcsTaskRoleListBucket"
        Effect = "Allow"
        Principal = {
          AWS = module.ecs.ecs_task_role_arn
        }
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          module.s3.access_point_arn
        ]
      },
      {
        Sid    = "AllowEcsTaskRoleObjectAccess"
        Effect = "Allow"
        Principal = {
          AWS = module.ecs.ecs_task_role_arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${module.s3.access_point_arn}/object/*"
        ]
      }
    ]
  })

  depends_on = [module.ecs]
}
