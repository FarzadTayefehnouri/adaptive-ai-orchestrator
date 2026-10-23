"""Intelligent model router based on task complexity, speed, cost, and quota."""
from typing import List, Optional
from src.orchestrator.models import TaskComplexity
from src.orchestrator.providers.quota_manager import QuotaManager

class ModelRouter:
    def __init__(self, quota_manager: QuotaManager):
        self.quota_mgr = quota_manager
        self.tier_preferences = {
            TaskComplexity.LIGHT: ["groq_llama_8b", "gemini_flash", "local_ollama"],
            TaskComplexity.MODERATE: ["gemini_flash", "groq_llama_70b", "openai_gpt4o_mini"],
            TaskComplexity.COMPLEX: ["gemini_pro", "anthropic_sonnet", "openai_gpt4o"],
            TaskComplexity.CRITICAL: ["gemini_pro", "anthropic_opus", "openai_gpt4o"]
        }

    def route(self, complexity: TaskComplexity) -> str:
        candidates = self.tier_preferences.get(complexity, ["gemini_flash"])
        selected = self.quota_mgr.find_available_provider(candidates)
        if not selected:
            for p_id, p_obj in self.quota_mgr.providers.items():
                if p_obj.is_active and p_obj.remaining_credits > 0:
                    return p_id
            raise RuntimeError("All configured model providers are currently depleted of quota.")
        return selected
