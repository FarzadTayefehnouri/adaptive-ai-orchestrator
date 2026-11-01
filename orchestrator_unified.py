#!/usr/bin/env python3
"""
================================================================================
Adaptive AI Orchestrator — Canonical Application Wrapper (Point 1.1)
================================================================================
Per architectural Point 1.1:
- `src/orchestrator/` is the single canonical source of truth.
- `orchestrator_unified.py` acts purely as a thin execution wrapper that delegates
  to `src/orchestrator/api/app.py` and `src/orchestrator/cli.py`, eliminating code
  duplication and ensuring tests run against the exact same codebase the user executes.
================================================================================
"""
import os
import sys
import time
import threading
import webbrowser

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.orchestrator.config import settings
from src.orchestrator.api.app import app

def _open_browser_delayed():
    time.sleep(1.2)
    url = f"http://{settings.host}:{settings.port}"
    print(f"\n[داشبورد مانیتورینگ آماده است]: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=_open_browser_delayed, daemon=True).start()
    print("=" * 68)
    print(f"  Adaptive AI Orchestrator v0.2.0 listening on {settings.host}:{settings.port}")
    print("=" * 68)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
