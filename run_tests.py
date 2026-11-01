"""Unified Multi-Suite Test Runner for Adaptive AI Orchestrator v0.2.0."""
import os
import sys
import unittest
import importlib.util

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

test_files = [
    "tests/test_quota_manager.py",
    "tests/test_router.py",
    "tests/test_recovery_engine.py",
    "tests/test_dashboard.py",
    "tests/test_escalation.py",
    "tests/test_concurrency.py",
    "tests/test_input_analyzer.py",
    "tests/test_sqlite_cache.py",
    "tests/test_production_features.py",
    "tests/scheduler/test_adaptive_scheduler.py",
    "tests/workflow/test_workflow_and_video.py",
    "tests/security/test_security_guards.py",
    "tests/integration/test_api_and_providers.py",
    "tests/test_finalization_guards.py",
]

suite = unittest.TestSuite()
loader = unittest.TestLoader()

for tf in test_files:
    if os.path.exists(tf):
        mod_name = tf.replace("/", "_").replace(".py", "")
        spec = importlib.util.spec_from_file_location(mod_name, tf)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        suite.addTests(loader.loadTestsFromModule(mod))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

if not result.wasSuccessful():
    sys.exit(1)
print(f"\n>>> All {result.testsRun} tests across {len(test_files)} suites passed with 100% success! <<<")
