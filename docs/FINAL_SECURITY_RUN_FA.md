# راهنمای اجرای امن نسخه نهایی

## اجرای محلی

برای استفاده محلی، سرور به‌صورت پیش‌فرض روی `127.0.0.1` اجرا می‌شود. برای ایجاد token امن:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

سپس در فایل `.env` قرار بده:

```env
ENVIRONMENT=development
HOST=127.0.0.1
REQUIRE_AUTH=true
ORCHESTRATOR_AUTH_TOKEN=توکن_تولیدشده
```

درخواست‌های API حساس باید هدر زیر را داشته باشند:

```http
Authorization: Bearer <token>
```

## اجرای production

در محیط production احراز هویت به‌صورت پیش‌فرض اجباری است. هرگز سرور را بدون HTTPS و reverse proxy روی اینترنت منتشر نکن. همچنین `OLLAMA_BASE_URL` و سایر URLهای provider باید با allowlist و سیاست شبکه مناسب محدود شوند.

## بررسی نهایی

```bash
python3 run_tests.py
```

انتظار می‌رود ۴۱ تست با وضعیت `OK` اجرا شوند.
