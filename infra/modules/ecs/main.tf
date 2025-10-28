# ECR Repository
resource "aws_ecr_repository" "validator_repo" {
  name                 = "validator-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "validator-service"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "validator_cluster" {
  name = "validator-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "validator_task" {
  family                   = "validator-service"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name  = "validator-service"
    image = "838693051036.dkr.ecr.us-east-1.amazonaws.com/validator-service:${var.image_tag}"

    memoryReservation = 1536
    memory             = 2048
    
    portMappings = [{
      containerPort = 3000
      hostPort      = 3000
      protocol      = "tcp"
    }]
    
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:3000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }

    environment = [
      {
        name  = "AWS_REGION"
        value = "us-east-1"
      },
      {
        name  = "PORT"
        value = "3000"
      },
      {
        name  = "ARTIFACTS_BUCKET"
        value = "pkg-artifacts"
      },
      {
        name  = "DDB_TABLE_PACKAGES"
        value = "packages"
      },
      {
        name  = "DDB_TABLE_DOWNLOADS"
        value = "downloads"
      },
      {
        name  = "DDB_TABLE_UPLOADS"
        value = "uploads"
      },
      {
        name  = "DDB_TABLE_USERS"
        value = "users"
      },
      {
        name  = "DDB_TABLE_TOKENS"
        value = "tokens"
      },
      {
        name  = "PYTHON_ENV"
        value = "production"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.validator_logs.name
        awslogs-region        = "us-east-1"
        awslogs-stream-prefix = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:3000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

# ECS Service
resource "aws_ecs_service" "validator_service" {
  name            = "validator-service"
  cluster         = aws_ecs_cluster.validator_cluster.id
  task_definition = aws_ecs_task_definition.validator_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.validator_subnet_1.id, aws_subnet.validator_subnet_2.id]
    security_groups  = [aws_security_group.validator_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.validator_tg.arn
    container_name   = "validator-service"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.validator_listener]
}

# Application Load Balancer
resource "aws_lb" "validator_lb" {
  name               = "validator-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.validator_sg.id]
  subnets            = [aws_subnet.validator_subnet_1.id, aws_subnet.validator_subnet_2.id]

  enable_deletion_protection = false
}

resource "aws_lb_target_group" "validator_tg" {
  name        = "validator-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.validator_vpc.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
    port                = "traffic-port"
    protocol            = "HTTP"
  }
}

resource "aws_lb_listener" "validator_listener" {
  load_balancer_arn = aws_lb.validator_lb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.validator_tg.arn
  }
}

# VPC
resource "aws_vpc" "validator_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "validator-vpc"
  }
}

resource "aws_subnet" "validator_subnet_1" {
  vpc_id                  = aws_vpc.validator_vpc.id
  cidr_block              = "10.0.10.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "validator-subnet-1"
  }
}

resource "aws_subnet" "validator_subnet_2" {
  vpc_id                  = aws_vpc.validator_vpc.id
  cidr_block              = "10.0.20.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = true

  tags = {
    Name = "validator-subnet-2"
  }
}

resource "aws_internet_gateway" "validator_igw" {
  vpc_id = aws_vpc.validator_vpc.id

  tags = {
    Name = "validator-igw"
  }
}

resource "aws_route_table" "validator_rt" {
  vpc_id = aws_vpc.validator_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.validator_igw.id
  }

  tags = {
    Name = "validator-rt"
  }
}

resource "aws_route_table_association" "validator_rta" {
  subnet_id      = aws_subnet.validator_subnet_1.id
  route_table_id = aws_route_table.validator_rt.id
}

# Security Group
resource "aws_security_group" "validator_sg" {
  name_prefix = "validator-sg"
  vpc_id      = aws_vpc.validator_vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "validator-sg"
  }
}

# IAM Roles
resource "aws_iam_role" "ecs_execution_role" {
  name = "ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "ecs-task-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifacts_bucket}",
          "arn:aws:s3:::${var.artifacts_bucket}/*",
          "arn:aws:s3:us-east-1:838693051036:accesspoint/cs450-s3",
          "arn:aws:s3:us-east-1:838693051036:accesspoint/cs450-s3/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = values(var.ddb_tables_arnmap)
      }
    ]
  })
}

resource "aws_iam_role_policy" "task_kms" {
  name = "validator-kms"
  role = aws_iam_role.ecs_task_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
        Resource = [var.validator_kms_key_id]
        Condition = {
          StringEquals = {
            "kms:EncryptionContext:Service" = "validator"
          }
        }
      }
    ]
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "validator_logs" {
  name              = "/ecs/validator-service"
  retention_in_days = 7
}

# Outputs
output "validator_service_url" {
  value = "http://${aws_lb.validator_lb.dns_name}"
}

output "validator_cluster_arn" {
  value = aws_ecs_cluster.validator_cluster.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.validator_repo.repository_url
}