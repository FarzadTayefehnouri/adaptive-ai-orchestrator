"""Adaptive AI Orchestrator Core Package (v0.2.0)."""
__version__ = "0.2.0"

import os
import sys
import importlib.util

_cur_dir = os.path.dirname(__file__)
for _pkg in [
    "security", "workflow", "scheduler", "providers", "routing",
    "agents", "memory", "recovery", "dashboard", "core", "api"
]:
    _pkg_dir = os.path.join(_cur_dir, _pkg)
    _init_path = os.path.join(_pkg_dir, "__init__.py")
    if os.path.exists(_init_path) and f"src.orchestrator.{_pkg}" not in sys.modules:
        try:
            _spec = importlib.util.spec_from_file_location(
                f"src.orchestrator.{_pkg}",
                _init_path,
                submodule_search_locations=[_pkg_dir]
            )
            _mod = importlib.util.module_from_spec(_spec)
            sys.modules[f"src.orchestrator.{_pkg}"] = _mod
            _spec.loader.exec_module(_mod)
        except Exception:
            pass

_cli_p = os.path.join(_cur_dir, "cli.py")
if os.path.exists(_cli_p) and "src.orchestrator.cli" not in sys.modules:
    _spec = importlib.util.spec_from_file_location("src.orchestrator.cli", _cli_p)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["src.orchestrator.cli"] = _mod
    _spec.loader.exec_module(_mod)
