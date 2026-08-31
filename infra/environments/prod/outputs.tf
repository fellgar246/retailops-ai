output "vpc_id" {
  value = module.platform.vpc_id
}

output "documents_bucket_name" {
  value = module.platform.documents_bucket_name
}

output "ecr_repository_urls" {
  value = module.platform.ecr_repository_urls
}

output "db_address" {
  value = module.platform.db_address
}

output "alb_dns_name" {
  value = module.platform.alb_dns_name
}

output "ecs_cluster_name" {
  value = module.platform.ecs_cluster_name
}

output "review_state_machine_arn" {
  value = module.platform.review_state_machine_arn
}

output "api_task_role_arn" {
  value = module.platform.api_task_role_arn
}

output "sagemaker_model_package_group" {
  value = module.platform.sagemaker_model_package_group
}
