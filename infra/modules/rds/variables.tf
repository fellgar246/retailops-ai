variable "name_prefix" {
  type        = string
  description = "Prefix for the instance identifier and subnet group."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet ids for the DB subnet group."
}

variable "vpc_security_group_ids" {
  type        = list(string)
  description = "Security groups attached to the instance."
}

variable "instance_class" {
  type        = string
  description = "RDS instance class."
  default     = "db.t4g.micro"
}

variable "engine_version" {
  type        = string
  description = "PostgreSQL engine version."
  default     = "16.4"
}

variable "db_name" {
  type        = string
  description = "Initial database name."
  default     = "retailops"
}

variable "username" {
  type        = string
  description = "Master username. Password is supplied separately."
  default     = "retailops"
}

variable "password" {
  type        = string
  description = "Master password. Set via TF_VAR or a secret store; never commit it."
  sensitive   = true
}

variable "allocated_storage" {
  type        = number
  description = "Allocated storage in gibibytes."
  default     = 20
}

variable "multi_az" {
  type        = bool
  description = "Whether to run a standby in a second AZ."
  default     = false
}

variable "backup_retention_period" {
  type        = number
  description = "Automated backup retention in days."
  default     = 7
}

variable "skip_final_snapshot" {
  type        = bool
  description = "Skip the final snapshot on destroy (dev only)."
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to RDS resources."
  default     = {}
}
