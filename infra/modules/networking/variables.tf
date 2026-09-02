variable "name_prefix" {
  type        = string
  description = "Prefix applied to VPC, subnet and security-group names."
}

variable "vpc_cidr" {
  type        = string
  description = "IPv4 CIDR for the VPC."
}

variable "azs" {
  type        = list(string)
  description = "Availability zones. Passed in so validation does not query the account."
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "One public subnet CIDR per availability zone."
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "One private subnet CIDR per availability zone."
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Create a single NAT gateway in the first public subnet."
  default     = true
}

variable "enable_public_ingress" {
  type        = bool
  description = "Open ALB ports 80 and 8080 to 0.0.0.0/0. Leave false until public traffic is intended."
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every networking resource."
  default     = {}
}
