output "name_prefix" {
  value = module.foundation.name_prefix
}

output "vpc_id" {
  value = module.foundation.vpc_id
}

output "public_subnet_ids" {
  value = module.foundation.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.foundation.private_subnet_ids
}

output "alb_security_group_id" {
  value = module.foundation.alb_security_group_id
}

output "ecs_security_group_id" {
  value = module.foundation.ecs_security_group_id
}

output "rds_security_group_id" {
  value = module.foundation.rds_security_group_id
}

output "documents_bucket_name" {
  value = module.foundation.documents_bucket_name
}

output "documents_bucket_arn" {
  value = module.foundation.documents_bucket_arn
}

output "ecr_repository_urls" {
  value = module.foundation.ecr_repository_urls
}

output "ecs_execution_role_arn" {
  value = module.foundation.ecs_execution_role_arn
}

output "ecs_execution_role_name" {
  value = module.foundation.ecs_execution_role_name
}

output "api_task_role_arn" {
  value = module.foundation.api_task_role_arn
}

output "api_task_role_name" {
  value = module.foundation.api_task_role_name
}

output "document_processor_role_arn" {
  value = module.foundation.document_processor_role_arn
}

output "document_processor_role_name" {
  value = module.foundation.document_processor_role_name
}

output "ml_role_arn" {
  value = module.foundation.ml_role_arn
}

output "ml_role_name" {
  value = module.foundation.ml_role_name
}

output "secret_arns" {
  value       = module.foundation.secret_arns
  description = "Secret ARNs only. Values are never exported."
}

output "secret_names" {
  value = module.foundation.secret_names
}

output "budget_name" {
  value = module.foundation.budget_name
}

output "bedrock_model_id" {
  value = module.foundation.bedrock_model_id
}

output "bedrock_inference_profile_id" {
  value = module.foundation.bedrock_inference_profile_id
}

output "identity_user_pool_id" {
  description = "User pool backing application sign-in."
  value       = module.foundation.identity_user_pool_id
}

output "identity_client_id" {
  description = "Application client id used as the token audience."
  value       = module.foundation.identity_client_id
}

output "identity_issuer" {
  description = "OpenID Connect issuer for the user pool."
  value       = module.foundation.identity_issuer
}

output "identity_hosted_domain" {
  description = "Hosted sign-in domain prefix."
  value       = module.foundation.identity_hosted_domain
}
