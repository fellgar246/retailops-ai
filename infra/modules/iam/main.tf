data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

locals {
  bedrock_foundation_arns = concat(
    ["arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"],
    [
      for region in var.bedrock_inference_destination_regions :
      "arn:aws:bedrock:${region}::foundation-model/${var.bedrock_model_id}"
    ]
  )
  bedrock_profile_arns = var.bedrock_inference_profile_id == "" ? [] : [
    "arn:aws:bedrock:${var.aws_region}:${var.account_id}:inference-profile/${var.bedrock_inference_profile_id}"
  ]
  bedrock_invoke_resources = concat(local.bedrock_foundation_arns, local.bedrock_profile_arns)
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${var.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-ecs-execution" })
}

resource "aws_iam_role_policy" "ecs_execution" {
  name = "execution"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "EcrPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = var.ecr_repository_arns
      },
      {
        Sid    = "WriteLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "${var.api_log_group_arn}:*",
          "${var.web_log_group_arn}:*"
        ]
      }
    ]
  })
}

resource "aws_iam_role" "api_task" {
  name               = "${var.name_prefix}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-api-task" })
}

resource "aws_iam_role_policy" "api_task" {
  name = "api-runtime"
  role = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "DocumentsObjectAccess"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${var.documents_bucket_arn}/*"]
      },
      {
        Sid      = "DocumentsListBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:HeadBucket"]
        Resource = [var.documents_bucket_arn]
      },
      {
        Sid    = "DocumentQueues"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [var.documents_queue_arn, var.review_callbacks_queue_arn]
      },
      {
        Sid      = "BedrockInvoke"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = local.bedrock_invoke_resources
      },
      {
        Sid      = "TextractAnalyze"
        Effect   = "Allow"
        Action   = ["textract:AnalyzeDocument", "textract:DetectDocumentText"]
        Resource = ["*"]
      },
      {
        Sid    = "SageMakerRegistry"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateModelPackage",
          "sagemaker:ListModelPackages",
          "sagemaker:DescribeModelPackage",
          "sagemaker:UpdateModelPackage",
          "sagemaker:DescribeModelPackageGroup"
        ]
        Resource = [
          var.sagemaker_model_package_group_arn,
          "${var.sagemaker_model_package_group_arn}/*"
        ]
      },
      {
        Sid      = "StepFunctionsCallbacks"
        Effect   = "Allow"
        Action   = ["states:SendTaskSuccess", "states:SendTaskFailure", "states:SendTaskHeartbeat"]
        Resource = ["arn:aws:states:${var.aws_region}:${var.account_id}:stateMachine:${var.name_prefix}-review"]
      },
      {
        Sid      = "ApiLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${var.api_log_group_arn}:*"]
      }
    ]
  })
}

resource "aws_iam_role" "document_processor" {
  name               = "${var.name_prefix}-document-processor"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-document-processor" })
}

resource "aws_iam_role_policy" "document_processor" {
  name = "document-processing"
  role = aws_iam_role.document_processor.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadWriteDocuments"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = ["${var.documents_bucket_arn}/*"]
      },
      {
        Sid      = "ListDocuments"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [var.documents_bucket_arn]
      },
      {
        Sid    = "DocumentQueue"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [var.documents_queue_arn]
      },
      {
        Sid      = "TextractAnalyze"
        Effect   = "Allow"
        Action   = ["textract:AnalyzeDocument", "textract:DetectDocumentText"]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_iam_role" "step_functions" {
  name               = "${var.name_prefix}-review-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-review-sfn" })
}

resource "aws_iam_role_policy" "step_functions" {
  name = "review-callback"
  role = aws_iam_role.step_functions.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "NotifyReviewQueue"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [var.review_callbacks_queue_arn]
      }
    ]
  })
}
