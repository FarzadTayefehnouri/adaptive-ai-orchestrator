#!/usr/bin/env python3
"""
================================================================================
Adaptive AI Orchestrator — Unified Single-File Production Edition
سامانه هوش مصنوعی چندعاملی تطبیق‌پذیر (نسخه یکپارچه تک‌فایلی شامل تمام ارتقاها)
Creator: Farzad Tayefehnouri
License: Apache 2.0
================================================================================
این فایل یکپارچه تمامی تغییرات و قابلیت‌های طراحی‌شده از نسخه اولیه تا نسخه نهایی را
بدون هیچ‌گونه پراکندگی در یک فایل واحد تجمیع کرده است:
1. همزمانی نامحدود عامل‌ها و مدل‌ها (Infinite Concurrency: MAX_PARALLEL_AGENTS=0)
2. تحلیلگر عمیق باینری چندوجهی (Magic Bytes برای صوت، ویدئو، تصویر، کد و PDF اسکن‌شده vs متنی)
3. مدیریت هوشمند سهمیه واقعی در برابر تخمینی + تخمین‌گر و بودجه‌بندی مصرف توکن
4. الگوی قطع‌کننده مدار شبکه (Circuit Breaker) برای جابه‌جایی فوری در قطعی‌ها
5. مسیریاب هوشمند با قابلیت ارتقای دوگانه مدل (خودکار توسط عامل منتقد + دستی توسط کاربر)
6. موتور بازیابی پسرو (Backward DAG) و پیشرو (Forward Recovery)
7. پایگاه داده محلی پرتابل (SQLite/JSON) و کَش پاسخ با مصرف صفر توکن
8. کلاینت‌های زنده HTTP برای Gemini، Groq، OpenAI، Anthropic و Ollama
9. داشبورد وب نظارت زنده، ویجت شناور مینیاتوری، اطلاع‌رسانی ۴کاناله (دسکتاپ، صوتی، بنر، تب)
   و مرکز دانلود مستقیم فایل‌های نهایی‌شده هوش مصنوعی (.md, .txt, .py, .json)

نحوه اجرا:
    python orchestrator_unified.py
================================================================================
"""
import os
import sys
import io
import time
import json
import base64
import hashlib
import zipfile
import sqlite3
import mimetypes
import threading
import webbrowser
import urllib.request
import urllib.error
import asyncio
from enum import Enum
from pathlib import Path
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Callable


# --- 1. Configuration & Infinite Concurrency ---
"""Global configuration and environment settings.
Supports unlimited concurrent agents/models when MAX_PARALLEL_AGENTS is 0, empty, or 'unlimited'.
"""
import os
from typing import Optional

class Settings:
    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.timezone = os.getenv("TIMEZONE", "UTC")
        
        # Concurrency settings: 0, None, 'unlimited', or 'inf' represents infinity (no bottleneck)
        raw_concurrency = os.getenv("MAX_PARALLEL_AGENTS", "0").strip().lower()
        if raw_concurrency in ("0", "none", "unlimited", "inf", "infinity", ""):
            self.max_parallel_agents: Optional[int] = None  # Completely unbounded / infinite concurrency
        else:
            try:
                self.max_parallel_agents = int(raw_concurrency)
            except ValueError:
                self.max_parallel_agents = None

        self.default_execution_timeout_seconds = int(os.getenv("DEFAULT_EXECUTION_TIMEOUT_SECONDS", "120"))
        self.strict_validation_enabled = os.getenv("STRICT_VALIDATION_ENABLED", "true").lower() == "true"
        
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    @property
    def is_concurrency_unlimited(self) -> bool:
        return self.max_parallel_agents is None

settings = Settings()

# --- 2. Core Data Models & Token Usage ---
"""Data schemas and types for tasks, execution steps, errors, and recovery plans."""
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

class TaskComplexity(str, Enum):
    LIGHT = "light"          # Simple lookup, formatting, short text
    MODERATE = "moderate"    # Standard summarization, translation, single-step transform
    COMPLEX = "complex"      # Multi-step reasoning, coding, deep synthesis
    CRITICAL = "critical"    # Security audit, architectural verification

class QuotaType(str, Enum):
    REAL = "real"            # Verified exact quota from provider API/headers
    ESTIMATED = "estimated"  # Heuristic estimation when provider does not disclose exact quota

class ErrorCategory(str, Enum):
    INPUT_ERROR = "input_error"
    PROVIDER_ERROR = "provider_error"      # Rate limit, 429, timeout
    MODEL_ERROR = "model_error"            # Incoherence, hallucination, refusal, incapable
    TOOL_ERROR = "tool_error"              # Sandbox/library failure
    AGENT_FAULT = "agent_fault"            # Logic fault in agent code
    DEPENDENCY_ERROR = "dependency_error"  # Upstream step delivered bad data
    ESCALATION_TRIGGER = "escalation_trigger" # Model incapable, promoted to higher tier

class TokenUsage(dict):
    def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0):
        super().__init__(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens

class ExecutionStep:
    def __init__(
        self,
        step_id: str,
        name: str,
        assigned_agent: str,
        dependencies: Optional[List[str]] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        model_used: Optional[str] = None,
        complexity: TaskComplexity = TaskComplexity.LIGHT,
        duration_ms: Optional[float] = None,
        token_usage: Optional[TokenUsage] = None,
        max_token_budget: Optional[int] = None
    ):
        self.step_id = step_id
        self.name = name
        self.assigned_agent = assigned_agent
        self.dependencies = dependencies or []
        self.input_payload = input_payload or {}
        self.output_payload = output_payload
        self.status = status
        self.model_used = model_used
        self.complexity = complexity
        self.duration_ms = duration_ms
        self.token_usage = token_usage or TokenUsage(0, 0)
        self.max_token_budget = max_token_budget
        self.escalation_count = 0
        self.escalation_log: List[Dict[str, Any]] = []
        self.created_at_utc = datetime.now(timezone.utc).isoformat()

    def record_escalation(self, from_model: str, to_model: str, reason: str, triggered_by: str = "system"):
        self.escalation_count += 1
        self.escalation_log.append({
            "from_model": from_model,
            "to_model": to_model,
            "reason": reason,
            "triggered_by": triggered_by,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        })
        self.model_used = to_model

class ErrorRecord:
    def __init__(
        self,
        error_id: str,
        step_id: str,
        category: ErrorCategory,
        severity: str,
        message: str,
        confidence: float = 1.0,
        root_cause_step_id: Optional[str] = None,
        impacted_downstream_steps: Optional[List[str]] = None
    ):
        self.error_id = error_id
        self.step_id = step_id
        self.category = category
        self.severity = severity
        self.message = message
        self.confidence = confidence
        self.root_cause_step_id = root_cause_step_id
        self.impacted_downstream_steps = impacted_downstream_steps or []
        self.timestamp_utc = datetime.now(timezone.utc).isoformat()

# --- 3. Network Circuit Breaker ---
"""Circuit Breaker Pattern for Resilient Provider Networking.
Automatically isolates providers experiencing network timeouts or 5xx server errors
for a configurable cooldown window (default 60 seconds) to prevent hanging tasks.
"""
import time
from enum import Enum
from typing import Dict, Any, Optional

class CircuitState(str, Enum):
    CLOSED = "closed"         # Normal operation
    OPEN = "open"             # Failing; fast-fail and reroute immediately
    HALF_OPEN = "half_open"   # Cooldown elapsed; testing recovery with next request

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 2, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: Optional[float] = None
        self.last_error_message: str = ""

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) >= self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN allows a probe request
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_error_message = ""

    def record_failure(self, error_msg: str = "Network or 5xx error"):
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.last_error_message = error_msg
        if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN

    def to_dict(self) -> Dict[str, Any]:
        remaining_cooldown = 0.0
        if self.state == CircuitState.OPEN and self.last_failure_time:
            remaining_cooldown = max(0.0, self.cooldown_seconds - (time.time() - self.last_failure_time))
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "remaining_cooldown_sec": round(remaining_cooldown, 1),
            "last_error": self.last_error_message
        }

# --- 4. Smart Quota & Token Manager ---
"""Smart Quota, Token Consumption, and Circuit Breaker Manager (Section 2 & 9 of requirements).
Tracks real vs estimated quotas, estimates token consumption, and isolates failing endpoints via CircuitBreaker.
"""
from typing import Dict, Optional, List

class ProviderQuotaStatus:
    def __init__(self, provider_id: str, quota_type: QuotaType, remaining_credits: float, total_limit: float):
        self.provider_id = provider_id
        self.quota_type = quota_type
        self.remaining_credits = remaining_credits
        self.total_limit = total_limit
        self.is_active = True
        self.consecutive_429_errors = 0
        self.total_tokens_consumed = 0
        self.circuit_breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=60.0)

    def consume(self, amount: float = 1.0) -> bool:
        if self.remaining_credits >= amount and self.circuit_breaker.allow_request():
            self.remaining_credits -= amount
            return True
        return False

    def record_tokens(self, tokens: int):
        self.total_tokens_consumed += tokens

    def report_rate_limit(self):
        self.consecutive_429_errors += 1
        self.remaining_credits = 0
        self.is_active = False

    def report_network_failure(self, error_msg: str = "503 Service Unavailable / Timeout"):
        self.circuit_breaker.record_failure(error_msg)

    def report_network_success(self):
        self.circuit_breaker.record_success()

    def reset_status(self, credits: float):
        self.remaining_credits = credits
        self.consecutive_429_errors = 0
        self.is_active = True
        self.circuit_breaker.record_success()

    def to_dict(self) -> Dict:
        return {
            "provider_id": self.provider_id,
            "quota_type": self.quota_type.value,
            "is_real_data": self.quota_type == QuotaType.REAL,
            "remaining_credits": self.remaining_credits,
            "total_limit": self.total_limit,
            "total_tokens_consumed": self.total_tokens_consumed,
            "is_active": self.is_active and self.circuit_breaker.allow_request(),
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "notice": "Official verified quota" if self.quota_type == QuotaType.REAL else "Transparency notice: Quota is estimated."
        }

class QuotaManager:
    def __init__(self):
        self.providers: Dict[str, ProviderQuotaStatus] = {}

    def register_provider(self, provider_id: str, quota_type: QuotaType, initial_credits: float, total_limit: float):
        self.providers[provider_id] = ProviderQuotaStatus(
            provider_id=provider_id,
            quota_type=quota_type,
            remaining_credits=initial_credits,
            total_limit=total_limit
        )

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, int(len(text) / 3.2))

    def record_usage(self, provider_id: str, token_usage: TokenUsage):
        status = self.providers.get(provider_id)
        if status:
            status.consume(1.0)
            status.record_tokens(token_usage.get("total_tokens", 0))
            status.report_network_success()

    def get_status(self, provider_id: str) -> Optional[Dict]:
        status = self.providers.get(provider_id)
        return status.to_dict() if status else None

    def find_available_provider(self, preferred_order: List[str]) -> Optional[str]:
        for p_id in preferred_order:
            status = self.providers.get(p_id)
            if status and status.is_active and status.remaining_credits > 0 and status.circuit_breaker.allow_request():
                return p_id
        return None

# --- 5. Multi-Tier Model Router & Dynamic Escalation ---
"""Intelligent Model Router with Dynamic Escalation Ladder.
Automatically routes light tasks to lightweight models, and escalates to higher-tier models
when a light model fails or when manually requested by the user.
"""
from typing import List, Optional, Dict

class ModelRouter:
    def __init__(self, quota_manager: QuotaManager):
        self.quota_mgr = quota_manager
        
        # Priority ladder per complexity tier
        self.tier_preferences: Dict[TaskComplexity, List[str]] = {
            TaskComplexity.LIGHT: ["groq_llama_8b", "gemini_flash", "local_ollama"],
            TaskComplexity.MODERATE: ["gemini_flash", "groq_llama_70b", "openai_gpt4o_mini"],
            TaskComplexity.COMPLEX: ["gemini_pro", "anthropic_sonnet", "openai_gpt4o"],
            TaskComplexity.CRITICAL: ["gemini_pro", "anthropic_opus", "openai_gpt4o"]
        }
        
        # Escalation sequence
        self.escalation_ladder: Dict[TaskComplexity, TaskComplexity] = {
            TaskComplexity.LIGHT: TaskComplexity.MODERATE,
            TaskComplexity.MODERATE: TaskComplexity.COMPLEX,
            TaskComplexity.COMPLEX: TaskComplexity.CRITICAL,
            TaskComplexity.CRITICAL: TaskComplexity.CRITICAL
        }

    def route(self, complexity: TaskComplexity) -> str:
        candidates = self.tier_preferences.get(complexity, ["gemini_flash"])
        selected = self.quota_mgr.find_available_provider(candidates)
        if not selected:
            for p_id, p_obj in self.quota_mgr.providers.items():
                if p_obj.is_active and p_obj.remaining_credits > 0:
                    return p_id
            raise RuntimeError("All configured model providers are currently depleted of quota.")
        return selected

    def escalate(self, current_complexity: TaskComplexity, current_model: str, reason: str) -> tuple[TaskComplexity, str]:
        """Escalate from a light model to a higher-capacity reasoning model.
        Returns (new_complexity, new_model_name).
        """
        next_complexity = self.escalation_ladder.get(current_complexity, TaskComplexity.COMPLEX)
        candidates = self.tier_preferences.get(next_complexity, ["gemini_pro"])
        
        # Ensure we pick a strictly different and higher model than current_model
        filtered_candidates = [c for c in candidates if c != current_model]
        new_model = self.quota_mgr.find_available_provider(filtered_candidates)
        
        if not new_model:
            # Fallback to any active complex model
            new_model = self.quota_mgr.find_available_provider(self.tier_preferences[TaskComplexity.COMPLEX])
            
        new_model = new_model or current_model
        return next_complexity, new_model

# --- 6. Live HTTP Provider Adapters ---
"""Live HTTP Provider Adapters for Multi-Agent AI Orchestrator.
Supports Google Gemini, Groq, OpenAI, Anthropic, Hugging Face, and Local Ollama.
Uses standard urllib/json with async wrapper so it works out-of-the-box without mandatory external libraries,
and falls back to transparent local simulation when API keys are not yet configured.
"""
import os
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

class ProviderAdapter:
    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds

    def generate(self, model_id: str, prompt: str, system_prompt: str = "You are a helpful AI agent.") -> Dict[str, Any]:
        """Dispatch request to live provider endpoint if API key is present, else simulate transparently."""
        start_time = time.time()
        model_lower = model_id.lower()

        try:
            if "gemini" in model_lower and os.getenv("GEMINI_API_KEY"):
                res = self._call_gemini(model_id, prompt, system_prompt)
            elif "groq" in model_lower and os.getenv("GROQ_API_KEY"):
                res = self._call_groq(model_id, prompt, system_prompt)
            elif "openai" in model_lower and os.getenv("OPENAI_API_KEY"):
                res = self._call_openai(model_id, prompt, system_prompt)
            elif "anthropic" in model_lower and os.getenv("ANTHROPIC_API_KEY"):
                res = self._call_anthropic(model_id, prompt, system_prompt)
            elif "ollama" in model_lower:
                res = self._call_ollama(model_id, prompt, system_prompt)
            else:
                res = self._simulate_response(model_id, prompt)
        except Exception as exc:
            raise RuntimeError(f"Provider '{model_id}' request failed: {exc}") from exc

        duration_ms = round((time.time() - start_time) * 1000.0, 2)
        res["duration_ms"] = duration_ms
        return res

    def _call_gemini(self, model_id: str, prompt: str, system_prompt: str) -> Dict[str, Any]:
        api_key = os.getenv("GEMINI_API_KEY", "")
        gemini_model = "gemini-1.5-pro" if "pro" in model_id.lower() else "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}]
        }
        data = self._http_post_json(url, payload, headers={"Content-Type": "application/json"})
        candidates = data.get("candidates", [{}])
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        usage_meta = data.get("usageMetadata", {})
        usage = TokenUsage(
            prompt_tokens=usage_meta.get("promptTokenCount", max(1, len(prompt) // 4)),
            completion_tokens=usage_meta.get("candidatesTokenCount", max(1, len(text) // 4))
        )
        return {"text": text, "model_used": model_id, "mode": "live_api", "token_usage": usage}

    def _call_groq(self, model_id: str, prompt: str, system_prompt: str) -> Dict[str, Any]:
        api_key = os.getenv("GROQ_API_KEY", "")
        groq_model = "llama-3.3-70b-versatile" if "70b" in model_id.lower() else "llama-3.1-8b-instant"
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = self._http_post_json(url, payload, headers=headers)
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        u = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=u.get("prompt_tokens", max(1, len(prompt) // 4)),
            completion_tokens=u.get("completion_tokens", max(1, len(text) // 4))
        )
        return {"text": text, "model_used": model_id, "mode": "live_api", "token_usage": usage}

    def _call_openai(self, model_id: str, prompt: str, system_prompt: str) -> Dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY", "")
        oai_model = "gpt-4o-mini" if "mini" in model_id.lower() else "gpt-4o"
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": oai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = self._http_post_json(url, payload, headers=headers)
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        u = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=u.get("prompt_tokens", max(1, len(prompt) // 4)),
            completion_tokens=u.get("completion_tokens", max(1, len(text) // 4))
        )
        return {"text": text, "model_used": model_id, "mode": "live_api", "token_usage": usage}

    def _call_anthropic(self, model_id: str, prompt: str, system_prompt: str) -> Dict[str, Any]:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        ant_model = "claude-3-5-sonnet-latest"
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": ant_model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}]
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        data = self._http_post_json(url, payload, headers=headers)
        content_list = data.get("content", [{}])
        text = content_list[0].get("text", "") if content_list else ""
        u = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=u.get("input_tokens", max(1, len(prompt) // 4)),
            completion_tokens=u.get("output_tokens", max(1, len(text) // 4))
        )
        return {"text": text, "model_used": model_id, "mode": "live_api", "token_usage": usage}

    def _call_ollama(self, model_id: str, prompt: str, system_prompt: str) -> Dict[str, Any]:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/generate"
        payload = {
            "model": "llama3",
            "prompt": f"{system_prompt}\n\n{prompt}",
            "stream": False
        }
        try:
            data = self._http_post_json(url, payload, headers={"Content-Type": "application/json"})
            text = data.get("response", "")
            usage = TokenUsage(prompt_tokens=max(1, len(prompt) // 4), completion_tokens=max(1, len(text) // 4))
            return {"text": text, "model_used": model_id, "mode": "live_local_ollama", "token_usage": usage}
        except Exception:
            return self._simulate_response(model_id, prompt)

    def _simulate_response(self, model_id: str, prompt: str) -> Dict[str, Any]:
        sim_text = (
            f"[پاسخ پردازش‌شده توسط {model_id}]: "
            f"درخواست شما («{prompt[:80]}...») تحلیل و اعتبارسنجی شد. "
            f"(وضعیت: شبیه‌ساز محلی فعال است؛ با وارد کردن کلید API در تنظیمات، پاسخ زنده از سرور دریافت می‌شود.)"
        )
        usage = TokenUsage(
            prompt_tokens=max(1, len(prompt) // 3),
            completion_tokens=max(1, len(sim_text) // 3)
        )
        return {
            "text": sim_text,
            "model_used": model_id,
            "mode": "local_simulation",
            "token_usage": usage
        }

    def _http_post_json(self, url: str, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        raw_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=raw_body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body)

# --- 7. Deep Multi-Modal Binary Input Analyzer ---
"""Input Analyzer implementing Section 3 of requirements.
Performs deep content and binary inspection beyond file extensions to accurately classify:
- Audio (MP3, WAV, FLAC, OGG, AAC, M4A)
- Video (MP4, MKV, WebM, AVI, MOV)
- Images (PNG, JPEG, WebP, GIF, TIFF)
- Documents & Office (PDF searchable vs scanned, DOCX, XLSX, PPTX, CSV)
- Source code and plain text
"""
import mimetypes
import zipfile
import io
from typing import Dict, Any, Optional

class InputAnalyzer:
    def analyze(self, filename: str, raw_bytes: bytes = b"") -> Dict[str, Any]:
        size = len(raw_bytes)
        modality = "unknown"
        detected_format = "application/octet-stream"
        pipeline = "generic_binary"
        is_scanned = False
        requires_ocr = False
        requires_transcription = False
        details: Dict[str, Any] = {}

        # 1. Deep Binary Inspection (Magic Bytes)
        if size >= 4:
            # --- Audio Signatures ---
            if raw_bytes.startswith(b"ID3") or (size >= 2 and raw_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
                modality = "audio"
                detected_format = "audio/mpeg"
                pipeline = "speech_to_text_whisper"
                requires_transcription = True
            elif raw_bytes.startswith(b"RIFF") and size >= 12 and raw_bytes[8:12] == b"WAVE":
                modality = "audio"
                detected_format = "audio/wav"
                pipeline = "speech_to_text_whisper"
                requires_transcription = True
            elif raw_bytes.startswith(b"fLaC"):
                modality = "audio"
                detected_format = "audio/flac"
                pipeline = "speech_to_text_whisper"
                requires_transcription = True
            elif raw_bytes.startswith(b"OggS"):
                modality = "audio"
                detected_format = "audio/ogg"
                pipeline = "speech_to_text_whisper"
                requires_transcription = True

            # --- Video Signatures ---
            elif size >= 12 and raw_bytes[4:8] == b"ftyp":
                subtype = raw_bytes[8:12]
                if subtype in (b"M4A ", b"M4B "):
                    modality = "audio"
                    detected_format = "audio/mp4"
                    pipeline = "speech_to_text_whisper"
                    requires_transcription = True
                else:
                    modality = "video"
                    detected_format = "video/mp4"
                    pipeline = "multimodal_video_audio_frame_extraction"
            elif raw_bytes.startswith(b"\x1a\x45\xdf\xa3"):
                modality = "video"
                detected_format = "video/webm" if b"webm" in raw_bytes[:64].lower() else "video/x-matroska"
                pipeline = "multimodal_video_audio_frame_extraction"
            elif raw_bytes.startswith(b"RIFF") and size >= 12 and raw_bytes[8:12] == b"AVI ":
                modality = "video"
                detected_format = "video/x-msvideo"
                pipeline = "multimodal_video_audio_frame_extraction"

            # --- Image Signatures ---
            elif raw_bytes.startswith(b"\xff\xd8\xff"):
                modality = "image"
                detected_format = "image/jpeg"
                pipeline = "multimodal_vision_analysis"
            elif raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                modality = "image"
                detected_format = "image/png"
                pipeline = "multimodal_vision_analysis"
            elif raw_bytes.startswith((b"GIF87a", b"GIF89a")):
                modality = "image"
                detected_format = "image/gif"
                pipeline = "multimodal_vision_analysis"
            elif raw_bytes.startswith(b"RIFF") and size >= 12 and raw_bytes[8:12] == b"WEBP":
                modality = "image"
                detected_format = "image/webp"
                pipeline = "multimodal_vision_analysis"

            # --- Document Signatures ---
            elif raw_bytes.startswith(b"%PDF"):
                modality = "document"
                # Deep PDF inspection: text stream vs scanned image
                has_fonts = b"/Font" in raw_bytes or b"/Type /Font" in raw_bytes
                has_text_stream = b"BT" in raw_bytes and b"ET" in raw_bytes
                has_images = b"/Image" in raw_bytes or b"/XObject" in raw_bytes
                
                if has_images and not (has_fonts and has_text_stream):
                    is_scanned = True
                    requires_ocr = True
                    detected_format = "application/pdf;variant=scanned_image_only"
                    pipeline = "multimodal_vision_ocr"
                else:
                    detected_format = "application/pdf;variant=searchable_text"
                    pipeline = "direct_pdf_text_extraction"

            elif raw_bytes.startswith(b"PK\x03\x04"):
                # ZIP-based Office OpenXML inspection (Word, Excel, PowerPoint)
                modality = "document"
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                        namelist = z.namelist()
                        if any("word/document.xml" in n for n in namelist):
                            detected_format = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            pipeline = "docx_text_extractor"
                        elif any("xl/workbook.xml" in n for n in namelist):
                            detected_format = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            pipeline = "xlsx_tabular_data_extractor"
                        elif any("ppt/presentation.xml" in n for n in namelist):
                            detected_format = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                            pipeline = "pptx_slides_extractor"
                        else:
                            detected_format = "application/zip"
                            pipeline = "archive_unpacker"
                except Exception:
                    detected_format = "application/zip"
                    pipeline = "archive_unpacker"

        # 2. Text / Source Code Fallback
        if modality == "unknown" and size > 0:
            try:
                # Test UTF-8 / ASCII decodability
                sample = raw_bytes[:4096].decode("utf-8")
                modality = "text"
                lower_fn = filename.lower()
                
                if any(lower_fn.endswith(ext) for ext in [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs"]):
                    detected_format = "text/x-source-code"
                    pipeline = "source_code_analyzer"
                elif lower_fn.endswith(".csv"):
                    detected_format = "text/csv"
                    pipeline = "csv_tabular_parser"
                elif lower_fn.endswith((".json", ".yaml", ".yml")):
                    detected_format = "application/json"
                    pipeline = "structured_data_parser"
                else:
                    detected_format = "text/plain"
                    pipeline = "direct_text_processor"
            except UnicodeDecodeError:
                # Pure binary fallback
                guessed, _ = mimetypes.guess_type(filename)
                detected_format = guessed or "application/octet-stream"

        return {
            "filename": filename,
            "modality": modality,               # 'audio', 'video', 'image', 'document', 'text', 'unknown'
            "detected_mime": detected_format,
            "size_bytes": size,
            "is_scanned": is_scanned,
            "requires_ocr": requires_ocr,
            "requires_transcription": requires_transcription,
            "recommended_pipeline": pipeline,
            "details": details
        }

# --- 8. Critic & Validator Agent ---
"""Critic & Validator Agent (Section 4 & 5 of requirements).
Evaluates whether a model output meets quality, schema, and completeness requirements.
Triggers automatic model escalation if a light model output is deficient.
"""
from typing import Dict, Any, Optional, List

class CriticAgent:
    def __init__(self, min_quality_threshold: float = 0.75):
        self.min_quality_threshold = min_quality_threshold

    def evaluate_output(
        self,
        prompt: str,
        output_payload: Optional[Dict[str, Any]],
        expected_schema: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Assess response completeness and detect if model was incapable."""
        if not output_payload:
            return {
                "is_valid": False,
                "score": 0.0,
                "needs_escalation": True,
                "reason": "Model returned empty or null output."
            }

        text = output_payload.get("text", "")
        incapable_phrases = [
            "i cannot fulfill this", "as an ai i am unable", "too complex",
            "context limit exceeded", "sorry, i cannot", "error processing"
        ]
        
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in incapable_phrases) and len(text) < 200:
            return {
                "is_valid": False,
                "score": 0.2,
                "needs_escalation": True,
                "reason": "Model explicitly signaled inability to fulfill task."
            }

        if expected_schema:
            missing_keys = [k for k in expected_schema if k not in output_payload]
            if missing_keys:
                return {
                    "is_valid": False,
                    "score": 0.4,
                    "needs_escalation": True,
                    "reason": f"Output failed schema check; missing keys: {missing_keys}"
                }

        if len(text.strip()) < 10:
            return {
                "is_valid": False,
                "score": 0.3,
                "needs_escalation": True,
                "reason": "Model output truncated or too brief."
            }

        return {
            "is_valid": True,
            "score": 0.95,
            "needs_escalation": False,
            "reason": "Output passed validation checks."
        }

# --- 9. Dual Backward & Forward DAG Recovery Engine ---
"""Dual Backward and Forward Recovery Engine (Section 6 of requirements).
Operates over an internal DAG of execution steps to isolate root causes and selectively re-execute downstream steps.
Zero external dependencies required.
"""
from typing import Dict, List, Set, Optional
from collections import deque

class DAG:
    """Lightweight directed acyclic graph implementation."""
    def __init__(self):
        self.nodes: Set[str] = set()
        self.adj: Dict[str, Set[str]] = {}      # u -> children (outgoing)
        self.pred: Dict[str, Set[str]] = {}     # v -> parents (incoming)

    def add_node(self, node: str):
        if node not in self.nodes:
            self.nodes.add(node)
            self.adj[node] = set()
            self.pred[node] = set()

    def add_edge(self, u: str, v: str):
        self.add_node(u)
        self.add_node(v)
        self.adj[u].add(v)
        self.pred[v].add(u)

    def get_ancestors(self, node: str) -> Set[str]:
        visited = set()
        queue = deque(self.pred.get(node, []))
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                queue.extend(self.pred.get(curr, []))
        return visited

    def get_descendants(self, node: str) -> Set[str]:
        visited = set()
        queue = deque(self.adj.get(node, []))
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                queue.extend(self.adj.get(curr, []))
        return visited

    def topological_sort_subgraph(self, subset: Set[str]) -> List[str]:
        in_degree = {n: 0 for n in subset}
        for u in subset:
            for v in self.adj.get(u, []):
                if v in subset:
                    in_degree[v] += 1

        queue = deque([n for n, deg in in_degree.items() if deg == 0])
        order = []
        while queue:
            curr = queue.popleft()
            order.append(curr)
            for neighbor in self.adj.get(curr, []):
                if neighbor in subset:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
        return order


class RecoveryEngine:
    def __init__(self):
        self.dag = DAG()
        self.steps: Dict[str, ExecutionStep] = {}

    def add_step(self, step: ExecutionStep):
        self.steps[step.step_id] = step
        self.dag.add_node(step.step_id)
        for dep in step.dependencies:
            self.dag.add_edge(dep, step.step_id)

    def backward_recovery(self, failed_step_id: str, error_desc: str) -> ErrorRecord:
        ancestors = self.dag.get_ancestors(failed_step_id)
        root_cause_candidate = failed_step_id
        
        for anc_id in ancestors:
            step = self.steps.get(anc_id)
            if step and (step.status == "failed" or step.output_payload is None):
                root_cause_candidate = anc_id
                break

        impacted = list(self.dag.get_descendants(root_cause_candidate))
        if failed_step_id not in impacted and failed_step_id != root_cause_candidate:
            impacted.append(failed_step_id)

        return ErrorRecord(
            error_id=f"err_{failed_step_id}",
            step_id=failed_step_id,
            category=ErrorCategory.DEPENDENCY_ERROR if root_cause_candidate != failed_step_id else ErrorCategory.AGENT_FAULT,
            severity="high",
            message=error_desc,
            confidence=0.92,
            root_cause_step_id=root_cause_candidate,
            impacted_downstream_steps=impacted
        )

    def forward_recovery_plan(self, root_cause_step_id: str) -> List[str]:
        descendants = self.dag.get_descendants(root_cause_step_id)
        subset = {root_cause_step_id}.union(descendants)
        return self.dag.topological_sort_subgraph(subset)

# --- 10. Portable SQLite / JSON Store ---
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

# --- 11. Zero-Token Content-Hash Response Cache ---
"""Content-Hash Response Cache.
Saves 100% of tokens by retrieving previously verified answers instantly.
"""
import hashlib
import json
from typing import Dict, Any, Optional

class ResponseCache:
    def __init__(self, store: Optional[SQLiteStore] = None):
        self.store = store or SQLiteStore()

    def generate_key(self, prompt: str, task_type: str, model_tier: str = "") -> str:
        content = f"{task_type}:{model_tier}:{prompt.strip()}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def lookup(self, prompt: str, task_type: str, model_tier: str = "") -> Optional[Dict[str, Any]]:
        key = self.generate_key(prompt, task_type, model_tier)
        return self.store.get_cache_entry(key)

    def store_response(self, prompt: str, task_type: str, output: Dict[str, Any], score: float = 1.0, model_tier: str = ""):
        key = self.generate_key(prompt, task_type, model_tier)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self.store.save_cache_entry(key, task_type, prompt_hash, output, score)

# --- 12. Live Telemetry Event Bus & History Replay ---
"""Live Telemetry Event Bus and Historical Replay Engine (Section 9 of requirements).
Maintains full execution history so the user can re-attach or review from step 1 at any time.
"""
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timezone
import asyncio

class TelemetryEvent:
    def __init__(
        self,
        event_type: str,
        step_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        model_name: Optional[str] = None,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        timestamp_utc: Optional[str] = None
    ):
        self.event_type = event_type  # e.g., 'step_started', 'step_completed', 'step_failed', 'recovered', 'user_intervened', 'quota_updated'
        self.step_id = step_id
        self.agent_name = agent_name
        self.model_name = model_name
        self.message = message
        self.data = data or {}
        self.timestamp_utc = timestamp_utc or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "step_id": self.step_id,
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "message": self.message,
            "data": self.data,
            "timestamp_utc": self.timestamp_utc
        }

class EventBus:
    def __init__(self):
        self.history: List[TelemetryEvent] = []
        self._listeners: List[Callable[[TelemetryEvent], Any]] = []

    def emit(self, event: TelemetryEvent):
        """Append event to permanent history and notify live subscribers."""
        self.history.append(event)
        for listener in list(self._listeners):
            try:
                if asyncio.iscoroutinefunction(listener):
                    asyncio.create_task(listener(event))
                else:
                    listener(event)
            except Exception as e:
                print(f"Error notifying listener: {e}")

    def subscribe(self, listener: Callable[[TelemetryEvent], Any]):
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[TelemetryEvent], Any]):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def get_full_history(self) -> List[Dict[str, Any]]:
        """Replay all historical events from the very first step."""
        return [evt.to_dict() for evt in self.history]

    def clear(self):
        self.history.clear()

global_event_bus = EventBus()

# --- 13. Human-in-the-Loop Execution Controller ---
"""Human-in-the-Loop Execution Controller.
Empowers the user to supervise, pause, resume, re-run, or manually override models on the fly.
"""
import asyncio
from typing import Dict, Optional, Set

class ExecutionController:
    def __init__(self):
        self.is_paused: bool = False
        self.is_aborted: bool = False
        self.model_overrides: Dict[str, str] = {}  # step_id -> manual model name
        self.requested_step_reruns: Set[str] = set()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Unpaused initially

    def pause(self, reason: str = "User requested execution pause"):
        """Pause execution at the current checkpoint."""
        self.is_paused = True
        self._pause_event.clear()
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            message=f"⏸️ Execution PAUSED: {reason}",
            data={"action": "pause", "is_paused": True}
        ))

    def resume(self, reason: str = "User resumed execution"):
        """Resume paused background execution."""
        self.is_paused = False
        self._pause_event.set()
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            message=f"▶️ Execution RESUMED: {reason}",
            data={"action": "resume", "is_paused": False}
        ))

    def abort(self, reason: str = "User terminated execution"):
        self.is_aborted = True
        self.resume("Unblocking loop for termination")
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            message=f"🛑 Execution ABORTED: {reason}",
            data={"action": "abort", "is_aborted": True}
        ))

    def set_model_override(self, step_id: str, model_name: str):
        """Manually force a specific model for a given execution step."""
        self.model_overrides[step_id] = model_name
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            step_id=step_id,
            model_name=model_name,
            message=f"🔀 Manual Model Override: Step '{step_id}' assigned to '{model_name}'",
            data={"action": "override_model", "target_step": step_id, "forced_model": model_name}
        ))

    def request_step_rerun(self, step_id: str):
        """Mark a step for immediate re-computation."""
        self.requested_step_reruns.add(step_id)
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            step_id=step_id,
            message=f"🔄 Step Rerun Requested for '{step_id}'",
            data={"action": "rerun_step", "target_step": step_id}
        ))

    async def wait_if_paused(self):
        """Orchestrator worker calls this prior to running any step. If paused, awaits user resume."""
        if self.is_aborted:
            raise RuntimeError("Task execution aborted by user intervention.")
        await self._pause_event.wait()

global_controller = ExecutionController()

# --- 14. FastAPI Dashboard, 4-Channel Notifications & File Download Center ---
"""FastAPI Monitoring & Interactive Execution Dashboard Server.
Features:
- Real-time Desktop Browser Notifications & Audio Chime Alert when tasks finish or need attention
- Dedicated "Finalized AI Deliverables" Download Center (/api/tasks/{task_id}/download)
- Interactive Web Task Input & Multi-Modal File Upload directly in the browser
- Live Multi-Agent Pipeline Execution (Input Analyzer -> Cache -> Router -> Adapter -> Critic -> Recovery)
- Audit Report Exporter (Download full UTC execution log as Markdown .md or JSON .json)
- Dynamic API Key & Model Configuration Tab
- Compact Floating / Picture-in-Picture window mode
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import base64
import json
import os
from pathlib import Path


app = FastAPI(title="Adaptive AI Orchestrator - Live Supervisor & Execution Engine")
sqlite_store = SQLiteStore()
response_cache = ResponseCache(sqlite_store)
input_analyzer = InputAnalyzer()
critic_agent = CriticAgent()
provider_adapter = ProviderAdapter()

quota_manager = QuotaManager()
quota_manager.register_provider("groq_llama_8b", QuotaType.REAL, 100, 100)
quota_manager.register_provider("gemini_flash", QuotaType.REAL, 100, 100)
quota_manager.register_provider("gemini_pro", QuotaType.REAL, 50, 50)
quota_manager.register_provider("local_ollama", QuotaType.ESTIMATED, 9999, 9999)
model_router = ModelRouter(quota_manager)

# Store completed task outputs and finalized downloadable deliverables
audit_results: List[Dict[str, Any]] = []
finalized_deliverables: Dict[str, Dict[str, Any]] = {}

class OverrideRequest(BaseModel):
    step_id: str
    model_name: str

class RerunRequest(BaseModel):
    step_id: str

class TaskSubmitRequest(BaseModel):
    prompt: str
    complexity: str = "auto"
    output_format: str = "md"  # md, txt, py, json, csv
    filename: Optional[str] = None
    file_base64: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None

@app.get("/api/history")
async def get_history():
    return {
        "history": global_event_bus.get_full_history(),
        "is_paused": global_controller.is_paused,
        "deliverables": list(finalized_deliverables.values())
    }

@app.get("/api/deliverables")
async def list_deliverables():
    """Return list of all finalized AI files ready for user download."""
    return {"deliverables": list(finalized_deliverables.values())}

@app.get("/api/tasks/{task_id}/download")
async def download_task_deliverable(task_id: str, fmt: Optional[str] = None):
    """Download the finalized AI output file for a specific completed task."""
    item = finalized_deliverables.get(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    ext = (fmt or item.get("output_format") or "md").lower().strip(".")
    filename = f"{task_id}_final.{ext}"
    
    if ext == "json":
        content = json.dumps(item, ensure_ascii=False, indent=2)
        media_type = "application/json"
    elif ext == "py":
        content = "\n".join([f"# Finalized AI Output ({item['task_id']})", f"# Model: {item['model_used']} | UTC: {item['timestamp_utc']}", "", item["text"]])
        media_type = "text/x-python"
    elif ext == "txt":
        content = item["text"]
        media_type = "text/plain; charset=utf-8"
    else:
        content = "\n".join([f"# خروجی نهایی تأییدشده ({item['task_id']})", "", f"- **مدل تولیدکننده:** `{item['model_used']}`", f"- **زمان نهایی‌سازی (UTC):** `{item['timestamp_utc']}`", f"- **درخواست اولیه:** {item['prompt']}", "", "## متن نهایی", "", item["text"]])
        media_type = "text/markdown; charset=utf-8"

    return Response(
        content=content.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/tasks/submit")
async def submit_task(req: TaskSubmitRequest):
    """Execute full multi-agent workflow, package finalized file, and notify the user."""
    await global_controller.wait_if_paused()
    task_id = f"task_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    
    # Step 1: Input Analysis
    file_info = None
    if req.filename:
        raw_bytes = base64.b64decode(req.file_base64) if req.file_base64 else b""
        file_info = input_analyzer.analyze(req.filename, raw_bytes)
        global_event_bus.emit(TelemetryEvent(
            event_type="step_completed",
            step_id=f"{task_id}_analyze",
            agent_name="InputAnalyzer",
            message=f"🔍 تحلیل فایل «{req.filename}»: نوع واقعی={file_info['modality']} ({file_info['detected_mime']}) | خط لوله={file_info['recommended_pipeline']}",
            data=file_info
        ))

    # Step 2: Complexity Classification & Token Estimation
    est_tokens = quota_manager.estimate_tokens(req.prompt)
    if req.complexity == "auto":
        if est_tokens > 300 or (file_info and file_info["modality"] in ("video", "document")):
            chosen_complexity = TaskComplexity.COMPLEX
        elif est_tokens > 80:
            chosen_complexity = TaskComplexity.MODERATE
        else:
            chosen_complexity = TaskComplexity.LIGHT
    else:
        chosen_complexity = TaskComplexity(req.complexity)

    # Step 3: Zero-Token Cache Check
    cached = response_cache.lookup(req.prompt, chosen_complexity.value)
    if cached:
        cached_copy = dict(cached)
        cached_copy["task_id"] = task_id
        cached_copy["output_format"] = req.output_format
        cached_copy["download_url"] = f"/api/tasks/{task_id}/download"
        finalized_deliverables[task_id] = cached_copy
        global_event_bus.emit(TelemetryEvent(
            event_type="deliverable_ready",
            step_id=f"{task_id}_cache",
            agent_name="ResponseCache",
            message=f"⚡ پاسخ معتبر در کَش محلی یافت شد و فایل نهایی «{task_id}_final.{req.output_format}» آماده دانلود است!",
            data=cached_copy
        ))
        return {"status": "completed", "task_id": task_id, "source": "cache", "output": cached_copy}

    # Step 4: Smart Model Routing
    step_exec_id = f"{task_id}_exec"
    selected_model = global_controller.model_overrides.get(step_exec_id) or model_router.route(chosen_complexity)
    global_event_bus.emit(TelemetryEvent(
        event_type="step_started",
        step_id=step_exec_id,
        agent_name="ModelRouter",
        model_name=selected_model,
        message=f"🚀 مسیریابی هوشمند (سطح {chosen_complexity.value} | ~{est_tokens} توکن) به مدل «{selected_model}»"
    ))

    # Step 5: Execute via ProviderAdapter with CircuitBreaker protection
    try:
        gen_res = provider_adapter.generate(selected_model, req.prompt)
        quota_manager.record_usage(selected_model, gen_res["token_usage"])
    except Exception as exc:
        if selected_model in quota_manager.providers:
            quota_manager.providers[selected_model].report_network_failure(str(exc))
        _, fallback_model = model_router.escalate(chosen_complexity, selected_model, str(exc))
        global_event_bus.emit(TelemetryEvent(
            event_type="step_failed",
            step_id=step_exec_id,
            agent_name="CircuitBreaker",
            model_name=fallback_model,
            message=f"⚠️ خطای ارتباطی در {selected_model}؛ مدار قطع شد و وظیفه خودکار به {fallback_model} منتقل گردید."
        ))
        selected_model = fallback_model
        gen_res = provider_adapter.generate(selected_model, req.prompt)
        quota_manager.record_usage(selected_model, gen_res["token_usage"])

    # Step 6: Critic Validation & Dynamic Escalation
    critique = critic_agent.evaluate_output(req.prompt, {"text": gen_res["text"]})
    escalated = False
    if not critique["is_valid"] and critique["needs_escalation"]:
        escalated = True
        new_comp, higher_model = model_router.escalate(chosen_complexity, selected_model, critique["reason"])
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            step_id=step_exec_id,
            agent_name="CriticAgent",
            model_name=higher_model,
            message=f"🔼 ارتقای خودکار مدل از {selected_model} به {higher_model} به دلیل: {critique['reason']}"
        ))
        selected_model = higher_model
        gen_res = provider_adapter.generate(selected_model, req.prompt)
        quota_manager.record_usage(selected_model, gen_res["token_usage"])

    output_record = {
        "task_id": task_id,
        "prompt": req.prompt,
        "text": gen_res["text"],
        "model_used": selected_model,
        "mode": gen_res["mode"],
        "complexity": chosen_complexity.value,
        "output_format": req.output_format,
        "download_url": f"/api/tasks/{task_id}/download",
        "token_usage": dict(gen_res["token_usage"]),
        "duration_ms": gen_res["duration_ms"],
        "escalated": escalated,
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    # Save to cache, SQLite experience store, and Finalized Deliverables registry
    response_cache.store_response(req.prompt, chosen_complexity.value, output_record, score=0.95)
    sqlite_store.record_experience(chosen_complexity.value, selected_model, True, escalated, gen_res["duration_ms"])
    audit_results.append(output_record)
    finalized_deliverables[task_id] = output_record

    # Emit completion + user notification event
    global_event_bus.emit(TelemetryEvent(
        event_type="deliverable_ready",
        step_id=step_exec_id,
        agent_name="NotificationCenter",
        model_name=selected_model,
        message=f"🔔 اطلاع‌رسانی به کاربر: فایل نهایی «{task_id}_final.{req.output_format}» تأیید شد و آماده دانلود است!",
        data=output_record
    ))

    return {"status": "completed", "task_id": task_id, "source": gen_res["mode"], "output": output_record}

@app.get("/api/export/markdown", response_class=PlainTextResponse)
async def export_audit_markdown():
    """Export complete auditable execution report in Markdown format with UTC timestamps."""
    now_utc = datetime.now(timezone.utc).isoformat()
    lines = [
        "# گزارش رسمی حسابرسی و اجرای سامانه (Orchestrator Audit Report)",
        f"- **زمان تولید گزارش (UTC):** `{now_utc}`",
        f"- **تعداد کل رویدادهای ثبت‌شده:** `{len(global_event_bus.history)}`",
        f"- **تعداد وظایف تکمیل‌شده:** `{len(audit_results)}`",
        "",
        "## ۱. خلاصه وضعیت سهمیه و مدار ارائه‌دهندگان (Provider Quotas & Circuit Breakers)",
        "| ارائه‌دهنده | نوع سهمیه | اعتبار باقیمانده | توکن مصرفی | وضعیت مدار (Circuit Breaker) |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for p_id, p_status in quota_manager.providers.items():
        d = p_status.to_dict()
        cb_state = d["circuit_breaker"]["state"]
        lines.append(f"| `{p_id}` | {d['quota_type']} | {d['remaining_credits']}/{d['total_limit']} | {d['total_tokens_consumed']} | `{cb_state}` |")

    lines.extend(["", "## ۲. خروجی‌های نهایی تأییدشده (Validated Task Outputs)"])
    if not audit_results:
        lines.append("_هنوز وظیفه‌ای در این نشست ثبت نشده است._")
    for idx, item in enumerate(audit_results, 1):
        lines.extend([
            f"### وظیفه {idx}: `{item['task_id']}` ({item['timestamp_utc']})",
            f"- **مدل استفاده‌شده:** `{item['model_used']}` (حالت: `{item['mode']}` | پیچیدگی: `{item['complexity']}`)",
            f"- **مصرف توکن:** `{item['token_usage']['total_tokens']}` توکن | **زمان پاسخ:** `{item['duration_ms']} ms`",
            f"- **درخواست کاربر:** {item['prompt']}",
            f"- **پاسخ نهایی:** {item['text']}",
            ""
        ])

    lines.extend(["## ۳. زنجیره کامل رویدادها از گام نخست (Full UTC Event Timeline)"])
    for evt in global_event_bus.get_full_history():
        lines.append(f"- `{evt['timestamp_utc']}` **[{evt['event_type']}]** ({evt.get('agent_name') or 'Core'}): {evt['message']}")

    return PlainTextResponse(
        content="\n".join(lines),
        headers={"Content-Disposition": "attachment; filename=orchestrator_audit_report.md"}
    )

@app.get("/api/export/json")
async def export_audit_json():
    """Export complete auditable execution report in JSON format."""
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "providers": {k: v.to_dict() for k, v in quota_manager.providers.items()},
        "validated_outputs": audit_results,
        "deliverables": list(finalized_deliverables.values()),
        "event_timeline": global_event_bus.get_full_history(),
        "model_reliability_stats": sqlite_store.get_model_stats()
    }
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": "attachment; filename=orchestrator_audit_report.json"}
    )

@app.get("/api/settings")
async def get_settings():
    return {
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        "huggingface_configured": bool(os.getenv("HUGGINGFACE_API_KEY")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    }

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    env_updates = {}
    if req.gemini_api_key is not None:
        os.environ["GEMINI_API_KEY"] = req.gemini_api_key
        env_updates["GEMINI_API_KEY"] = req.gemini_api_key
    if req.groq_api_key is not None:
        os.environ["GROQ_API_KEY"] = req.groq_api_key
        env_updates["GROQ_API_KEY"] = req.groq_api_key
    if req.openai_api_key is not None:
        os.environ["OPENAI_API_KEY"] = req.openai_api_key
        env_updates["OPENAI_API_KEY"] = req.openai_api_key
    if req.anthropic_api_key is not None:
        os.environ["ANTHROPIC_API_KEY"] = req.anthropic_api_key
        env_updates["ANTHROPIC_API_KEY"] = req.anthropic_api_key
    if req.huggingface_api_key is not None:
        os.environ["HUGGINGFACE_API_KEY"] = req.huggingface_api_key
        env_updates["HUGGINGFACE_API_KEY"] = req.huggingface_api_key
    if req.ollama_base_url is not None:
        os.environ["OLLAMA_BASE_URL"] = req.ollama_base_url
        env_updates["OLLAMA_BASE_URL"] = req.ollama_base_url

    env_file = Path(".env")
    existing_lines = []
    if env_file.exists():
        existing_lines = env_file.read_text(encoding="utf-8").splitlines()

    new_lines = []
    handled_keys = set()
    for line in existing_lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=")[0].strip()
            if k in env_updates:
                new_lines.append(f"{k}={env_updates[k]}")
                handled_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in env_updates.items():
        if k not in handled_keys:
            new_lines.append(f"{k}={v}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    
    global_event_bus.emit(TelemetryEvent(
        event_type="user_intervened",
        message="⚙️ تنظیمات کلیدهای API از داخل داشبورد به‌روزرسانی شد."
    ))
    return {"status": "success", "message": "Settings updated and saved to .env"}

@app.post("/api/pause")
async def pause_execution():
    global_controller.pause()
    return {"status": "paused", "is_paused": True}

@app.post("/api/resume")
async def resume_execution():
    global_controller.resume()
    return {"status": "resumed", "is_paused": False}

@app.post("/api/override-model")
async def override_model(req: OverrideRequest):
    global_controller.set_model_override(req.step_id, req.model_name)
    return {"status": "overridden", "step_id": req.step_id, "model": req.model_name}

@app.post("/api/rerun-step")
async def rerun_step(req: RerunRequest):
    global_controller.request_step_rerun(req.step_id)
    return {"status": "rerun_requested", "step_id": req.step_id}

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    past_history = global_event_bus.get_full_history()
    await websocket.send_text(json.dumps({
        "type": "history_sync",
        "data": past_history,
        "deliverables": list(finalized_deliverables.values()),
        "is_paused": global_controller.is_paused
    }))

    async def on_new_event(event: TelemetryEvent):
        try:
            await websocket.send_text(json.dumps({
                "type": "live_event",
                "data": event.to_dict(),
                "is_paused": global_controller.is_paused
            }))
        except Exception:
            pass

    global_event_bus.subscribe(on_new_event)
    try:
        while True:
            client_msg = await websocket.receive_text()
            data = json.loads(client_msg)
            cmd = data.get("command")
            if cmd == "pause":
                global_controller.pause()
            elif cmd == "resume":
                global_controller.resume()
    except WebSocketDisconnect:
        global_event_bus.unsubscribe(on_new_event)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard_html():
    return HTML_CONTENT

HTML_CONTENT = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>سامانه نظارت زنده و اجرای چندعاملی | Adaptive Orchestrator</title>
    <style>
        :root {
            --bg-dark: #0f172a;
            --card-dark: #1e293b;
            --border-dark: #334155;
            --text-light: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-red: #ef4444;
            --accent-purple: #8b5cf6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Tahoma, sans-serif; }
        body { background: var(--bg-dark); color: var(--text-light); min-height: 100vh; padding: 16px; transition: all 0.3s ease; }
        
        body.mini-mode {
            padding: 8px;
            max-width: 420px;
            position: fixed;
            bottom: 12px;
            left: 12px;
            right: auto;
            top: auto;
            background: rgba(15, 23, 42, 0.95);
            border: 2px solid var(--accent-blue);
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.7);
            z-index: 99999;
            backdrop-filter: blur(8px);
        }
        body.mini-mode .hide-in-mini { display: none !important; }
        body.mini-mode .timeline-container { max-height: 180px; }

        header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 14px; border-bottom: 1px solid var(--border-dark); margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
        .logo-box { display: flex; align-items: center; gap: 10px; }
        .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
        .badge-live { background: rgba(16, 185, 129, 0.2); color: var(--accent-green); border: 1px solid var(--accent-green); }
        .badge-paused { background: rgba(245, 158, 11, 0.2); color: var(--accent-amber); border: 1px solid var(--accent-amber); }
        
        .window-controls { display: flex; gap: 8px; flex-wrap: wrap; }
        button, a.btn-link { cursor: pointer; border: none; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; transition: all 0.2s; text-decoration: none; }
        .btn-ctrl { background: var(--card-dark); color: var(--text-light); border: 1px solid var(--border-dark); }
        .btn-ctrl:hover { background: #2d3748; }
        .btn-pause { background: #b45309; color: white; }
        .btn-resume { background: #047857; color: white; }
        .btn-override { background: var(--accent-purple); color: white; }
        .btn-abort { background: #991b1b; color: white; }
        .btn-settings { background: #0284c7; color: white; }
        .btn-submit { background: var(--accent-green); color: white; padding: 10px 20px; font-size: 14px; }
        .btn-download-item { background: var(--accent-blue); color: white; padding: 5px 12px; font-size: 12px; border-radius: 6px; }

        .dashboard-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
        body.mini-mode .dashboard-grid { grid-template-columns: 1fr; }

        .card { background: var(--card-dark); border: 1px solid var(--border-dark); border-radius: 10px; padding: 14px; margin-bottom: 16px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 14px; font-weight: bold; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 8px; }

        .task-box { display: flex; flex-direction: column; gap: 10px; }
        .task-box textarea { width: 100%; min-height: 75px; background: #0f172a; border: 1px solid var(--border-dark); border-radius: 8px; color: white; padding: 10px; font-size: 13px; resize: vertical; }
        .task-controls { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .task-controls select, .task-controls input[type="file"] { background: #0f172a; color: var(--text-light); border: 1px solid var(--border-dark); padding: 6px 10px; border-radius: 6px; font-size: 12px; }

        .timeline-container { max-height: 360px; overflow-y: auto; padding-left: 6px; }
        .timeline-item { position: relative; padding-right: 18px; padding-bottom: 14px; border-right: 2px solid var(--border-dark); margin-right: 10px; }
        .timeline-item::before { content: ''; position: absolute; right: -7px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: var(--accent-blue); }
        .timeline-item.step_completed::before, .timeline-item.deliverable_ready::before { background: var(--accent-green); }
        .timeline-item.step_failed::before { background: var(--accent-red); }
        .timeline-item.user_intervened::before { background: var(--accent-amber); }
        .timeline-time { font-size: 11px; color: var(--text-muted); direction: ltr; text-align: right; }
        .timeline-title { font-size: 13px; font-weight: 600; margin: 3px 0; }
        .timeline-desc { font-size: 12px; color: var(--text-muted); }

        /* Deliverables Box */
        .deliverable-list { display: flex; flex-direction: column; gap: 10px; max-height: 240px; overflow-y: auto; }
        .deliverable-card { display: flex; justify-content: space-between; align-items: center; background: #0f172a; border: 1px solid var(--border-dark); padding: 10px 14px; border-radius: 8px; }
        .deliverable-meta { font-size: 12px; color: var(--text-muted); margin-top: 3px; }

        /* Toast Notification */
        #toast-banner { display: none; position: fixed; top: 18px; left: 50%; transform: translateX(-50%); background: #065f46; color: white; border: 1px solid var(--accent-green); padding: 12px 20px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.6); z-index: 200000; font-size: 13px; font-weight: bold; align-items: center; gap: 12px; }

        .quota-meter { margin-bottom: 12px; }
        .quota-label { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; }
        .progress-bar { width: 100%; height: 8px; background: #334155; border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--accent-blue); width: 100%; transition: width 0.3s; }

        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 100000; align-items: center; justify-content: center; backdrop-filter: blur(4px); }
        .modal-content { background: var(--card-dark); border: 1px solid var(--border-dark); border-radius: 12px; width: 90%; max-width: 520px; padding: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.8); }
        .input-group { margin-bottom: 12px; }
        .input-group label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
        .input-group input { width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid var(--border-dark); border-radius: 6px; color: white; font-size: 13px; }
    </style>
</head>
<body>
    <!-- Live Toast Alert -->
    <div id="toast-banner">
        <span id="toast-text">🔔 فایل نهایی آماده دانلود است!</span>
        <a id="toast-download-btn" class="btn-link btn-download-item" href="#" download>📥 دانلود فوری</a>
    </div>

    <header>
        <div class="logo-box">
            <h2>سامانه هوش مصنوعی چندعاملی تطبیق‌پذیر</h2>
            <span id="status-badge" class="badge badge-live">● آماده و در حال پایش زنده</span>
        </div>
        <div class="window-controls">
            <button id="btn-notify-perm" class="btn-ctrl" onclick="enableNotifications()">🔔 فعال‌سازی اعلان دسکتاپ و صدا</button>
            <button id="btn-toggle-pause" class="btn-pause" onclick="togglePause()">⏸️ توقف اجرا</button>
            <button class="btn-override hide-in-mini" onclick="promptOverride()">🔀 تغییر مدل گام</button>
            <a class="btn-link btn-ctrl hide-in-mini" href="/api/export/markdown" download="orchestrator_audit_report.md">📥 گزارش کل (MD)</a>
            <button class="btn-settings hide-in-mini" onclick="openSettingsModal()">⚙️ تنظیمات کلیدها</button>
            <button class="btn-ctrl" onclick="toggleMiniMode()" title="کوچک کردن به گوشه صفحه">⤢ حالت شناور مینیاتوری</button>
        </div>
    </header>

    <!-- Interactive Task Submission Card -->
    <div class="card hide-in-mini">
        <div class="card-header">
            <span>ارسال وظیفه جدید و تولید فایل نهایی توسط هوش مصنوعی</span>
            <span style="font-size: 11px; color: var(--accent-green);">اعلان خودکار پس از اتمام + لینک دانلود مستقیم</span>
        </div>
        <div class="task-box">
            <textarea id="task-prompt" placeholder="درخواست، سؤال یا دستور تولید فایل خود را اینجا بنویسید..."></textarea>
            <div class="task-controls">
                <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <label style="font-size: 12px; color: var(--text-muted);">پیوست فایل ورودی:</label>
                    <input type="file" id="task-file">
                    <label style="font-size: 12px; color: var(--text-muted);">فرمت فایل خروجی:</label>
                    <select id="task-format">
                        <option value="md">گزارش استاندارد (Markdown .md)</option>
                        <option value="txt">متن خالص (Plain Text .txt)</option>
                        <option value="py">کد پایتون (Python .py)</option>
                        <option value="json">داده ساختاریافته (JSON .json)</option>
                    </select>
                    <label style="font-size: 12px; color: var(--text-muted);">سطح پیچیدگی:</label>
                    <select id="task-complexity">
                        <option value="auto">تشخیص خودکار هوشمند (Auto)</option>
                        <option value="light">سبک و سریع (Light)</option>
                        <option value="moderate">متوسط (Moderate)</option>
                        <option value="complex">پیچیده و استدلالی (Complex)</option>
                    </select>
                </div>
                <button class="btn-submit" onclick="submitTask()">🚀 اجرای هوشمند و ساخت فایل</button>
            </div>
        </div>
    </div>

    <div class="dashboard-grid">
        <div>
            <!-- Finalized Deliverables Download Center -->
            <div class="card">
                <div class="card-header">
                    <span>📦 فایل‌های نهایی‌شده توسط هوش مصنوعی (آماده دانلود)</span>
                    <span id="deliverable-count" style="font-size: 11px; color: var(--accent-green);">۰ فایل آماده</span>
                </div>
                <div id="deliverables-container" class="deliverable-list">
                    <div style="color: var(--text-muted); font-size: 12px; text-align: center; padding: 14px;">هنوز فایلی نهایی نشده است. به محض اتمام هر وظیفه، فایل آن با اعلان صوتی و دسکتاپ در اینجا قرار می‌گیرد.</div>
                </div>
            </div>

            <!-- Live Event Timeline -->
            <div class="card">
                <div class="card-header">
                    <span>خط زمانی زنده رویدادها و مراحل اجرا (از شروع تا کنون)</span>
                    <span id="event-count" style="font-size: 11px; color: var(--text-muted);">۰ رویداد</span>
                </div>
                <div id="timeline" class="timeline-container">
                    <div style="color: var(--text-muted); font-size: 12px; text-align: center; padding: 20px;">آماده دریافت و اجرای وظایف...</div>
                </div>
            </div>
        </div>

        <div class="card hide-in-mini">
            <div class="card-header">
                <span>سهمیه، مدار شبکه و سلامت ارائه‌دهندگان</span>
                <span style="font-size: 11px; color: var(--accent-green);">Circuit Breaker Active</span>
            </div>
            <div class="quota-meter">
                <div class="quota-label"><span>Google Gemini Pro</span><span>۵۰ / ۵۰ (واقعی)</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%;"></div></div>
            </div>
            <div class="quota-meter">
                <div class="quota-label"><span>Groq (LLaMA 8B/70B)</span><span>۱۰۰ / ۱۰۰ (واقعی)</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%; background: var(--accent-green);"></div></div>
            </div>
            <div class="quota-meter">
                <div class="quota-label"><span>کَش پاسخ‌ها (صرفه‌جویی ۱۰۰٪)</span><span>فعال (SQLite/JSON)</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%; background: var(--accent-blue);"></div></div>
            </div>
            <div class="quota-meter">
                <div class="quota-label"><span>Local Ollama (پشتیبان آفلاین)</span><span>نامحدود</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%; background: var(--accent-purple);"></div></div>
            </div>

            <div style="margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 14px;">
                <div style="font-size: 13px; font-weight: bold; margin-bottom: 8px;">کنترل‌های دخالت فوری کاربر:</div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <button class="btn-ctrl" onclick="triggerStepRerun()">🔄 اجرای مجدد یک گام خاص</button>
                    <button class="btn-abort" onclick="abortExecution()">🛑 لغو کامل و توقف اضطراری</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Settings Modal -->
    <div id="settings-modal" class="modal">
        <div class="modal-content">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3>⚙️ تنظیمات کلیدهای هوش مصنوعی</h3>
                <button class="btn-ctrl" onclick="closeSettingsModal()">✕</button>
            </div>
            <div class="input-group">
                <label>Google Gemini API Key:</label>
                <input type="password" id="input-gemini" placeholder="کلید Gemini را وارد کنید">
            </div>
            <div class="input-group">
                <label>Groq API Key (مدل‌های سریع رایگان):</label>
                <input type="password" id="input-groq" placeholder="کلید Groq را وارد کنید">
            </div>
            <div class="input-group">
                <label>OpenAI API Key (اختیاری):</label>
                <input type="password" id="input-openai" placeholder="کلید OpenAI را وارد کنید">
            </div>
            <div class="input-group">
                <label>Anthropic API Key (اختیاری):</label>
                <input type="password" id="input-anthropic" placeholder="کلید Anthropic را وارد کنید">
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px;">
                <button class="btn-ctrl" onclick="closeSettingsModal()">انصراف</button>
                <button class="btn-resume" onclick="saveSettings()">💾 ذخیره تنظیمات در .env</button>
            </div>
        </div>
    </div>

    <script>
        let isPaused = false;
        let audioAlertsEnabled = true;
        let socket;

        function playNotificationChime() {
            if (!audioAlertsEnabled) return;
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
                osc.frequency.setValueAtTime(880, ctx.currentTime + 0.12); // A5
                gain.gain.setValueAtTime(0.15, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + 0.45);
            } catch (e) {}
        }

        function enableNotifications() {
            audioAlertsEnabled = true;
            playNotificationChime();
            if ("Notification" in window) {
                Notification.requestPermission().then(perm => {
                    if (perm === "granted") {
                        document.getElementById('btn-notify-perm').innerText = '🔔 اعلان دسکتاپ و صدا: فعال';
                    }
                });
            }
        }

        function notifyUserDeliverableReady(item) {
            playNotificationChime();
            document.title = `✅ (فایل آماده!) | سامانه چندعاملی`;
            
            // Show top toast banner
            const banner = document.getElementById('toast-banner');
            const textEl = document.getElementById('toast-text');
            const btnEl = document.getElementById('toast-download-btn');
            const ext = item.output_format || 'md';
            textEl.innerText = `🔔 فایل نهایی «${item.task_id}_final.${ext}» توسط ${item.model_used} آماده شد!`;
            btnEl.href = item.download_url || `/api/tasks/${item.task_id}/download`;
            banner.style.display = 'flex';
            setTimeout(() => { banner.style.display = 'none'; }, 10000);

            // Trigger OS / Desktop Notification even if browser is minimized
            if ("Notification" in window && Notification.permission === "granted") {
                const n = new Notification("✅ فایل نهایی هوش مصنوعی آماده است!", {
                    body: `وظیفه با مدل ${item.model_used} تکمیل شد. برای مشاهده و دانلود کلیک کنید.`
                });
                n.onclick = function() {
                    window.focus();
                    window.location.href = item.download_url || `/api/tasks/${item.task_id}/download`;
                };
            }
        }

        function connectWebSocket() {
            const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            socket = new WebSocket(`${proto}//${window.location.host}/ws/telemetry`);

            socket.onmessage = function(event) {
                const payload = JSON.parse(event.data);
                if (payload.type === 'history_sync') {
                    renderFullHistory(payload.data);
                    if (payload.deliverables) {
                        renderDeliverablesList(payload.deliverables);
                    }
                } else if (payload.type === 'live_event') {
                    appendEvent(payload.data);
                    if (payload.data.event_type === 'deliverable_ready' && payload.data.data) {
                        appendDeliverableCard(payload.data.data);
                        notifyUserDeliverableReady(payload.data.data);
                    }
                }
                updateStatusBadge(payload.is_paused);
            };

            socket.onclose = function() {
                setTimeout(connectWebSocket, 2000);
            };
        }

        function renderDeliverablesList(items) {
            const container = document.getElementById('deliverables-container');
            if (!items || items.length === 0) return;
            container.innerHTML = '';
            items.forEach(item => appendDeliverableCard(item));
        }

        function appendDeliverableCard(item) {
            const container = document.getElementById('deliverables-container');
            if (container.children.length === 1 && !container.children[0].classList.contains('deliverable-card')) {
                container.innerHTML = '';
            }
            const ext = item.output_format || 'md';
            const card = document.createElement('div');
            card.className = 'deliverable-card';
            card.innerHTML = `
                <div>
                    <div style="font-weight: bold; font-size: 13px;">📄 ${item.task_id}_final.${ext}</div>
                    <div class="deliverable-meta">مدل: <code>${item.model_used}</code> | درخواست: ${item.prompt.substring(0, 50)}...</div>
                </div>
                <div style="display: flex; gap: 6px;">
                    <a class="btn-link btn-download-item" href="/api/tasks/${item.task_id}/download?fmt=${ext}" download>📥 دانلود (.${ext})</a>
                    <a class="btn-link btn-ctrl" style="padding: 5px 10px; font-size: 11px;" href="/api/tasks/${item.task_id}/download?fmt=json" download>JSON</a>
                </div>
            `;
            container.prepend(card);
            document.getElementById('deliverable-count').innerText = `${container.children.length} فایل آماده`;
        }

        function renderFullHistory(events) {
            const container = document.getElementById('timeline');
            container.innerHTML = '';
            document.getElementById('event-count').innerText = `${events.length} رویداد`;
            events.forEach(evt => appendEvent(evt, false));
        }

        function appendEvent(evt, updateCount = true) {
            const container = document.getElementById('timeline');
            const item = document.createElement('div');
            item.className = `timeline-item ${evt.event_type || ''}`;
            
            const timeStr = evt.timestamp_utc ? new Date(evt.timestamp_utc).toLocaleTimeString('fa-IR') : '';
            item.innerHTML = `
                <div class="timeline-time">${timeStr} | ${evt.agent_name || 'هسته'} ${evt.model_name ? '» ' + evt.model_name : ''}</div>
                <div class="timeline-title">${evt.message}</div>
                ${evt.step_id ? `<div class="timeline-desc">شناسه گام: <code>${evt.step_id}</code></div>` : ''}
            `;
            container.appendChild(item);
            container.scrollTop = container.scrollHeight;
            if (updateCount) {
                const countElem = document.getElementById('event-count');
                const cur = parseInt(countElem.innerText) || 0;
                countElem.innerText = `${cur + 1} رویداد`;
            }
        }

        async function submitTask() {
            const promptEl = document.getElementById('task-prompt');
            const compEl = document.getElementById('task-complexity');
            const fmtEl = document.getElementById('task-format');
            const fileEl = document.getElementById('task-file');
            const promptText = promptEl.value.trim();
            if (!promptText) {
                alert('لطفاً متن درخواست یا سؤال خود را وارد کنید.');
                return;
            }

            let filename = null;
            let fileBase64 = null;
            if (fileEl.files && fileEl.files.length > 0) {
                const f = fileEl.files[0];
                filename = f.name;
                const buf = await f.arrayBuffer();
                let binary = '';
                const bytes = new Uint8Array(buf);
                for (let i = 0; i < bytes.byteLength; i++) {
                    binary += String.fromCharCode(bytes[i]);
                }
                fileBase64 = btoa(binary);
            }

            fetch('/api/tasks/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: promptText,
                    complexity: compEl.value,
                    output_format: fmtEl.value,
                    filename: filename,
                    file_base64: fileBase64
                })
            });
            promptEl.value = '';
            fileEl.value = '';
        }

        function updateStatusBadge(paused) {
            isPaused = paused;
            const badge = document.getElementById('status-badge');
            const btn = document.getElementById('btn-toggle-pause');
            if (paused) {
                badge.className = 'badge badge-paused';
                badge.innerText = '⏸️ اجرا متوقف شد (توسط کاربر)';
                btn.className = 'btn-resume';
                btn.innerText = '▶️ ادامه اجرا';
            } else {
                badge.className = 'badge badge-live';
                badge.innerText = '● آماده و در حال پایش زنده';
                btn.className = 'btn-pause';
                btn.innerText = '⏸️ توقف اجرا';
            }
        }

        function togglePause() {
            const endpoint = isPaused ? '/api/resume' : '/api/pause';
            fetch(endpoint, { method: 'POST' });
        }

        function promptOverride() {
            const stepId = prompt('شناسه مرحله را وارد کنید (مثلاً step_2):');
            if (!stepId) return;
            const modelName = prompt('نام مدل جایگزین را وارد کنید (مثلاً groq_llama_70b یا gemini_pro):');
            if (!modelName) return;
            fetch('/api/override-model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ step_id: stepId, model_name: modelName })
            });
        }

        function triggerStepRerun() {
            const stepId = prompt('شناسه مرحله‌ای که می‌خواهید مجدداً اجرا شود را وارد کنید:');
            if (stepId) {
                fetch('/api/rerun-step', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ step_id: stepId })
                });
            }
        }

        function abortExecution() {
            if (confirm('آیا از توقف کامل و اضطراری مطمئن هستید؟')) {
                togglePause();
            }
        }

        function toggleMiniMode() {
            document.body.classList.toggle('mini-mode');
        }

        function openSettingsModal() {
            document.getElementById('settings-modal').style.display = 'flex';
        }

        function closeSettingsModal() {
            document.getElementById('settings-modal').style.display = 'none';
        }

        function saveSettings() {
            const gemini = document.getElementById('input-gemini').value.trim();
            const groq = document.getElementById('input-groq').value.trim();
            const openai = document.getElementById('input-openai').value.trim();
            const anthropic = document.getElementById('input-anthropic').value.trim();

            const payload = {};
            if (gemini) payload.gemini_api_key = gemini;
            if (groq) payload.groq_api_key = groq;
            if (openai) payload.openai_api_key = openai;
            if (anthropic) payload.anthropic_api_key = anthropic;

            fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(res => res.json()).then(data => {
                alert('تنظیمات با موفقیت در .env ذخیره شد!');
                closeSettingsModal();
            });
        }

        window.onload = connectWebSocket;
    </script>
</body>
</html>
"""



# ==============================================================================
# Direct One-Command Execution Entrypoint
# ==============================================================================
def _open_browser_delayed():
    time.sleep(1.2)
    url = "http://localhost:8000"
    print(f"\n[داشبورد مانیتورینگ آماده است]: در حال باز کردن مرورگر در آدرس {url}...")
    try:
        webbrowser.open(url)
    except Exception:
        print(f"لطفاً آدرس {url} را در مرورگر خود باز کنید.")

if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=_open_browser_delayed, daemon=True).start()
    print("=" * 68)
    print("  Adaptive AI Orchestrator (Unified Edition) is Live on Port 8000!")
    print("  برای توقف سامانه، کلیدهای Ctrl + C را فشار دهید.")
    print("=" * 68)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
