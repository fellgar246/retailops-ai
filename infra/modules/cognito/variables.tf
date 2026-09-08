variable "name_prefix" {
  type        = string
  description = "Shared {project}-{environment} prefix for pool resources."
}

variable "domain_prefix" {
  type        = string
  description = "Globally unique prefix for the provider-hosted sign-in domain."
}

variable "tier" {
  type        = string
  description = "User pool feature tier. Both LITE and ESSENTIALS include the same free monthly active users; PLUS has no free allowance."
  default     = "ESSENTIALS"

  validation {
    condition     = contains(["LITE", "ESSENTIALS", "PLUS"], var.tier)
    error_message = "tier must be LITE, ESSENTIALS or PLUS."
  }
}

variable "callback_urls" {
  type        = list(string)
  description = "Exact redirect targets accepted after sign-in."

  validation {
    condition     = length(var.callback_urls) > 0
    error_message = "at least one callback URL is required."
  }
}

variable "logout_urls" {
  type        = list(string)
  description = "Exact redirect targets accepted after sign-out."
}

variable "roles" {
  type        = list(string)
  description = "Groups mapped onto application roles."
  default     = ["reviewer", "viewer"]
}

variable "access_token_validity_minutes" {
  type        = number
  description = "Access token lifetime."
  default     = 60
}

variable "id_token_validity_minutes" {
  type        = number
  description = "Identity token lifetime."
  default     = 60
}

variable "refresh_token_validity_days" {
  type        = number
  description = "Refresh token lifetime."
  default     = 1
}

variable "deletion_protection" {
  type        = string
  description = "ACTIVE keeps the pool from being destroyed. Disposable environments may set INACTIVE."
  default     = "ACTIVE"

  validation {
    condition     = contains(["ACTIVE", "INACTIVE"], var.deletion_protection)
    error_message = "deletion_protection must be ACTIVE or INACTIVE."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource in this module."
  default     = {}
}
