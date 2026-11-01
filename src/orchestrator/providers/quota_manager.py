"""Smart Quota, Token Consumption, and Circuit Breaker Manager (Section 2 & 9 of requirements).
Tracks real vs estimated quotas, estimates token consumption, and isolates failing endpoints via CircuitBreaker.
"""
from typing import Dict, Optional, List
from src.orchestrator.models import QuotaType, TokenUsage
from src.orchestrator.providers.circuit_breaker import CircuitBreaker

class ProviderQuotaStatus:
    def __init__(self, provider_id: str, quota_type: QuotaType, remaining_credits: float, total_limit: float):
        self.provider_id = provider_id
        self.quota_type = quota_type
        self.remaining_credits = remaining_credits
        self.total_limit = total_limit
        self.is_active = True
        self.consecutive_429_errors = 0
        self.total_tokens_consumed = 0
        self.circuit_breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=60.0)

    def consume(self, amount: float = 1.0) -> bool:
        if self.remaining_credits >= amount and self.circuit_breaker.allow_request():
            self.remaining_credits -= amount
            return True
        return False

    def record_tokens(self, tokens: int):
        self.total_tokens_consumed += tokens

    def report_rate_limit(self):
        self.consecutive_429_errors += 1
        self.remaining_credits = 0
        self.is_active = False

    def report_network_failure(self, error_msg: str = "503 Service Unavailable / Timeout"):
        self.circuit_breaker.record_failure(error_msg)

    def report_network_success(self):
        self.circuit_breaker.record_success()

    def reset_status(self, credits: float):
        self.remaining_credits = credits
        self.consecutive_429_errors = 0
        self.is_active = True
        self.circuit_breaker.record_success()

    def to_dict(self) -> Dict:
        return {
            "provider_id": self.provider_id,
            "quota_type": self.quota_type.value,
            "is_real_data": self.quota_type == QuotaType.REAL,
            "remaining_credits": self.remaining_credits,
            "total_limit": self.total_limit,
            "total_tokens_consumed": self.total_tokens_consumed,
            "is_active": self.is_active and self.circuit_breaker.allow_request(),
            "circuit_breaker": self.circuit_breaker.to_dict(),
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

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, int(len(text) / 3.2))

    def record_usage(self, provider_id: str, token_usage: TokenUsage):
        status = self.providers.get(provider_id)
        if status:
            status.consume(1.0)
            status.record_tokens(token_usage.get("total_tokens", 0))
            status.report_network_success()

    def get_status(self, provider_id: str) -> Optional[Dict]:
        status = self.providers.get(provider_id)
        return status.to_dict() if status else None

    def find_available_provider(self, preferred_order: List[str]) -> Optional[str]:
        for p_id in preferred_order:
            status = self.providers.get(p_id)
            if status and status.is_active and status.remaining_credits > 0 and status.circuit_breaker.allow_request():
                return p_id
        return None
