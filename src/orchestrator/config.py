"""Global Configuration for Adaptive AI Orchestrator (v0.2.0).
Replaces unbounded concurrency with Adaptive Controlled Concurrency,
strict resource/input limits, and secure default local binding (127.0.0.1).
"""
import os
import secrets
from typing import Optional

class Settings:
    def __init__(self):
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.timezone: str = "UTC"

        # 11.2 Secure Server Binding (Default 127.0.0.1 instead of 0.0.0.0)
        self.host: str = os.getenv("HOST", "127.0.0.1")
        self.port: int = int(os.getenv("PORT", "8000"))

        # 2.1 Adaptive Controlled Concurrency (No unbounded 0)
        self.min_workers: int = max(1, int(os.getenv("MIN_WORKERS", "2")))
        self.default_workers: int = max(self.min_workers, int(os.getenv("DEFAULT_WORKERS", "5")))
        self.max_workers: int = max(self.default_workers, int(os.getenv("MAX_WORKERS", "12")))
        self.max_queue_size: int = max(1, int(os.getenv("MAX_QUEUE_SIZE", "100")))
        self.max_tasks_per_user: int = max(1, int(os.getenv("MAX_TASKS_PER_USER", "10")))

        # 2.3 & 13 Resource & Input Guardrails
        self.max_file_size_bytes: int = int(os.getenv("MAX_FILE_SIZE", str(25 * 1024 * 1024)))  # 25 MB
        self.max_prompt_length: int = int(os.getenv("MAX_PROMPT_LENGTH", "32000"))
        self.max_file_count: int = int(os.getenv("MAX_FILE_COUNT", "5"))
        self.max_pdf_pages: int = int(os.getenv("MAX_PDF_PAGES", "200"))
        self.max_video_duration_sec: int = int(os.getenv("MAX_VIDEO_DURATION", "7200"))
        self.max_base64_length: int = int(os.getenv("MAX_BASE64_LENGTH", str(35 * 1024 * 1024)))
        self.max_output_size_bytes: int = int(os.getenv("MAX_OUTPUT_SIZE", str(10 * 1024 * 1024)))
        self.max_tokens_per_task: int = int(os.getenv("MAX_TOKENS_PER_TASK", "16384"))
        self.max_retries_per_item: int = int(os.getenv("MAX_RETRIES", "3"))
        self.default_execution_timeout_seconds: int = int(os.getenv("DEFAULT_EXECUTION_TIMEOUT_SECONDS", "120"))
        self.default_lease_seconds: int = int(os.getenv("DEFAULT_LEASE_SECONDS", "60"))

        # 20.3 Memory Retention Guardrails
        self.max_in_memory_events: int = int(os.getenv("MAX_IN_MEMORY_EVENTS", "5000"))
        self.event_retention_days: int = int(os.getenv("EVENT_RETENTION_DAYS", "30"))

        # 18 Simulation Policy: In production, disallow fake responses if no real provider is active
        self.allow_simulation_fallback: bool = (
            os.getenv("ALLOW_SIMULATION_FALLBACK", "true" if self.environment != "production" else "false").lower() == "true"
        )

        # 11.1 Local API Authentication Token
        self.api_auth_token: str = os.getenv("ORCHESTRATOR_AUTH_TOKEN", "")
        self.require_auth: bool = os.getenv("REQUIRE_AUTH", "true" if self.environment == "production" else "false").lower() == "true"

        # Provider Credentials (injected via environment / secret manager)
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
        self.huggingface_api_key: Optional[str] = os.getenv("HUGGINGFACE_API_KEY")
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

settings = Settings()
