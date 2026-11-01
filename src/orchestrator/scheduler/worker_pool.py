"""Elastic Worker Pool with Bounded Adaptive Scaling (Point 2.1 & 2.2)."""
from typing import Dict, List, Set, Optional
from src.orchestrator.config import settings
from src.orchestrator.scheduler.capability_matcher import WorkerNode

class WorkerPool:
    def __init__(
        self,
        min_workers: Optional[int] = None,
        default_workers: Optional[int] = None,
        max_workers: Optional[int] = None
    ):
        self.min_workers = min_workers or settings.min_workers
        self.default_workers = default_workers or settings.default_workers
        self.max_workers = max_workers or settings.max_workers
        self.workers: Dict[str, WorkerNode] = {}
        self._init_default_workers()

    def _init_default_workers(self):
        default_caps = {"text", "json", "video", "audio", "speech_to_text", "persian", "ocr", "vision", "summarization", "multilingual"}
        for i in range(1, self.default_workers + 1):
            wid = f"worker_{i:02d}"
            self.workers[wid] = WorkerNode(worker_id=wid, capabilities=set(default_caps))

    def adjust_pool_size(self, queue_length: int, quota_exhausted: bool = False) -> int:
        """Dynamically scale workers between min_workers and max_workers based on queue depth & quota."""
        current_count = len(self.workers)
        if quota_exhausted:
            target = self.min_workers
        elif queue_length > current_count * 2 and current_count < self.max_workers:
            target = min(self.max_workers, current_count + 2)
        elif queue_length == 0 and current_count > self.min_workers:
            target = max(self.min_workers, current_count - 1)
        else:
            target = current_count

        default_caps = {"text", "json", "video", "audio", "speech_to_text", "persian", "ocr", "vision", "summarization", "multilingual"}
        while len(self.workers) < target:
            idx = len(self.workers) + 1
            wid = f"worker_{idx:02d}"
            self.workers[wid] = WorkerNode(worker_id=wid, capabilities=set(default_caps))

        if len(self.workers) > target:
            # Remove only idle workers down to target
            idle_ids = [w.worker_id for w in self.workers.values() if not w.active_items and not w.ready_queue]
            for wid in idle_ids:
                if len(self.workers) <= target:
                    break
                del self.workers[wid]

        return len(self.workers)

    def list_workers(self) -> List[WorkerNode]:
        return list(self.workers.values())
