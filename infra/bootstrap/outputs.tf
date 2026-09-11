output "state_bucket_name" {
  value = aws_s3_bucket.state.bucket
}

output "state_bucket_arn" {
  value = aws_s3_bucket.state.arn
}

output "dev_state_key" {
  value = "${var.project}/dev/terraform.tfstate"
}

output "bootstrap_state_key" {
  value = "${var.project}/bootstrap/terraform.tfstate"
}

output "pipeline_deploy_role_arn" {
  description = "Role the delivery pipeline assumes to deploy."
  value       = module.pipeline_identity.deploy_role_arn
}

output "pipeline_plan_role_arn" {
  description = "Read-only role a pull request assumes to plan."
  value       = module.pipeline_identity.plan_role_arn
}

output "pipeline_deploy_subject" {
  description = "The only token subject that may assume the deploy role."
  value       = module.pipeline_identity.deploy_subject
}
