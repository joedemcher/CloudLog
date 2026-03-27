import argparse
import os
import sys
import time
from pathlib import Path

import boto3
import requests

API_URL = os.environ.get("CLOUDLOG_API_URL", "").rstrip("/")
if not API_URL:
    raise SystemExit("Error: CLOUDLOG_API_URL environment variable not set.")

S3_BUCKET = os.environ.get("CLOUDLOG_S3_BUCKET")
if not S3_BUCKET:
    raise SystemExit("Error: CLOUDLOG_S3_BUCKET environment variable not set.")

s3 = boto3.client("s3")


def format_metrics(metrics: dict) -> str:
    lines = []

    lines.append(f"Total Requests: {metrics['total_requests']}")
    lines.append(f"Unique IPs: {metrics['unique_ips']}")
    lines.append("")

    lines.append("Top IPs:")
    for ip, count in metrics["top_10_ips"]:
        lines.append(f"  {ip} — {count}")
    lines.append("")

    lines.append("Status Codes:")
    for status, count in metrics["status_code_distribution"].items():
        lines.append(f"  {status} — {count}")
    lines.append("")

    lines.append(f"Error Rate: {metrics['error_rate']:.2f}%")
    lines.append("")
    lines.append(f"Total Bytes: {metrics['total_bytes']}")
    lines.append(f"Average Bytes / Request: {metrics['average_bytes_per_request']:.2f}")

    return "\n".join(lines)


def cmd_submit(args):
    path = Path(args.logfile)
    if not path.exists():
        raise SystemExit(f"Error: File not found: {path}")

    s3_key = f"logs/{path.name}"

    print(f"Uploading {path.name} to S3...")
    s3.upload_file(str(path), S3_BUCKET, s3_key)

    print("Creating job...")
    response = requests.post(f"{API_URL}/jobs", json={"s3_key": s3_key})
    response.raise_for_status()

    job_id = response.json()["job_id"]
    print(f"Job created: {job_id}")

    if args.wait:
        cmd_wait(job_id)


def cmd_status(args):
    response = requests.get(f"{API_URL}/jobs/{args.job_id}")
    if response.status_code == 404:
        raise SystemExit(f"Error: Job {args.job_id} not found.")
    response.raise_for_status()

    data = response.json()
    print(f"Job ID: {data['job_id']}")
    print(f"Status: {data['status']}")
    print(f"Created: {data['created_at']}")


def cmd_report(args):
    response = requests.get(f"{API_URL}/jobs/{args.job_id}/report")
    if response.status_code == 404:
        raise SystemExit(f"Error: Job {args.job_id} not found.")
    response.raise_for_status()

    data = response.json()
    status = data["status"]

    if status == "COMPLETED":
        print(format_metrics(data["result"]))
    elif status == "FAILED":
        raise SystemExit(f"Job failed: {data.get('error_message', 'unknown error')}")
    else:
        raise SystemExit(f"Report not ready yet. Status: {status}")


def cmd_wait(job_id, poll_interval=3, timeout=120):
    """Poll until job reaches a terminal state. Used by submit --wait."""
    print("Waiting for job to complete ", end="", flush=True)
    elapsed = 0

    while elapsed < timeout:
        response = requests.get(f"{API_URL}/jobs/{job_id}")
        response.raise_for_status()
        status = response.json()["status"]

        if status == "COMPLETED":
            print(" done.")
            response = requests.get(f"{API_URL}/jobs/{job_id}/report")
            response.raise_for_status()
            print(format_metrics(response.json()["result"]))
            return
        elif status == "FAILED":
            print()
            raise SystemExit(f"Job failed: {response.json().get('error_message')}")

        print(".", end="", flush=True)
        time.sleep(poll_interval)
        elapsed += poll_interval

    print()
    raise SystemExit(f"Timed out after {timeout}s. Check status with: cloudlog status {job_id}")


def main():
    parser = argparse.ArgumentParser(
        prog="cloudlog",
        description="CloudLog — async log analytics CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # cloudlog submit <logfile> [--wait]
    sub_submit = subparsers.add_parser("submit", help="Upload a log file and create a job")
    sub_submit.add_argument("logfile", help="Path to the log file")
    sub_submit.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the job to complete and print the report",
    )

    # cloudlog status <job_id>
    sub_status = subparsers.add_parser("status", help="Check job status")
    sub_status.add_argument("job_id", help="Job ID returned by submit")

    # cloudlog report <job_id>
    sub_report = subparsers.add_parser("report", help="Print the completed job report")
    sub_report.add_argument("job_id", help="Job ID returned by submit")

    args = parser.parse_args()

    if args.command == "submit":
        cmd_submit(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()