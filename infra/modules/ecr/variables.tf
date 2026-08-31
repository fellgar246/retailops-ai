variable "repository_names" {
  type        = list(string)
  description = "ECR repository names for application images."
}

variable "image_tag_mutability" {
  type        = string
  description = "IMMUTABLE or MUTABLE."
  default     = "IMMUTABLE"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to each repository."
  default     = {}
}
