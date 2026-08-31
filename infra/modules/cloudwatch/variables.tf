variable "name_prefix" {
  type        = string
  description = "Prefix for log groups and alarms."
}

variable "retention_in_days" {
  type        = number
  description = "Log retention."
  default     = 30
}

variable "ecs_cluster_name" {
  type        = string
  description = "ECS cluster name used on CPU alarms. Empty skips those alarms."
  default     = ""
}

variable "ecs_service_names" {
  type        = list(string)
  description = "ECS service names to alarm on."
  default     = []
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to log groups and alarms."
  default     = {}
}
