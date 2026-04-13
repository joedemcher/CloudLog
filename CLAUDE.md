# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Lint:**
```bash
black .
ruff check . --fix
```

**Install dependencies:**
```bash
pip install -r cli/requirements.txt       # CLI
pip install -r api/requirements.txt       # API Lambda
pip install -r worker/requirements.txt    # Worker
pip install -r dev-requirements.txt       # Linting tools
```

**Build and push worker image:**
```bash
docker build --platform linux/amd64 -t cloudlog-worker ./worker
docker tag cloudlog-worker:latest $ECR_URL:latest
docker push "${ECR_URL}:latest"
aws ecs update-service --cluster cloudlog-cluster --service cloudlog-worker --force-new-deployment
```

**Provision/update infrastructure:**
```bash
cd terraform && terraform init && terraform apply
```

**Use the CLI (after deployment):**
```bash
python cli/cloudlog.py submit path/to/access.log --wait
python cli/cloudlog.py status <job_id>
python cli/cloudlog.py report <job_id>
```

There is no test suite in this repository.

## Architecture

CloudLog processes Apache Combined Log Format files asynchronously. Users submit a log file and get a `job_id` immediately (202); the worker processes it in the background and stores results in DynamoDB.

### Data flow

```
CLI → S3 (upload log) → Lambda POST /jobs → DynamoDB (PENDING) + SQS message
                                                          ↓
                                                  Worker polls SQS
                                                          ↓
                                          S3 download → parse → compute metrics
                                                          ↓
                                                DynamoDB (COMPLETED/FAILED)
                                                          ↓
                                              CLI polls GET /jobs/{id}/report
```

### Components

- **`api/handler.py`** — Lambda function behind API Gateway. `POST /jobs` creates a DynamoDB record (PENDING) and enqueues an SQS message. `GET /jobs/{id}` returns status. `GET /jobs/{id}/report` returns computed metrics.

- **`worker/app.py`** — Long-running ECS Fargate service that polls SQS. Downloads the log from S3, parses it, computes metrics, and updates DynamoDB to COMPLETED or FAILED. On crash, the SQS visibility timeout (300s) triggers automatic retry; after 3 failures the message moves to a DLQ with a CloudWatch alarm.

- **`worker/parser.py`** — Regex parser for Apache Combined Log Format. Returns `LogEntry` dataclasses; silently skips malformed lines.

- **`worker/metrics.py`** — Computes top 10 IPs, status code distribution, error rate (4xx/5xx), total and average bytes. Uses `Decimal` for division.

- **`cli/cloudlog.py`** — CLI client. Uploads to S3, calls the API, optionally polls until complete (`--wait`).

- **`terraform/`** — All AWS infrastructure: S3, DynamoDB (PAY_PER_REQUEST), SQS + DLQ, Lambda, API Gateway, ECS Fargate (0.25 vCPU/512 MB), ECR, VPC, IAM roles, CloudWatch.

### Key design decisions

- **ECS Fargate (not Lambda) for the worker** — the worker is a long-running SQS polling loop, not event-driven.
- **Two IAM roles for ECS** — execution role (ECS control plane) and task role (application S3/DynamoDB/SQS access), following least privilege.
- **Public IPs instead of NAT gateway** — avoids ~$30/month cost; acceptable for a portfolio project.
- **DynamoDB keyed on `job_id`** — single access pattern makes DynamoDB a natural fit over RDS.
