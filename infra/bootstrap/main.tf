resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name
  tags = {
    Name      = var.state_bucket_name
    DataClass = "terraform-state"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

data "aws_iam_policy_document" "state" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.state.arn,
      "${aws_s3_bucket.state.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state.json

  depends_on = [aws_s3_bucket_public_access_block.state]
}

resource "aws_ce_cost_allocation_tag" "standard" {
  for_each = var.enable_cost_allocation_tags ? toset([
    "Project",
    "Environment",
    "ManagedBy",
    "Repository",
  ]) : toset([])

  tag_key = each.value
  status  = "Active"
}

# The delivery pipeline authenticates here. It belongs with the state bucket
# rather than with an environment: the provider is account-wide, and the roles
# must exist before anything they deploy does.
module "pipeline_identity" {
  source = "../modules/github_oidc"

  name_prefix           = "${var.project}-pipeline"
  repository            = var.pipeline_repository
  deploy_branch         = var.pipeline_deploy_branch
  create_provider       = var.create_github_oidc_provider
  existing_provider_arn = var.existing_github_oidc_provider_arn
  state_bucket_arn      = aws_s3_bucket.state.arn
  state_key_prefix      = var.project
  ecr_repository_arns   = var.pipeline_ecr_repository_arns
  deploy_policy_arns    = var.pipeline_deploy_policy_arns

  tags = {
    Project   = var.project
    ManagedBy = "terraform"
    Component = "pipeline"
  }
}
