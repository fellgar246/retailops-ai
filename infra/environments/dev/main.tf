module "foundation" {
  source = "../../modules/foundation"

  project                      = var.project
  environment                  = var.environment
  aws_region                   = var.aws_region
  account_id                   = var.account_id
  azs                          = var.azs
  vpc_cidr                     = var.vpc_cidr
  public_subnet_cidrs          = var.public_subnet_cidrs
  private_subnet_cidrs         = var.private_subnet_cidrs
  enable_nat_gateway           = false
  enable_public_ingress        = false
  documents_bucket_name        = var.documents_bucket_name
  force_destroy_documents      = true
  ecr_repository_names         = ["${var.project}-${var.environment}-api", "${var.project}-${var.environment}-web"]
  image_tag_mutability         = "IMMUTABLE"
  secret_recovery_window_days  = 0
  budget_limit_usd             = var.budget_limit_usd
  budget_alert_email           = var.budget_alert_email
  budget_time_period_start     = var.budget_time_period_start
  bedrock_model_id             = var.bedrock_model_id
  bedrock_inference_profile_id = var.bedrock_inference_profile_id
}
