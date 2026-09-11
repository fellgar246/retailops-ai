variable "name_prefix" {
  type        = string
  description = "Prefix for the cluster, services and load balancer."
}

variable "cluster_name" {
  type        = string
  description = "ECS cluster name. Shared with CloudWatch alarms so modules do not cycle."
}

variable "vpc_id" {
  type        = string
  description = "VPC that hosts the load balancer target groups."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for the application load balancer."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for Fargate tasks."
}

variable "alb_security_group_id" {
  type        = string
  description = "Security group attached to the load balancer."
}

variable "ecs_security_group_id" {
  type        = string
  description = "Security group attached to Fargate tasks."
}

variable "execution_role_arn" {
  type        = string
  description = "ECS task execution role."
}

variable "api_task_role_arn" {
  type        = string
  description = "Application role for the API task."
}

variable "api_image" {
  type        = string
  description = "Container image for the API."
}

variable "web_image" {
  type        = string
  description = "Container image for the web console."
}

variable "api_log_group_name" {
  type        = string
  description = "CloudWatch log group for API stdout."
}

variable "web_log_group_name" {
  type        = string
  description = "CloudWatch log group for web stdout."
}

variable "aws_region" {
  type        = string
  description = "Region used in the awslogs driver."
}

variable "api_cpu" {
  type        = number
  description = "Fargate CPU units for the API task."
  default     = 512
}

variable "api_memory" {
  type        = number
  description = "Fargate memory (MiB) for the API task."
  default     = 1024
}

variable "web_cpu" {
  type        = number
  description = "Fargate CPU units for the web task."
  default     = 256
}

variable "web_memory" {
  type        = number
  description = "Fargate memory (MiB) for the web task."
  default     = 512
}

variable "desired_count" {
  type        = number
  description = "Desired task count per service."
  default     = 1
}

variable "database_url" {
  type        = string
  description = "SQLAlchemy URL injected into the API task. Sensitive."
  sensitive   = true
}

variable "cors_origins" {
  type        = string
  description = "CORS origins passed to the API."
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to ECS and load-balancer resources."
  default     = {}
}

variable "auth_provider" {
  type        = string
  description = "Identity provider the application validates tokens against."
  default     = "cognito"
}

variable "cognito_user_pool_id" {
  type        = string
  description = "User pool the API validates tokens against."
  default     = ""
}

variable "cognito_client_id" {
  type        = string
  description = "Application client id used as the token audience."
  default     = ""
}

variable "cognito_domain" {
  type        = string
  description = "Hosted sign-in domain used by the web application."
  default     = ""
}

variable "worker_cpu" {
  type        = number
  description = "CPU units for the worker task."
  default     = 512
}

variable "worker_memory" {
  type        = number
  description = "Memory for the worker task."
  default     = 1024
}

variable "worker_count" {
  type        = number
  description = "How many workers run. Concurrency comes from more of them."
  default     = 1
}

variable "document_processor_role_arn" {
  type        = string
  description = "Task role the worker assumes."
  default     = ""
}

variable "documents_bucket" {
  type        = string
  description = "Object store holding supplier documents."
  default     = ""
}

variable "jobs_queue_url" {
  type        = string
  description = "Queue the API announces work on and the worker consumes."
  default     = ""
}

variable "assign_task_public_ip" {
  type        = bool
  description = "Place tasks in public subnets with a public address. Required when there is no NAT gateway, because Fargate cannot otherwise reach the registry."
  default     = false
}
