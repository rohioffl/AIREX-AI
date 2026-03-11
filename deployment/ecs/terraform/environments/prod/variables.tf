variable "create_vpc" {
  description = "Create a dedicated VPC, subnets, routes, and NAT gateways for this stack"
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "CIDR block for the Terraform-managed VPC"
  type        = string
  default     = "10.40.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDR blocks used when create_vpc is true"
  type        = list(string)
  default     = ["10.40.0.0/24", "10.40.1.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) >= 2
    error_message = "At least two public subnet CIDRs are required when create_vpc is true."
  }
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDR blocks used when create_vpc is true"
  type        = list(string)
  default     = ["10.40.10.0/24", "10.40.11.0/24"]

  validation {
    condition     = length(var.private_subnet_cidrs) >= 2
    error_message = "At least two private subnet CIDRs are required when create_vpc is true."
  }
}

variable "aws_region" {
  description = "Primary deployment region"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project identifier"
  type        = string
  default     = "airex"
}

variable "domain_root" {
  description = "Root domain name"
  type        = string
  default     = ""
}

variable "frontend_domain" {
  description = "Frontend public domain"
  type        = string
  default     = ""
}

variable "litellm_domain" {
  description = "LiteLLM public domain"
  type        = string
  default     = ""
}

variable "langfuse_domain" {
  description = "Langfuse public domain"
  type        = string
  default     = ""
}

variable "enable_custom_domains" {
  description = "Attach custom domains and ACM certificates now; disable to deploy first on AWS default domains"
  type        = bool
  default     = false

  validation {
    condition = var.enable_custom_domains ? (
      trimspace(var.frontend_domain) != "" &&
      trimspace(var.litellm_domain) != "" &&
      trimspace(var.langfuse_domain) != "" &&
      trimspace(var.alb_certificate_arn) != "" &&
      trimspace(var.cloudfront_certificate_arn) != ""
    ) : true
    error_message = "When enable_custom_domains is true, set frontend_domain, litellm_domain, langfuse_domain, alb_certificate_arn, and cloudfront_certificate_arn."
  }
}

variable "vpc_id" {
  description = "Existing VPC ID"
  type        = string
  default     = ""
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB"
  type        = list(string)
  default     = []
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS services"
  type        = list(string)
  default     = []
}

variable "api_desired_count" {
  description = "Desired count for API service"
  type        = number
  default     = 2
}

variable "worker_desired_count" {
  description = "Desired count for worker service"
  type        = number
  default     = 1
}

variable "litellm_desired_count" {
  description = "Desired count for LiteLLM service"
  type        = number
  default     = 1
}

variable "langfuse_desired_count" {
  description = "Desired count for Langfuse service"
  type        = number
  default     = 1
}

variable "api_image" {
  description = "ECR image for API service"
  type        = string
}

variable "worker_image" {
  description = "ECR image for worker service"
  type        = string
}

variable "litellm_image" {
  description = "ECR image for LiteLLM service"
  type        = string
}

variable "langfuse_image" {
  description = "Container image for Langfuse"
  type        = string
  default     = "langfuse/langfuse:2"
}

variable "cors_origins" {
  description = "CORS origins JSON string"
  type        = string
  default     = "[\"https://airex.rohitpt.online\"]"
}

variable "llm_primary_model" {
  description = "Primary model alias"
  type        = string
  default     = "gemini-2.0-flash"
}

variable "llm_fallback_model" {
  description = "Fallback model alias"
  type        = string
  default     = "nova-lite"
}

variable "llm_embedding_model" {
  description = "Embedding model alias"
  type        = string
  default     = "text-embedding"
}

variable "alb_certificate_arn" {
  description = "Existing ACM certificate ARN in the deployment region for the ALB"
  type        = string
  default     = ""
}

variable "cloudfront_certificate_arn" {
  description = "Existing ACM certificate ARN in us-east-1 for CloudFront"
  type        = string
  default     = ""
}

variable "database_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "database_name_airex" {
  description = "AIREX postgres database name"
  type        = string
  default     = "airex"
}

variable "database_name_langfuse" {
  description = "Langfuse postgres database name"
  type        = string
  default     = "langfuse"
}

variable "database_username" {
  description = "Master username for postgres instances"
  type        = string
  default     = "airexadmin"
}
variable "frontend_url" {
  description = "Frontend URL for invitation links and email notifications"
  type        = string
  default     = ""
}

