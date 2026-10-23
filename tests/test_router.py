import unittest
from src.orchestrator.models import TaskComplexity, QuotaType
from src.orchestrator.providers.quota_manager import QuotaManager
from src.orchestrator.providers.router import ModelRouter

class TestModelRouter(unittest.TestCase):
    def test_router_complexity_tiering(self):
        qm = QuotaManager()
        qm.register_provider("groq_llama_8b", QuotaType.REAL, 100, 100)
        qm.register_provider("gemini_pro", QuotaType.REAL, 50, 50)
        
        router = ModelRouter(qm)
        
        self.assertEqual(router.route(TaskComplexity.LIGHT), "groq_llama_8b")
        self.assertEqual(router.route(TaskComplexity.COMPLEX), "gemini_pro")

if __name__ == '__main__':
    unittest.main()
