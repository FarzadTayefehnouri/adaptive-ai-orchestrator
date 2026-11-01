"""Capability and Quota-Aware Model Router separating Provider from Model (Points 8 & 9.2)."""
from typing import List, Optional, Set
from src.orchestrator.providers.base import ModelSpec
from src.orchestrator.routing.quota import AtomicQuotaManager

DEFAULT_MODEL_CATALOG: List[ModelSpec] = [
    ModelSpec(provider="groq", model="llama-3.1-8b-instant", tier="light", capabilities=["text", "json"], max_context_tokens=32000),
    ModelSpec(provider="gemini", model="gemini-1.5-flash", tier="light", capabilities=["text", "json", "vision", "audio", "video", "ocr"], max_context_tokens=128000),
    ModelSpec(provider="groq", model="llama-3.3-70b-versatile", tier="moderate", capabilities=["text", "json", "code"], max_context_tokens=64000),
    ModelSpec(provider="openai", model="gpt-4o-mini", tier="moderate", capabilities=["text", "json", "vision"], max_context_tokens=128000),
    ModelSpec(provider="gemini", model="gemini-1.5-pro", tier="complex", capabilities=["text", "json", "vision", "audio", "video", "ocr", "code"], max_context_tokens=1000000),
    ModelSpec(provider="anthropic", model="claude-3-5-sonnet-latest", tier="complex", capabilities=["text", "json", "code", "vision"], max_context_tokens=200000),
    ModelSpec(provider="ollama", model="llama3", tier="light", capabilities=["text", "json"], max_context_tokens=16000),
]

class CapabilityRouter:
    def __init__(self, quota_manager: AtomicQuotaManager, catalog: Optional[List[ModelSpec]] = None):
        self.quota_manager = quota_manager
        self.catalog = catalog or list(DEFAULT_MODEL_CATALOG)

    def select_candidates(
        self,
        tier: str = "light",
        required_capabilities: Optional[Set[str]] = None,
        min_context_tokens: int = 1000
    ) -> List[ModelSpec]:
        req_caps = required_capabilities or {"text"}
        matches: List[ModelSpec] = []
        for spec in self.catalog:
            if not req_caps.issubset(set(spec.capabilities)):
                continue
            if spec.max_context_tokens < min_context_tokens:
                continue
            ledger = self.quota_manager.ledgers.get(spec.provider)
            if ledger and (not ledger.is_active or ledger.available_requests() <= 0):
                continue
            matches.append(spec)

        # Prioritize matching tier first
        tier_matches = [m for m in matches if m.tier == tier]
        other_matches = [m for m in matches if m.tier != tier]
        return tier_matches + other_matches
