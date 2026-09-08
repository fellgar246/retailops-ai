output "name_prefix" {
  value = local.name_prefix
}

output "vpc_id" {
  value = module.networking.vpc_id
}

output "public_subnet_ids" {
  value = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.networking.private_subnet_ids
}

output "alb_security_group_id" {
  value = module.networking.alb_security_group_id
}

output "ecs_security_group_id" {
  value = module.networking.ecs_security_group_id
}

output "rds_security_group_id" {
  value = module.networking.rds_security_group_id
}

output "documents_bucket_name" {
  value = module.documents.bucket_name
}

output "documents_bucket_arn" {
  value = module.documents.bucket_arn
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}

output "ecr_repository_arns" {
  value = module.ecr.repository_arns
}

output "ecs_execution_role_arn" {
  value = module.iam.ecs_execution_role_arn
}

output "ecs_execution_role_name" {
  value = module.iam.ecs_execution_role_name
}

output "api_task_role_arn" {
  value = module.iam.api_task_role_arn
}

output "api_task_role_name" {
  value = module.iam.api_task_role_name
}

output "document_processor_role_arn" {
  value = module.iam.document_processor_role_arn
}

output "document_processor_role_name" {
  value = module.iam.document_processor_role_name
}

output "ml_role_arn" {
  value = module.iam.ml_role_arn
}

output "ml_role_name" {
  value = module.iam.ml_role_name
}

output "secret_arns" {
  value       = module.secrets.secret_arns
  description = "Secret ARNs only. Values are never exported."
}

output "secret_names" {
  value = module.secrets.secret_names
}

output "secret_ids" {
  value = module.secrets.secret_ids
}

output "budget_name" {
  value = module.budget.budget_name
}

output "bedrock_model_id" {
  value = var.bedrock_model_id
}

output "bedrock_inference_profile_id" {
  value = var.bedrock_inference_profile_id
}

output "identity_user_pool_id" {
  description = "User pool backing application sign-in."
  value       = module.identity.user_pool_id
}

output "identity_client_id" {
  description = "Application client id used as the token audience."
  value       = module.identity.client_id
}

output "identity_issuer" {
  description = "OpenID Connect issuer for the user pool."
  value       = module.identity.issuer
}

output "identity_hosted_domain" {
  description = "Hosted sign-in domain prefix."
  value       = module.identity.hosted_domain
}
