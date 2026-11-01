"""API Request Rate Limiter per Client/User (Point 2.1 & 11)."""
import time
from collections import deque
from typing import Dict, Deque

class APIRateLimiter:
    def __init__(self, max_requests_per_minute: int = 60):
        self.max_rpm = max_requests_per_minute
        self.hits: Dict[str, Deque[float]] = {}

    def allow(self, client_id: str = "local") -> bool:
        now = time.time()
        q = self.hits.setdefault(client_id, deque())
        while q and (now - q[0]) > 60.0:
            q.popleft()
        if len(q) >= self.max_rpm:
            return False
        q.append(now)
        return True
