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

output "secrets_created" {
  value = module.platform.secrets_created
}
