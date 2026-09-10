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

variable "document_object_prefixes" {
  type        = list(string)
  description = "S3 key prefixes the document-processor role may read and write."
  default     = ["supplier-documents", "live-smoke", "documents"]
}

variable "bedrock_model_id" {
  type        = string
  description = "Bedrock foundation-model id the API task role may invoke."
  default     = "anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "bedrock_inference_profile_id" {
  type        = string
  description = "Cross-region inference profile used as the Converse model id."
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "bedrock_inference_destination_regions" {
  type        = list(string)
  description = "Regions the US inference profile may route to."
  default     = ["us-east-1", "us-east-2", "us-west-2"]
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to IAM roles."
  default     = {}
}

variable "jobs_queue_arns" {
  type        = list(string)
  description = "Queues the document processor may consume. Empty grants nothing."
  default     = []
}
