import unittest
from src.orchestrator.models import ExecutionStep
from src.orchestrator.recovery.engine import RecoveryEngine

class TestRecoveryEngine(unittest.TestCase):
    def test_backward_and_forward_recovery(self):
        engine = RecoveryEngine()
        
        # Build DAG: step_1 -> step_2 -> step_3
        #                   \-> step_2b (parallel)
        s1 = ExecutionStep(step_id="step_1", name="Analyze Input", assigned_agent="analyzer", output_payload={"text": "raw"})
        s2 = ExecutionStep(step_id="step_2", name="Transform Text", assigned_agent="worker", dependencies=["step_1"], output_payload=None, status="failed")
        s2b = ExecutionStep(step_id="step_2b", name="Metadata Extraction", assigned_agent="metadata", dependencies=["step_1"], output_payload={"meta": "ok"})
        s3 = ExecutionStep(step_id="step_3", name="Final Synthesis", assigned_agent="critic", dependencies=["step_2", "step_2b"])
        
        engine.add_step(s1)
        engine.add_step(s2)
        engine.add_step(s2b)
        engine.add_step(s3)
        
        # Step 3 fails because Step 2 was faulty
        err = engine.backward_recovery("step_3", "Missing synthesis inputs")
        self.assertEqual(err.root_cause_step_id, "step_2")
        self.assertIn("step_3", err.impacted_downstream_steps)
        
        # Forward recovery plan: should ONLY re-run step_2 and step_3, NOT step_1 or step_2b
        replan = engine.forward_recovery_plan("step_2")
        self.assertEqual(replan, ["step_2", "step_3"])
        self.assertNotIn("step_2b", replan)
        self.assertNotIn("step_1", replan)

if __name__ == '__main__':
    unittest.main()
