# Sized to be affordable rather than production-shaped. The differences from
# `prod` are deliberate and are listed in the deployment runbook: no NAT
# gateway, the smallest database that runs the schema, single-AZ, one task per
# service, and log retention measured in days.
module "platform" {
  source = "../../modules/platform"

  project              = var.project
  environment          = var.environment
  aws_region           = var.aws_region
  account_id           = var.account_id
  azs                  = var.azs
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  # A NAT gateway is the single largest line on a quiet environment.
  enable_nat_gateway         = false
  documents_bucket_name      = var.documents_bucket_name
  ecr_namespace              = "${var.project}/${var.environment}"
  image_tag_mutability       = "IMMUTABLE"
  master_password            = var.master_password
  db_instance_class          = "db.t4g.micro"
  db_multi_az                = false
  db_backup_retention_period = 1
  skip_final_snapshot        = false
  api_image                  = var.api_image
  web_image                  = var.web_image
  desired_count              = 1
  cors_origins               = var.cors_origins
  bedrock_model_id           = var.bedrock_model_id
  sagemaker_model_group      = var.sagemaker_model_group
  log_retention_days         = 7
}
