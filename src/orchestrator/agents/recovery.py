"""Multi-Root-Cause DAG Fault Localization and Selective Dependency Rerun (Point 16.2 & 16.3)."""
from typing import Dict, Any, List
from src.orchestrator.workflow.dag import WorkflowDAG

class MultiRootRecoveryAnalyzer:
    def __init__(self, dag: WorkflowDAG):
        self.dag = dag

    def analyze_root_causes(self, failed_node_id: str, node_states: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Point 16.2: Inspect all ancestors, status, validation_score, and timestamps to rank root causes."""
        ancestors = self.dag.get_ancestors(failed_node_id)
        candidates = [failed_node_id] + ancestors
        root_causes: List[Dict[str, Any]] = []

        for nid in candidates:
            st = node_states.get(nid, {})
            status = st.get("status", "unknown")
            val_score = st.get("validation_score", 1.0)
            if status == "failed" or val_score < 0.70:
                confidence = round(max(0.5, 1.0 - val_score if val_score < 1.0 else 0.9), 2)
                root_causes.append({
                    "root_cause_node_id": nid,
                    "status": status,
                    "validation_score": val_score,
                    "confidence": confidence,
                    "evidence": st.get("error", "Low validation score or explicit failure")
                })

        root_causes.sort(key=lambda x: x["confidence"], reverse=True)
        return root_causes

    def compute_selective_rerun_plan(
        self,
        root_cause_ids: List[str],
        node_states: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """Point 16.3: Re-execute only root causes and downstream steps whose cache/output is invalid."""
        impacted = set(root_cause_ids)
        for r_id in root_cause_ids:
            for desc in self.dag.get_descendants(r_id):
                st = node_states.get(desc, {})
                if not st.get("cache_locked", False):
                    impacted.add(desc)
        return self.dag.topological_sort(subset=impacted)
