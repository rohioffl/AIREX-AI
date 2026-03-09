output "alb_dns_name" {
  value = aws_lb.public.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_services" {
  value = {
    api      = aws_ecs_service.api.name
    worker   = aws_ecs_service.worker.name
    litellm  = aws_ecs_service.litellm.name
    langfuse = aws_ecs_service.langfuse.name
  }
}

output "ecs_services_security_group_id" {
  value = aws_security_group.ecs_services.id
}

output "secrets_created" {
  value = [
    aws_secretsmanager_secret.backend_database_url.name,
    aws_secretsmanager_secret.backend_redis_url.name,
    aws_secretsmanager_secret.backend_secret_key.name,
    aws_secretsmanager_secret.litellm_master_key.name,
    aws_secretsmanager_secret.langfuse_database_url.name,
    aws_secretsmanager_secret.langfuse_nextauth_secret.name,
    aws_secretsmanager_secret.langfuse_salt.name,
    aws_secretsmanager_secret.langfuse_public_key.name,
    aws_secretsmanager_secret.langfuse_secret_key.name,
  ]
}
