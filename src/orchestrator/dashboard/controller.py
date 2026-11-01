"""Human-in-the-Loop Execution Controller.
Empowers the user to supervise, pause, resume, re-run, or manually override models on the fly.
"""
import asyncio
from typing import Dict, Optional, Set
from src.orchestrator.dashboard.events import global_event_bus, TelemetryEvent

class ExecutionController:
    def __init__(self):
        self.is_paused: bool = False
        self.is_aborted: bool = False
        self.model_overrides: Dict[str, str] = {}  # step_id -> manual model name
        self.requested_step_reruns: Set[str] = set()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Unpaused initially

    def pause(self, reason: str = "User requested execution pause"):
        """Pause execution at the current checkpoint."""
        self.is_paused = True
        self._pause_event.clear()
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            message=f"⏸️ Execution PAUSED: {reason}",
            data={"action": "pause", "is_paused": True}
        ))

    def resume(self, reason: str = "User resumed execution"):
        """Resume paused background execution."""
        self.is_paused = False
        self._pause_event.set()
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            message=f"▶️ Execution RESUMED: {reason}",
            data={"action": "resume", "is_paused": False}
        ))

    def abort(self, reason: str = "User terminated execution"):
        self.is_aborted = True
        self.resume("Unblocking loop for termination")
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            message=f"🛑 Execution ABORTED: {reason}",
            data={"action": "abort", "is_aborted": True}
        ))

    def set_model_override(self, step_id: str, model_name: str):
        """Manually force a specific model for a given execution step."""
        self.model_overrides[step_id] = model_name
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            step_id=step_id,
            model_name=model_name,
            message=f"🔀 Manual Model Override: Step '{step_id}' assigned to '{model_name}'",
            data={"action": "override_model", "target_step": step_id, "forced_model": model_name}
        ))

    def request_step_rerun(self, step_id: str):
        """Mark a step for immediate re-computation."""
        self.requested_step_reruns.add(step_id)
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            step_id=step_id,
            message=f"🔄 Step Rerun Requested for '{step_id}'",
            data={"action": "rerun_step", "target_step": step_id}
        ))

    async def wait_if_paused(self):
        """Orchestrator worker calls this prior to running any step. If paused, awaits user resume."""
        if self.is_aborted:
            raise RuntimeError("Task execution aborted by user intervention.")
        await self._pause_event.wait()

global_controller = ExecutionController()
