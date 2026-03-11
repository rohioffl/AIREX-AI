locals {
  effective_vpc_id              = var.create_vpc ? module.vpc.vpc_id : var.vpc_id
  effective_public_subnet_ids   = var.create_vpc ? module.vpc.public_subnet_ids : var.public_subnet_ids
  effective_private_subnet_ids  = var.create_vpc ? module.vpc.private_subnet_ids : var.private_subnet_ids
}

module "vpc" {
  source = "../../modules/vpc"

  project_name         = var.project_name
  environment          = var.environment
  create_vpc           = var.create_vpc
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
}

module "platform" {
  source = "../../modules/platform"

  project_name             = var.project_name
  environment              = var.environment
  aws_region               = var.aws_region
  vpc_id                   = local.effective_vpc_id
  public_subnet_ids        = local.effective_public_subnet_ids
  private_subnet_ids       = local.effective_private_subnet_ids
  enable_custom_domains    = var.enable_custom_domains
  frontend_domain          = var.frontend_domain
  litellm_domain           = var.litellm_domain
  langfuse_domain          = var.langfuse_domain
  alb_certificate_arn      = var.alb_certificate_arn
  api_image                = var.api_image
  worker_image             = var.worker_image
  litellm_image            = var.litellm_image
  langfuse_image           = var.langfuse_image
  api_desired_count        = var.api_desired_count
  worker_desired_count     = var.worker_desired_count
  litellm_desired_count    = var.litellm_desired_count
  langfuse_desired_count   = var.langfuse_desired_count
  database_instance_class  = var.database_instance_class
  database_name_airex      = var.database_name_airex
  database_name_langfuse   = var.database_name_langfuse
  database_username        = var.database_username
  redis_node_type          = var.redis_node_type
  cors_origins             = var.cors_origins
  llm_primary_model        = var.llm_primary_model
  llm_fallback_model       = var.llm_fallback_model
  llm_embedding_model      = var.llm_embedding_model
  frontend_url             = var.frontend_url
}

frontend_url = var.frontend_url
  }
module "frontend" {
  source = "../../modules/frontend"

  project_name               = var.project_name
  environment                = var.environment
  enable_custom_domains      = var.enable_custom_domains
  frontend_domain            = var.frontend_domain
  cloudfront_certificate_arn = var.cloudfront_certificate_arn
  alb_dns_name               = module.platform.alb_dns_name
}
