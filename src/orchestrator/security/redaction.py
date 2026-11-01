"""Secret Masking and Log Redaction (Point 12.2 & 29)."""
import re
from typing import Any, Dict

SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(gsk_[0-9A-Za-z]{20,})"),
    re.compile(r"(sk-[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(hf_[0-9A-Za-z]{20,})"),
]

def mask_secret(value: str) -> str:
    if not value or len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-3:]}"

def redact_text(text: str) -> str:
    if not text:
        return text
    redacted = text
    for pat in SECRET_PATTERNS:
        redacted = pat.sub("[REDACTED_SECRET]", redacted)
    return redacted

def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for k, v in data.items():
        if any(sk in k.lower() for sk in ("key", "secret", "token", "password", "authorization")):
            clean[k] = "***REDACTED***"
        elif isinstance(v, str):
            clean[k] = redact_text(v)
        elif isinstance(v, dict):
            clean[k] = redact_dict(v)
        else:
            clean[k] = v
    return clean
