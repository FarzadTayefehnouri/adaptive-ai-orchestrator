"""Retry, Exponential Backoff with Jitter, and Provider Failover (Point 10.4)."""
import asyncio
import random
from typing import Callable, Any, List
from src.orchestrator.providers.base import ProviderError

async def execute_with_retry_and_fallback(
    provider_callables: List[Callable[[], Any]],
    max_retries_per_provider: int = 2,
    base_delay_sec: float = 0.02
) -> Any:
    last_error = None
    for call_fn in provider_callables:
        for attempt in range(max_retries_per_provider + 1):
            try:
                return await call_fn()
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt == max_retries_per_provider:
                    # Non-retryable (e.g. AuthenticationError 401 or QuotaExceeded) -> break to next provider immediately
                    break
                delay = exc.retry_after_sec if exc.retry_after_sec is not None else (base_delay_sec * (2 ** attempt))
                jitter = random.uniform(0.0, delay * 0.25)
                await asyncio.sleep(min(0.1, delay + jitter))
            except Exception as exc:
                last_error = exc
                break
    raise last_error or RuntimeError("All providers in fallback chain failed.")
