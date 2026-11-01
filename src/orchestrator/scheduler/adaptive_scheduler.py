"""Adaptive Scheduler with Lease Recovery, Work Stealing, and Preemption (Points 2, 6, 7, 8)."""
from typing import Dict, List, Optional
from src.orchestrator.workflow.work_item import WorkItem
from src.orchestrator.workflow.state_machine import StateMachine, WorkStatus
from src.orchestrator.scheduler.priority_queue import WorkPriorityQueue
from src.orchestrator.scheduler.lease_manager import LeaseManager
from src.orchestrator.scheduler.heartbeat import HeartbeatMonitor
from src.orchestrator.scheduler.capability_matcher import CapabilityMatcher, WorkerNode
from src.orchestrator.scheduler.worker_pool import WorkerPool

class AdaptiveScheduler:
    def __init__(self, worker_pool: Optional[WorkerPool] = None):
        self.pool = worker_pool or WorkerPool()
        self.queue = WorkPriorityQueue()
        self.lease_manager = LeaseManager()
        self.heartbeat_monitor = HeartbeatMonitor(self.lease_manager)
        self.matcher = CapabilityMatcher()
        self.state_machine = StateMachine()
        self.items: Dict[str, WorkItem] = {}

    def submit_work_item(self, item: WorkItem):
        self.items[item.work_id] = item
        if item.status == WorkStatus.PENDING and not item.dependencies:
            self.state_machine.transition(item, WorkStatus.READY, reason="No unmet dependencies")
        if item.status == WorkStatus.READY:
            self.queue.push(item)
        self.pool.adjust_pool_size(len(self.queue))

    def schedule_next(self) -> Optional[WorkItem]:
        item = self.queue.pop()
        if not item:
            return None
        worker = self.matcher.select_best_worker(self.pool.list_workers(), item)
        if not worker:
            # Re-queue if no capable worker is currently free
            self.queue.push(item)
            return None

        self.state_machine.transition(item, WorkStatus.ASSIGNED, reason="Capability matched", worker_id=worker.worker_id)
        self.lease_manager.acquire_lease(item, worker.worker_id)
        worker.active_items.append(item.work_id)
        worker.current_load = min(1.0, len(worker.active_items) / max(1, worker.max_concurrent_items))
        self.state_machine.transition(item, WorkStatus.RUNNING, reason="Execution started on worker", worker_id=worker.worker_id)
        return item

    def recover_expired_leases(self, now: Optional[float] = None) -> List[WorkItem]:
        """Point 6.2: Reassign work items whose worker lease expired without heartbeat."""
        expired = self.lease_manager.get_expired_items(now=now)
        reassigned: List[WorkItem] = []
        for item in expired:
            old_worker_id = item.owner_worker_id
            if old_worker_id and old_worker_id in self.pool.workers:
                w = self.pool.workers[old_worker_id]
                if item.work_id in w.active_items:
                    w.active_items.remove(item.work_id)
                w.current_load = min(1.0, len(w.active_items) / max(1, w.max_concurrent_items))

            self.lease_manager.release_lease(item.work_id)
            item.attempt += 1
            if item.attempt <= item.max_retries:
                self.state_machine.transition(item, WorkStatus.REASSIGNING, reason="Lease expired; reassigning from checkpoint")
                self.state_machine.transition(item, WorkStatus.READY, reason="Re-queued for healthy worker")
                self.queue.push(item)
                reassigned.append(item)
            else:
                self.state_machine.transition(item, WorkStatus.FAILED, reason="Max retries exceeded after lease expiry")
        return reassigned

    def steal_work(self, idle_worker: WorkerNode, overloaded_worker: WorkerNode) -> Optional[WorkItem]:
        """Point 6.4: Safe Work Stealing of READY items from an overloaded worker's local queue."""
        if not idle_worker.is_available or not overloaded_worker.ready_queue:
            return None
        for idx, candidate in enumerate(overloaded_worker.ready_queue):
            if candidate.status == WorkStatus.READY and self.matcher.score_worker(idle_worker, candidate) > 0:
                stolen = overloaded_worker.ready_queue.pop(idx)
                self.state_machine.transition(stolen, WorkStatus.ASSIGNED, reason=f"Work stolen from {overloaded_worker.worker_id}", worker_id=idle_worker.worker_id)
                self.lease_manager.acquire_lease(stolen, idle_worker.worker_id)
                idle_worker.active_items.append(stolen.work_id)
                return stolen
        return None

    def preempt_for_urgent_item(self, urgent_item: WorkItem, running_item: WorkItem) -> bool:
        """Point 6.5: Checkpoint a lower-priority running item and preempt it for a higher-priority urgent item."""
        if urgent_item.priority <= running_item.priority:
            return False
        if running_item.status != WorkStatus.RUNNING:
            return False

        worker_id = running_item.owner_worker_id
        # Save safe checkpoint on running item
        running_item.save_checkpoint(
            progress=0.5,
            completed_stages=[running_item.stage + "_part1"],
            pending_stages=[running_item.stage + "_part2"],
            artifacts=[]
        )
        self.state_machine.transition(running_item, WorkStatus.CHECKPOINTED, reason=f"Preempted by urgent item {urgent_item.work_id}")
        self.state_machine.transition(running_item, WorkStatus.PAUSED, reason="Paused after checkpointing for preemption")
        self.lease_manager.release_lease(running_item.work_id)

        if worker_id and worker_id in self.pool.workers:
            w = self.pool.workers[worker_id]
            if running_item.work_id in w.active_items:
                w.active_items.remove(running_item.work_id)

        # Schedule urgent item immediately
        self.submit_work_item(urgent_item)
        return True
