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
