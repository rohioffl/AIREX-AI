locals {
  name_prefix              = "${var.project_name}-${var.environment}"
  custom_domains_enabled   = var.enable_custom_domains
  alb_listener_port        = local.custom_domains_enabled ? 443 : 80
  alb_listener_protocol    = local.custom_domains_enabled ? "HTTPS" : "HTTP"
  cloudfront_aliases       = local.custom_domains_enabled ? [var.frontend_domain] : []
  cloudfront_origin_policy = local.custom_domains_enabled ? "https-only" : "http-only"

  vpc_id = var.create_vpc ? aws_vpc.main[0].id : var.vpc_id

  public_subnet_ids = var.create_vpc ? [
    for subnet in aws_subnet.public : subnet.id
  ] : var.public_subnet_ids

  private_subnet_ids = var.create_vpc ? [
    for subnet in aws_subnet.private : subnet.id
  ] : var.private_subnet_ids

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
