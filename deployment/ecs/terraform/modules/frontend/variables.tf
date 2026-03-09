variable "project_name" { type = string }
variable "environment" { type = string }
variable "enable_custom_domains" { type = bool }
variable "frontend_domain" { type = string }
variable "cloudfront_certificate_arn" { type = string }
variable "alb_dns_name" { type = string }

locals {
  name_prefix              = "${var.project_name}-${var.environment}"
  custom_domains_enabled   = var.enable_custom_domains
  cloudfront_aliases       = local.custom_domains_enabled ? [var.frontend_domain] : []
  cloudfront_origin_policy = local.custom_domains_enabled ? "https-only" : "http-only"
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

