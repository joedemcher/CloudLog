import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
QUEUE_URL = os.environ["SQS_QUEUE_URL"]

table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    try:
        if method == "POST" and path == "/jobs":
            return create_job(event)
        elif method == "GET" and path.startswith("/jobs/") and "report" not in path:
            return get_job_status(path_params.get("job_id"))
        elif method == "GET" and path.startswith("/jobs/") and path.endswith("/report"):
            return get_job_report(path_params.get("job_id"))
        else:
            return response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Unhandled error")
        return response(500, {"error": str(e)})


# POST /jobs
# Body: { "s3_key": "logs/myfile.log" }
# Returns: { "job_id": "<uuid>" }
def create_job(event):
    body = json.loads(event.get("body") or "{}")
    s3_key = body.get("s3_key")

    if not s3_key:
        return response(400, {"error": "s3_key is required"})

    job_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    table.put_item(
        Item={
            "job_id": job_id,
            "status": "PENDING",
            "created_at": created_at,
            "s3_key": s3_key,
            "result": None,
            "error_message": None,
        }
    )

    # Push message to SQS
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({"job_id": job_id, "s3_key": s3_key}),
    )

    logger.info(
        json.dumps({"event": "job_created", "job_id": job_id, "s3_key": s3_key})
    )
    return response(202, {"job_id": job_id})


# GET /jobs/{job_id}
# Returns: { "job_id": ..., "status": ..., "created_at": ... }
def get_job_status(job_id):
    if not job_id:
        return response(400, {"error": "job_id is required"})

    item = _get_job(job_id)
    if item is None:
        return response(404, {"error": f"Job {job_id} not found"})

    return response(
        200,
        {
            "job_id": item["job_id"],
            "status": item["status"],
            "created_at": item["created_at"],
        },
    )


# GET /jobs/{job_id}/report
# Returns the full result JSON if COMPLETED, or error details if FAILED
def get_job_report(job_id):
    if not job_id:
        return response(400, {"error": "job_id is required"})

    item = _get_job(job_id)
    if item is None:
        return response(404, {"error": f"Job {job_id} not found"})

    status = item["status"]

    if status == "COMPLETED":
        return response(
            200, {"job_id": job_id, "status": status, "result": item.get("result")}
        )
    elif status == "FAILED":
        return response(
            200,
            {
                "job_id": job_id,
                "status": status,
                "error_message": item.get("error_message"),
            },
        )
    else:
        # PENDING or PROCESSING — report not ready yet
        return response(
            202, {"job_id": job_id, "status": status, "message": "Report not ready yet"}
        )


def _get_job(job_id):
    result = table.get_item(Key={"job_id": job_id})
    return result.get("Item")


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
