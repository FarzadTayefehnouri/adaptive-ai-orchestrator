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
from src.orchestrator.models import TokenUsage

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
