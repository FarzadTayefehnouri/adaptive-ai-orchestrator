import unittest
import os
from src.orchestrator.memory.sqlite_store import SQLiteStore
from src.orchestrator.memory.cache import ResponseCache

class TestSQLiteAndCache(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_orchestrator.db"
        self.json_file = "test_orchestrator_data.json"
        self._cleanup()
        self.store = SQLiteStore(self.test_db)
        self.cache = ResponseCache(self.store)

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        for f in [self.test_db, getattr(self, "json_file", "test_orchestrator_data.json")]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_cache_miss_and_hit(self):
        prompt = "خلاصه گزارش ماهانه پروژه"
        task_type = "summarization"
        
        # Initial lookup must be a cache miss
        hit = self.cache.lookup(prompt, task_type)
        self.assertIsNone(hit)
        
        # Store response
        sample_output = {"summary": "این یک خلاصه معتبر است", "points": [1, 2, 3]}
        self.cache.store_response(prompt, task_type, sample_output, score=0.98)
        
        # Second lookup must be a cache hit (0 tokens consumed!)
        cached_result = self.cache.lookup(prompt, task_type)
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result["summary"], sample_output["summary"])
        self.assertEqual(len(cached_result["points"]), 3)

    def test_experience_logging(self):
        self.store.record_experience("coding", "groq_llama_8b", success=True, duration_ms=450.0)
        self.store.record_experience("coding", "groq_llama_8b", success=False, escalated=True, duration_ms=800.0)
        
        stats = self.store.get_model_stats()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["model_used"], "groq_llama_8b")
        self.assertEqual(stats[0]["total_runs"], 2)
        self.assertEqual(stats[0]["successful_runs"], 1)
        self.assertEqual(stats[0]["escalations"], 1)

if __name__ == '__main__':
    unittest.main()
