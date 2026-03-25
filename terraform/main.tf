terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- Outputs ---

output "s3_bucket_name" {
  description = "S3 bucket for log uploads"
  value       = aws_s3_bucket.logs.bucket
}

output "dynamodb_table_name" {
  description = "DynamoDB table for job state"
  value       = aws_dynamodb_table.jobs.name
}

output "sqs_queue_url" {
  description = "SQS queue URL for job messages"
  value       = aws_sqs_queue.jobs.url
}

output "api_gateway_url" {
  description = "Base URL for the CloudLog API"
  value       = "${aws_api_gateway_stage.prod.invoke_url}"
}

output "ecr_repository_url" {
  description = "ECR repository URL — push your worker image here"
  value       = aws_ecr_repository.worker.repository_url
}
