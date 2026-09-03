data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "sagemaker_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "ecs_execution" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage"
    ]
    resources = var.ecr_repository_arns
  }

  statement {
    sid = "WriteFutureTaskLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${var.account_id}:log-group:/ecs/${var.name_prefix}-*:*"
    ]
  }

  dynamic "statement" {
    for_each = length(var.secret_arns) > 0 ? [1] : []
    content {
      sid       = "ReadTaskSecrets"
      actions   = ["secretsmanager:GetSecretValue"]
      resources = var.secret_arns
    }
  }
}

locals {
  document_object_arns = [
    for prefix in var.document_object_prefixes :
    "${var.documents_bucket_arn}/${prefix}/*"
  ]
  bedrock_invoke_resources = concat(
    [
      "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}",
      "arn:aws:bedrock:${var.aws_region}:${var.account_id}:inference-profile/${var.bedrock_inference_profile_id}"
    ],
    [
      for region in var.bedrock_inference_destination_regions :
      "arn:aws:bedrock:${region}::foundation-model/${var.bedrock_model_id}"
    ]
  )
}

data "aws_iam_policy_document" "api_task" {
  statement {
    sid       = "DocumentsObjectAccess"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.documents_bucket_arn}/*"]
  }

  statement {
    sid       = "DocumentsListBucket"
    actions   = ["s3:ListBucket", "s3:HeadBucket"]
    resources = [var.documents_bucket_arn]
  }

  statement {
    sid       = "BedrockInvoke"
    actions   = ["bedrock:InvokeModel"]
    resources = local.bedrock_invoke_resources
  }

  dynamic "statement" {
    for_each = length(var.secret_arns) > 0 ? [1] : []
    content {
      sid       = "ReadApplicationSecrets"
      actions   = ["secretsmanager:GetSecretValue"]
      resources = var.secret_arns
    }
  }
}

data "aws_iam_policy_document" "document_processor" {
  statement {
    sid       = "ReadWriteDocuments"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:HeadObject"]
    resources = local.document_object_arns
  }

  statement {
    sid       = "ListDocuments"
    actions   = ["s3:ListBucket"]
    resources = [var.documents_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = [for prefix in var.document_object_prefixes : "${prefix}/*"]
    }
  }

  statement {
    sid       = "TextractAnalyze"
    actions   = ["textract:AnalyzeDocument", "textract:DetectDocumentText"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "ml" {
  statement {
    sid       = "ModelArtifactObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${var.documents_bucket_arn}/${var.model_artifact_prefix}/*"]
  }

  statement {
    sid       = "ListModelArtifacts"
    actions   = ["s3:ListBucket"]
    resources = [var.documents_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.model_artifact_prefix}/*"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${var.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-ecs-execution" })
}

resource "aws_iam_role_policy" "ecs_execution" {
  name   = "execution"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_execution.json
}

resource "aws_iam_role" "api_task" {
  name               = "${var.name_prefix}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-api-task" })
}

resource "aws_iam_role_policy" "api_task" {
  name   = "api-runtime"
  role   = aws_iam_role.api_task.id
  policy = data.aws_iam_policy_document.api_task.json
}

resource "aws_iam_role" "document_processor" {
  name               = "${var.name_prefix}-document-processor"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-document-processor" })
}

resource "aws_iam_role_policy" "document_processor" {
  name   = "document-processing"
  role   = aws_iam_role.document_processor.id
  policy = data.aws_iam_policy_document.document_processor.json
}

resource "aws_iam_role" "ml" {
  name               = "${var.name_prefix}-ml"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-ml" })
}

resource "aws_iam_role_policy" "ml" {
  name   = "model-artifacts"
  role   = aws_iam_role.ml.id
  policy = data.aws_iam_policy_document.ml.json
}
