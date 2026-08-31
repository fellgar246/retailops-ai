variable "name_prefix" {
  type        = string
  description = "Prefix for queues and the event bus."
}

variable "account_id" {
  type        = string
  description = "AWS account id used in queue policies. Passed in; not looked up."
}

variable "aws_region" {
  type        = string
  description = "Region used to build the EventBridge principal ARN."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to messaging resources."
  default     = {}
}
