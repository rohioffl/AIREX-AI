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

output "migrate_task_definition_arn" {
  value = aws_ecs_task_definition.migrate.arn
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

output "hostinger_dns_records" {
  value = {
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

output "acm_dns_validation_records_ap_south_1" {
  value = var.certificate_arn_ap_south_1 == "" ? [
    for dvo in aws_acm_certificate.alb_wildcard[0].domain_validation_options : {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  ] : []
}

output "acm_dns_validation_records_us_east_1" {
  value = var.frontend_certificate_arn_us_east_1 == "" ? [
    for dvo in aws_acm_certificate.cloudfront_frontend[0].domain_validation_options : {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  ] : []
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
