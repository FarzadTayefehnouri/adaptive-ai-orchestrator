"""Capability-Based Worker Matcher (Point 8).
Matches WorkItem required_capabilities against WorkerNode capabilities, load, speed, and reliability.
"""
from dataclasses import dataclass, field
from typing import Set, List, Optional
from src.orchestrator.workflow.work_item import WorkItem

@dataclass
class WorkerNode:
    worker_id: str
    capabilities: Set[str] = field(default_factory=lambda: {"text", "json"})
    max_context_tokens: int = 32000
    speed_score: float = 0.85
    reliability_score: float = 0.95
    current_load: float = 0.0
    max_concurrent_items: int = 2
    active_items: List[str] = field(default_factory=list)
    ready_queue: List[WorkItem] = field(default_factory=list)

    @property
    def is_available(self) -> bool:
        return len(self.active_items) < self.max_concurrent_items and self.current_load < 0.95

class CapabilityMatcher:
    def score_worker(self, worker: WorkerNode, item: WorkItem, required_tokens: int = 1000) -> float:
        """Return composite fitness score, or -1.0 if worker lacks required capabilities or context window."""
        if not item.required_capabilities.issubset(worker.capabilities):
            return -1.0
        if required_tokens > worker.max_context_tokens:
            return -1.0
        if not worker.is_available:
            return -1.0

        load_headroom = max(0.0, 1.0 - worker.current_load)
        score = (
            worker.reliability_score * 0.45
            + worker.speed_score * 0.30
            + load_headroom * 0.25
        )
        return round(score, 4)

    def select_best_worker(
        self,
        workers: List[WorkerNode],
        item: WorkItem,
        required_tokens: int = 1000
    ) -> Optional[WorkerNode]:
        best_worker: Optional[WorkerNode] = None
        best_score = -1.0
        for w in workers:
            s = self.score_worker(w, item, required_tokens)
            if s > best_score:
                best_score = s
                best_worker = w
        return best_worker
