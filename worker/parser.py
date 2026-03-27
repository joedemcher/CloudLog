import re
from models import LogEntry
from typing import Optional


# Regex Combined Log Format
LOG_PATTERN = re.compile(
    r"(?P<ip>\S+) "  # IP address
    r"(?P<ident>\S+) "  # ident (unused)
    r"(?P<user>\S+) "  # authenticated user
    r"\[(?P<timestamp>[^\]]+)\] "  # timestamp
    r'"(?P<request>[^"]*)"\s'  # request line
    r"(?P<status>\d{3}) "  # status code
    r"(?P<bytes>\S+) "  # bytes
    r"(?P<referer>\S+) "  # referer
    r'"(?P<user_agent>[^"]*)"'  # user agent
)


def parse_request(request: str):
    """
    Splits request string into method + path.
    Example: 'GET /index.html HTTP/1.1'
    """
    parts = request.split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None


def parse_line(line: str) -> Optional[LogEntry]:
    match = LOG_PATTERN.match(line)
    if not match:
        return None

    data = match.groupdict()

    method, path = parse_request(data["request"])

    bytes_sent = 0 if data["bytes"] == "-" else int(data["bytes"])

    return LogEntry(
        ip=data["ip"],
        user=data["user"],
        timestamp=data["timestamp"],
        method=method,
        path=path,
        status=int(data["status"]),
        bytes=bytes_sent,
    )
