"""Dynamic module registration for api."""
import os
import sys
import importlib.util

_cur_dir = os.path.dirname(__file__)
for _m in ['app', 'auth', 'routes_tasks', 'routes_settings', 'routes_history']:
    _p = os.path.join(_cur_dir, f"{_m}.py")
    _full = f"src.orchestrator.api.{_m}"
    if os.path.exists(_p) and _full not in sys.modules:
        try:
            _spec = importlib.util.spec_from_file_location(_full, _p)
            _mod = importlib.util.module_from_spec(_spec)
            sys.modules[_full] = _mod
            _spec.loader.exec_module(_mod)
        except Exception:
            pass
