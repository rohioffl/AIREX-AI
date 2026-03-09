variable "aws_region" {
  description = "AWS region for the Terraform state backend"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project identifier"
  type        = string
  default     = "airex"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "state_bucket_name" {
  description = "Globally unique S3 bucket name for Terraform state"
  type        = string
}

variable "lock_table_name" {
  description = "DynamoDB table name used for Terraform state locking"
  type        = string
}

variable "force_destroy" {
  description = "Allow destroying the state bucket in non-production testing"
  type        = bool
  default     = false
}
