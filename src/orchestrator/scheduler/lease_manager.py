"""WorkItem Lease Manager (Point 6.2).
Grants time-bounded leases (default 60s) to workers and detects expired leases for safe reassignment.
"""
import time
from typing import Dict, List, Optional
from src.orchestrator.workflow.work_item import WorkItem
from src.orchestrator.config import settings

class LeaseManager:
    def __init__(self, default_lease_seconds: Optional[float] = None):
        self.default_lease_seconds = default_lease_seconds or float(settings.default_lease_seconds)
        self.active_leases: Dict[str, WorkItem] = {}

    def acquire_lease(self, item: WorkItem, worker_id: str, duration_sec: Optional[float] = None) -> float:
        dur = duration_sec if duration_sec is not None else self.default_lease_seconds
        expires_at = time.time() + dur
        item.owner_worker_id = worker_id
        item.lease_expires_at = expires_at
        self.active_leases[item.work_id] = item
        return expires_at

    def renew_lease(self, work_id: str, worker_id: str, duration_sec: Optional[float] = None) -> bool:
        item = self.active_leases.get(work_id)
        if not item or item.owner_worker_id != worker_id:
            return False
        dur = duration_sec if duration_sec is not None else self.default_lease_seconds
        item.lease_expires_at = time.time() + dur
        return True

    def release_lease(self, work_id: str):
        item = self.active_leases.pop(work_id, None)
        if item:
            item.lease_expires_at = None

    def get_expired_items(self, now: Optional[float] = None) -> List[WorkItem]:
        current = now if now is not None else time.time()
        expired = [
            item for item in self.active_leases.values()
            if item.lease_expires_at is not None and current >= item.lease_expires_at
        ]
        return expired
