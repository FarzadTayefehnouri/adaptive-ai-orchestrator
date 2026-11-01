"""WorkItem Dataclass and Checkpoint Representation (Points 3 & 6.1).
Each WorkItem is an independent, portable unit of execution that can be checkpointed
and migrated across workers or providers.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Set, Optional, Dict, Any
from src.orchestrator.workflow.state_machine import WorkStatus

@dataclass
class CheckpointData:
    work_id: str
    status: str = "checkpointed"
    progress: float = 0.0
    completed_stages: List[str] = field(default_factory=list)
    pending_stages: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    last_processed_frame: int = 0
    version: int = 1
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_id": self.work_id,
            "status": self.status,
            "progress": round(self.progress, 4),
            "completed_stages": list(self.completed_stages),
            "pending_stages": list(self.pending_stages),
            "artifacts": list(self.artifacts),
            "last_processed_frame": self.last_processed_frame,
            "version": self.version,
            "timestamp_utc": self.timestamp_utc
        }

@dataclass
class WorkItem:
    work_id: str
    parent_task_id: str
    chunk_id: Optional[str]
    stage: str
    priority: int = 5  # 1 (lowest) to 10 (highest)
    dependencies: List[str] = field(default_factory=list)
    required_capabilities: Set[str] = field(default_factory=set)
    estimated_cost: float = 0.0
    estimated_duration: float = 5.0
    status: WorkStatus = WorkStatus.PENDING
    attempt: int = 0
    max_retries: int = 3
    preferred_model: Optional[str] = None
    preferred_provider: Optional[str] = None
    checkpoint_id: Optional[str] = None
    checkpoint_data: Optional[CheckpointData] = None
    input_artifact_ids: List[str] = field(default_factory=list)
    output_artifact_ids: List[str] = field(default_factory=list)
    lease_expires_at: Optional[float] = None
    owner_worker_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    state_history: List[Dict[str, Any]] = field(default_factory=list)

    def save_checkpoint(
        self,
        progress: float,
        completed_stages: List[str],
        pending_stages: List[str],
        artifacts: List[str],
        last_processed_frame: int = 0
    ) -> CheckpointData:
        next_version = (self.checkpoint_data.version + 1) if self.checkpoint_data else 1
        cp = CheckpointData(
            work_id=self.work_id,
            status="checkpointed",
            progress=progress,
            completed_stages=completed_stages,
            pending_stages=pending_stages,
            artifacts=artifacts,
            last_processed_frame=last_processed_frame,
            version=next_version
        )
        self.checkpoint_data = cp
        self.checkpoint_id = f"cp_{self.work_id}_v{next_version}"
        return cp
