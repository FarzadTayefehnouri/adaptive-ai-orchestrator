""" ماژول مستقل درگاه هوش مصنوعی، مدیریت سهمیه و مسیریاب هوشمند (Zero-Dependency AI Gateway) طراحی‌شده بر اساس معماری سامانه هوش مصنوعی چندعاملی تطبیقی تحت مجوز GNU AGPLv3 """

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskComplexity(Enum):
    """سطح پیچیدگی وظیفه برای انتخاب هوشمند مدل"""
    SIMPLE = "simple"        # کارهای سریع، دسته‌بندی، خلاصه‌سازی کوتاه
    MODERATE = "moderate"    # تحلیل متن، ترجمه دقیق، استخراج ساختاریافته
    COMPLEX = "complex"      # کدنویسی، استدلال چندمرحله‌ای، ریشه‌یابی خطا


class QuotaSourceType(Enum):
    """تفکیک اطلاعات واقعی سهمیه از تخمین‌های محلی (الزام بخش ۲ و ۳.۵ سند)"""
    EXACT_PROVIDER_HEADER = "exact"      # اعلام‌شده رسمی توسط هدرهای سرور ارائه‌دهنده
    ESTIMATED_LOCAL = "estimated"        # محاسبه‌شده توسط شمارنده داخلی سامانه


@dataclass
class QuotaStatus:
    """وضعیت لحظه‌ای مصرف و سهمیه هر سرویس"""
    provider_name: str
    requests_per_minute_limit: int
    daily_token_limit: int
    used_tokens_today: int = 0
    remaining_requests_window: float = 0.0
    source_type: QuotaSourceType = QuotaSourceType.ESTIMATED_LOCAL
    is_available: bool = True
    last_error: Optional[str] = None
    last_updated_utc: float = field(default_factory=time.time)


class TokenBucketRateLimiter:
    """ کنترل‌کننده نرخ درخواست و سهمیه (Token Bucket) بدون وابستگی خارجی جلوگیری از بروز خطای HTTP 429 در اجرای هم‌زمان عامل‌ها """

    def __init__(self, rpm_limit: int, daily_token_limit: int):
        self.rpm_limit = max(1, rpm_limit)
        self.daily_token_limit = daily_token_limit
        self.tokens = float(rpm_limit)
        self.used_tokens_today = 0
        self.last_refill = time.monotonic()
        self.day_start = time.time()
        self.exact_remaining_override: Optional[int] = None

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_rate = self.rpm_limit / 60.0
        self.tokens = min(float(self.rpm_limit), self.tokens + elapsed * refill_rate)
        self.last_refill = now

        # بازنشانی سهمیه روزانه پس از ۲۴ ساعت
        if time.time() - self.day_start >= 86400:
            self.used_tokens_today = 0
            self.day_start = time.time()

    def can_proceed(self, estimated_tokens: int = 500) -> bool:
        self._refill()
        if self.used_tokens_today + estimated_tokens > self.daily_token_limit:
            return False
        if self.exact_remaining_override is not None and self.exact_remaining_override <= 0:
            return False
        return self.tokens >= 1.0

    def consume(self, actual_tokens: int, provider_reported_remaining: Optional[int] = None) -> None:
        self._refill()
        self.tokens = max(0.0, self.tokens - 1.0)
        self.used_tokens_today += max(0, actual_tokens)
        if provider_reported_remaining is not None:
            self.exact_remaining_override = provider_reported_remaining


@dataclass
class GatewayResponse:
    """ساختار استاندارد خروجی درگاه برای تمام مدل‌ها"""
    success: bool
    content: str
    provider_used: str
    model_used: str
    tokens_used: int
    quota_source: QuotaSourceType
    latency_ms: float
    fallback_triggered: bool = False
    attempted_providers: List[str] = field(default_factory=list)
    error_details: Optional[str] = None


class BaseAIProvider:
    """کلاس پایه برای اتصال مستقیم HTTP به ارائه‌دهندگان هوش مصنوعی"""

    def __init__( self, name: str, api_key_env: str, rpm_limit: int, daily_token_limit: int, models_by_complexity: Dict[TaskComplexity, str], ):
        self.name = name
        self.api_key_env = api_key_env
        self.limiter = TokenBucketRateLimiter(rpm_limit, daily_token_limit)
        self.models_by_complexity = models_by_complexity
        self.last_error: Optional[str] = None
        self.cooldown_until: float = 0.0

    def get_api_key(self, user_supplied_key: Optional[str] = None) -> Optional[str]:
        """پشتیبانی هم‌زمان از کلید شخصی کاربر (BYOK) و کلید محیطی سامانه"""
        if user_supplied_key and user_supplied_key.strip():
            return user_supplied_key.strip()
        return os.environ.get(self.api_key_env)

    def is_healthy(self, user_key: Optional[str] = None) -> bool:
        if time.time() < self.cooldown_until:
            return False
        if not self.get_api_key(user_key):
            return False
        return self.limiter.can_proceed()

    def get_quota_status(self, user_key: Optional[str] = None) -> QuotaStatus:
        self.limiter._refill()
        source = (
            QuotaSourceType.EXACT_PROVIDER_HEADER
            if self.limiter.exact_remaining_override is not None
            else QuotaSourceType.ESTIMATED_LOCAL
        )
        remaining_req = (
            float(self.limiter.exact_remaining_override)
            if self.limiter.exact_remaining_override is not None
            else round(self.limiter.tokens, 2)
        )
        return QuotaStatus(
            provider_name=self.name,
            requests_per_minute_limit=self.limiter.rpm_limit,
            daily_token_limit=self.limiter.daily_token_limit,
            used_tokens_today=self.limiter.used_tokens_today,
            remaining_requests_window=remaining_req,
            source_type=source,
            is_available=self.is_healthy(user_key),
            last_error=self.last_error,
        )

    def call_api( self, prompt: str, complexity: TaskComplexity = TaskComplexity.MODERATE, system_instruction: str = "", user_key: Optional[str] = None, ) -> GatewayResponse:
        raise NotImplementedError


class GeminiProvider(BaseAIProvider):
    """اتصال مستقیم به Google AI Studio (سهمیه رایگان قانونی مدل‌های Gemini)"""

    def __init__(self):
        super().__init__(
            name="Google_Gemini",
            api_key_env="GEMINI_API_KEY",
            rpm_limit=15,
            daily_token_limit=1_000_000,
            models_by_complexity={
                TaskComplexity.SIMPLE: "gemini-1.5-flash",
                TaskComplexity.MODERATE: "gemini-1.5-flash",
                TaskComplexity.COMPLEX: "gemini-1.5-pro",
            },
        )

    def call_api( self, prompt: str, complexity: TaskComplexity = TaskComplexity.MODERATE, system_instruction: str = "", user_key: Optional[str] = None, ) -> GatewayResponse:
        api_key = self.get_api_key(user_key)
        model = self.models_by_complexity.get(complexity, "gemini-1.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        start_ts = time.perf_counter()
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw_body = resp.read().decode("utf-8")
                data = json.loads(raw_body)
                latency = (time.perf_counter() - start_ts) * 1000.0

                candidates = data.get("candidates", [])
                text = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)

                usage = data.get("usageMetadata", {})
                total_tokens = int(usage.get("totalTokenCount", len(prompt) // 4 + len(text) // 4))
                self.limiter.consume(total_tokens)
                self.last_error = None

                return GatewayResponse(
                    success=True,
                    content=text,
                    provider_used=self.name,
                    model_used=model,
                    tokens_used=total_tokens,
                    quota_source=QuotaSourceType.ESTIMATED_LOCAL,
                    latency_ms=round(latency, 2),
                )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self.cooldown_until = time.time() + 60.0
            self.last_error = f"HTTP {e.code}: {e.reason}"
            return GatewayResponse(
                success=False,
                content="",
                provider_used=self.name,
                model_used=model,
                tokens_used=0,
                quota_source=QuotaSourceType.ESTIMATED_LOCAL,
                latency_ms=round((time.perf_counter() - start_ts) * 1000.0, 2),
                error_details=self.last_error,
            )
        except Exception as e:
            self.last_error = str(e)
            return GatewayResponse(
                success=False,
                content="",
                provider_used=self.name,
                model_used=model,
                tokens_used=0,
                quota_source=QuotaSourceType.ESTIMATED_LOCAL,
                latency_ms=round((time.perf_counter() - start_ts) * 1000.0, 2),
                error_details=self.last_error,
            )


class OpenAICompatibleProvider(BaseAIProvider):
    """ کلاس استاندارد برای سرویس‌های منطبق با ساختار OpenAI مانند Groq Cloud و مدل‌های رایگان OpenRouter """

    def __init__( self, name: str, api_key_env: str, base_url: str, rpm_limit: int, daily_token_limit: int, models_by_complexity: Dict[TaskComplexity, str], ):
        super().__init__(name, api_key_env, rpm_limit, daily_token_limit, models_by_complexity)
        self.base_url = base_url

    def call_api( self, prompt: str, complexity: TaskComplexity = TaskComplexity.MODERATE, system_instruction: str = "", user_key: Optional[str] = None, ) -> GatewayResponse:
        api_key = self.get_api_key(user_key)
        model = self.models_by_complexity[complexity]

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model, "messages": messages}
        start_ts = time.perf_counter()

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Adaptive-MultiAgent-Orchestrator/0.1",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw_body = resp.read().decode("utf-8")
                data = json.loads(raw_body)
                latency = (time.perf_counter() - start_ts) * 1000.0

                # بررسی هدرهای رسمی سهمیه در صورت وجود
                rem_header = resp.headers.get("x-ratelimit-remaining-requests")
                reported_rem = int(rem_header) if rem_header and rem_header.isdigit() else None
                q_source = (
                    QuotaSourceType.EXACT_PROVIDER_HEADER
                    if reported_rem is not None
                    else QuotaSourceType.ESTIMATED_LOCAL
                )

                choices = data.get("choices", [])
                text = choices[0].get("message", {}).get("content", "") if choices else ""
                usage = data.get("usage", {})
                total_tokens = int(usage.get("total_tokens", len(prompt) // 4 + len(text) // 4))

                self.limiter.consume(total_tokens, provider_reported_remaining=reported_rem)
                self.last_error = None

                return GatewayResponse(
                    success=True,
                    content=text,
                    provider_used=self.name,
                    model_used=model,
                    tokens_used=total_tokens,
                    quota_source=q_source,
                    latency_ms=round(latency, 2),
                )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self.cooldown_until = time.time() + 60.0
            self.last_error = f"HTTP {e.code}: {e.reason}"
            return GatewayResponse(
                success=False,
                content="",
                provider_used=self.name,
                model_used=model,
                tokens_used=0,
                quota_source=QuotaSourceType.ESTIMATED_LOCAL,
                latency_ms=round((time.perf_counter() - start_ts) * 1000.0, 2),
                error_details=self.last_error,
            )
        except Exception as e:
            self.last_error = str(e)
            return GatewayResponse(
                success=False,
                content="",
                provider_used=self.name,
                model_used=model,
                tokens_used=0,
                quota_source=QuotaSourceType.ESTIMATED_LOCAL,
                latency_ms=round((time.perf_counter() - start_ts) * 1000.0, 2),
                error_details=self.last_error,
            )


class SmartRouterGateway:
    """ مسیریاب هوشمند مرکزی با قابلیت جابه‌جایی خودکار (Failover) بین سرویس‌های دارای سهمیه رایگان مجاز """

    def __init__(self):
        self.providers: List[BaseAIProvider] = [
            GeminiProvider(),
            OpenAICompatibleProvider(
                name="Groq_Cloud",
                api_key_env="GROQ_API_KEY",
                base_url="https://api.groq.com/openai/v1/chat/completions",
                rpm_limit=30,
                daily_token_limit=500_000,
                models_by_complexity={
                    TaskComplexity.SIMPLE: "llama-3.1-8b-instant",
                    TaskComplexity.MODERATE: "llama-3.3-70b-versatile",
                    TaskComplexity.COMPLEX: "llama-3.3-70b-versatile",
                },
            ),
            OpenAICompatibleProvider(
                name="OpenRouter_Free",
                api_key_env="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1/chat/completions",
                rpm_limit=20,
                daily_token_limit=200_000,
                models_by_complexity={
                    TaskComplexity.SIMPLE: "meta-llama/llama-3.1-8b-instruct:free",
                    TaskComplexity.MODERATE: "meta-llama/llama-3.1-8b-instruct:free",
                    TaskComplexity.COMPLEX: "google/gemma-2-9b-it:free",
                },
            ),
        ]

    def get_all_quotas(self, user_keys: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """گزارش شفاف وضعیت سهمیه‌ها برای نمایش در داشبورد"""
        user_keys = user_keys or {}
        report = []
        for p in self.providers:
            status = p.get_quota_status(user_keys.get(p.name))
            report.append({
                "provider": status.provider_name,
                "available": status.is_available,
                "remaining_requests_in_minute": status.remaining_requests_window,
                "used_tokens_today": status.used_tokens_today,
                "daily_token_limit": status.daily_token_limit,
                "quota_precision": status.source_type.value,
                "last_error": status.last_error,
            })
        return report

    def dispatch( self, prompt: str, complexity: TaskComplexity = TaskComplexity.MODERATE, system_instruction: str = "", user_keys: Optional[Dict[str, str]] = None, ) -> GatewayResponse:
        """ ارسال هوشمند درخواست به بهترین سرویس در دسترس و سوییچ خودکار به سرویس بعدی در صورت اتمام سهمیه یا بروز خطا """
        user_keys = user_keys or {}
        attempted: List[str] = []
        errors: List[str] = []

        # برای کارهای ساده، ابتدا سریع‌ترین سرویس (Groq) و برای کارهای پیچیده، دقیق‌ترین (Gemini) اولویت می‌گیرد
        ordered_providers = list(self.providers)
        if complexity == TaskComplexity.SIMPLE:
            ordered_providers.sort(key=lambda x: 0 if x.name == "Groq_Cloud" else 1)

        for provider in ordered_providers:
            u_key = user_keys.get(provider.name)
            if not provider.is_healthy(u_key):
                continue

            attempted.append(provider.name)
            res = provider.call_api(
                prompt=prompt,
                complexity=complexity,
                system_instruction=system_instruction,
                user_key=u_key,
            )

            if res.success:
                res.attempted_providers = attempted
                res.fallback_triggered = len(attempted) > 1
                return res

            errors.append(f"{provider.name}: {res.error_details}")

        return GatewayResponse(
            success=False,
            content="",
            provider_used="None",
            model_used="None",
            tokens_used=0,
            quota_source=QuotaSourceType.ESTIMATED_LOCAL,
            latency_ms=0.0,
            fallback_triggered=len(attempted) > 1,
            attempted_providers=attempted,
            error_details=" | ".join(errors) if errors else "هیچ کلید فعالی یافت نشد یا سهمیه تمام سرویس‌ها به پایان رسیده است.",
        )


if __name__ == "__main__":
    # اجرای آزمایشی وضعیت سهمیه‌ها بدون نیاز به کلید
    gateway = SmartRouterGateway()
    print("=== گزارش وضعیت درگاه و سهمیه سرویس‌ها ===")
    print(json.dumps(gateway.get_all_quotas(), indent=2, ensure_ascii=False))