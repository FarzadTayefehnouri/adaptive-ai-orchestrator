"""Three-tier memory store (Section 7 of requirements)."""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

class MemoryStore:
    def __init__(self):
        self.working_memory: Dict[str, Any] = {}
        self.validated_store: Dict[str, Dict[str, Any]] = {}
        self.experience_memory: List[Dict[str, Any]] = []

    def save_working(self, key: str, value: Any):
        self.working_memory[key] = value

    def commit_validated(self, step_id: str, output: Any, validation_score: float, reason: str):
        timestamp = datetime.now(timezone.utc).isoformat()
        current_version = 1
        if step_id in self.validated_store:
            current_version = self.validated_store[step_id]["version"] + 1

        self.validated_store[step_id] = {
            "version": current_version,
            "output": output,
            "validation_score": validation_score,
            "reason": reason,
            "committed_at_utc": timestamp
        }

    def record_experience(self, task_type: str, model_used: str, success: bool, recovery_needed: bool):
        self.experience_memory.append({
            "task_type": task_type,
            "model_used": model_used,
            "success": success,
            "recovery_needed": recovery_needed,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        })
