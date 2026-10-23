"""Smart Quota Manager adhering to Section 2 of requirements.
Distinguishes real vs estimated quota and performs graceful failover.
"""
from typing import Dict, Optional, List
from src.orchestrator.models import QuotaType

class ProviderQuotaStatus:
    def __init__(self, provider_id: str, quota_type: QuotaType, remaining_credits: float, total_limit: float):
        self.provider_id = provider_id
        self.quota_type = quota_type
        self.remaining_credits = remaining_credits
        self.total_limit = total_limit
        self.is_active = True
        self.consecutive_429_errors = 0

    def consume(self, amount: float = 1.0) -> bool:
        if self.remaining_credits >= amount:
            self.remaining_credits -= amount
            return True
        return False

    def report_rate_limit(self):
        self.consecutive_429_errors += 1
        self.remaining_credits = 0
        self.is_active = False

    def reset_status(self, credits: float):
        self.remaining_credits = credits
        self.consecutive_429_errors = 0
        self.is_active = True

    def to_dict(self) -> Dict:
        return {
            "provider_id": self.provider_id,
            "quota_type": self.quota_type.value,
            "is_real_data": self.quota_type == QuotaType.REAL,
            "remaining_credits": self.remaining_credits,
            "total_limit": self.total_limit,
            "is_active": self.is_active,
            "notice": "Official verified quota" if self.quota_type == QuotaType.REAL else "Transparency notice: Quota is estimated."
        }

class QuotaManager:
    def __init__(self):
        self.providers: Dict[str, ProviderQuotaStatus] = {}

    def register_provider(self, provider_id: str, quota_type: QuotaType, initial_credits: float, total_limit: float):
        self.providers[provider_id] = ProviderQuotaStatus(
            provider_id=provider_id,
            quota_type=quota_type,
            remaining_credits=initial_credits,
            total_limit=total_limit
        )

    def get_status(self, provider_id: str) -> Optional[Dict]:
        status = self.providers.get(provider_id)
        return status.to_dict() if status else None

    def find_available_provider(self, preferred_order: List[str]) -> Optional[str]:
        for p_id in preferred_order:
            status = self.providers.get(p_id)
            if status and status.is_active and status.remaining_credits > 0:
                return p_id
        return None
