variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name used as a prefix for all resource names"
  type        = string
  default     = "cloudlog"
}

variable "sqs_max_receive_count" {
  description = "Number of times a message is retried before moving to the DLQ"
  type        = number
  default     = 3
}

variable "log_retention_days" {
  description = "CloudWatch log group retention in days"
  type        = number
  default     = 14
}
