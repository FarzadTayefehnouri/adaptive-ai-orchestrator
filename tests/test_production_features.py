import unittest
import asyncio
from src.orchestrator.providers.circuit_breaker import CircuitBreaker, CircuitState
from src.orchestrator.providers.adapters import ProviderAdapter
from src.orchestrator.dashboard.server import (
    submit_task, export_audit_markdown, export_audit_json,
    download_task_deliverable, list_deliverables, TaskSubmitRequest
)

class TestProductionFeatures(unittest.TestCase):
    def test_circuit_breaker_transitions(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.allow_request())

        cb.record_failure("503 Service Unavailable")
        cb.record_failure("Connection Timeout")
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertFalse(cb.allow_request())

        import time
        time.sleep(0.15)
        self.assertTrue(cb.allow_request())
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_provider_adapter_simulation_fallback(self):
        adapter = ProviderAdapter()
        res = adapter.generate("groq_llama_8b", "سلام، وضعیت سامانه را بررسی کن")
        self.assertIn("text", res)
        self.assertEqual(res["model_used"], "groq_llama_8b")
        self.assertGreater(res["token_usage"]["total_tokens"], 0)

    def test_end_to_end_task_submission_notification_and_file_download(self):
        req = TaskSubmitRequest(
            prompt="تولید ماژول پایتون برای تحلیل داده",
            complexity="auto",
            output_format="py",
            filename="sample.py",
            file_base64="ZGVmIGhlbGxvKCk6CiAgICByZXR1cm4gTrue"
        )
        res = asyncio.run(submit_task(req))
        self.assertEqual(res["status"], "completed")
        task_id = res["task_id"]

        # Verify deliverable is listed in Download Center
        deliv_list = asyncio.run(list_deliverables())
        self.assertTrue(any(d["task_id"] == task_id for d in deliv_list["deliverables"]))

        # Verify direct file download of finalized AI output (.py and .md)
        dl_resp = asyncio.run(download_task_deliverable(task_id, fmt="py"))
        dl_content = dl_resp.body.decode("utf-8")
        self.assertIn(task_id, dl_content)
        self.assertIn("attachment; filename=", dl_resp.headers["content-disposition"])

        # Verify Markdown & JSON Audit Exports
        md_resp = asyncio.run(export_audit_markdown())
        md_text = md_resp.body.decode("utf-8")
        self.assertIn("Orchestrator Audit Report", md_text)

        json_resp = asyncio.run(export_audit_json())
        self.assertEqual(json_resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
