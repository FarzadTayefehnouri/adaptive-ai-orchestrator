"""Bounded Priority Queue for WorkItems (Point 2.1 & 2.2)."""
import heapq
from typing import List, Optional, Tuple
from src.orchestrator.workflow.work_item import WorkItem
from src.orchestrator.config import settings

class QueueOverflowError(RuntimeError):
    pass

class WorkPriorityQueue:
    def __init__(self, max_size: Optional[int] = None):
        self.max_size = max_size or settings.max_queue_size
        self._heap: List[Tuple[int, int, WorkItem]] = []
        self._counter = 0

    def push(self, item: WorkItem):
        if len(self._heap) >= self.max_size:
            raise QueueOverflowError(f"Work queue reached maximum capacity ({self.max_size}).")
        self._counter += 1
        # Negate priority so higher priority (e.g. 10) pops before lower priority (e.g. 1)
        heapq.heappush(self._heap, (-item.priority, self._counter, item))

    def pop(self) -> Optional[WorkItem]:
        if not self._heap:
            return None
        _, _, item = heapq.heappop(self._heap)
        return item

    def peek(self) -> Optional[WorkItem]:
        if not self._heap:
            return None
        return self._heap[0][2]

    def __len__(self) -> int:
        return len(self._heap)
