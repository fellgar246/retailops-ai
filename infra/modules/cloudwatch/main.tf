resource "aws_cloudwatch_log_group" "api" {
  name              = "/retailops/${var.name_prefix}/api"
  retention_in_days = var.retention_in_days
  tags              = merge(var.tags, { Name = "${var.name_prefix}-api-logs" })
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/retailops/${var.name_prefix}/web"
  retention_in_days = var.retention_in_days
  tags              = merge(var.tags, { Name = "${var.name_prefix}-web-logs" })
}

resource "aws_cloudwatch_log_group" "workflows" {
  name              = "/retailops/${var.name_prefix}/workflows"
  retention_in_days = var.retention_in_days
  tags              = merge(var.tags, { Name = "${var.name_prefix}-workflows-logs" })
}

resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  for_each            = var.ecs_cluster_name == "" ? toset([]) : toset(var.ecs_service_names)
  alarm_name          = "${var.name_prefix}-${each.value}-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Fargate CPU for ${each.value} exceeded 80%."
  tags                = var.tags

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = each.value
  }
}
