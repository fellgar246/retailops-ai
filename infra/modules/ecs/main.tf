locals {
  # Fargate needs a route to the registry and to the AWS APIs. With a NAT
  # gateway that is a private subnet; without one it must be a public subnet
  # with a public address. Inbound is still only what the security group
  # allows, which is the load balancer.
  task_subnet_ids = var.assign_task_public_ip ? var.public_subnet_ids : var.private_subnet_ids
}

resource "aws_ecs_cluster" "this" {
  name = var.cluster_name
  tags = merge(var.tags, { Name = var.cluster_name })

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids
  tags               = merge(var.tags, { Name = "${var.name_prefix}-alb" })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name_prefix}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  tags        = merge(var.tags, { Name = "${var.name_prefix}-api-tg" })

  health_check {
    path                = "/health"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_target_group" "web" {
  name        = "${var.name_prefix}-web-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  tags        = merge(var.tags, { Name = "${var.name_prefix}-web-tg" })

  health_check {
    path                = "/"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_listener" "web" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.this.arn
  port              = 8080
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.api_task_role_arn
  tags                     = merge(var.tags, { Name = "${var.name_prefix}-api" })

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [{
        containerPort = 8000
        protocol      = "tcp"
      }]
      environment = [
        { name = "DATABASE_URL", value = var.database_url },
        { name = "CORS_ORIGINS", value = var.cors_origins },
        { name = "AWS_ENABLED", value = "true" },
        { name = "AWS_USE_S3_STORAGE", value = "true" },
        { name = "AWS_DOCUMENTS_BUCKET", value = var.documents_bucket },
        { name = "INSTANCE_COUNT", value = tostring(var.desired_count) },
        { name = "JOB_QUEUE_PROVIDER", value = "sqs" },
        { name = "JOBS_QUEUE_URL", value = var.jobs_queue_url },
        { name = "AUTH_PROVIDER", value = var.auth_provider },
        { name = "COGNITO_USER_POOL_ID", value = var.cognito_user_pool_id },
        { name = "COGNITO_CLIENT_ID", value = var.cognito_client_id }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.api_log_group_name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.name_prefix}-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.web_cpu
  memory                   = var.web_memory
  execution_role_arn       = var.execution_role_arn
  tags                     = merge(var.tags, { Name = "${var.name_prefix}-web" })

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = var.web_image
      essential = true
      portMappings = [{
        containerPort = 3000
        protocol      = "tcp"
      }]
      environment = [
        { name = "API_ORIGIN", value = "http://${aws_lb.this.dns_name}:8080" },
        { name = "APP_ORIGIN", value = "http://${aws_lb.this.dns_name}" },
        { name = "AUTH_PROVIDER", value = var.auth_provider },
        { name = "COGNITO_CLIENT_ID", value = var.cognito_client_id },
        { name = "COGNITO_DOMAIN", value = var.cognito_domain }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.web_log_group_name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "web"
        }
      }
    }
  ])
}

# Run by the pipeline before any service moves. Never a service: it must run
# exactly once per deployment, and a failure must stop the rollout rather than
# restart forever.
resource "aws_ecs_task_definition" "migration" {
  family                   = "${var.name_prefix}-migration"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.api_task_role_arn
  tags                     = merge(var.tags, { Name = "${var.name_prefix}-migration" })

  container_definitions = jsonencode([
    {
      name      = "migration"
      image     = var.api_image
      essential = true
      # The same image being deployed, so the migrations and the code that
      # expects them are the same commit.
      command = ["alembic", "upgrade", "head"]
      environment = [
        { name = "DATABASE_URL", value = var.database_url }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.api_log_group_name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "migration"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name_prefix}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.document_processor_role_arn
  tags                     = merge(var.tags, { Name = "${var.name_prefix}-worker" })

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = var.api_image
      essential = true
      command   = ["retailops-worker"]
      environment = [
        { name = "DATABASE_URL", value = var.database_url },
        { name = "AWS_ENABLED", value = "true" },
        # A worker and the API do not share a filesystem, so the document must
        # live in the object store or it is unreadable exactly when it matters.
        { name = "AWS_USE_S3_STORAGE", value = "true" },
        { name = "AWS_USE_TEXTRACT", value = "true" },
        { name = "AWS_USE_BEDROCK", value = "true" },
        { name = "AWS_DOCUMENTS_BUCKET", value = var.documents_bucket },
        { name = "INSTANCE_COUNT", value = tostring(var.desired_count) },
        { name = "JOB_QUEUE_PROVIDER", value = "sqs" },
        { name = "JOBS_QUEUE_URL", value = var.jobs_queue_url },
        { name = "AUTH_PROVIDER", value = var.auth_provider },
        { name = "COGNITO_USER_POOL_ID", value = var.cognito_user_pool_id },
        { name = "COGNITO_CLIENT_ID", value = var.cognito_client_id }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.api_log_group_name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name            = "${var.name_prefix}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_count
  launch_type     = "FARGATE"
  tags            = merge(var.tags, { Name = "${var.name_prefix}-worker" })

  network_configuration {
    subnets          = local.task_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = var.assign_task_public_ip
  }
}

resource "aws_ecs_service" "api" {
  name            = "${var.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  tags            = merge(var.tags, { Name = "${var.name_prefix}-api" })

  network_configuration {
    subnets          = local.task_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = var.assign_task_public_ip
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.api]
}

resource "aws_ecs_service" "web" {
  name            = "${var.name_prefix}-web"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  tags            = merge(var.tags, { Name = "${var.name_prefix}-web" })

  network_configuration {
    subnets          = local.task_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = var.assign_task_public_ip
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.web]
}
