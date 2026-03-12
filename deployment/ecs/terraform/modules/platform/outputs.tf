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

output "data_security_group_id" {
  description = "Security group ID for RDS and Redis (allows ECS ingress on 5432 and 6379)"
  value       = aws_security_group.data.id
}

output "rds_airex_endpoint" {
  description = "AIREX RDS Postgres endpoint (host:port)"
  value       = "${aws_db_instance.airex.address}:${aws_db_instance.airex.port}"
}

output "rds_airex_address" {
  description = "AIREX RDS Postgres hostname"
  value       = aws_db_instance.airex.address
}

output "rds_langfuse_endpoint" {
  description = "Langfuse RDS Postgres endpoint (host:port)"
  value       = "${aws_db_instance.langfuse.address}:${aws_db_instance.langfuse.port}"
}

output "rds_langfuse_address" {
  description = "Langfuse RDS Postgres hostname"
  value       = aws_db_instance.langfuse.address
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint address"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "ElastiCache Redis port"
  value       = aws_elasticache_replication_group.redis.port
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

