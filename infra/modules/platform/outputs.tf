output "name_prefix" {
  value = local.name_prefix
}

output "vpc_id" {
  value = module.networking.vpc_id
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

output "db_address" {
  value = module.database.address
}

output "alb_dns_name" {
  value = module.runtime.alb_dns_name
}

output "ecs_cluster_name" {
  value = module.runtime.cluster_name
}

output "review_state_machine_arn" {
  value = module.review_workflow.state_machine_arn
}

output "api_task_role_arn" {
  value = module.iam.api_task_role_arn
}

output "event_bus_name" {
  value = module.messaging.event_bus_name
}

output "sagemaker_model_package_group" {
  value = module.registry.model_package_group_name
}
