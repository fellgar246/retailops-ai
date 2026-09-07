variable "project" {
  type        = string
  description = "Project name used in resource prefixes and tags."
}

variable "environment" {
  type        = string
  description = "Environment name. Only dev is applied today."
}

variable "aws_region" {
  type        = string
  description = "AWS region. Passed to modules; no account lookup."
}

variable "account_id" {
  type        = string
  description = "AWS account id used to build ARNs. Not looked up at plan time."
}

variable "azs" {
  type        = list(string)
  description = "Availability zones supplied by the environment."
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR."
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs, one per AZ."
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private subnet CIDRs, one per AZ."
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Create a NAT gateway. Leave false until private Fargate egress is required."
  default     = false
}

variable "enable_public_ingress" {
  type        = bool
  description = "Open ALB ports to the internet. Leave false until public traffic is intended."
  default     = false
}

variable "documents_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket for supplier documents and declared model URIs."
}

variable "force_destroy_documents" {
  type        = bool
  description = "Empty the documents bucket on destroy. True only for disposable dev."
  default     = false
}

variable "ecr_repository_names" {
  type        = list(string)
  description = "ECR repository names for the API and web images."
}

variable "image_tag_mutability" {
  type        = string
  description = "ECR tag mutability."
  default     = "IMMUTABLE"
}

variable "secret_recovery_window_days" {
  type        = number
  description = "Secrets Manager recovery window. 0 allows immediate recreate in disposable dev."
  default     = 0
}

variable "budget_limit_usd" {
  type        = string
  description = "Monthly AWS Budget limit in USD."
  default     = "5"
}

variable "budget_alert_email" {
  type        = string
  description = "Optional budget alert subscriber. Empty skips notifications."
  default     = ""
}

variable "budget_time_period_start" {
  type        = string
  description = "Budget start in AWS format YYYY-MM-DD_HH:MM."
}

variable "bedrock_model_id" {
  type        = string
  description = "Bedrock foundation-model id the API task role may invoke."
  default     = "anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "bedrock_inference_profile_id" {
  type        = string
  description = "Cross-region inference profile used as the Converse model id."
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "tags" {
  type        = map(string)
  description = "Additional tags merged with the standard project tags."
  default     = {}
}
