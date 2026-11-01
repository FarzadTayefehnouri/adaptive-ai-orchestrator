"""Circuit Breaker Pattern for Resilient Provider Networking.
Automatically isolates providers experiencing network timeouts or 5xx server errors
for a configurable cooldown window (default 60 seconds) to prevent hanging tasks.
"""
import time
from enum import Enum
from typing import Dict, Any, Optional

class CircuitState(str, Enum):
    CLOSED = "closed"         # Normal operation
    OPEN = "open"             # Failing; fast-fail and reroute immediately
    HALF_OPEN = "half_open"   # Cooldown elapsed; testing recovery with next request

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 2, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: Optional[float] = None
        self.last_error_message: str = ""

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) >= self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN allows a probe request
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_error_message = ""

    def record_failure(self, error_msg: str = "Network or 5xx error"):
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.last_error_message = error_msg
        if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN

    def to_dict(self) -> Dict[str, Any]:
        remaining_cooldown = 0.0
        if self.state == CircuitState.OPEN and self.last_failure_time:
            remaining_cooldown = max(0.0, self.cooldown_seconds - (time.time() - self.last_failure_time))
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "remaining_cooldown_sec": round(remaining_cooldown, 1),
            "last_error": self.last_error_message
        }
