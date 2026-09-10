output "documents_queue_arn" {
  value = aws_sqs_queue.documents.arn
}

output "documents_queue_url" {
  value = aws_sqs_queue.documents.url
}

output "review_callbacks_queue_arn" {
  value = var.enable_review_callbacks ? aws_sqs_queue.review_callbacks[0].arn : ""
}

output "review_callbacks_queue_url" {
  value = var.enable_review_callbacks ? aws_sqs_queue.review_callbacks[0].url : ""
}

output "event_bus_arn" {
  value = var.enable_event_routing ? aws_cloudwatch_event_bus.this[0].arn : ""
}

output "event_bus_name" {
  value = var.enable_event_routing ? aws_cloudwatch_event_bus.this[0].name : ""
}
