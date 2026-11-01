"""Intelligent Model Router with Dynamic Escalation Ladder.
Automatically routes light tasks to lightweight models, and escalates to higher-tier models
when a light model fails or when manually requested by the user.
"""
from typing import List, Optional, Dict
from src.orchestrator.models import TaskComplexity
from src.orchestrator.providers.quota_manager import QuotaManager

class ModelRouter:
    def __init__(self, quota_manager: QuotaManager):
        self.quota_mgr = quota_manager
        
        # Priority ladder per complexity tier
        self.tier_preferences: Dict[TaskComplexity, List[str]] = {
            TaskComplexity.LIGHT: ["groq_llama_8b", "gemini_flash", "local_ollama"],
            TaskComplexity.MODERATE: ["gemini_flash", "groq_llama_70b", "openai_gpt4o_mini"],
            TaskComplexity.COMPLEX: ["gemini_pro", "anthropic_sonnet", "openai_gpt4o"],
            TaskComplexity.CRITICAL: ["gemini_pro", "anthropic_opus", "openai_gpt4o"]
        }
        
        # Escalation sequence
        self.escalation_ladder: Dict[TaskComplexity, TaskComplexity] = {
            TaskComplexity.LIGHT: TaskComplexity.MODERATE,
            TaskComplexity.MODERATE: TaskComplexity.COMPLEX,
            TaskComplexity.COMPLEX: TaskComplexity.CRITICAL,
            TaskComplexity.CRITICAL: TaskComplexity.CRITICAL
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

    def escalate(self, current_complexity: TaskComplexity, current_model: str, reason: str) -> tuple[TaskComplexity, str]:
        """Escalate from a light model to a higher-capacity reasoning model.
        Returns (new_complexity, new_model_name).
        """
        next_complexity = self.escalation_ladder.get(current_complexity, TaskComplexity.COMPLEX)
        candidates = self.tier_preferences.get(next_complexity, ["gemini_pro"])
        
        # Ensure we pick a strictly different and higher model than current_model
        filtered_candidates = [c for c in candidates if c != current_model]
        new_model = self.quota_mgr.find_available_provider(filtered_candidates)
        
        if not new_model:
            # Fallback to any active complex model
            new_model = self.quota_mgr.find_available_provider(self.tier_preferences[TaskComplexity.COMPLEX])
            
        new_model = new_model or current_model
        return next_complexity, new_model
