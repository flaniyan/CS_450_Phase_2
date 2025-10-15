# ECR Repository
resource "aws_ecr_repository" "validator_repo" {
  name                 = "validator-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
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
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name  = "validator-service"
    image = "${aws_ecr_repository.validator_repo.repository_url}:latest"
    
    portMappings = [{
      containerPort = 3001
      protocol      = "tcp"
    }]
    
    environment = [
      { name = "PYTHON_ENV", value = "production" },
      { name = "PORT", value = "3001" },
      { name = "AWS_REGION", value = "us-east-1" },
      { name = "ARTIFACTS_BUCKET", value = var.artifacts_bucket },
      { name = "DDB_TABLE_PACKAGES", value = "packages" },
      { name = "DDB_TABLE_DOWNLOADS", value = "downloads" },
      { name = "DDB_TABLE_USERS", value = "users" },
      { name = "DDB_TABLE_TOKENS", value = "tokens" },
      { name = "DDB_TABLE_UPLOADS", value = "uploads" }
    ]
    
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.validator_logs.name
        "awslogs-region"        = "us-east-1"
        "awslogs-stream-prefix" = "ecs"
      }
    }
    
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:3001/health || exit 1"]
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

  load_balancer {
    target_group_arn = aws_lb_target_group.validator_tg.arn
    container_name   = "validator-service"
    container_port   = 3001
  }

  network_configuration {
    subnets          = [aws_subnet.validator_subnet_1.id, aws_subnet.validator_subnet_2.id]
    security_groups  = [aws_security_group.validator_sg.id]
    assign_public_ip = true
  }

  depends_on = [aws_lb_listener.validator_listener]
}

# VPC and Networking
resource "aws_vpc" "validator_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "validator-vpc"
  }
}

# Subnets
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
    from_port   = 3001
    to_port     = 3001
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

# Load Balancer
resource "aws_lb" "validator_lb" {
  name               = "validator-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.validator_sg.id]
  subnets            = [aws_subnet.validator_subnet_1.id, aws_subnet.validator_subnet_2.id]

  tags = {
    Name = "validator-lb"
  }
}

resource "aws_lb_target_group" "validator_tg" {
  name     = "validator-tg"
  port     = 3001
  protocol = "HTTP"
  vpc_id   = aws_vpc.validator_vpc.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
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

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "validator_logs" {
  name              = "/ecs/validator-service"
  retention_in_days = 7
}

# IAM Roles
resource "aws_iam_role" "ecs_execution_role" {
  name = "ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
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
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "ecs_task_policy" {
  name = "ecs-task-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifacts_bucket}",
          "arn:aws:s3:::${var.artifacts_bucket}/*"
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

resource "aws_iam_role_policy_attachment" "ecs_task_role_policy" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.ecs_task_policy.arn
}

output "validator_service_url" {
  value = "http://${aws_lb.validator_lb.dns_name}"
}

output "validator_cluster_arn" {
  value = aws_ecs_cluster.validator_cluster.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.validator_repo.repository_url
}
