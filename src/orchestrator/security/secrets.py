"""Secure API Key Validation and Secret Storage (Point 12.1, 12.2)."""
import os
import stat
from pathlib import Path
from typing import Dict

class SecretValidationError(ValueError):
    pass

def validate_api_key(key_name: str, value: str) -> str:
    """Validate API key length, forbid newlines and control characters."""
    if value is None:
        return ""
    if "\n" in value or "\r" in value or "\0" in value:
        raise SecretValidationError(f"Secret '{key_name}' contains forbidden newline or null characters.")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise SecretValidationError(f"Secret '{key_name}' contains control characters.")
    cleaned = value.strip()
    if len(cleaned) > 512:
        raise SecretValidationError(f"Secret '{key_name}' exceeds maximum allowed length (512).")
    return cleaned

def write_env_securely(env_path: Path, updates: Dict[str, str]):
    """Write .env for local development only with strict 0600 permissions."""
    validated_updates: Dict[str, str] = {}
    for k, v in updates.items():
        validated_updates[k] = validate_api_key(k, v)
        os.environ[k] = validated_updates[k]

    existing_lines = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    new_lines = []
    handled = set()
    for line in existing_lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in validated_updates:
                new_lines.append(f"{k}={validated_updates[k]}")
                handled.add(k)
                continue
        new_lines.append(line)

    for k, v in validated_updates.items():
        if k not in handled:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    try:
        os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 permissions
    except Exception:
        pass
