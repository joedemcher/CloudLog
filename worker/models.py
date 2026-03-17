from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LogEntry:
    ip: str
    user: str
    timestamp: str
    method: Optional[str]
    path: Optional[str]
    status: int
    bytes: int
