resource "aws_sqs_queue" "documents_dlq" {
  name                      = "${var.name_prefix}-documents-dlq"
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600
  tags                      = merge(var.tags, { Name = "${var.name_prefix}-documents-dlq" })
}

resource "aws_sqs_queue" "documents" {
  name                       = "${var.name_prefix}-documents"
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.documents_dlq.arn
    maxReceiveCount     = 5
  })
  tags = merge(var.tags, { Name = "${var.name_prefix}-documents" })
}

resource "aws_sqs_queue" "review_callbacks_dlq" {
  name                      = "${var.name_prefix}-review-callbacks-dlq"
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600
  tags                      = merge(var.tags, { Name = "${var.name_prefix}-review-callbacks-dlq" })
}

resource "aws_sqs_queue" "review_callbacks" {
  name                       = "${var.name_prefix}-review-callbacks"
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = 60
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.review_callbacks_dlq.arn
    maxReceiveCount     = 5
  })
  tags = merge(var.tags, { Name = "${var.name_prefix}-review-callbacks" })
}

resource "aws_cloudwatch_event_bus" "this" {
  name = "${var.name_prefix}-ops"
  tags = merge(var.tags, { Name = "${var.name_prefix}-ops" })
}

resource "aws_cloudwatch_event_rule" "document_received" {
  name           = "${var.name_prefix}-document-received"
  event_bus_name = aws_cloudwatch_event_bus.this.name
  event_pattern = jsonencode({
    source      = ["retailops.documents"]
    detail-type = ["document.received"]
  })
  tags = var.tags
}

resource "aws_cloudwatch_event_target" "documents_queue" {
  rule           = aws_cloudwatch_event_rule.document_received.name
  event_bus_name = aws_cloudwatch_event_bus.this.name
  arn            = aws_sqs_queue.documents.arn
}

resource "aws_sqs_queue_policy" "documents_from_events" {
  queue_url = aws_sqs_queue.documents.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowEventBridge"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.documents.arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_cloudwatch_event_rule.document_received.arn
        }
      }
    }]
  })
}
