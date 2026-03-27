from collections import Counter
from decimal import Decimal
from typing import List, Dict

from models import LogEntry


def compute_metrics(log_entries: List[LogEntry]) -> Dict[str, object]:
    total_requests = len(log_entries)
    ip_counter = Counter(log.ip for log in log_entries)
    unique_ips = len(ip_counter)
    top_10_ips = ip_counter.most_common(10)
    status_code_distribution = {str(k): v for k, v in Counter(log.status for log in log_entries).items()}
    error_count = sum(1 for log in log_entries if 400 <= log.status < 600)
    error_rate = (Decimal(error_count) / Decimal(total_requests)) if total_requests > 0 else Decimal(0)
    total_bytes = sum(log.bytes for log in log_entries)
    average_bytes_per_request = (
        (Decimal(total_bytes) / Decimal(total_requests)) if total_requests > 0 else Decimal(0)
    )

    return {
        "total_requests": total_requests,
        "unique_ips": unique_ips,
        "top_10_ips": top_10_ips,
        "status_code_distribution": status_code_distribution,
        "error_rate": error_rate,
        "total_bytes": total_bytes,
        "average_bytes_per_request": average_bytes_per_request,
    }
