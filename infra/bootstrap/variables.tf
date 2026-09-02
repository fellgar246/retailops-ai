variable "project" {
  type    = string
  default = "retailops-ai"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "account_id" {
  type        = string
  description = "AWS account that owns the remote-state bucket."
}

variable "state_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket for Terraform state. Do not reuse the documents bucket."
}

variable "enable_cost_allocation_tags" {
  type        = bool
  description = "Activate standard cost-allocation tags. Requires Cost Explorer to already be enabled on the account."
  default     = false
}
