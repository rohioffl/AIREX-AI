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
      name  = "api"
      image = var.api_image
      essential = true
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
      name      = "litellm"
      image     = var.litellm_image
      essential = true
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
      name      = "langfuse"
      image     = var.langfuse_image
      essential = true
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

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${local.name_prefix}-migrate"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  network_mode             = "awsvpc"
  execution_role_arn       = aws_iam_role.execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name      = "migrate"
      image     = var.api_image
      command   = ["alembic", "upgrade", "head"]
      essential = true
      secrets = [
        { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.backend_database_url.arn }
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
