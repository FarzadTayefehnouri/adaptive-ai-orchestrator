"""Dual Backward and Forward Recovery Engine (Section 6 of requirements).
Operates over an internal DAG of execution steps to isolate root causes and selectively re-execute downstream steps.
Zero external dependencies required.
"""
from typing import Dict, List, Set, Optional
from collections import deque
from src.orchestrator.models import ExecutionStep, ErrorRecord, ErrorCategory

class DAG:
    """Lightweight directed acyclic graph implementation."""
    def __init__(self):
        self.nodes: Set[str] = set()
        self.adj: Dict[str, Set[str]] = {}      # u -> children (outgoing)
        self.pred: Dict[str, Set[str]] = {}     # v -> parents (incoming)

    def add_node(self, node: str):
        if node not in self.nodes:
            self.nodes.add(node)
            self.adj[node] = set()
            self.pred[node] = set()

    def add_edge(self, u: str, v: str):
        self.add_node(u)
        self.add_node(v)
        self.adj[u].add(v)
        self.pred[v].add(u)

    def get_ancestors(self, node: str) -> Set[str]:
        visited = set()
        queue = deque(self.pred.get(node, []))
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                queue.extend(self.pred.get(curr, []))
        return visited

    def get_descendants(self, node: str) -> Set[str]:
        visited = set()
        queue = deque(self.adj.get(node, []))
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                queue.extend(self.adj.get(curr, []))
        return visited

    def topological_sort_subgraph(self, subset: Set[str]) -> List[str]:
        in_degree = {n: 0 for n in subset}
        for u in subset:
            for v in self.adj.get(u, []):
                if v in subset:
                    in_degree[v] += 1

        queue = deque([n for n, deg in in_degree.items() if deg == 0])
        order = []
        while queue:
            curr = queue.popleft()
            order.append(curr)
            for neighbor in self.adj.get(curr, []):
                if neighbor in subset:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
        return order


class RecoveryEngine:
    def __init__(self):
        self.dag = DAG()
        self.steps: Dict[str, ExecutionStep] = {}

    def add_step(self, step: ExecutionStep):
        self.steps[step.step_id] = step
        self.dag.add_node(step.step_id)
        for dep in step.dependencies:
            self.dag.add_edge(dep, step.step_id)

    def backward_recovery(self, failed_step_id: str, error_desc: str) -> ErrorRecord:
        ancestors = self.dag.get_ancestors(failed_step_id)
        root_cause_candidate = failed_step_id
        
        for anc_id in ancestors:
            step = self.steps.get(anc_id)
            if step and (step.status == "failed" or step.output_payload is None):
                root_cause_candidate = anc_id
                break

        impacted = list(self.dag.get_descendants(root_cause_candidate))
        if failed_step_id not in impacted and failed_step_id != root_cause_candidate:
            impacted.append(failed_step_id)

        return ErrorRecord(
            error_id=f"err_{failed_step_id}",
            step_id=failed_step_id,
            category=ErrorCategory.DEPENDENCY_ERROR if root_cause_candidate != failed_step_id else ErrorCategory.AGENT_FAULT,
            severity="high",
            message=error_desc,
            confidence=0.92,
            root_cause_step_id=root_cause_candidate,
            impacted_downstream_steps=impacted
        )

    def forward_recovery_plan(self, root_cause_step_id: str) -> List[str]:
        descendants = self.dag.get_descendants(root_cause_step_id)
        subset = {root_cause_step_id}.union(descendants)
        return self.dag.topological_sort_subgraph(subset)
