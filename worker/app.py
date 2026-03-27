import json
import logging
import os
import sys

from datetime import datetime, timezone

import boto3

from metrics import compute_metrics
from parser import parse_line

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(message)s",
)

s3 = boto3.client("s3")
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")

S3_BUCKET = os.environ["S3_BUCKET"]
QUEUE_URL = os.environ["SQS_QUEUE_URL"]
TABLE_NAME = os.environ["DYNAMODB_TABLE"]
POLL_WAIT_SECONDS = int(os.environ.get("POLL_WAIT_SECONDS", "20"))
MAX_MESSAGES = int(os.environ.get("MAX_MESSAGES", "1"))

table = dynamodb.Table(TABLE_NAME)


def log(level, event, job_id=None, **kwargs):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
    }
    if job_id:
        entry["job_id"] = job_id
    entry.update(kwargs)
    getattr(logger, level.lower(), logger.info)(json.dumps(entry))


def update_job(job_id, **fields):
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": v for k, v in fields.items()}
    table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def process_message(message):
    body = json.loads(message["Body"])
    job_id = body["job_id"]
    s3_key = body["s3_key"]
    receipt_handle = message["ReceiptHandle"]

    log("INFO", "job_started", job_id=job_id, s3_key=s3_key)

    update_job(job_id, status="PROCESSING")

    log("INFO", "s3_download_start", job_id=job_id, s3_key=s3_key)
    obj = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
    raw_lines = obj["Body"].read().decode("utf-8").splitlines()
    log("INFO", "s3_download_done", job_id=job_id, line_count=len(raw_lines))

    entries = parse_log_lines(raw_lines)
    log(
        "INFO",
        "parse_done",
        job_id=job_id,
        parsed=len(entries),
        skipped=len(raw_lines) - len(entries),
    )

    result = compute_metrics(entries)
    log("INFO", "metrics_done", job_id=job_id)

    update_job(job_id, status="COMPLETED", result=result)
    log("INFO", "job_completed", job_id=job_id)

    sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
    log("INFO", "sqs_message_deleted", job_id=job_id)


def poll_forever():
    log("INFO", "worker_started", queue_url=QUEUE_URL)

    while True:
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=MAX_MESSAGES,
            WaitTimeSeconds=POLL_WAIT_SECONDS,
            AttributeNames=["ApproximateReceiveCount"],
        )

        messages = response.get("Messages", [])
        if not messages:
            log("INFO", "poll_empty")
            continue

        for message in messages:
            job_id = None
            try:
                body = json.loads(message["Body"])
                job_id = body.get("job_id", "unknown")
                process_message(message)
            except Exception as e:
                log("ERROR", "job_failed", job_id=job_id, error=str(e))

                if job_id and job_id != "unknown":
                    try:
                        update_job(job_id, status="FAILED", error_message=str(e))
                    except Exception as db_err:
                        log(
                            "ERROR",
                            "dynamo_update_failed",
                            job_id=job_id,
                            error=str(db_err),
                        )

                log(
                    "WARNING",
                    "sqs_message_not_deleted",
                    job_id=job_id,
                    note="message will be retried or sent to DLQ",
                )


if __name__ == "__main__":
    poll_forever()
