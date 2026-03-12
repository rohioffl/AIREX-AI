output "ecs_cluster_name" {
  value = module.platform.ecs_cluster_name
}

output "ecs_services" {
  value = module.platform.ecs_services
}

output "alb_dns_name" {
  value = module.platform.alb_dns_name
}

output "cloudfront_domain_name" {
  value = module.frontend.cloudfront_domain_name
}

output "frontend_bucket_name" {
  value = module.frontend.frontend_bucket_name
}

output "frontend_cloudfront_distribution_id" {
  value = module.frontend.frontend_cloudfront_distribution_id
}

output "hostinger_dns_records" {
  value = var.frontend_domain == "" && var.litellm_domain == "" && var.langfuse_domain == "" ? null : {
    frontend = {
      type  = "CNAME"
      name  = var.frontend_domain
      value = module.frontend.cloudfront_domain_name
    }
    litellm = {
      type  = "CNAME"
      name  = var.litellm_domain
      value = module.platform.alb_dns_name
    }
    langfuse = {
      type  = "CNAME"
      name  = var.langfuse_domain
      value = module.platform.alb_dns_name
    }
  }
}

output "rds_airex_endpoint" {
  description = "AIREX Postgres RDS endpoint (host:port)"
  value       = module.platform.rds_airex_endpoint
}

output "rds_langfuse_endpoint" {
  description = "Langfuse Postgres RDS endpoint (host:port)"
  value       = module.platform.rds_langfuse_endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = module.platform.redis_endpoint
}

output "redis_port" {
  description = "ElastiCache Redis port"
  value       = module.platform.redis_port
}

output "data_security_group_id" {
  description = "Security group for RDS and Redis"
  value       = module.platform.data_security_group_id
}

output "secrets_created" {
  value = module.platform.secrets_created
}

