output "ecs_execution_role_arn" {
  value = aws_iam_role.ecs_execution.arn
}

output "api_task_role_arn" {
  value = aws_iam_role.api_task.arn
}

output "document_processor_role_arn" {
  value = aws_iam_role.document_processor.arn
}

output "step_functions_role_arn" {
  value = aws_iam_role.step_functions.arn
}
