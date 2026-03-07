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
  default     = "rohitpt.online"
}

variable "frontend_domain" {
  description = "Frontend public domain"
  type        = string
  default     = "airex.rohitpt.online"
}

variable "litellm_domain" {
  description = "LiteLLM public domain"
  type        = string
  default     = "litellm.rohitpt.online"
}

variable "langfuse_domain" {
  description = "Langfuse public domain"
  type        = string
  default     = "langfuse.rohitpt.online"
}

variable "vpc_id" {
  description = "Existing VPC ID"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS services"
  type        = list(string)
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

variable "certificate_arn_ap_south_1" {
  description = "Optional existing ACM cert ARN in ap-south-1 for ALB"
  type        = string
  default     = ""
}

variable "frontend_certificate_arn_us_east_1" {
  description = "Optional existing ACM cert ARN in us-east-1 for CloudFront"
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
