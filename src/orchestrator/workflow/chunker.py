"""Adaptive Horizontal, Vertical, and Hybrid Video/Task Chunker (Points 4 & 5).
Splits large media or tasks into variable-length chunks based on multi-factor complexity metrics
and builds a combined horizontal + vertical DAG of WorkItems.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set
from src.orchestrator.workflow.work_item import WorkItem
from src.orchestrator.workflow.state_machine import WorkStatus

@dataclass
class VideoSegmentProfile:
    start_sec: float
    end_sec: float
    scene_change_rate: float = 0.1      # 0.0 to 1.0
    motion_intensity: float = 0.2       # 0.0 to 1.0
    face_count: int = 1
    speaker_count: int = 1
    audio_quality: float = 0.9          # 1.0 = clean, 0.2 = noisy
    speech_density: float = 0.4         # 0.0 to 1.0
    is_multilingual: bool = False
    onscreen_text_density: float = 0.1  # triggers OCR
    object_count: int = 2
    has_music_or_noise: bool = False
    semantic_complexity: float = 0.3    # 0.0 to 1.0

    def compute_complexity_score(self) -> float:
        """Compute normalized complexity score in [0.0, 1.0]."""
        score = (
            self.scene_change_rate * 0.18
            + self.motion_intensity * 0.15
            + min(1.0, self.face_count / 10.0) * 0.07
            + min(1.0, self.speaker_count / 5.0) * 0.08
            + (1.0 - self.audio_quality) * 0.10
            + self.speech_density * 0.10
            + (0.12 if self.is_multilingual else 0.0)
            + self.onscreen_text_density * 0.10
            + (0.05 if self.has_music_or_noise else 0.0)
            + self.semantic_complexity * 0.15
        )
        return min(1.0, max(0.05, round(score, 3)))

    def recommended_chunk_duration_sec(self) -> float:
        """Point 5: Simple static/dialogue scenes get 10-15 min chunks; dense/fast/multilingual get 2-4 min chunks."""
        c = self.compute_complexity_score()
        if c >= 0.70:
            return 120.0   # 2 minutes for high action / dense scenes
        elif c >= 0.45:
            return 240.0   # 4 minutes for multilingual / moderate complexity
        elif c >= 0.25:
            return 600.0   # 10 minutes for simple dialogue
        return 900.0       # 15 minutes for static scenes

class AdaptiveChunker:
    def create_adaptive_video_chunks(
        self,
        parent_task_id: str,
        segments: List[VideoSegmentProfile],
        priority: int = 5
    ) -> List[WorkItem]:
        """Point 4.3 & 5: Hybrid Horizontal (time chunks) + Vertical (audio, vision, OCR, merger) decomposition."""
        work_items: List[WorkItem] = []
        chunk_idx = 0
        leaf_stage_ids: List[str] = []

        for seg in segments:
            max_dur = seg.recommended_chunk_duration_sec()
            cur = seg.start_sec
            while cur < seg.end_sec:
                chunk_idx += 1
                nxt = min(seg.end_sec, cur + max_dur)
                chunk_id = f"chunk_{chunk_idx:02d}"
                comp_score = seg.compute_complexity_score()

                # Vertical stage 1: Audio Analysis
                audio_wid = f"{parent_task_id}_{chunk_id}_audio"
                audio_caps = {"audio", "speech_to_text"}
                if seg.is_multilingual:
                    audio_caps.add("multilingual")
                work_items.append(WorkItem(
                    work_id=audio_wid,
                    parent_task_id=parent_task_id,
                    chunk_id=chunk_id,
                    stage="audio_analysis",
                    priority=priority,
                    dependencies=[],
                    required_capabilities=audio_caps,
                    estimated_cost=round(0.01 * (nxt - cur) / 60.0, 4),
                    estimated_duration=round((nxt - cur) * 0.05, 2),
                    status=WorkStatus.READY,
                    payload={"start_sec": cur, "end_sec": nxt, "complexity": comp_score}
                ))

                # Vertical stage 2: Vision Scene Analysis
                vision_wid = f"{parent_task_id}_{chunk_id}_vision"
                work_items.append(WorkItem(
                    work_id=vision_wid,
                    parent_task_id=parent_task_id,
                    chunk_id=chunk_id,
                    stage="vision_analysis",
                    priority=priority,
                    dependencies=[],
                    required_capabilities={"video", "vision"},
                    estimated_cost=round(0.02 * (nxt - cur) / 60.0, 4),
                    estimated_duration=round((nxt - cur) * 0.08, 2),
                    status=WorkStatus.READY,
                    payload={"start_sec": cur, "end_sec": nxt, "complexity": comp_score}
                ))

                leaf_stage_ids.extend([audio_wid, vision_wid])

                # Vertical stage 3: OCR (if onscreen text exists)
                if seg.onscreen_text_density > 0.05:
                    ocr_wid = f"{parent_task_id}_{chunk_id}_ocr"
                    work_items.append(WorkItem(
                        work_id=ocr_wid,
                        parent_task_id=parent_task_id,
                        chunk_id=chunk_id,
                        stage="ocr_extraction",
                        priority=priority,
                        dependencies=[vision_wid],
                        required_capabilities={"ocr", "vision"},
                        estimated_cost=0.005,
                        estimated_duration=2.0,
                        status=WorkStatus.PENDING,
                        payload={"start_sec": cur, "end_sec": nxt}
                    ))
                    leaf_stage_ids.append(ocr_wid)

                cur = nxt

        # Final Temporal & Semantic Merger Stage
        merger_wid = f"{parent_task_id}_merger"
        work_items.append(WorkItem(
            work_id=merger_wid,
            parent_task_id=parent_task_id,
            chunk_id=None,
            stage="temporal_semantic_merger",
            priority=priority,
            dependencies=leaf_stage_ids,
            required_capabilities={"text", "summarization"},
            estimated_cost=0.01,
            estimated_duration=3.0,
            status=WorkStatus.PENDING,
            payload={"total_chunks": chunk_idx}
        ))

        return work_items
