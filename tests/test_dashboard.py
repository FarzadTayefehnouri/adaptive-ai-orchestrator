import unittest
import asyncio
from src.orchestrator.dashboard.events import EventBus, TelemetryEvent
from src.orchestrator.dashboard.controller import ExecutionController

class TestDashboardSupervision(unittest.TestCase):
    def test_event_history_replay(self):
        """Verify full history can be replayed from the very first step upon client connection."""
        bus = EventBus()
        bus.emit(TelemetryEvent(event_type="step_started", step_id="s1", message="Started step 1"))
        bus.emit(TelemetryEvent(event_type="step_completed", step_id="s1", message="Finished step 1"))
        
        history = bus.get_full_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["step_id"], "s1")
        self.assertEqual(history[0]["event_type"], "step_started")
        self.assertEqual(history[1]["event_type"], "step_completed")

    def test_user_pause_and_resume(self):
        """Verify user pause and resume intervention toggles controller state."""
        ctrl = ExecutionController()
        self.assertFalse(ctrl.is_paused)
        
        ctrl.pause("User clicked pause")
        self.assertTrue(ctrl.is_paused)
        
        ctrl.resume("User resumed")
        self.assertFalse(ctrl.is_paused)

    def test_model_override_intervention(self):
        """Verify user can force a specific model on a step."""
        ctrl = ExecutionController()
        ctrl.set_model_override("step_3", "gemini_pro")
        self.assertEqual(ctrl.model_overrides.get("step_3"), "gemini_pro")

if __name__ == '__main__':
    unittest.main()
