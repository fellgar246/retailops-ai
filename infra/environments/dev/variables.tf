variable "project" {
  type    = string
  default = "retailops"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "account_id" {
  type        = string
  description = "AWS account id. Placeholder until a real account is selected."
}

variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.0.0/24", "10.20.1.0/24"]
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "documents_bucket_name" {
  type        = string
  description = "Globally unique documents bucket. Include the account id in the name."
}

variable "bedrock_model_id" {
  type        = string
  description = "Bedrock model id the API may invoke after account access is granted."
}

variable "sagemaker_model_group" {
  type    = string
  default = "category-forecast"
}

variable "master_password" {
  type        = string
  sensitive   = true
  description = "RDS master password. Set TF_VAR_master_password; do not put a real value in tfvars."
}

variable "api_image" {
  type    = string
  default = "public.ecr.aws/docker/library/python:3.12-slim"
}

variable "web_image" {
  type    = string
  default = "public.ecr.aws/docker/library/node:20-alpine"
}

variable "cors_origins" {
  type        = string
  default     = ""
  description = "Set to the load-balancer origin after the first apply."
}
