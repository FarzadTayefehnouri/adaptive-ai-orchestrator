"""Temporal and Semantic Output Merger (Point 4.3)."""
from typing import List, Dict, Any

class OutputMerger:
    def merge_chunks(self, chunk_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Sort completed chunk artifacts chronologically by start_sec and synthesize unified output."""
        sorted_chunks = sorted(
            chunk_outputs,
            key=lambda x: (x.get("start_sec", 0.0), x.get("stage", ""))
        )
        timeline_summary = []
        combined_text_parts = []
        for c in sorted_chunks:
            stage = c.get("stage", "chunk")
            text = c.get("text", "")
            start_s = c.get("start_sec", 0.0)
            end_s = c.get("end_sec", 0.0)
            timeline_summary.append({
                "window": f"{start_s:.1f}s-{end_s:.1f}s",
                "stage": stage,
                "summary": text
            })
            if text:
                combined_text_parts.append(f"[{start_s:.0f}s-{end_s:.0f}s | {stage}]: {text}")

        return {
            "merged_count": len(sorted_chunks),
            "timeline": timeline_summary,
            "synthesized_text": "\n".join(combined_text_parts)
        }
