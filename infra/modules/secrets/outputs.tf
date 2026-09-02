output "secret_arns" {
  value       = { for key, secret in aws_secretsmanager_secret.this : key => secret.arn }
  description = "Secret ARNs only. Values are never read or exported."
}

output "secret_names" {
  value       = { for key, secret in aws_secretsmanager_secret.this : key => secret.name }
  description = "Secret names for later ECS valueFrom references."
}

output "secret_ids" {
  value       = { for key, secret in aws_secretsmanager_secret.this : key => secret.id }
  description = "Secret ids for AWS CLI describe calls."
}
