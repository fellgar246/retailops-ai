variable "budget_name" {
  type        = string
  description = "AWS Budgets display name."
}

variable "limit_usd" {
  type        = string
  description = "Monthly cost limit in USD."
}

variable "time_period_start" {
  type        = string
  description = "Budget start in AWS format YYYY-MM-DD_HH:MM."
}

variable "alert_email" {
  type        = string
  description = "Optional subscriber for 80% and 100% actual-cost alerts. Empty skips notifications."
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the budget."
  default     = {}
}
