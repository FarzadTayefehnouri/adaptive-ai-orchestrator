"""Test Controlled Adaptive Concurrency Settings (Point 2.1)."""
import unittest
import os
from src.orchestrator.config import Settings

class TestConcurrencySettings(unittest.TestCase):
    def test_controlled_worker_bounds_default(self):
        os.environ.pop("MIN_WORKERS", None)
        os.environ.pop("DEFAULT_WORKERS", None)
        os.environ.pop("MAX_WORKERS", None)
        s = Settings()
        self.assertEqual(s.min_workers, 2)
        self.assertEqual(s.default_workers, 5)
        self.assertEqual(s.max_workers, 12)
        self.assertEqual(s.max_queue_size, 100)
        self.assertEqual(s.max_tasks_per_user, 10)
        self.assertEqual(s.host, "127.0.0.1")

    def test_custom_worker_bounds(self):
        os.environ["MIN_WORKERS"] = "3"
        os.environ["DEFAULT_WORKERS"] = "6"
        os.environ["MAX_WORKERS"] = "16"
        s = Settings()
        self.assertEqual(s.min_workers, 3)
        self.assertEqual(s.default_workers, 6)
        self.assertEqual(s.max_workers, 16)
        os.environ.pop("MIN_WORKERS", None)
        os.environ.pop("DEFAULT_WORKERS", None)
        os.environ.pop("MAX_WORKERS", None)

if __name__ == '__main__':
    unittest.main()
