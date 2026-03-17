from models import LogEntry
from collections import Counter
from typing import List, Dict


def aggregate_metrics(log_entries: List[LogEntry]) -> Dict[str, Counter]:
    """
    Aggregates metrics from a list of LogEntry objects.
    Returns a dictionary with counters for status codes, methods, and paths.
    """
    status_counter = Counter()
    method_counter = Counter()
    path_counter = Counter()

    for entry in log_entries:
        status_counter[entry.status] += 1
        if entry.method:
            method_counter[entry.method] += 1
        if entry.path:
            path_counter[entry.path] += 1

    return {
        "status": status_counter,
        "method": method_counter,
        "path": path_counter,
    }
