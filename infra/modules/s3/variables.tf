variable "bucket_name" {
  type        = string
  description = "Globally unique documents bucket name."
}

variable "force_destroy" {
  type        = bool
  description = "Allow Terraform to empty the bucket on destroy. True only for disposable dev."
  default     = false
}

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Abort incomplete multipart uploads after this many days."
  default     = 7
}

variable "noncurrent_version_expiration_days" {
  type        = number
  description = "Expire noncurrent object versions after this many days. 0 disables the rule."
  default     = 90
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the bucket."
  default     = {}
}
