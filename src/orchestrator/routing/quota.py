"""Multi-Dimensional Quota Manager with Atomic Reservation (Points 10.1, 10.2, 10.3)."""
import asyncio
import uuid
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional

class QuotaSource(str, Enum):
    OFFICIAL_API = "official_api"
    RESPONSE_HEADER = "response_header"
    USER_CONFIGURED = "user_configured"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"

@dataclass
class ProviderQuotaLedger:
    provider_id: str
    source: QuotaSource = QuotaSource.ESTIMATED
    remaining_requests: int = 100
    remaining_input_tokens: int = 100000
    remaining_output_tokens: int = 50000
    remaining_budget_usd: float = 10.0
    rpm_limit: int = 30
    rpd_limit: int = 1000
    reserved_requests: int = 0
    reserved_tokens: int = 0
    is_active: bool = True

    def available_requests(self) -> int:
        return max(0, self.remaining_requests - self.reserved_requests)

    def available_tokens(self) -> int:
        return max(0, (self.remaining_input_tokens + self.remaining_output_tokens) - self.reserved_tokens)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "quota_source": self.source.value,
            "remaining_requests": self.remaining_requests,
            "reserved_requests": self.reserved_requests,
            "remaining_input_tokens": self.remaining_input_tokens,
            "remaining_output_tokens": self.remaining_output_tokens,
            "remaining_budget_usd": round(self.remaining_budget_usd, 4),
            "rpm_limit": self.rpm_limit,
            "rpd_limit": self.rpd_limit,
            "is_active": self.is_active
        }

@dataclass
class QuotaReservation:
    reservation_id: str
    provider_id: str
    reserved_requests: int
    reserved_tokens: int
    estimated_cost_usd: float
    committed: bool = False
    released: bool = False

class AtomicQuotaManager:
    def __init__(self):
        self.ledgers: Dict[str, ProviderQuotaLedger] = {}
        self.reservations: Dict[str, QuotaReservation] = {}
        self.quota_lock = asyncio.Lock()

    def register_provider(
        self,
        provider_id: str,
        source: QuotaSource = QuotaSource.ESTIMATED,
        remaining_requests: int = 100,
        remaining_input_tokens: int = 100000,
        remaining_output_tokens: int = 50000,
        remaining_budget_usd: float = 10.0
    ):
        self.ledgers[provider_id] = ProviderQuotaLedger(
            provider_id=provider_id,
            source=source,
            remaining_requests=remaining_requests,
            remaining_input_tokens=remaining_input_tokens,
            remaining_output_tokens=remaining_output_tokens,
            remaining_budget_usd=remaining_budget_usd
        )

    async def reserve(self, provider_id: str, estimated_tokens: int = 500, estimated_cost_usd: float = 0.0) -> Optional[QuotaReservation]:
        """Point 10.3: Atomically reserve quota prior to execution."""
        async with self.quota_lock:
            ledger = self.ledgers.get(provider_id)
            if not ledger or not ledger.is_active:
                return None
            if ledger.available_requests() < 1 or ledger.available_tokens() < estimated_tokens:
                return None
            if ledger.remaining_budget_usd < estimated_cost_usd:
                return None

            ledger.reserved_requests += 1
            ledger.reserved_tokens += estimated_tokens
            res = QuotaReservation(
                reservation_id=f"res_{uuid.uuid4().hex[:10]}",
                provider_id=provider_id,
                reserved_requests=1,
                reserved_tokens=estimated_tokens,
                estimated_cost_usd=estimated_cost_usd
            )
            self.reservations[res.reservation_id] = res
            return res

    async def commit(self, reservation: QuotaReservation, actual_input_tokens: int, actual_output_tokens: int, actual_cost_usd: float = 0.0):
        """Point 10.3: Commit actual usage and clear reservation."""
        async with self.quota_lock:
            if reservation.committed or reservation.released:
                return
            ledger = self.ledgers.get(reservation.provider_id)
            if ledger:
                ledger.reserved_requests = max(0, ledger.reserved_requests - reservation.reserved_requests)
                ledger.reserved_tokens = max(0, ledger.reserved_tokens - reservation.reserved_tokens)
                ledger.remaining_requests = max(0, ledger.remaining_requests - 1)
                ledger.remaining_input_tokens = max(0, ledger.remaining_input_tokens - actual_input_tokens)
                ledger.remaining_output_tokens = max(0, ledger.remaining_output_tokens - actual_output_tokens)
                ledger.remaining_budget_usd = max(0.0, ledger.remaining_budget_usd - actual_cost_usd)
            reservation.committed = True

    async def release(self, reservation: QuotaReservation):
        """Point 10.3: Roll back reservation on provider error so quota is not leaked."""
        async with self.quota_lock:
            if reservation.committed or reservation.released:
                return
            ledger = self.ledgers.get(reservation.provider_id)
            if ledger:
                ledger.reserved_requests = max(0, ledger.reserved_requests - reservation.reserved_requests)
                ledger.reserved_tokens = max(0, ledger.reserved_tokens - reservation.reserved_tokens)
            reservation.released = True
