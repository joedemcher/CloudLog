import sys
from pathlib import Path
import argparse

from worker.parser import parse_line
from worker.metrics import compute_cloudlog_metrics

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def format_metrics(metrics: dict) -> str:
    lines = []

    lines.append(f"Total Requests: {metrics['total_requests']}")
    lines.append(f"Unique IPs: {metrics['unique_ips']}")
    lines.append("")

    lines.append("Top IPs:")
    for ip, count in metrics["top_10_ips"]:
        lines.append(f"{ip} — {count}")
    lines.append("")

    lines.append("Status Codes:")
    for status, count in metrics["status_code_distribution"].items():
        lines.append(f"{status} — {count}")
    lines.append("")

    lines.append(f"Error Rate: {metrics['error_rate']:.2f}%")
    lines.append("")
    lines.append(f"Total Bytes: {metrics['total_bytes']}")
    lines.append(
        f"Average Bytes / Request: \
        {metrics['average_bytes_per_request']:.2f}"
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="CloudLog CLI")
    parser.add_argument("logfile", type=Path, help="Path to log file")

    args = parser.parse_args()

    if not args.logfile.exists():
        print(f"Error: File not found: {args.logfile}")
        return

    with open(args.logfile) as f:
        entries = tuple(filter(None, (parse_line(line.strip()) for line in f)))

    metrics = compute_cloudlog_metrics(entries)

    output = format_metrics(metrics)
    print(output)


if __name__ == "__main__":
    main()
