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

output "alb_dns_name" {
  value = aws_lb.public.dns_name
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.frontend.domain_name
}

output "frontend_bucket_name" {
  value = aws_s3_bucket.frontend.bucket
}

output "frontend_cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.frontend.id
}

output "hostinger_dns_records" {
  value = var.frontend_domain == "" && var.litellm_domain == "" && var.langfuse_domain == "" ? null : {
    frontend = {
      type  = "CNAME"
      name  = var.frontend_domain
      value = aws_cloudfront_distribution.frontend.domain_name
    }
    litellm = {
      type  = "CNAME"
      name  = var.litellm_domain
      value = aws_lb.public.dns_name
    }
    langfuse = {
      type  = "CNAME"
      name  = var.langfuse_domain
      value = aws_lb.public.dns_name
    }
  }
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
