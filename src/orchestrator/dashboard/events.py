"""Bounded Live Telemetry Event Bus and Historical Replay Engine (Point 20.3 & 29).
Caps in-memory events at MAX_IN_MEMORY_EVENTS (default 5000) to prevent unbounded RAM growth.
"""
from collections import deque
from typing import Dict, Any, List, Callable, Optional, Deque
from datetime import datetime, timezone
import asyncio
from src.orchestrator.config import settings
from src.orchestrator.security.redaction import redact_text, redact_dict

class TelemetryEvent:
    def __init__(
        self,
        event_type: str,
        step_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        model_name: Optional[str] = None,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        timestamp_utc: Optional[str] = None,
        task_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        provider: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        self.event_type = event_type
        self.task_id = task_id
        self.step_id = step_id
        self.worker_id = worker_id
        self.agent_name = agent_name
        self.provider = provider
        self.model_name = model_name
        self.message = redact_text(message)
        self.data = redact_dict(data or {})
        self.duration_ms = duration_ms
        self.timestamp_utc = timestamp_utc or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "worker_id": self.worker_id,
            "agent_name": self.agent_name,
            "provider": self.provider,
            "model_name": self.model_name,
            "message": self.message,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "timestamp_utc": self.timestamp_utc
        }

class EventBus:
    def __init__(self, max_events: Optional[int] = None):
        limit = max_events or settings.max_in_memory_events
        self.history: Deque[TelemetryEvent] = deque(maxlen=limit)
        self._listeners: List[Callable[[TelemetryEvent], Any]] = []

    def emit(self, event: TelemetryEvent):
        self.history.append(event)
        for listener in list(self._listeners):
            try:
                if asyncio.iscoroutinefunction(listener):
                    asyncio.create_task(listener(event))
                else:
                    listener(event)
            except Exception:
                pass

    def subscribe(self, listener: Callable[[TelemetryEvent], Any]):
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[TelemetryEvent], Any]):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def get_full_history(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        items = list(self.history)
        sliced = items[offset: offset + limit] if limit else items
        return [evt.to_dict() for evt in sliced]

    def clear(self):
        self.history.clear()

global_event_bus = EventBus()
