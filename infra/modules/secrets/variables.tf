variable "secrets" {
  type = map(object({
    name        = string
    description = string
  }))
  description = "Secret containers to create. Values are never written by Terraform."
}

variable "recovery_window_in_days" {
  type        = number
  description = "Secrets Manager recovery window. 0 allows immediate recreate in disposable dev."
  default     = 7
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to each secret."
  default     = {}
}
