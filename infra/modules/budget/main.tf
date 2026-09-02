resource "aws_budgets_budget" "monthly" {
  name              = var.budget_name
  budget_type       = "COST"
  limit_amount      = var.limit_usd
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = var.time_period_start

  dynamic "notification" {
    for_each = var.alert_email != "" ? [80, 100] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alert_email]
    }
  }

  tags = var.tags
}
