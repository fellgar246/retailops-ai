locals {
  name_prefix = "${var.project}-${var.environment}"
  common_tags = merge(var.tags, {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Repository  = "retailops-ai"
  })
}

module "networking" {
  source                = "../networking"
  name_prefix           = local.name_prefix
  vpc_cidr              = var.vpc_cidr
  azs                   = var.azs
  public_subnet_cidrs   = var.public_subnet_cidrs
  private_subnet_cidrs  = var.private_subnet_cidrs
  enable_nat_gateway    = var.enable_nat_gateway
  enable_public_ingress = var.enable_public_ingress
  tags                  = merge(local.common_tags, { Component = "network" })
}

module "documents" {
  source        = "../s3"
  bucket_name   = var.documents_bucket_name
  force_destroy = var.force_destroy_documents
  tags          = merge(local.common_tags, { Component = "documents", DataClass = "supplier-documents" })
}

module "ecr" {
  source               = "../ecr"
  repository_names     = var.ecr_repository_names
  image_tag_mutability = var.image_tag_mutability
  tags                 = merge(local.common_tags, { Component = "ecr" })
}

module "secrets" {
  source                  = "../secrets"
  recovery_window_in_days = var.secret_recovery_window_days
  tags                    = merge(local.common_tags, { Component = "secrets" })
  secrets = {
    database = {
      name        = "${var.project}/${var.environment}/database"
      description = "Database credentials placeholder. Set the value out of band before RDS or ECS."
    }
    application = {
      name        = "${var.project}/${var.environment}/application"
      description = "Application secrets placeholder. Set the value out of band before ECS."
    }
  }
}

module "iam" {
  source                       = "../iam_foundation"
  name_prefix                  = local.name_prefix
  aws_region                   = var.aws_region
  account_id                   = var.account_id
  documents_bucket_arn         = module.documents.bucket_arn
  ecr_repository_arns          = values(module.ecr.repository_arns)
  secret_arns                  = values(module.secrets.secret_arns)
  bedrock_model_id             = var.bedrock_model_id
  bedrock_inference_profile_id = var.bedrock_inference_profile_id
  tags                         = merge(local.common_tags, { Component = "iam" })
}

module "budget" {
  source            = "../budget"
  budget_name       = "${local.name_prefix}-monthly"
  limit_usd         = var.budget_limit_usd
  time_period_start = var.budget_time_period_start
  alert_email       = var.budget_alert_email
  tags              = merge(local.common_tags, { Component = "cost" })
}
