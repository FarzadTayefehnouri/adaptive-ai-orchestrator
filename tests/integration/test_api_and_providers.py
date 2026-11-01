"""Integration Tests for Providers, Atomic Quota, Format Critic, Versioned Store, and V2 API (Points 9, 10, 14, 15, 17, 18, 19, 20)."""
import unittest
import asyncio
from src.orchestrator.providers.base import ProviderRequest, RateLimitError, AuthenticationError
from src.orchestrator.providers.groq import GroqProvider
from src.orchestrator.providers.gemini import GeminiProvider
from src.orchestrator.routing.quota import AtomicQuotaManager, QuotaSource
from src.orchestrator.routing.fallback import execute_with_retry_and_fallback
from src.orchestrator.agents.classifier import EnhancedInputAnalyzer
from src.orchestrator.agents.critic import FormatValidatorCritic
from src.orchestrator.memory.validated import ArtifactAndVersionStore
from src.orchestrator.api.app import (
    create_task_v2, get_task_status, cancel_task, health_endpoint, readiness_endpoint, V2TaskCreateRequest
)
from src.orchestrator.security.auth import UserRole

class TestIntegrationAndProvidersSuite(unittest.TestCase):
    def test_atomic_quota_reserve_commit_and_release(self):
        async def _run():
            qm = AtomicQuotaManager()
            qm.register_provider("groq", source=QuotaSource.ESTIMATED, remaining_requests=2, remaining_input_tokens=1000)

            res1 = await qm.reserve("groq", estimated_tokens=400)
            self.assertIsNotNone(res1)
            self.assertEqual(qm.ledgers["groq"].available_requests(), 1)

            # Release rolls back reservation
            await qm.release(res1)
            self.assertEqual(qm.ledgers["groq"].available_requests(), 2)

            # Commit deducts actual usage
            res2 = await qm.reserve("groq", estimated_tokens=300)
            await qm.commit(res2, actual_input_tokens=120, actual_output_tokens=80)
            self.assertEqual(qm.ledgers["groq"].remaining_requests, 1)
            self.assertEqual(qm.ledgers["groq"].remaining_input_tokens, 880)

        asyncio.run(_run())

    def test_provider_retry_and_fallback_chain(self):
        async def _run():
            groq = GroqProvider(api_key="test_key")
            gemini = GeminiProvider(api_key="test_key")

            # First provider raises 429, fallback succeeds on second provider
            async def call_failing_groq():
                return await groq.generate(ProviderRequest(prompt="__SIMULATE_429__", model="llama-3.1-8b-instant"))

            async def call_healthy_gemini():
                return await gemini.generate(ProviderRequest(prompt="Hello world", model="gemini-1.5-flash"))

            result = await execute_with_retry_and_fallback([call_failing_groq, call_healthy_gemini], max_retries_per_provider=1)
            self.assertEqual(result["provider"], "gemini")
            self.assertTrue(result["is_real_provider_response"])

        asyncio.run(_run())

    def test_simulation_mode_transparency(self):
        async def _run():
            groq_no_key = GroqProvider(api_key="")
            res = await groq_no_key.generate(ProviderRequest(prompt="Test simulation", model="llama-3.1-8b-instant"))
            self.assertEqual(res["mode"], "simulation")
            self.assertFalse(res["is_real_provider_response"])
            self.assertIsNotNone(res["warning"])

        asyncio.run(_run())

    def test_pdf_evidence_and_format_validator_critic(self):
        analyzer = EnhancedInputAnalyzer()
        scanned_pdf = b"%PDF-1.4\n/Type /Page\n/Subtype /Image\n"
        info = analyzer.analyze("scan.pdf", scanned_pdf)
        self.assertEqual(info["pdf_analysis"]["classification"], "scanned")
        self.assertGreater(info["confidence"], 0.7)

        critic = FormatValidatorCritic()
        valid_py = critic.validate("def add(a, b):\n    return a + b\n", expected_format="py")
        self.assertTrue(valid_py["is_valid"])

        invalid_py = critic.validate("def broken(:", expected_format="py")
        self.assertFalse(invalid_py["is_valid"])

        valid_json = critic.validate('{"status": "ok", "count": 3}', expected_format="json", required_json_keys=["status"])
        self.assertTrue(valid_json["is_valid"])

    def test_versioned_outputs_and_v2_api_idempotency(self):
        async def _run():
            store = ArtifactAndVersionStore()
            v1 = store.append_validated_output("t100", "step_1", {"ans": "draft 1"}, 0.85)
            v2 = store.append_validated_output("t100", "step_1", {"ans": "refined 2"}, 0.96)
            self.assertEqual(v1.version, 1)
            self.assertEqual(v2.version, 2)
            self.assertEqual(v2.supersedes_id, v1.record_id)

            # V2 API idempotency test
            req = V2TaskCreateRequest(prompt="Check idempotency v2", complexity="light", output_format="md")
            first_resp = await create_task_v2(req, role=UserRole.ADMIN)
            second_resp = await create_task_v2(req, role=UserRole.ADMIN)
            self.assertFalse(first_resp["idempotent_replay"])
            self.assertTrue(second_resp["idempotent_replay"])
            self.assertEqual(first_resp["task_id"], second_resp["task_id"])

            h = await health_endpoint()
            self.assertEqual(h["status"], "healthy")
            r = await readiness_endpoint()
            self.assertTrue(r["ready"])

        asyncio.run(_run())
