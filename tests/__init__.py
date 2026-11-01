import os
import sys
import importlib.util

# Ensure all test modules can be imported across any filesystem
_cur_dir = os.path.dirname(__file__)
for _f in os.listdir(_cur_dir) if os.path.exists(_cur_dir) else []:
    if _f.startswith("test_") and _f.endswith(".py"):
        _mod_name = _f[:-3]
        _path = os.path.join(_cur_dir, _f)
        if f"tests.{_mod_name}" not in sys.modules:
            try:
                _spec = importlib.util.spec_from_file_location(f"tests.{_mod_name}", _path)
                _mod = importlib.util.module_from_spec(_spec)
                sys.modules[f"tests.{_mod_name}"] = _mod
                _spec.loader.exec_module(_mod)
            except Exception:
                pass
