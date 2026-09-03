variable "name_prefix" {
  type        = string
  description = "Prefix for IAM role names."
}

variable "aws_region" {
  type        = string
  description = "Region used to build service ARNs."
}

variable "account_id" {
  type        = string
  description = "Account id used to build ARNs. Passed in; not looked up."
}

variable "documents_bucket_arn" {
  type        = string
  description = "Documents bucket ARN."
}

variable "documents_queue_arn" {
  type        = string
  description = "Document intake queue ARN."
}

variable "review_callbacks_queue_arn" {
  type        = string
  description = "Human-review callback queue ARN."
}

variable "bedrock_model_id" {
  type        = string
  description = "Bedrock foundation-model id the API may invoke."
}

variable "bedrock_inference_profile_id" {
  type        = string
  description = "Optional inference profile the API may invoke."
  default     = ""
}

variable "bedrock_inference_destination_regions" {
  type        = list(string)
  description = "Regions a geo inference profile may route to."
  default     = ["us-east-1", "us-east-2", "us-west-2"]
}

variable "sagemaker_model_package_group_arn" {
  type        = string
  description = "Model package group ARN for registry writes."
}

variable "api_log_group_arn" {
  type        = string
  description = "API log group ARN."
}

variable "web_log_group_arn" {
  type        = string
  description = "Web log group ARN."
}

variable "ecr_repository_arns" {
  type        = list(string)
  description = "ECR repositories the execution role may pull from."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to IAM roles."
  default     = {}
}
