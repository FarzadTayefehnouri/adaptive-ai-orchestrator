"""Global configuration and environment settings."""
import os

class Settings:
    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.timezone = os.getenv("TIMEZONE", "UTC")
        self.max_parallel_agents = int(os.getenv("MAX_PARALLEL_AGENTS", "5"))
        self.default_execution_timeout_seconds = int(os.getenv("DEFAULT_EXECUTION_TIMEOUT_SECONDS", "120"))
        self.strict_validation_enabled = os.getenv("STRICT_VALIDATION_ENABLED", "true").lower() == "true"
        
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

settings = Settings()
