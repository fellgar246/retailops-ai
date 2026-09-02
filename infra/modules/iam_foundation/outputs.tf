output "ecs_execution_role_arn" {
  value = aws_iam_role.ecs_execution.arn
}

output "ecs_execution_role_name" {
  value = aws_iam_role.ecs_execution.name
}

output "api_task_role_arn" {
  value = aws_iam_role.api_task.arn
}

output "api_task_role_name" {
  value = aws_iam_role.api_task.name
}

output "document_processor_role_arn" {
  value = aws_iam_role.document_processor.arn
}

output "document_processor_role_name" {
  value = aws_iam_role.document_processor.name
}

output "ml_role_arn" {
  value = aws_iam_role.ml.arn
}

output "ml_role_name" {
  value = aws_iam_role.ml.name
}
