"""Directed Acyclic Graph (DAG) with Cycle Detection (Point 16.1)."""
from collections import deque
from typing import Dict, Set, List, Any

class CycleDetectedError(ValueError):
    pass

class WorkflowDAG:
    def __init__(self):
        self.nodes: Dict[str, Any] = {}
        self.forward_edges: Dict[str, Set[str]] = {}   # u -> set of downstream nodes v
        self.backward_edges: Dict[str, Set[str]] = {}  # v -> set of upstream dependencies u

    def add_node(self, node_id: str, data: Any = None):
        self.nodes[node_id] = data
        self.forward_edges.setdefault(node_id, set())
        self.backward_edges.setdefault(node_id, set())

    def is_reachable(self, start: str, target: str) -> bool:
        if start == target:
            return True
        visited: Set[str] = set()
        queue = deque([start])
        while queue:
            curr = queue.popleft()
            if curr == target:
                return True
            for nxt in self.forward_edges.get(curr, set()):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return False

    def add_edge(self, u: str, v: str):
        """Add directed dependency edge u -> v (v depends on u). Raises CycleDetectedError if cycle would form."""
        if u not in self.nodes:
            self.add_node(u)
        if v not in self.nodes:
            self.add_node(v)
        if u == v or self.is_reachable(v, u):
            raise CycleDetectedError(f"Cycle detected when adding edge {u} -> {v}")
        self.forward_edges[u].add(v)
        self.backward_edges[v].add(u)

    def get_ancestors(self, node_id: str) -> List[str]:
        visited: Set[str] = set()
        queue = deque(self.backward_edges.get(node_id, set()))
        ancestors: List[str] = []
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                ancestors.append(curr)
                for parent in self.backward_edges.get(curr, set()):
                    if parent not in visited:
                        queue.append(parent)
        return ancestors

    def get_descendants(self, node_id: str) -> List[str]:
        visited: Set[str] = set()
        queue = deque(self.forward_edges.get(node_id, set()))
        descendants: List[str] = []
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                descendants.append(curr)
                for child in self.forward_edges.get(curr, set()):
                    if child not in visited:
                        queue.append(child)
        return descendants

    def topological_sort(self, subset: Set[str] = None) -> List[str]:
        target_nodes = subset if subset is not None else set(self.nodes.keys())
        in_degree = {
            n: len(self.backward_edges.get(n, set()) & target_nodes)
            for n in target_nodes
        }
        queue = deque([n for n, deg in in_degree.items() if deg == 0])
        order: List[str] = []
        while queue:
            curr = queue.popleft()
            order.append(curr)
            for child in self.forward_edges.get(curr, set()):
                if child in in_degree:
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        queue.append(child)
        if len(order) != len(target_nodes):
            raise CycleDetectedError("Graph contains a cycle.")
        return order
