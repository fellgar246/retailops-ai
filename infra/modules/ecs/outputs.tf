output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "alb_dns_name" {
  value = var.enable_load_balancer ? aws_lb.this[0].dns_name : ""
}

output "api_service_name" {
  value = var.enable_load_balancer ? aws_ecs_service.api[0].name : ""
}

output "web_service_name" {
  value = var.enable_load_balancer ? aws_ecs_service.web[0].name : ""
}

output "migration_task_family" {
  description = "Task the pipeline runs to apply the schema."
  value       = aws_ecs_task_definition.migration.family
}

output "service_names" {
  description = "Services the pipeline rolls forward."
  value = var.enable_load_balancer ? [
    aws_ecs_service.api[0].name,
    aws_ecs_service.web[0].name,
    aws_ecs_service.worker.name,
    ] : [
    aws_ecs_service.application[0].name,
    aws_ecs_service.worker.name,
  ]
}
