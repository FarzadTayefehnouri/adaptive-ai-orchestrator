# Security Policy & Threat Model (v0.2.0)

## 1. Protected Assets
- **API Credentials (`GEMINI_API_KEY`, `GROQ_API_KEY`, etc.)**: Validated against control/newline injection, masked in logs, stored locally with `0600` permissions when using `.env`.
- **User Prompts & Uploaded Files**: Validated for size, Base64 bounds, and ZIP compression ratios prior to processing; isolated from system instructions using `<UNTRUSTED_FILE_DATA>` delimiters.
- **Validated Outputs, Checkpoints & Artifacts**: Stored with SHA-256 integrity hashes and immutable version history (`supersedes_id`).
- **SQLite State & Audit Logs**: Protected against secret leakage via automated regex redaction.

## 2. Threat Actors
- **Unauthenticated Network Actor**: Prevented by default `127.0.0.1` binding and optional Bearer Token / RBAC enforcement (`REQUIRE_AUTH=true`).
- **Malicious File / Archive Uploader**: Mitigated by pre-decode Base64 size checks, `MAX_FILE_SIZE` limits, and Zip-Bomb ratio inspection.
- **Prompt Injection Payload**: Mitigated by strict separation of system prompts from untrusted file streams and non-execution of generated `.py` files (`ast.parse` static syntax validation only).
- **Compromised or Unreachable External Provider**: Mitigated by per-provider `CircuitBreaker`, `TimeoutError` handling, and SSRF validation on configurable endpoints (`OLLAMA_BASE_URL`).

## 3. Threat Matrix & Mitigations

| Threat | Vector | Mitigation Implemented |
| :--- | :--- | :--- |
| **API Key Exposure** | Logs, telemetry, or `/api/settings` | Regex secret redaction (`redaction.py`), never returned in GET responses, `0600` file mode. |
| **Cross-Site Scripting (XSS)** | Malicious prompt or model output in Dashboard | `escapeHtml()` sanitization on all dynamic DOM fields + strict `Content-Security-Policy` header. |
| **Server-Side Request Forgery (SSRF)** | Custom `OLLAMA_BASE_URL` pointing to `169.254.169.254` or internal IPs | `validate_url_no_ssrf()` blocks cloud metadata endpoints and private ranges in public mode. |
| **Denial of Service (DoS) / Unbounded RAM** | Unlimited workers, huge queues, or unbounded telemetry history | Bounded `WorkerPool` (`MIN_WORKERS=2..MAX_WORKERS=12`), `MAX_QUEUE_SIZE=100`, `MAX_IN_MEMORY_EVENTS=5000`. |
| **Arbitrary Code Execution (RCE)** | Executing AI-generated `.py` deliverables | Generated `.py` files are validated via `ast.parse` only and served strictly as downloadable text. |
| **Quota Leakage on Crash** | Concurrent requests exhausting provider credits | `AtomicQuotaManager` with `asyncio.Lock` (`reserve` -> `commit` / `release`). |

## 4. External Provider Data Privacy Notice
When submitting files or prompts to external cloud providers (Gemini, Groq, OpenAI, Anthropic), payload segments are transmitted over HTTPS to the selected provider. For strictly air-gapped or confidential data, configure and select the local `ollama` provider.

## 5. Reporting a Vulnerability
Please report suspected vulnerabilities privately via **GitHub Security Advisories** on the repository.
