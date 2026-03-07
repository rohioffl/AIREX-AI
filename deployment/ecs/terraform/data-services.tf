resource "aws_security_group" "data" {
  name        = "${local.name_prefix}-data-sg"
  description = "RDS and Redis security group"
  vpc_id      = var.vpc_id

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
  subnet_ids = var.private_subnet_ids
  tags       = local.tags
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = var.private_subnet_ids
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
  secret_string = "rediss://:${random_password.redis_auth_token.result}@${aws_elasticache_replication_group.redis.configuration_endpoint_address}:6379/0"
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
