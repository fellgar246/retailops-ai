# Placeholder only. Do not apply staging while only the dev foundation is live.
module "platform" {
  source = "../../modules/platform"

  project                    = var.project
  environment                = var.environment
  aws_region                 = var.aws_region
  account_id                 = var.account_id
  azs                        = var.azs
  vpc_cidr                   = var.vpc_cidr
  public_subnet_cidrs        = var.public_subnet_cidrs
  private_subnet_cidrs       = var.private_subnet_cidrs
  enable_nat_gateway         = true
  documents_bucket_name      = var.documents_bucket_name
  ecr_namespace              = "${var.project}/${var.environment}"
  image_tag_mutability       = "IMMUTABLE"
  master_password            = var.master_password
  db_instance_class          = "db.t4g.small"
  db_multi_az                = false
  db_backup_retention_period = 7
  skip_final_snapshot        = false
  api_image                  = var.api_image
  web_image                  = var.web_image
  desired_count              = 1
  cors_origins               = var.cors_origins
  bedrock_model_id           = var.bedrock_model_id
  sagemaker_model_group      = var.sagemaker_model_group
  log_retention_days         = 30
}
