"""Composite Content-Hash Response Cache (Point 20.1).
Computes cache_key = sha256(prompt + input_hash + model_policy + workflow_version).
"""
import hashlib
from typing import Dict, Any, Optional
from src.orchestrator.memory.sqlite_store import SQLiteStore

class ResponseCache:
    def __init__(self, store: Optional[SQLiteStore] = None, workflow_version: str = "v0.2.0"):
        self.store = store or SQLiteStore()
        self.workflow_version = workflow_version

    def generate_key(
        self,
        prompt: str,
        model_policy: str = "auto",
        input_hash: str = "",
        workflow_version: Optional[str] = None
    ) -> str:
        wf_ver = workflow_version or self.workflow_version
        composite = f"{prompt.strip()}|{input_hash}|{model_policy}|{wf_ver}"
        return hashlib.sha256(composite.encode("utf-8")).hexdigest()

    def lookup(
        self,
        prompt: str,
        model_policy: str = "auto",
        input_hash: str = ""
    ) -> Optional[Dict[str, Any]]:
        key = self.generate_key(prompt, model_policy, input_hash)
        return self.store.get_cache_entry(key)

    def store_response(
        self,
        prompt: str,
        model_policy: str,
        output: Dict[str, Any],
        score: float = 1.0,
        input_hash: str = ""
    ):
        key = self.generate_key(prompt, model_policy, input_hash)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self.store.save_cache_entry(key, model_policy, prompt_hash, output, score)
