"""Workflow, State Machine, Cycle Detection, and Adaptive Video Chunking Tests (Points 4, 5, 7, 16)."""
import unittest
from src.orchestrator.workflow.work_item import WorkItem
from src.orchestrator.workflow.state_machine import StateMachine, WorkStatus, InvalidStateTransitionError
from src.orchestrator.workflow.dag import WorkflowDAG, CycleDetectedError
from src.orchestrator.workflow.chunker import AdaptiveChunker, VideoSegmentProfile
from src.orchestrator.workflow.merger import OutputMerger
from src.orchestrator.agents.recovery import MultiRootRecoveryAnalyzer

class TestWorkflowAndVideoSuite(unittest.TestCase):
    def test_state_machine_valid_and_invalid_transitions(self):
        sm = StateMachine()
        item = WorkItem(work_id="w1", parent_task_id="t1", chunk_id=None, stage="init")
        sm.transition(item, WorkStatus.READY, reason="Dependencies met")
        sm.transition(item, WorkStatus.ASSIGNED, reason="Worker assigned", worker_id="worker_01")
        sm.transition(item, WorkStatus.RUNNING, reason="Started")
        sm.transition(item, WorkStatus.CHECKPOINTED, reason="Saved progress 50%")
        sm.transition(item, WorkStatus.COMPLETED, reason="Done")
        self.assertEqual(item.status, WorkStatus.COMPLETED)
        self.assertEqual(len(item.state_history), 5)

        # Completed -> Running is illegal
        with self.assertRaises(InvalidStateTransitionError):
            sm.transition(item, WorkStatus.RUNNING, reason="Illegal")

    def test_dag_cycle_detection(self):
        dag = WorkflowDAG()
        dag.add_edge("step_1", "step_2")
        dag.add_edge("step_2", "step_3")
        with self.assertRaises(CycleDetectedError):
            dag.add_edge("step_3", "step_1")

    def test_adaptive_video_chunking_and_merger(self):
        chunker = AdaptiveChunker()
        segments = [
            # High complexity fast action (should get 120s chunks)
            VideoSegmentProfile(
                start_sec=0.0, end_sec=240.0,
                scene_change_rate=0.9, motion_intensity=0.9,
                face_count=8, speaker_count=4, audio_quality=0.4,
                speech_density=0.9, is_multilingual=True,
                onscreen_text_density=0.8, semantic_complexity=0.9
            ),
            # Static low complexity scene (should get 900s chunk)
            VideoSegmentProfile(
                start_sec=240.0, end_sec=840.0,
                scene_change_rate=0.05, motion_intensity=0.05,
                face_count=1, speaker_count=1, audio_quality=0.98,
                speech_density=0.1, is_multilingual=False,
                onscreen_text_density=0.0, semantic_complexity=0.1
            )
        ]
        items = chunker.create_adaptive_video_chunks("task_vid", segments)
        # First 240s split into two 120s chunks (each has audio + vision + ocr = 6 items)
        # Next 600s fits in one chunk (audio + vision = 2 items) + 1 final merger = 9 items total
        self.assertEqual(len(items), 9)
        self.assertEqual(items[-1].stage, "temporal_semantic_merger")

        merger = OutputMerger()
        merged = merger.merge_chunks([
            {"start_sec": 120.0, "end_sec": 240.0, "stage": "audio", "text": "Second part"},
            {"start_sec": 0.0, "end_sec": 120.0, "stage": "audio", "text": "First part"},
        ])
        self.assertEqual(merged["merged_count"], 2)
        self.assertTrue(merged["synthesized_text"].startswith("[0s-120s"))

    def test_multi_root_cause_recovery(self):
        dag = WorkflowDAG()
        dag.add_edge("ingest", "transcribe")
        dag.add_edge("ingest", "vision")
        dag.add_edge("transcribe", "merge")
        dag.add_edge("vision", "merge")

        analyzer = MultiRootRecoveryAnalyzer(dag)
        states = {
            "ingest": {"status": "completed", "validation_score": 0.98, "cache_locked": True},
            "transcribe": {"status": "failed", "validation_score": 0.10, "error": "Audio corrupted"},
            "vision": {"status": "completed", "validation_score": 0.45, "error": "Low OCR confidence"},
            "merge": {"status": "failed", "validation_score": 0.0}
        }
        roots = analyzer.analyze_root_causes("merge", states)
        self.assertGreaterEqual(len(roots), 2)
        plan = analyzer.compute_selective_rerun_plan(["transcribe"], states)
        self.assertEqual(plan, ["transcribe", "merge"])
