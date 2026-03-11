variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "enable_custom_domains" { type = bool }
variable "frontend_domain" { type = string }
variable "litellm_domain" { type = string }
variable "langfuse_domain" { type = string }
variable "alb_certificate_arn" { type = string }
variable "api_image" { type = string }
variable "worker_image" { type = string }
variable "litellm_image" { type = string }
variable "langfuse_image" { type = string }
variable "api_desired_count" { type = number }
variable "worker_desired_count" { type = number }
variable "litellm_desired_count" { type = number }
variable "langfuse_desired_count" { type = number }
variable "database_instance_class" { type = string }
variable "database_name_airex" { type = string }
variable "database_name_langfuse" { type = string }
variable "database_username" { type = string }
variable "redis_node_type" { type = string }
variable "cors_origins" { type = string }
variable "llm_primary_model" { type = string }
variable "llm_fallback_model" { type = string }
variable "llm_embedding_model" { type = string }

variable "frontend_url" {
  description = "Frontend URL for invitation links and email notifications"
  type        = string
  default     = "http://localhost:5173"
}

locals {
  name_prefix              = "${var.project_name}-${var.environment}"
  custom_domains_enabled   = var.enable_custom_domains
  alb_listener_port        = local.custom_domains_enabled ? 443 : 80
  alb_listener_protocol    = local.custom_domains_enabled ? "HTTPS" : "HTTP"
  cloudfront_aliases       = local.custom_domains_enabled ? [var.frontend_domain] : []
  cloudfront_origin_policy = local.custom_domains_enabled ? "https-only" : "http-only"
  vpc_id                   = var.vpc_id
  public_subnet_ids        = var.public_subnet_ids
  private_subnet_ids       = var.private_subnet_ids
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
