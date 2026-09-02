variable "name_prefix" {
  type        = string
  description = "Prefix for IAM role names."
}

variable "aws_region" {
  type        = string
  description = "Region used to build log-group ARNs."
}

variable "account_id" {
  type        = string
  description = "Account id used to build ARNs. Passed in; not looked up."
}

variable "documents_bucket_arn" {
  type        = string
  description = "Documents bucket ARN."
}

variable "ecr_repository_arns" {
  type        = list(string)
  description = "ECR repositories the execution role may pull from."
}

variable "secret_arns" {
  type        = list(string)
  description = "Secrets Manager ARNs the execution and API task roles may read."
}

variable "model_artifact_prefix" {
  type        = string
  description = "S3 key prefix the ML role may use for declared model artifacts."
  default     = "models"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to IAM roles."
  default     = {}
}
