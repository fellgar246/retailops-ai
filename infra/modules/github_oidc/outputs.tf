output "provider_arn" {
  description = "OIDC provider the pipeline authenticates against."
  value       = local.provider_arn
}

output "deploy_role_arn" {
  description = "Role the pipeline assumes to deploy."
  value       = aws_iam_role.deploy.arn
}

output "plan_role_arn" {
  description = "Read-only role a pull request assumes to plan."
  value       = aws_iam_role.plan.arn
}

output "deploy_subject" {
  description = "The only token subject that may assume the deploy role."
  value       = local.deploy_subject
}
