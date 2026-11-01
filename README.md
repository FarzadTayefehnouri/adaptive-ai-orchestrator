# Adaptive AI Orchestrator (v0.2.0)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

An adaptive, work-item-based multi-agent orchestration framework written in Python. Rather than relying on unbounded concurrency, the orchestrator decomposes complex tasks (including multi-modal files and variable-complexity video streams) into portable `WorkItem` units scheduled across a bounded, elastic `WorkerPool` with capability matching, checkpointed leases, work stealing, and atomic quota reservations.

## Architecture Overview (v0.2.0)

```text
User / API Request
        ↓
Input Validation & Prompt Injection Guard (SSRF / ZipBomb / Size Checks)
        ↓
Adaptive Chunker (Horizontal Time Chunks + Vertical Stage Decomposition)
        ↓
Portable WorkItems  ──►  Bounded Priority Queue (MAX_QUEUE_SIZE=100)
                                ↓
               Adaptive Scheduler & Capability Matcher
        (MIN_WORKERS=2 .. DEFAULT_WORKERS=5 .. MAX_WORKERS=12)
                                ↓
     Atomic Quota Reservation (reserve ──► generate ──► commit / release)
                                ↓
   Checkpoints, 60s Leases, Heartbeats, Work Stealing & Urgent Preemption
                                ↓
     Format-Aware Critic Validation (JSON / Python AST / CSV / Markdown)
                                ↓
       Temporal & Semantic Merger  ──►  Versioned Artifact Store
```

## Implementation Status Matrix (Point 30)

To maintain engineering transparency, each architectural capability is labeled with its exact current verification state:

| Capability / Subsystem | Status | Notes & Scope |
| :--- | :--- | :--- |
| **Single Canonical Package (`src/orchestrator/`)** | **Implemented** | `orchestrator_unified.py` is now a thin wrapper around `src/orchestrator/api/app.py`. |
| **Bounded Elastic Worker Pool & Priority Queue** | **Implemented** | Scales between `MIN_WORKERS=2` and `MAX_WORKERS=12` with `MAX_QUEUE_SIZE=100`. |
| **WorkItem State Machine (`WorkStatus`)** | **Implemented** | Strict 12-state enum with validated transitions and full audit history. |
| **Checkpoints, 60s Leases, Heartbeats & Work Stealing** | **Implemented** | Supports lease expiration recovery, safe work stealing, and urgent preemption. |
| **Adaptive Video Decomposition (`workflow/chunker.py`)** | **Experimental** | Heuristic complexity scoring (2m/4m/10m/15m chunks) + horizontal/vertical DAG generation. |
| **Multi-Provider Routing & Standardized Exceptions** | **Implemented** | Separate `Provider` classes (`Gemini`, `Groq`, `OpenAI`, `Anthropic`, `Ollama`) + `ModelSpec`. |
| **Atomic Quota Reservation (`reserve`/`commit`/`release`)** | **Implemented** | Protected by `asyncio.Lock` with explicit `QuotaSource` (`ESTIMATED`, `USER_CONFIGURED`, etc.). |
| **Real-Time Provider Quota Discovery via Headers** | **Partial** | Tracks configured/estimated ledgers locally; live header parsing is best-effort per provider. |
| **PDF Character/Image Ratio & Magic-Bytes Classifier** | **Partial** | Heuristic PDF stream character/page/image counting with confidence scores + magic bytes. |
| **DAG Cycle Detection & Multi-Root-Cause Recovery** | **Implemented** | In-memory DAG cycle prevention + ancestor confidence ranking and selective rerun. |
| **Security Guards (Auth, CSP, XSS, SSRF, Secret Masking)** | **Implemented** | Default `127.0.0.1` bind, CSP headers, DOM escaping, SSRF IP checks, `0600` `.env` mode. |
| **Community Release Gate (`>80%` Voting Policy)** | **Planned Policy** | Current GitHub Action validates numerical thresholds; cryptographic voter identity is planned. |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the full 5-suite verification tests
python run_tests.py

# 3. Start the local supervisor server (binds to 127.0.0.1:8000 by default)
python orchestrator_unified.py
# Or via CLI:
python -m src.orchestrator.cli serve
```

---

# نسخه فارسی (Persian Overview)

سامانه هماهنگ‌کننده چندعاملی تطبیق‌پذیر (نسخه `v0.2.0`) بر پایه **تقسیم هوشمند کار به `WorkItem`های مستقل، زمان‌بندی تطبیقی و کنترل‌شده (`WorkerPool`)، تطبیق قابلیت‌ها (`Capability Matching`)، ذخیره وضعیت میانی (`Checkpoint & Lease`) و جابه‌جایی ایمن وظایف بین عامل‌ها و ارائه‌دهندگان** طراحی شده است:

- **مرجع واحد کد (`src/orchestrator/`):** تمامی منطق در پکیج ماژولار قرار دارد و فایل `orchestrator_unified.py` صرفاً یک راه‌انداز سبک (Thin Wrapper) است.
- **همزمانی کنترل‌شده به جای همزمانی رها:** صف اولویت‌دار با ظرفیت مشخص (`MAX_QUEUE_SIZE=100`) و استخر کارگران پویا (`MIN_WORKERS=2` تا `MAX_WORKERS=12`).
- **تقسیم افقی، عمودی و تطبیقی ویدئو و وظایف:** شکستن بخش‌های پرتحرک یا چندزبانه به قطعات کوتاه (۲ تا ۴ دقیقه) و بخش‌های ساده به قطعات بلندتر (۱۰ تا ۱۵ دقیقه).
- **امنیت و شفافیت:** اتصال پیش‌فرض روی `127.0.0.1`، محافظت در برابر XSS و SSRF، جداسازی صریح حالت `simulation` از `live_api`، و رزرو اتمیک سهمیه پیش از اجرا.

## Secure deployment

For secure local or production configuration, see [docs/FINAL_SECURITY_RUN_FA.md](docs/FINAL_SECURITY_RUN_FA.md). Production mode requires API authentication by default. Sensitive legacy dashboard routes are protected by the same token dependency as the versioned API.
