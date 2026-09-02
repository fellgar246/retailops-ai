variable "project" {
  type    = string
  default = "retailops-ai"
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
  description = "AWS account id. Must match the authenticated caller."
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

variable "budget_limit_usd" {
  type        = string
  description = "Monthly AWS Budget limit in USD for this account."
  default     = "50"
}

variable "budget_alert_email" {
  type        = string
  description = "Optional budget alert subscriber. Empty skips notifications."
  default     = ""
}

variable "budget_time_period_start" {
  type        = string
  description = "Budget start in AWS format YYYY-MM-DD_HH:MM."
  default     = "2026-09-01_00:00"
}
