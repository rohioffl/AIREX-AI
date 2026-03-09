resource "aws_ssm_parameter" "cors_origins" {
  name  = "/${var.project_name}/${var.environment}/app/cors_origins"
  type  = "String"
  value = var.cors_origins
  tags  = local.tags
}

resource "aws_ssm_parameter" "llm_primary_model" {
  name  = "/${var.project_name}/${var.environment}/app/llm_primary_model"
  type  = "String"
  value = var.llm_primary_model
  tags  = local.tags
}

resource "aws_ssm_parameter" "llm_fallback_model" {
  name  = "/${var.project_name}/${var.environment}/app/llm_fallback_model"
  type  = "String"
  value = var.llm_fallback_model
  tags  = local.tags
}

resource "aws_ssm_parameter" "llm_embedding_model" {
  name  = "/${var.project_name}/${var.environment}/app/llm_embedding_model"
  type  = "String"
  value = var.llm_embedding_model
  tags  = local.tags
}

resource "aws_ssm_parameter" "litellm_host" {
  name  = "/${var.project_name}/${var.environment}/litellm/base_url"
  type  = "String"
  value = "https://${var.litellm_domain}/v1"
  tags  = local.tags
}

resource "aws_ssm_parameter" "langfuse_host" {
  name  = "/${var.project_name}/${var.environment}/langfuse/host"
  type  = "String"
  value = "https://${var.langfuse_domain}"
  tags  = local.tags
}

resource "aws_secretsmanager_secret" "backend_database_url" {
  name = "/${var.project_name}/${var.environment}/backend/database_url"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "backend_redis_url" {
  name = "/${var.project_name}/${var.environment}/backend/redis_url"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "backend_secret_key" {
  name = "/${var.project_name}/${var.environment}/backend/secret_key"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "litellm_master_key" {
  name = "/${var.project_name}/${var.environment}/litellm/master_key"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "langfuse_database_url" {
  name = "/${var.project_name}/${var.environment}/langfuse/database_url"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "langfuse_nextauth_secret" {
  name = "/${var.project_name}/${var.environment}/langfuse/nextauth_secret"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "langfuse_salt" {
  name = "/${var.project_name}/${var.environment}/langfuse/salt"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "langfuse_public_key" {
  name = "/${var.project_name}/${var.environment}/langfuse/public_key"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "langfuse_secret_key" {
  name = "/${var.project_name}/${var.environment}/langfuse/secret_key"
  tags = local.tags
}

resource "aws_ecr_repository" "api" {
  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-api" })
}

resource "aws_ecr_repository" "worker" {
  name                 = "${local.name_prefix}-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-worker" })
}

resource "aws_ecr_repository" "litellm" {
  name                 = "${local.name_prefix}-litellm"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-litellm" })
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name_prefix}-api"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name_prefix}-worker"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "litellm" {
  name              = "/ecs/${local.name_prefix}-litellm"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "langfuse" {
  name              = "/ecs/${local.name_prefix}-langfuse"
  retention_in_days = 30
  tags              = local.tags
}

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution_role" {
  name               = "${local.name_prefix}-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "execution_default" {
  role       = aws_iam_role.execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets_access" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "ssm:GetParameter",
      "ssm:GetParameters"
    ]

    resources = [
      aws_secretsmanager_secret.backend_database_url.arn,
      aws_secretsmanager_secret.backend_redis_url.arn,
      aws_secretsmanager_secret.backend_secret_key.arn,
      aws_secretsmanager_secret.litellm_master_key.arn,
      aws_secretsmanager_secret.langfuse_database_url.arn,
      aws_secretsmanager_secret.langfuse_nextauth_secret.arn,
      aws_secretsmanager_secret.langfuse_salt.arn,
      aws_secretsmanager_secret.langfuse_public_key.arn,
      aws_secretsmanager_secret.langfuse_secret_key.arn,
      aws_ssm_parameter.cors_origins.arn,
      aws_ssm_parameter.llm_primary_model.arn,
      aws_ssm_parameter.llm_fallback_model.arn,
      aws_ssm_parameter.llm_embedding_model.arn,
      aws_ssm_parameter.litellm_host.arn,
      aws_ssm_parameter.langfuse_host.arn,
    ]
  }
}

resource "aws_iam_role_policy" "execution_secrets_access" {
  name   = "${local.name_prefix}-execution-secrets"
  role   = aws_iam_role.execution_role.id
  policy = data.aws_iam_policy_document.execution_secrets_access.json
}

resource "aws_iam_role" "task_role" {
  name               = "${local.name_prefix}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags               = local.tags
}

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.tags
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  network_mode             = "awsvpc"
  execution_role_arn       = aws_iam_role.execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name         = "api"
      image        = var.api_image
      essential    = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "LLM_BASE_URL", value = aws_ssm_parameter.litellm_host.value },
        { name = "LLM_PRIMARY_MODEL", value = aws_ssm_parameter.llm_primary_model.value },
        { name = "LLM_FALLBACK_MODEL", value = aws_ssm_parameter.llm_fallback_model.value },
        { name = "LLM_EMBEDDING_MODEL", value = aws_ssm_parameter.llm_embedding_model.value },
        { name = "CORS_ORIGINS", value = aws_ssm_parameter.cors_origins.value }
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.backend_database_url.arn },
        { name = "REDIS_URL", valueFrom = aws_secretsmanager_secret.backend_redis_url.arn },
        { name = "SECRET_KEY", valueFrom = aws_secretsmanager_secret.backend_secret_key.arn },
        { name = "LLM_API_KEY", valueFrom = aws_secretsmanager_secret.litellm_master_key.arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  network_mode             = "awsvpc"
  execution_role_arn       = aws_iam_role.execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = var.worker_image
      command   = ["arq", "app.core.worker.WorkerSettings"]
      essential = true
      environment = [
        { name = "LLM_BASE_URL", value = aws_ssm_parameter.litellm_host.value },
        { name = "LLM_PRIMARY_MODEL", value = aws_ssm_parameter.llm_primary_model.value },
        { name = "LLM_FALLBACK_MODEL", value = aws_ssm_parameter.llm_fallback_model.value },
        { name = "LLM_EMBEDDING_MODEL", value = aws_ssm_parameter.llm_embedding_model.value }
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.backend_database_url.arn },
        { name = "REDIS_URL", valueFrom = aws_secretsmanager_secret.backend_redis_url.arn },
        { name = "LLM_API_KEY", valueFrom = aws_secretsmanager_secret.litellm_master_key.arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "litellm" {
  family                   = "${local.name_prefix}-litellm"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  network_mode             = "awsvpc"
  execution_role_arn       = aws_iam_role.execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name         = "litellm"
      image        = var.litellm_image
      essential    = true
      portMappings = [{ containerPort = 4000, protocol = "tcp" }]
      environment = [
        { name = "LANGFUSE_HOST", value = aws_ssm_parameter.langfuse_host.value }
      ]
      secrets = [
        { name = "LITELLM_MASTER_KEY", valueFrom = aws_secretsmanager_secret.litellm_master_key.arn },
        { name = "LANGFUSE_PUBLIC_KEY", valueFrom = aws_secretsmanager_secret.langfuse_public_key.arn },
        { name = "LANGFUSE_SECRET_KEY", valueFrom = aws_secretsmanager_secret.langfuse_secret_key.arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.litellm.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "langfuse" {
  family                   = "${local.name_prefix}-langfuse"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  network_mode             = "awsvpc"
  execution_role_arn       = aws_iam_role.execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name         = "langfuse"
      image        = var.langfuse_image
      essential    = true
      portMappings = [{ containerPort = 3000, protocol = "tcp" }]
      environment = [
        { name = "NEXTAUTH_URL", value = "https://${var.langfuse_domain}" },
        { name = "TELEMETRY_ENABLED", value = "false" }
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.langfuse_database_url.arn },
        { name = "NEXTAUTH_SECRET", valueFrom = aws_secretsmanager_secret.langfuse_nextauth_secret.arn },
        { name = "SALT", valueFrom = aws_secretsmanager_secret.langfuse_salt.arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.langfuse.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_security_group" "data" {
  name        = "${local.name_prefix}-data-sg"
  description = "RDS and Redis security group"
  vpc_id      = local.vpc_id

  ingress {
    description     = "Postgres from ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_services.id]
  }

  ingress {
    description     = "Redis from ECS"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_services.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = local.private_subnet_ids
  tags       = local.tags
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = local.private_subnet_ids
}

resource "random_password" "db_airex_password" {
  length  = 24
  special = false
}

resource "random_password" "db_langfuse_password" {
  length  = 24
  special = false
}

resource "random_password" "redis_auth_token" {
  length  = 32
  special = false
}

resource "aws_db_instance" "airex" {
  identifier             = "${local.name_prefix}-airex-db"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = var.database_instance_class
  allocated_storage      = 20
  storage_encrypted      = true
  db_name                = var.database_name_airex
  username               = var.database_username
  password               = random_password.db_airex_password.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.data.id]
  skip_final_snapshot    = true
  publicly_accessible    = false
  deletion_protection    = false

  tags = merge(local.tags, { Name = "${local.name_prefix}-airex-db" })
}

resource "aws_db_instance" "langfuse" {
  identifier             = "${local.name_prefix}-langfuse-db"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = var.database_instance_class
  allocated_storage      = 20
  storage_encrypted      = true
  db_name                = var.database_name_langfuse
  username               = var.database_username
  password               = random_password.db_langfuse_password.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.data.id]
  skip_final_snapshot    = true
  publicly_accessible    = false
  deletion_protection    = false

  tags = merge(local.tags, { Name = "${local.name_prefix}-langfuse-db" })
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = replace("${local.name_prefix}-redis", "_", "-")
  description                = "Redis for ${local.name_prefix}"
  engine                     = "redis"
  node_type                  = var.redis_node_type
  num_cache_clusters         = 1
  port                       = 6379
  parameter_group_name       = "default.redis7"
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.data.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth_token.result

  tags = local.tags
}

resource "random_password" "app_secret_key" {
  length  = 64
  special = false
}

resource "random_password" "litellm_master_key_value" {
  length  = 48
  special = false
}

resource "random_password" "langfuse_nextauth_secret_value" {
  length  = 48
  special = false
}

resource "random_password" "langfuse_salt_value" {
  length  = 32
  special = false
}

resource "random_password" "langfuse_public_key_value" {
  length  = 24
  special = false
}

resource "random_password" "langfuse_secret_key_value" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret_version" "backend_database_url" {
  secret_id     = aws_secretsmanager_secret.backend_database_url.id
  secret_string = "postgresql+asyncpg://${var.database_username}:${random_password.db_airex_password.result}@${aws_db_instance.airex.address}:5432/${var.database_name_airex}"
}

resource "aws_secretsmanager_secret_version" "backend_redis_url" {
  secret_id     = aws_secretsmanager_secret.backend_redis_url.id
  secret_string = "rediss://:${random_password.redis_auth_token.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
}

resource "aws_secretsmanager_secret_version" "backend_secret_key" {
  secret_id     = aws_secretsmanager_secret.backend_secret_key.id
  secret_string = random_password.app_secret_key.result
}

resource "aws_secretsmanager_secret_version" "litellm_master_key" {
  secret_id     = aws_secretsmanager_secret.litellm_master_key.id
  secret_string = "sk-${random_password.litellm_master_key_value.result}"
}

resource "aws_secretsmanager_secret_version" "langfuse_database_url" {
  secret_id     = aws_secretsmanager_secret.langfuse_database_url.id
  secret_string = "postgresql://${var.database_username}:${random_password.db_langfuse_password.result}@${aws_db_instance.langfuse.address}:5432/${var.database_name_langfuse}"
}

resource "aws_secretsmanager_secret_version" "langfuse_nextauth_secret" {
  secret_id     = aws_secretsmanager_secret.langfuse_nextauth_secret.id
  secret_string = random_password.langfuse_nextauth_secret_value.result
}

resource "aws_secretsmanager_secret_version" "langfuse_salt" {
  secret_id     = aws_secretsmanager_secret.langfuse_salt.id
  secret_string = random_password.langfuse_salt_value.result
}

resource "aws_secretsmanager_secret_version" "langfuse_public_key" {
  secret_id     = aws_secretsmanager_secret.langfuse_public_key.id
  secret_string = "pk-${random_password.langfuse_public_key_value.result}"
}

resource "aws_secretsmanager_secret_version" "langfuse_secret_key" {
  secret_id     = aws_secretsmanager_secret.langfuse_secret_key.id
  secret_string = "sk-${random_password.langfuse_secret_key_value.result}"
}

resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "ALB security group"
  vpc_id      = local.vpc_id

  ingress {
    description = local.custom_domains_enabled ? "HTTPS" : "HTTP"
    from_port   = local.alb_listener_port
    to_port     = local.alb_listener_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "ecs_services" {
  name        = "${local.name_prefix}-ecs-sg"
  description = "ECS services security group"
  vpc_id      = local.vpc_id

  ingress {
    description     = "API from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description     = "LiteLLM from ALB"
    from_port       = 4000
    to_port         = 4000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description     = "Langfuse from ALB"
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_lb" "public" {
  name               = "${local.name_prefix}-alb"
  load_balancer_type = "application"
  subnets            = local.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]

  tags = local.tags
}

resource "aws_lb_target_group" "api" {
  name        = substr("${local.name_prefix}-api-tg", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = local.vpc_id

  health_check {
    enabled             = true
    path                = "/health"
    matcher             = "200-399"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  tags = local.tags
}

resource "aws_lb_target_group" "litellm" {
  name        = substr("${local.name_prefix}-litel-tg", 0, 32)
  port        = 4000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = local.vpc_id

  health_check {
    enabled             = true
    path                = "/health/liveliness"
    matcher             = "200-399"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  tags = local.tags
}

resource "aws_lb_target_group" "langfuse" {
  name        = substr("${local.name_prefix}-langf-tg", 0, 32)
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = local.vpc_id

  health_check {
    enabled             = true
    path                = "/"
    matcher             = "200-399"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  tags = local.tags
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.public.arn
  port              = local.alb_listener_port
  protocol          = local.alb_listener_protocol
  ssl_policy        = local.custom_domains_enabled ? "ELBSecurityPolicy-TLS13-1-2-2021-06" : null
  certificate_arn   = local.custom_domains_enabled ? var.alb_certificate_arn : null

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener_rule" "litellm_host" {
  count        = local.custom_domains_enabled ? 1 : 0
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.litellm.arn
  }

  condition {
    host_header {
      values = [var.litellm_domain]
    }
  }
}

resource "aws_lb_listener_rule" "litellm_path" {
  count        = local.custom_domains_enabled ? 0 : 1
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.litellm.arn
  }

  condition {
    path_pattern {
      values = ["/litellm*", "/health/liveliness"]
    }
  }
}

resource "aws_lb_listener_rule" "langfuse_host" {
  count        = local.custom_domains_enabled ? 1 : 0
  listener_arn = aws_lb_listener.https.arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.langfuse.arn
  }

  condition {
    host_header {
      values = [var.langfuse_domain]
    }
  }
}

resource "aws_lb_listener_rule" "langfuse_path" {
  count        = local.custom_domains_enabled ? 0 : 1
  listener_arn = aws_lb_listener.https.arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.langfuse.arn
  }

  condition {
    path_pattern {
      values = ["/langfuse*", "/auth/*"]
    }
  }
}

resource "aws_lb_listener_rule" "api_host_path" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 30

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  dynamic "condition" {
    for_each = local.custom_domains_enabled ? [1] : []

    content {
      host_header {
        values = [var.frontend_domain]
      }
    }
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = false
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs_services.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]
  tags       = local.tags
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name_prefix}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = false
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs_services.id]
  }

  tags = local.tags
}

resource "aws_ecs_service" "litellm" {
  name            = "${local.name_prefix}-litellm"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.litellm.arn
  desired_count   = var.litellm_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = false
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs_services.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.litellm.arn
    container_name   = "litellm"
    container_port   = 4000
  }

  depends_on = [aws_lb_listener.https]
  tags       = local.tags
}

resource "aws_ecs_service" "langfuse" {
  name            = "${local.name_prefix}-langfuse"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.langfuse.arn
  desired_count   = var.langfuse_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = false
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs_services.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.langfuse.arn
    container_name   = "langfuse"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.https]
  tags       = local.tags
}
