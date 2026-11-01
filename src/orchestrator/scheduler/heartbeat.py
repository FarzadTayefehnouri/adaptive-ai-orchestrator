"""Worker Heartbeat Monitor (Point 6.3)."""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.orchestrator.scheduler.lease_manager import LeaseManager

class HeartbeatMonitor:
    def __init__(self, lease_manager: LeaseManager):
        self.lease_manager = lease_manager
        self.latest_heartbeats: Dict[str, Dict[str, Any]] = {}

    def record_heartbeat(
        self,
        work_id: str,
        worker_id: str,
        progress: float,
        last_checkpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        renewed = self.lease_manager.renew_lease(work_id, worker_id)
        hb = {
            "work_id": work_id,
            "worker_id": worker_id,
            "progress": round(progress, 4),
            "last_checkpoint": last_checkpoint,
            "lease_renewed": renewed,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.latest_heartbeats[work_id] = hb
        return hb
