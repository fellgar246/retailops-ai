resource "aws_secretsmanager_secret" "this" {
  for_each                = var.secrets
  name                    = each.value.name
  description             = each.value.description
  recovery_window_in_days = var.recovery_window_in_days
  tags                    = merge(var.tags, { Name = each.value.name })
}
