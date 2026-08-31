variable "project" {
  type    = string
  default = "retailops"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "account_id" {
  type = string
}

variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.40.0.0/24", "10.40.1.0/24"]
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.40.10.0/24", "10.40.11.0/24"]
}

variable "documents_bucket_name" {
  type = string
}

variable "bedrock_model_id" {
  type = string
}

variable "sagemaker_model_group" {
  type    = string
  default = "category-forecast"
}

variable "master_password" {
  type      = string
  sensitive = true
}

variable "api_image" {
  type    = string
  default = "public.ecr.aws/docker/library/python:3.12-slim"
}

variable "web_image" {
  type    = string
  default = "public.ecr.aws/docker/library/node:20-alpine"
}

variable "cors_origins" {
  type    = string
  default = ""
}
