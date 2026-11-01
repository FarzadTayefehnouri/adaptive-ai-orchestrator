import os
import unittest

from src.orchestrator.scheduler import AdaptiveScheduler
from src.orchestrator.config import Settings


class TestFinalizationGuards(unittest.TestCase):
    def test_scheduler_public_export(self):
        self.assertTrue(AdaptiveScheduler)

    def test_production_auth_defaults_to_required(self):
        old_environment = os.environ.get("ENVIRONMENT")
        old_require_auth = os.environ.get("REQUIRE_AUTH")
        try:
            os.environ["ENVIRONMENT"] = "production"
            os.environ.pop("REQUIRE_AUTH", None)
            self.assertTrue(Settings().require_auth)
        finally:
            if old_environment is None:
                os.environ.pop("ENVIRONMENT", None)
            else:
                os.environ["ENVIRONMENT"] = old_environment
            if old_require_auth is None:
                os.environ.pop("REQUIRE_AUTH", None)
            else:
                os.environ["REQUIRE_AUTH"] = old_require_auth


if __name__ == "__main__":
    unittest.main()
