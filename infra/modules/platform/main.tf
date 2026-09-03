locals {
  name_prefix  = "${var.project}-${var.environment}"
  cluster_name = "${local.name_prefix}-cluster"
  common_tags = merge(var.tags, {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}

module "networking" {
  source               = "../networking"
  name_prefix          = local.name_prefix
  vpc_cidr             = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = var.enable_nat_gateway
  tags                 = local.common_tags
}

module "documents" {
  source      = "../s3"
  bucket_name = var.documents_bucket_name
  tags        = local.common_tags
}

module "ecr" {
  source               = "../ecr"
  repository_names     = ["${var.ecr_namespace}/api", "${var.ecr_namespace}/web"]
  image_tag_mutability = var.image_tag_mutability
  tags                 = local.common_tags
}

module "logs" {
  source            = "../cloudwatch"
  name_prefix       = local.name_prefix
  retention_in_days = var.log_retention_days
  ecs_cluster_name  = local.cluster_name
  ecs_service_names = ["${local.name_prefix}-api", "${local.name_prefix}-web"]
  tags              = local.common_tags
}

module "registry" {
  source                   = "../sagemaker"
  model_package_group_name = var.sagemaker_model_group
  tags                     = local.common_tags
}

module "messaging" {
  source      = "../messaging"
  name_prefix = local.name_prefix
  account_id  = var.account_id
  aws_region  = var.aws_region
  tags        = local.common_tags
}

module "iam" {
  source                            = "../iam"
  name_prefix                       = local.name_prefix
  aws_region                        = var.aws_region
  account_id                        = var.account_id
  documents_bucket_arn              = module.documents.bucket_arn
  documents_queue_arn               = module.messaging.documents_queue_arn
  review_callbacks_queue_arn        = module.messaging.review_callbacks_queue_arn
  bedrock_model_id                  = var.bedrock_model_id
  bedrock_inference_profile_id      = var.bedrock_inference_profile_id
  sagemaker_model_package_group_arn = module.registry.model_package_group_arn
  api_log_group_arn                 = module.logs.api_log_group_arn
  web_log_group_arn                 = module.logs.web_log_group_arn
  ecr_repository_arns               = values(module.ecr.repository_arns)
  tags                              = local.common_tags
}

module "database" {
  source                  = "../rds"
  name_prefix             = local.name_prefix
  subnet_ids              = module.networking.private_subnet_ids
  vpc_security_group_ids  = [module.networking.rds_security_group_id]
  instance_class          = var.db_instance_class
  db_name                 = var.db_name
  username                = var.db_username
  password                = var.master_password
  multi_az                = var.db_multi_az
  backup_retention_period = var.db_backup_retention_period
  skip_final_snapshot     = var.skip_final_snapshot
  tags                    = local.common_tags
}

module "runtime" {
  source                = "../ecs"
  name_prefix           = local.name_prefix
  cluster_name          = local.cluster_name
  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  private_subnet_ids    = module.networking.private_subnet_ids
  alb_security_group_id = module.networking.alb_security_group_id
  ecs_security_group_id = module.networking.ecs_security_group_id
  execution_role_arn    = module.iam.ecs_execution_role_arn
  api_task_role_arn     = module.iam.api_task_role_arn
  api_image             = var.api_image
  web_image             = var.web_image
  api_log_group_name    = module.logs.api_log_group_name
  web_log_group_name    = module.logs.web_log_group_name
  aws_region            = var.aws_region
  desired_count         = var.desired_count
  database_url          = "postgresql+psycopg://${var.db_username}:${var.master_password}@${module.database.address}:5432/${var.db_name}"
  cors_origins          = var.cors_origins
  tags                  = local.common_tags
}

module "review_workflow" {
  source           = "../step_functions"
  name_prefix      = local.name_prefix
  role_arn         = module.iam.step_functions_role_arn
  review_queue_url = module.messaging.review_callbacks_queue_url
  timeout_seconds  = var.review_timeout_seconds
  tags             = local.common_tags
}
