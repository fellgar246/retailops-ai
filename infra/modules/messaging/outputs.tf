output "documents_queue_arn" {
  value = aws_sqs_queue.documents.arn
}

output "documents_queue_url" {
  value = aws_sqs_queue.documents.url
}

output "review_callbacks_queue_arn" {
  value = aws_sqs_queue.review_callbacks.arn
}

output "review_callbacks_queue_url" {
  value = aws_sqs_queue.review_callbacks.url
}

output "event_bus_arn" {
  value = aws_cloudwatch_event_bus.this.arn
}

output "event_bus_name" {
  value = aws_cloudwatch_event_bus.this.name
}
