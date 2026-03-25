resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${var.project}-jobs-dlq"
  message_retention_seconds = 1209600 # 14 days
}

# Main job queue
resource "aws_sqs_queue" "jobs" {
  name                       = "${var.project}-jobs"
  visibility_timeout_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })
}

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "${var.project}-dlq-not-empty"
  alarm_description   = "Messages are accumulating in the DLQ — jobs are failing"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.jobs_dlq.name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
