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

variable "pipeline_repository" {
  type        = string
  description = "The only repository whose workflows may assume the pipeline roles, as owner/name."
}

variable "pipeline_deploy_branch" {
  type        = string
  description = "The only branch that may deploy."
  default     = "main"
}

variable "create_github_oidc_provider" {
  type        = bool
  description = "Create the OIDC provider. False when the account already has one."
  default     = true
}

variable "existing_github_oidc_provider_arn" {
  type        = string
  description = "ARN of an existing provider, used when one is not created."
  default     = ""
}

variable "pipeline_ecr_repository_arns" {
  type        = list(string)
  description = "Registry repositories the pipeline may push to."
  default     = []
}

variable "pipeline_deploy_policy_arns" {
  type        = list(string)
  description = "Managed policies the deploy role needs to apply an environment."
  default     = []
}
