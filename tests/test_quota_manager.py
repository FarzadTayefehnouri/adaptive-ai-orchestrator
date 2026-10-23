import unittest
from src.orchestrator.models import QuotaType
from src.orchestrator.providers.quota_manager import QuotaManager

class TestQuotaManager(unittest.TestCase):
    def test_quota_transparency(self):
        qm = QuotaManager()
        qm.register_provider("groq", QuotaType.REAL, 100, 100)
        qm.register_provider("huggingface", QuotaType.ESTIMATED, 50, 50)
        
        groq_stat = qm.get_status("groq")
        hf_stat = qm.get_status("huggingface")
        
        self.assertTrue(groq_stat["is_real_data"])
        self.assertFalse(hf_stat["is_real_data"])
        self.assertIn("Transparency notice", hf_stat["notice"])

    def test_failover_on_rate_limit(self):
        qm = QuotaManager()
        qm.register_provider("provider_a", QuotaType.REAL, 5, 10)
        qm.register_provider("provider_b", QuotaType.REAL, 20, 20)
        
        best = qm.find_available_provider(["provider_a", "provider_b"])
        self.assertEqual(best, "provider_a")
        
        # Provider A hits 429
        qm.providers["provider_a"].report_rate_limit()
        
        fallback = qm.find_available_provider(["provider_a", "provider_b"])
        self.assertEqual(fallback, "provider_b")

if __name__ == '__main__':
    unittest.main()
