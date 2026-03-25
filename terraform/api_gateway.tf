locals {
  lambda_zip = "${path.module}/../api/handler.zip"
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../api"
  output_path = local.lambda_zip
}

resource "aws_lambda_function" "api" {
  function_name    = "${var.project}-api"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = local.lambda_zip
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.jobs.name
      SQS_QUEUE_URL  = aws_sqs_queue.jobs.url
    }
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.api.function_name}"
  retention_in_days = var.log_retention_days
}

# ─── API Gateway ──────────────────────────────────────────────────────────────

resource "aws_api_gateway_rest_api" "main" {
  name = "${var.project}-api"
}

# /jobs
resource "aws_api_gateway_resource" "jobs" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "jobs"
}

# /jobs/{job_id}
resource "aws_api_gateway_resource" "job" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.jobs.id
  path_part   = "{job_id}"
}

# /jobs/{job_id}/report
resource "aws_api_gateway_resource" "report" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.job.id
  path_part   = "report"
}

# POST /jobs
resource "aws_api_gateway_method" "post_jobs" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.jobs.id
  http_method   = "POST"
  authorization = "NONE"
}

# GET /jobs/{job_id}
resource "aws_api_gateway_method" "get_job" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.job.id
  http_method   = "GET"
  authorization = "NONE"
}

# GET /jobs/{job_id}/report
resource "aws_api_gateway_method" "get_report" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.report.id
  http_method   = "GET"
  authorization = "NONE"
}

locals {
  lambda_uri = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.api.arn}/invocations"
}

resource "aws_api_gateway_integration" "post_jobs" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.jobs.id
  http_method             = aws_api_gateway_method.post_jobs.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

resource "aws_api_gateway_integration" "get_job" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.job.id
  http_method             = aws_api_gateway_method.get_job.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

resource "aws_api_gateway_integration" "get_report" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.report.id
  http_method             = aws_api_gateway_method.get_report.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  depends_on = [
    aws_api_gateway_integration.post_jobs,
    aws_api_gateway_integration.get_job,
    aws_api_gateway_integration.get_report,
  ]

  # Force a new deployment when routes change
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.jobs,
      aws_api_gateway_resource.job,
      aws_api_gateway_resource.report,
      aws_api_gateway_method.post_jobs,
      aws_api_gateway_method.get_job,
      aws_api_gateway_method.get_report,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "prod" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  deployment_id = aws_api_gateway_deployment.main.id
  stage_name    = "prod"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}
