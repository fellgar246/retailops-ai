output "api_log_group_name" {
  value = aws_cloudwatch_log_group.api.name
}

output "web_log_group_name" {
  value = aws_cloudwatch_log_group.web.name
}

output "workflows_log_group_name" {
  value = aws_cloudwatch_log_group.workflows.name
}

output "api_log_group_arn" {
  value = aws_cloudwatch_log_group.api.arn
}

output "web_log_group_arn" {
  value = aws_cloudwatch_log_group.web.arn
}
