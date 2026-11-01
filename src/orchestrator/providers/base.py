"""Standardized Provider Interface, Exceptions, and Model Catalog (Points 9 & 18)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from src.orchestrator.config import settings

class ProviderError(Exception):
    def __init__(self, message: str, retryable: bool = False, retry_after_sec: Optional[float] = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_sec = retry_after_sec

class AuthenticationError(ProviderError):
    def __init__(self, message: str = "Authentication failed (HTTP 401/403)"):
        super().__init__(message, retryable=False)

class RateLimitError(ProviderError):
    def __init__(self, message: str = "Rate limit exceeded (HTTP 429)", retry_after_sec: float = 5.0):
        super().__init__(message, retryable=True, retry_after_sec=retry_after_sec)

class QuotaExceededError(ProviderError):
    def __init__(self, message: str = "Provider quota exhausted"):
        super().__init__(message, retryable=False)

class TimeoutError(ProviderError):
    def __init__(self, message: str = "Provider request timed out"):
        super().__init__(message, retryable=True, retry_after_sec=2.0)

class InvalidResponseError(ProviderError):
    def __init__(self, message: str = "Malformed or invalid provider response"):
        super().__init__(message, retryable=True, retry_after_sec=1.0)

@dataclass
class ModelSpec:
    """Point 9.2: Strictly separates provider from model name, tier, and capabilities."""
    provider: str
    model: str
    tier: str
    capabilities: List[str] = field(default_factory=lambda: ["text", "json"])
    max_context_tokens: int = 32000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "tier": self.tier,
            "capabilities": list(self.capabilities),
            "max_context_tokens": self.max_context_tokens
        }

@dataclass
class ProviderRequest:
    prompt: str
    model: str
    system_prompt: str = "You are a helpful AI execution worker."
    max_tokens: int = 1024
    temperature: float = 0.2
    expected_format: str = "text"

class Provider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def generate(self, request: ProviderRequest) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_quota(self) -> Dict[str, Any]:
        pass

    def _build_simulation_response(self, request: ProviderRequest) -> Dict[str, Any]:
        """Point 18: Transparent simulation output with explicit warning; raises error if disallowed in production."""
        if not settings.allow_simulation_fallback:
            raise AuthenticationError(
                f"Provider '{self.provider_name}' API key is not configured and simulation mode is disabled in production."
            )
        prompt_tokens = max(1, len(request.prompt) // 4)
        sim_text = f"[SIMULATION:{self.provider_name}/{request.model}] Processed: {request.prompt[:80]}"
        comp_tokens = max(1, len(sim_text) // 4)
        return {
            "provider": self.provider_name,
            "model": request.model,
            "text": sim_text,
            "mode": "simulation",
            "is_real_provider_response": False,
            "warning": "This response was generated locally in simulation mode because no live API key was configured.",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": comp_tokens,
            "total_tokens": prompt_tokens + comp_tokens
        }
