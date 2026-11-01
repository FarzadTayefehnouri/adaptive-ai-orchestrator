"""Scheduler Test Suite (Point 22: WorkItem splitting, CapabilityMatcher, WorkerPool, Lease, Heartbeat, Work Stealing, Preemption)."""
import unittest
import time
from src.orchestrator.workflow.work_item import WorkItem
from src.orchestrator.workflow.state_machine import WorkStatus
from src.orchestrator.scheduler.priority_queue import WorkPriorityQueue, QueueOverflowError
from src.orchestrator.scheduler.capability_matcher import WorkerNode, CapabilityMatcher
from src.orchestrator.scheduler.worker_pool import WorkerPool
from src.orchestrator.scheduler.adaptive_scheduler import AdaptiveScheduler

class TestAdaptiveSchedulerSuite(unittest.TestCase):
    def test_priority_queue_ordering_and_overflow(self):
        pq = WorkPriorityQueue(max_size=2)
        low = WorkItem(work_id="w_low", parent_task_id="t1", chunk_id=None, stage="s1", priority=2, status=WorkStatus.READY)
        high = WorkItem(work_id="w_high", parent_task_id="t1", chunk_id=None, stage="s2", priority=9, status=WorkStatus.READY)
        pq.push(low)
        pq.push(high)

        with self.assertRaises(QueueOverflowError):
            pq.push(WorkItem(work_id="w_extra", parent_task_id="t1", chunk_id=None, stage="s3", priority=5))

        first = pq.pop()
        self.assertEqual(first.work_id, "w_high")

    def test_capability_matching_and_worker_selection(self):
        matcher = CapabilityMatcher()
        w_text = WorkerNode(worker_id="w1", capabilities={"text", "json"}, reliability_score=0.9)
        w_video = WorkerNode(worker_id="w2", capabilities={"video", "persian", "ocr"}, reliability_score=0.95)

        item = WorkItem(
            work_id="vid_item",
            parent_task_id="t1",
            chunk_id="c1",
            stage="ocr",
            required_capabilities={"video", "persian", "ocr"},
            status=WorkStatus.READY
        )
        selected = matcher.select_best_worker([w_text, w_video], item)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.worker_id, "w2")

    def test_lease_expiry_heartbeat_and_reassignment(self):
        sched = AdaptiveScheduler(WorkerPool(min_workers=2, default_workers=2, max_workers=4))
        item = WorkItem(
            work_id="w_lease",
            parent_task_id="t1",
            chunk_id="c1",
            stage="audio",
            required_capabilities={"audio"},
            status=WorkStatus.READY
        )
        sched.submit_work_item(item)
        running = sched.schedule_next()
        self.assertEqual(running.status, WorkStatus.RUNNING)

        # Record valid heartbeat -> renews lease
        hb = sched.heartbeat_monitor.record_heartbeat("w_lease", running.owner_worker_id, progress=0.5, last_checkpoint="frame_100")
        self.assertTrue(hb["lease_renewed"])

        # Force lease expiration in the past
        running.lease_expires_at = time.time() - 10.0
        reassigned = sched.recover_expired_leases()
        self.assertEqual(len(reassigned), 1)
        self.assertEqual(reassigned[0].status, WorkStatus.READY)
        self.assertEqual(reassigned[0].attempt, 1)

    def test_work_stealing_and_urgent_preemption(self):
        sched = AdaptiveScheduler(WorkerPool(min_workers=2, default_workers=2, max_workers=4))
        w1, w2 = sched.pool.list_workers()[:2]

        queued_item = WorkItem(
            work_id="steal_me",
            parent_task_id="t1",
            chunk_id="c2",
            stage="text",
            required_capabilities={"text"},
            status=WorkStatus.READY
        )
        w2.ready_queue.append(queued_item)

        stolen = sched.steal_work(idle_worker=w1, overloaded_worker=w2)
        self.assertIsNotNone(stolen)
        self.assertEqual(stolen.owner_worker_id, w1.worker_id)
        self.assertEqual(stolen.status, WorkStatus.ASSIGNED)

        # Transition stolen item to RUNNING and test preemption by higher-priority item
        sched.state_machine.transition(stolen, WorkStatus.RUNNING, reason="Start")
        urgent = WorkItem(
            work_id="urgent_99",
            parent_task_id="t2",
            chunk_id=None,
            stage="critical_step",
            priority=10,
            required_capabilities={"text"},
            status=WorkStatus.READY
        )
        preempted = sched.preempt_for_urgent_item(urgent, stolen)
        self.assertTrue(preempted)
        self.assertEqual(stolen.status, WorkStatus.PAUSED)
        self.assertIsNotNone(stolen.checkpoint_data)
