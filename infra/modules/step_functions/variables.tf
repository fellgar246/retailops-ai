variable "name_prefix" {
  type        = string
  description = "Prefix for the state machine."
}

variable "role_arn" {
  type        = string
  description = "IAM role the state machine assumes."
}

variable "review_queue_url" {
  type        = string
  description = "SQS queue that receives the wait-for-callback task token."
}

variable "timeout_seconds" {
  type        = number
  description = "Maximum time a human review may stay open."
  default     = 604800
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the state machine."
  default     = {}
}
