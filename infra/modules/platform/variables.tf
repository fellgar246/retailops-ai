variable "project" {
  type        = string
  description = "Project name used in resource prefixes and tags."
}

variable "environment" {
  type        = string
  description = "Environment name: dev, staging or prod."
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
  description = "Create a NAT gateway for private Fargate egress."
  default     = true
}

variable "documents_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket for supplier documents and declared model URIs."
}

variable "ecr_namespace" {
  type        = string
  description = "Prefix for ECR repository names."
}

variable "image_tag_mutability" {
  type        = string
  description = "ECR tag mutability."
  default     = "IMMUTABLE"
}

variable "db_name" {
  type    = string
  default = "retailops"
}

variable "db_username" {
  type    = string
  default = "retailops"
}

variable "master_password" {
  type        = string
  sensitive   = true
  description = "RDS master password. Supply via TF_VAR_master_password; never commit it."
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_multi_az" {
  type    = bool
  default = false
}

variable "db_backup_retention_period" {
  type    = number
  default = 7
}

variable "skip_final_snapshot" {
  type    = bool
  default = true
}

variable "api_image" {
  type        = string
  description = "API container image. Placeholder until ECR is populated."
}

variable "web_image" {
  type        = string
  description = "Web container image. Placeholder until ECR is populated."
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "cors_origins" {
  type        = string
  description = "Comma-separated CORS origins for the API task."
  default     = ""
}

variable "bedrock_model_id" {
  type        = string
  description = "Bedrock model id the API task role may invoke."
}

variable "bedrock_inference_profile_id" {
  type        = string
  description = "Optional Bedrock inference profile the API task role may invoke."
  default     = ""
}

variable "sagemaker_model_group" {
  type        = string
  description = "SageMaker model package group name."
  default     = "category-forecast"
}

variable "review_timeout_seconds" {
  type    = number
  default = 604800
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "tags" {
  type        = map(string)
  description = "Additional tags merged with the standard project tags."
  default     = {}
}

variable "enable_load_balancer" {
  type        = bool
  description = "Put the services behind a load balancer. False runs one task holding both containers, which removes the largest fixed cost."
  default     = true
}

variable "use_fargate_spot" {
  type        = bool
  description = "Run on spare capacity: far cheaper, interruptible."
  default     = false
}

variable "application_cpu" {
  type        = number
  description = "CPU for the combined task."
  default     = 512
}

variable "application_memory" {
  type        = number
  description = "Memory for the combined task."
  default     = 1536
}

variable "worker_count" {
  type        = number
  description = "How many workers run."
  default     = 1
}

variable "auth_provider" {
  type        = string
  description = "Identity provider the application validates tokens against."
  default     = "cognito"
}

variable "cognito_user_pool_id" {
  type        = string
  description = "User pool the API validates tokens against."
  default     = ""
}

variable "cognito_client_id" {
  type        = string
  description = "Application client id used as the token audience."
  default     = ""
}

variable "cognito_domain" {
  type        = string
  description = "Hosted sign-in domain used by the web application."
  default     = ""
}

variable "app_origin" {
  type        = string
  description = "Public origin of the web application, used for sign-in redirects."
  default     = ""
}
