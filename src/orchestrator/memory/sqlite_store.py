"""Portable Storage for Orchestrator State.
Dual Engine:
1. SQLite (Default on Windows, Mac, Linux filesystems)
2. Robust JSON fallback (if running inside container/VM filesystem with locking restrictions)
"""
import sqlite3
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

class SQLiteStore:
    def __init__(self, db_path: str = "orchestrator.db"):
        self.db_path = db_path
        self.use_json_fallback = False
        self.json_data_path = db_path.replace(".db", "") + "_data.json"
        self._json_store: Dict[str, Any] = {
            "tasks": {},
            "steps": {},
            "response_cache": {},
            "experience_logs": []
        }
        self._init_store()

    def _init_store(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS response_cache (
                    cache_key TEXT PRIMARY KEY,
                    task_type TEXT,
                    prompt_hash TEXT,
                    output_payload TEXT,
                    validation_score REAL,
                    created_at_utc TEXT,
                    hit_count INTEGER DEFAULT 1
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS experience_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT,
                    model_used TEXT,
                    success INTEGER,
                    escalated INTEGER,
                    duration_ms REAL,
                    timestamp_utc TEXT
                )
                """)
            conn.close()
            self.use_json_fallback = False
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            # Gracefully switch to JSON fallback for environments that disallow SQLite locking (e.g. 9p VM mount)
            self.use_json_fallback = True
            if os.path.exists(self.json_data_path):
                try:
                    with open(self.json_data_path, "r", encoding="utf-8") as f:
                        self._json_store = json.load(f)
                except Exception:
                    pass

    def _save_json(self):
        try:
            with open(self.json_data_path, "w", encoding="utf-8") as f:
                json.dump(self._json_store, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_cache_entry(self, cache_key: str, task_type: str, prompt_hash: str, output: Dict[str, Any], score: float = 1.0):
        if self.use_json_fallback:
            existing = self._json_store["response_cache"].get(cache_key, {})
            hit_count = existing.get("hit_count", 0) + 1
            self._json_store["response_cache"][cache_key] = {
                "task_type": task_type,
                "prompt_hash": prompt_hash,
                "output_payload": output,
                "validation_score": score,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "hit_count": hit_count
            }
            self._save_json()
            return

        conn = sqlite3.connect(self.db_path)
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO response_cache (cache_key, task_type, prompt_hash, output_payload, validation_score, created_at_utc, hit_count)
            VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT hit_count + 1 FROM response_cache WHERE cache_key = ?), 1))
            """, (
                cache_key,
                task_type,
                prompt_hash,
                json.dumps(output, ensure_ascii=False),
                score,
                datetime.now(timezone.utc).isoformat(),
                cache_key
            ))

    def get_cache_entry(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if self.use_json_fallback:
            entry = self._json_store["response_cache"].get(cache_key)
            if entry:
                entry["hit_count"] = entry.get("hit_count", 1) + 1
                self._save_json()
                return entry["output_payload"]
            return None

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT output_payload FROM response_cache WHERE cache_key = ?", (cache_key,))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE response_cache SET hit_count = hit_count + 1 WHERE cache_key = ?", (cache_key,))
                return json.loads(row["output_payload"])
        return None

    def record_experience(self, task_type: str, model_used: str, success: bool, escalated: bool = False, duration_ms: float = 0.0):
        if self.use_json_fallback:
            self._json_store["experience_logs"].append({
                "task_type": task_type,
                "model_used": model_used,
                "success": 1 if success else 0,
                "escalated": 1 if escalated else 0,
                "duration_ms": duration_ms,
                "timestamp_utc": datetime.now(timezone.utc).isoformat()
            })
            self._save_json()
            return

        conn = sqlite3.connect(self.db_path)
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO experience_logs (task_type, model_used, success, escalated, duration_ms, timestamp_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                task_type,
                model_used,
                1 if success else 0,
                1 if escalated else 0,
                duration_ms,
                datetime.now(timezone.utc).isoformat()
            ))

    def get_model_stats(self) -> List[Dict[str, Any]]:
        if self.use_json_fallback:
            stats_map: Dict[str, Dict[str, Any]] = {}
            for log in self._json_store["experience_logs"]:
                m = log["model_used"]
                if m not in stats_map:
                    stats_map[m] = {"model_used": m, "total_runs": 0, "successful_runs": 0, "escalations": 0, "total_latency": 0.0}
                stats_map[m]["total_runs"] += 1
                stats_map[m]["successful_runs"] += log["success"]
                stats_map[m]["escalations"] += log["escalated"]
                stats_map[m]["total_latency"] += log["duration_ms"]

            result = []
            for m, s in stats_map.items():
                result.append({
                    "model_used": m,
                    "total_runs": s["total_runs"],
                    "successful_runs": s["successful_runs"],
                    "escalations": s["escalations"],
                    "avg_latency": s["total_latency"] / max(1, s["total_runs"])
                })
            return result

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT model_used, 
                   COUNT(*) as total_runs, 
                   SUM(success) as successful_runs,
                   SUM(escalated) as escalations,
                   AVG(duration_ms) as avg_latency
            FROM experience_logs
            GROUP BY model_used
            """)
            return [dict(row) for row in cursor.fetchall()]
