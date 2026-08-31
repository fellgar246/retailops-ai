variable "model_package_group_name" {
  type        = string
  description = "SageMaker model package group used as the hosted registry."
}

variable "description" {
  type        = string
  description = "Human-readable group description."
  default     = "RetailOps demand-model versions."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the package group."
  default     = {}
}
