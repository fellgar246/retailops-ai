locals {
  provider_url = "https://token.actions.githubusercontent.com"
  provider_arn = var.create_provider ? aws_iam_openid_connect_provider.github[0].arn : var.existing_provider_arn

  # The exact subject a workflow presents. No wildcard over the repository or
  # the branch: one would let any workflow in any repository of the account's
  # organisation assume a role that can deploy.
  deploy_subject = "repo:${var.repository}:ref:refs/heads/${var.deploy_branch}"
  plan_subject   = "repo:${var.repository}:pull_request"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_provider ? 1 : 0
  url   = local.provider_url
  # The audience a workflow must request. A token issued for anything else is
  # refused before the subject is even considered.
  client_id_list = ["sts.amazonaws.com"]
  tags           = merge(var.tags, { Name = "${var.name_prefix}-github-oidc" })
}

data "aws_iam_policy_document" "deploy_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # StringEquals, not StringLike: the subject must match exactly.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.deploy_subject]
    }
  }
}

data "aws_iam_policy_document" "plan_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # A pull request in this repository only. A fork's workflow presents a
    # different repository in its subject and is refused here, rather than
    # relying on a workflow choosing not to ask.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.plan_subject]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.name_prefix}-deploy"
  description          = "Assumed by the delivery pipeline from ${var.repository}@${var.deploy_branch}."
  assume_role_policy   = data.aws_iam_policy_document.deploy_assume.json
  max_session_duration = 3600
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-deploy" })
}

resource "aws_iam_role" "plan" {
  name                 = "${var.name_prefix}-plan"
  description          = "Assumed by a pull request in ${var.repository}. Reads only."
  assume_role_policy   = data.aws_iam_policy_document.plan_assume.json
  max_session_duration = 3600
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-plan" })
}

data "aws_iam_policy_document" "state" {
  statement {
    sid       = "ReadStateBucket"
    actions   = ["s3:ListBucket"]
    resources = [var.state_bucket_arn]
  }

  statement {
    sid = "ReadWriteState"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${var.state_bucket_arn}/${var.state_key_prefix}/*"]
  }
}

data "aws_iam_policy_document" "state_read_only" {
  statement {
    sid       = "ReadStateBucket"
    actions   = ["s3:ListBucket"]
    resources = [var.state_bucket_arn]
  }

  statement {
    sid       = "ReadState"
    actions   = ["s3:GetObject"]
    resources = ["${var.state_bucket_arn}/${var.state_key_prefix}/*"]
  }
}

data "aws_iam_policy_document" "registry" {
  statement {
    sid       = "RegistryAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  dynamic "statement" {
    for_each = length(var.ecr_repository_arns) > 0 ? [1] : []
    content {
      sid = "PushImages"
      actions = [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:CompleteLayerUpload",
        "ecr:DescribeImages",
        "ecr:GetDownloadUrlForLayer",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:UploadLayerPart",
      ]
      resources = var.ecr_repository_arns
    }
  }
}

resource "aws_iam_role_policy" "deploy_state" {
  name   = "terraform-state"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.state.json
}

resource "aws_iam_role_policy" "deploy_registry" {
  name   = "registry"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.registry.json
}

resource "aws_iam_role_policy" "plan_state" {
  name   = "terraform-state"
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.state_read_only.json
}

# Reading infrastructure is enough to produce a plan, and is all the planning
# role may ever do.
resource "aws_iam_role_policy_attachment" "plan_read_only" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "deploy_extra" {
  for_each   = toset(var.deploy_policy_arns)
  role       = aws_iam_role.deploy.name
  policy_arn = each.value
}
