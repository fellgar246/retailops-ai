resource "aws_sfn_state_machine" "review" {
  name     = "${var.name_prefix}-review"
  role_arn = var.role_arn
  tags     = merge(var.tags, { Name = "${var.name_prefix}-review" })

  definition = jsonencode({
    Comment        = "Human review wait-for-callback. Local cases stay the source of truth."
    StartAt        = "NotifyReviewer"
    TimeoutSeconds = var.timeout_seconds
    States = {
      NotifyReviewer = {
        Type             = "Task"
        Resource         = "arn:aws:states:::sqs:sendMessage.waitForTaskToken"
        TimeoutSeconds   = var.timeout_seconds
        HeartbeatSeconds = 86400
        Parameters = {
          QueueUrl = var.review_queue_url
          MessageBody = {
            "TaskToken.$"       = "$$.Task.Token"
            "case_id.$"         = "$.case_id"
            "correlation_id.$"  = "$.correlation_id"
            "idempotency_key.$" = "$.idempotency_key"
          }
        }
        Next = "DecisionApplied"
        Catch = [
          {
            ErrorEquals = ["States.Timeout"]
            Next        = "TimedOut"
          },
          {
            ErrorEquals = ["States.ALL"]
            Next        = "CallbackFailed"
          }
        ]
      }
      DecisionApplied = {
        Type = "Succeed"
      }
      TimedOut = {
        Type  = "Fail"
        Error = "ReviewTimeout"
        Cause = "Human review wait exceeded the configured timeout."
      }
      CallbackFailed = {
        Type  = "Fail"
        Error = "ReviewCallbackFailed"
        Cause = "The review callback reported failure."
      }
    }
  })
}
