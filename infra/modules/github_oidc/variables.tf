variable "name_prefix" {
  type        = string
  description = "Shared {project}-{environment} prefix for the roles."
}

variable "repository" {
  type        = string
  description = "The only repository allowed to assume these roles, as owner/name."

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.repository))
    error_message = "repository must be owner/name, with no wildcard."
  }
}

variable "deploy_branch" {
  type        = string
  description = "The only branch allowed to assume the deploy role."
  default     = "main"

  validation {
    condition     = !can(regex("[*?]", var.deploy_branch))
    error_message = "deploy_branch must name one branch; a wildcard would let any branch deploy."
  }
}

variable "create_provider" {
  type        = bool
  description = "Create the OIDC provider. False when the account already has one."
  default     = true
}

variable "existing_provider_arn" {
  type        = string
  description = "ARN of an existing provider, used when create_provider is false."
  default     = ""
}

variable "state_bucket_arn" {
  type        = string
  description = "Terraform state bucket the pipeline reads and writes."
}

variable "state_key_prefix" {
  type        = string
  description = "Key prefix inside the state bucket the pipeline may touch."
}

variable "ecr_repository_arns" {
  type        = list(string)
  description = "Registry repositories the pipeline may push to."
  default     = []
}

variable "deploy_policy_arns" {
  type        = list(string)
  description = "Additional managed policies the deploy role needs to apply an environment."
  default     = []
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource in this module."
  default     = {}
}
