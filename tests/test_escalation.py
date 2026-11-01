import unittest
from src.orchestrator.models import TaskComplexity, QuotaType, ExecutionStep, TokenUsage
from src.orchestrator.providers.quota_manager import QuotaManager
from src.orchestrator.providers.router import ModelRouter
from src.orchestrator.agents.critic import CriticAgent

class TestEscalationAndTokens(unittest.TestCase):
    def setUp(self):
        self.qm = QuotaManager()
        self.qm.register_provider("groq_llama_8b", QuotaType.REAL, 100, 100)
        self.qm.register_provider("gemini_flash", QuotaType.REAL, 100, 100)
        self.qm.register_provider("gemini_pro", QuotaType.REAL, 50, 50)
        self.router = ModelRouter(self.qm)
        self.critic = CriticAgent()

    def test_token_estimation_and_tracking(self):
        text = "This is a prompt to test token consumption estimation."
        tokens = self.qm.estimate_tokens(text)
        self.assertGreater(tokens, 0)
        
        usage = TokenUsage(prompt_tokens=15, completion_tokens=45)
        self.assertEqual(usage.total_tokens, 60)
        
        self.qm.record_usage("groq_llama_8b", usage)
        status = self.qm.get_status("groq_llama_8b")
        self.assertEqual(status["total_tokens_consumed"], 60)
        self.assertEqual(status["remaining_credits"], 99)

    def test_automatic_model_escalation_on_incapacity(self):
        """When light model returns inadequate output, critic triggers escalation to higher tier."""
        step = ExecutionStep(
            step_id="step_calc",
            name="Solve Advanced Math",
            assigned_agent="reasoner",
            complexity=TaskComplexity.LIGHT,
            model_used="groq_llama_8b"
        )
        
        # Simulate weak model failing with refusal or truncation
        weak_output = {"text": "Sorry, as an AI I am unable to calculate this complex formula."}
        critique = self.critic.evaluate_output("Solve advanced math", weak_output)
        
        self.assertFalse(critique["is_valid"])
        self.assertTrue(critique["needs_escalation"])
        
        # System escalates task to higher tier
        new_complexity, new_model = self.router.escalate(
            current_complexity=step.complexity,
            current_model=step.model_used,
            reason=critique["reason"]
        )
        
        step.record_escalation(
            from_model=step.model_used,
            to_model=new_model,
            reason=critique["reason"],
            triggered_by="critic_agent"
        )
        
        self.assertEqual(new_complexity, TaskComplexity.MODERATE)
        self.assertEqual(new_model, "gemini_flash")
        self.assertEqual(step.escalation_count, 1)

    def test_manual_user_escalation_to_complex_tier(self):
        """User manually escalates directly from light model to top reasoning tier."""
        step = ExecutionStep(
            step_id="step_code",
            name="Write Orchestrator Module",
            assigned_agent="coder",
            complexity=TaskComplexity.LIGHT,
            model_used="groq_llama_8b"
        )
        
        # User intervenes and forces escalation to COMPLEX tier
        new_complexity, new_model = self.router.escalate(
            current_complexity=TaskComplexity.MODERATE,
            current_model=step.model_used,
            reason="User judged task requires deep reasoning model"
        )
        
        step.record_escalation(
            from_model=step.model_used,
            to_model=new_model,
            reason="User intervention",
            triggered_by="human_user"
        )
        
        self.assertEqual(new_complexity, TaskComplexity.COMPLEX)
        self.assertEqual(new_model, "gemini_pro")
        self.assertEqual(step.model_used, "gemini_pro")
        self.assertEqual(step.escalation_log[0]["triggered_by"], "human_user")

if __name__ == '__main__':
    unittest.main()
