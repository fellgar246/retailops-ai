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
