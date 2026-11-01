"""Formal WorkItem State Machine (Point 7).
Enforces allowed state transitions and records full audit history per transition.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Set, List, Any, Optional

class WorkStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    ASSIGNED = "assigned"
    RUNNING = "running"
    CHECKPOINTED = "checkpointed"
    PAUSING = "pausing"
    PAUSED = "paused"
    REASSIGNING = "reassigning"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

ALLOWED_TRANSITIONS: Dict[WorkStatus, Set[WorkStatus]] = {
    WorkStatus.PENDING: {WorkStatus.READY, WorkStatus.CANCELLED},
    WorkStatus.READY: {WorkStatus.ASSIGNED, WorkStatus.CANCELLED},
    WorkStatus.ASSIGNED: {WorkStatus.RUNNING, WorkStatus.REASSIGNING, WorkStatus.CANCELLED},
    WorkStatus.RUNNING: {
        WorkStatus.CHECKPOINTED,
        WorkStatus.COMPLETED,
        WorkStatus.PAUSING,
        WorkStatus.REASSIGNING,
        WorkStatus.RETRYING,
        WorkStatus.FAILED,
        WorkStatus.CANCELLED,
    },
    WorkStatus.CHECKPOINTED: {
        WorkStatus.RUNNING,
        WorkStatus.COMPLETED,
        WorkStatus.PAUSED,
        WorkStatus.REASSIGNING,
        WorkStatus.ASSIGNED,
        WorkStatus.CANCELLED,
    },
    WorkStatus.PAUSING: {WorkStatus.PAUSED, WorkStatus.CHECKPOINTED, WorkStatus.CANCELLED},
    WorkStatus.PAUSED: {WorkStatus.READY, WorkStatus.ASSIGNED, WorkStatus.RUNNING, WorkStatus.CANCELLED},
    WorkStatus.REASSIGNING: {WorkStatus.ASSIGNED, WorkStatus.READY, WorkStatus.FAILED, WorkStatus.CANCELLED},
    WorkStatus.RETRYING: {WorkStatus.ASSIGNED, WorkStatus.READY, WorkStatus.FAILED, WorkStatus.CANCELLED},
    WorkStatus.COMPLETED: set(),
    WorkStatus.FAILED: {WorkStatus.RETRYING, WorkStatus.READY},
    WorkStatus.CANCELLED: set(),
}

class InvalidStateTransitionError(ValueError):
    pass

class StateMachine:
    def __init__(self):
        self.transition_log: List[Dict[str, Any]] = []

    def transition(
        self,
        work_item: Any,
        new_status: WorkStatus,
        reason: str = "",
        worker_id: Optional[str] = None
    ) -> Dict[str, Any]:
        old_status = WorkStatus(work_item.status) if not isinstance(work_item.status, WorkStatus) else work_item.status
        target = WorkStatus(new_status)

        if target not in ALLOWED_TRANSITIONS.get(old_status, set()):
            raise InvalidStateTransitionError(
                f"Illegal state transition for '{work_item.work_id}': {old_status.value} -> {target.value}"
            )

        work_item.status = target
        record = {
            "task_id": work_item.parent_task_id,
            "step_id": work_item.stage,
            "work_id": work_item.work_id,
            "old_status": old_status.value,
            "new_status": target.value,
            "reason": reason,
            "worker_id": worker_id or work_item.owner_worker_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
        self.transition_log.append(record)
        work_item.state_history.append(record)
        return record
