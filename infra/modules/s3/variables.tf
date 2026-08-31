variable "bucket_name" {
  type        = string
  description = "Globally unique documents bucket name."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the bucket."
  default     = {}
}
