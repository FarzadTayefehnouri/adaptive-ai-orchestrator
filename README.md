Adaptive AI Orchestrator

A self-improving, fault-resilient multi-agent artificial intelligence orchestrator designed for personal empowerment and public-benefit collaboration. The system dynamically connects to multiple AI providers, maximizes free-tier allowances, performs deep multi-modal input analysis, and guarantees execution integrity through dual backward and forward error recovery.

Table of Contents

1. Core Objectives

2. Key Architectural Innovations

Intelligent Quota & Multi-Provider Routing

Deep Input Analysis

Dual Recovery Engine: Backward & Forward

Three-Tier Memory Architecture

3. Multi-Agent Architecture

4. Repository Structure

5. Getting Started & Installation

6. Governance, Provenance & Release Policy

7. Security & Secrets Management

8. License

نسخه فارسی (Persian Version)

1. Core Objectives

Public-Benefit & Self-Sustaining: Built for personal utility and open community benefit, engineered so that its ongoing vitality does not depend on the permanent involvement of a single individual.

Cost-Free Optimization: Utilizes available free-tier quotas and community credits across reputable AI providers under strict compliance with official terms of service.

Deep Content-Aware Processing: Inspects raw file content, font tables, and media streams rather than relying on superficial file extensions (e.g., distinguishing searchable text PDFs from scanned image PDFs).

Resilient Dual Recovery: Implements graph-based backward fault localization (identifying root causes) and forward selective re-execution (recomputing only affected downstream dependencies).

Evidence-Based Governance: Stable releases are strictly gated by automated technical/security audits and a verified community approval threshold strictly exceeding 80.0%.

2. Key Architectural Innovations

Intelligent Quota & Multi-Provider Routing

Quota Transparency: Distinguishes verified real-time quota data from heuristic estimates. Unreported quotas are explicitly flagged to the user.

Dynamic Failover: Automatically reroutes tasks to available fallback providers when encountering rate limits (HTTP 429) or quota exhaustion.

Complexity-Tiered Dispatching: Routes simple tasks to low-latency, lightweight models (e.g., Groq LLaMA 8B, Gemini Flash) and reserves high-capacity reasoning models (Gemini Pro, Claude 3.5 Sonnet, GPT-4o) for complex multi-step reasoning.

Deep Input Analysis

Examines binary streams across text, audio, images, video, source code, tabular datasets, and composite documents. Automatically detects scanned documents requiring multi-modal OCR versus native searchable documents.

Dual Recovery Engine: Backward & Forward

Backward Recovery (Root-Cause Isolation): Traverses the execution Directed Acyclic Graph (DAG) backwards from a point of failure to isolate the earliest faulty component, model, tool, or corrupted input.

Forward Recovery (Minimal Recomputation): Repairs the identified faulty step and topologically re-executes only its dependent downstream descendants, preserving all previously validated intermediate results.

Three-Tier Memory Architecture

Ephemeral Working Memory: Fast in-memory state tracking for active task execution.

Validated Results Store: Versioned, immutable storage of verified intermediate and final artifacts.

Empirical Experience Memory: Vectorized performance telemetry recording model reliability, recurring error patterns, and successful recovery strategies.

3. Multi-Agent Architecture

               +-------------------------------------------------+
               |                   User / Client                 |
               +-------------------------------------------------+
                                        | (Input Request & Files)
                                        v
               +-------------------------------------------------+
               |            Input Analyzer Agent                 |
               | (Deep Stream Inspection: Text/Scanned PDF, etc.)|
               +-------------------------------------------------+
                                        |
                                        v
               +-------------------------------------------------+
               |           Task Classifier Agent                 |
               |     (Complexity, Resource & DAG Planning)       |
               +-------------------------------------------------+
                                        |
                                        v
               +-------------------------------------------------+
               |             Smart Model Router                  |
               |  (Quota-Aware, Cost, Speed & Tier Selection)    |
               +-------------------------------------------------+
                                        |
                                        v
               +-------------------------------------------------+
               |           Workflow Coordinator                  |
               |       (Parallel DAG Execution Engine)           |
               +-------------------------------------------------+
                         /              |              \
                        v               v               v
                [Coding Agent]  [Data Analytics]  [Reasoning Agent]
                        \               |              /
                         v               v             v
               +-------------------------------------------------+
               |           Critic & Validator Agent              |
               |   (Factual Verification, Schema & Quality Gate) |
               +-------------------------------------------------+
                                        |
                    +-------------------+-------------------+
                    | (Validation Passed)                   | (Fault Detected)
                    v                                       v
         +--------------------+             +-------------------------------+
         | Validated Store    |             | Dual Recovery Engine          |
         | & Handoff to User  |             | (Backward DAG & Forward Plan) |
         +--------------------+             +-------------------------------+


4. Repository Structure

adaptive-ai-orchestrator/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                     # Automated testing & code verification
│   │   └── release-gate.yml           # Strict >80% approval community release gate
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md              # Categorized fault reporting (Input, Model, Tool, Agent, DAG)
│   │   └── feature_request.md         # Architecture-aligned feature request template
│   └── PULL_REQUEST_TEMPLATE.md       # Digital signature and compliance checklist
├── docs/
│   ├── architecture.md               # Detailed DAG execution lifecycle and agent behavior
│   ├── governance.md                 # Provenance, UTC versioning, and voting bylaws
│   └── requirements_fa.md            # Original 18-section foundational specification (Persian)
├── src/
│   └── orchestrator/
│       ├── __init__.py
│       ├── config.py                 # Configuration and environment loaders
│       ├── models.py                 # Pydantic schemas (Task, Step, Error, Validation)
│       ├── providers/
│       │   ├── quota_manager.py      # Real vs estimated quota tracking & failover engine
│       │   └── router.py             # Multi-tier complexity-based model router
│       ├── agents/
│       │   └── input_analyzer.py     # Binary stream analyzer (Text vs Scanned PDF)
│       ├── recovery/
│       │   └── engine.py             # Zero-dependency DAG backward and forward recovery
│       └── memory/
│           └── store.py              # Three-tier memory (Working, Validated, Experience)
├── tests/
│   ├── test_quota_manager.py         # Quota transparency & rate-limit failover tests
│   ├── test_router.py                # Model complexity routing tests
│   └── test_recovery_engine.py       # DAG back-traversal and selective forward replay tests
├── .env.example                      # Template environment variables
├── .gitignore                        # Strict secret and cache exclusions
├── pyproject.toml / requirements.txt # Standard packaging definitions
├── README.md                         # Bilingual documentation (English & Persian)
├── CONTRIBUTING.md                   # Contribution bylaws and signed commit standards
├── SECURITY.md                       # Secret segregation and responsible disclosure policy
└── LICENSE                           # Apache 2.0 Open Source License


5. Getting Started & Installation

Prerequisites

Python 3.10 or higher

Git

Installation

# 1. Clone the repository
git clone https://github.com/FarzadTayefehnouri/adaptive-ai-orchestrator.git
cd adaptive-ai-orchestrator

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment credentials
cp .env.example .env
# Edit .env to add your free-tier keys (e.g. Gemini, Groq)

# 5. Run the automated test suite
python3 -m unittest discover tests/ -v


6. Governance, Provenance & Release Policy

Original Project Creator: Farzad Tayefehnouri.

Historical Ownership: The identity of the original creator and first verified contributors remains permanent and immutable across all future releases.

Digital Signatures: All official contributions must be cryptographically signed (git commit -S) using verified GPG/SSH keys.

Strict UTC Timestamps: All releases, audit logs, and benchmark evaluations are recorded in Coordinated Universal Time (UTC) with second-level precision.

Democratic Release Gate: Promoting a release from Beta to Stable requires:

A verified community approval rate strictly greater than 80.0% (Approval > 80.0%; exactly 80.0% is insufficient).

Fulfillment of minimum statistical quorum (insufficient sample counts default to "Insufficient Evidence").

100% pass rate across automated security and technical test suites.

7. Security & Secrets Management

Complete segregation between open-source codebase and private operational data/API keys.

Secret masking in all application logs and telemetry.

Security vulnerabilities must be reported privately via GitHub Security Advisories.

8. License

Distributed under the Apache 2.0 License.
# Adaptive AI Orchestrator (سامانه هوش مصنوعی چندعاملی تطبیق‌پذیر)

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-alpha%20(v0.1.0)-orange)](#)
[![Public Benefit](https://img.shields.io/badge/initiative-Public%20Benefit%20%2F%20Open%20Source-green)](#)

سامانه هوشمند، خودبهبوددهنده و چندعاملی برای مدیریت توزیع‌شده مدل‌های هوش مصنوعی، مسیریابی بهینه سهمیه‌های رایگان، تشخیص ریشه‌ای خطاها و بازیابی هوشمند (پسرو و پیشرو).

---

## فهرست مطالب / Table of Contents
- [اهداف اصلی / Core Objectives](#اهداف-اصلی--core-objectives)
- [ویژگی‌های کلیدی / Key Features](#ویژگیهای-کلیدی--key-features)
- [معماری چندعاملی / Multi-Agent Architecture](#معماری-چندعاملی--multi-agent-architecture)
- [ساختار مخزن / Project Structure](#ساختار-مخزن--project-structure)
- [نصب و راه‌اندازی / Installation & Quickstart](#نصب-و-راهاندازی--installation--quickstart)
- [دستورالعمل ثبت در گیت‌هاب / Pushing to GitHub](#دستورالعمل-ثبت-در-گیتهاب--pushing-to-github)
- [حاکمیت و مشارکت / Governance & Contribution](#حاکمیت-و-مشارکت--governance--contribution)
- [مجوز / License](#مجوز--license)

---

## اهداف اصلی / Core Objectives
1. **عام‌المنفعه و مستقل:** طراحی شده برای استفاده شخصی و عمومی، بدون وابستگی حیاتی به حضور مداوم شخص خاص.
2. **استفاده حداکثری از سهمیه‌های رایگان:** اتصال به ارائه‌دهندگان مختلف (Google Gemini، Groq، Hugging Face، OpenAI، Anthropic، و مدل‌های محلی نظیر Ollama) با رعایت شرایط رسمی و جابه‌جایی خودکار در زمان اتمام سهمیه.
3. **تحلیل عمیق محتوا:** تشخیص ساختار واقعی ورودی (متن، صوت، تصویر، ویدئو، کد و تمایز دقیق بین PDF متنی و PDF اسکن‌شده).
4. **تشخیص و اصلاح هوشمند خطا:** بازیابی پسرو (Backward Recovery برای ریشه‌یابی) و بازیابی پیشرو (Forward Recovery برای محاسبه مجدد حداقل مراحل متأثر).
5. **ارتقای دموکراتیک و داده‌محور:** ارتقا از نسخه بتا به نسخه پایدار منوط به کسب **بیش از ۸۰٪ آرای معتبر جامعه** (نه دقیقاً ۸۰٪) به همراه قبولی در آزمون‌های امنیتی و فنی خودکار.

---

## ویژگی‌های کلیدی / Key Features

### ۱. مدیریت هوشمند مدل‌ها و سهمیه‌ها (Quota & Provider Management)
- تفکیک قطعی سهمیه واقعی از برآوردهای تخمینی با برچسب‌گذاری صریح `real` در مقابل `estimated`.
- جابه‌جایی بدون قطعی (Failover) بین سرویس‌ها هنگام مواجهه با خطای Rate Limit (`429`) یا اتمام سهمیه مجاز.
- هدایت وظایف سبک به مدل‌های سریع و کم‌هزینه و وظایف سنگین/استدلالی به مدل‌های پیشرفته.

### ۲. سازوکار بازیابی دوگانه (Dual Recovery Engine)
- **بازیابی پسرو (Backward Recovery):** پیمایش معکوس روی گراف وابستگی مراحل (DAG) برای شناسایی ریشه خطا در عامل، مدل، ابزار یا ورودی اولیه.
- **بازیابی پیشرو (Forward Recovery):** اجرای مجدد مرحله اصلاح‌شده و محاسبه مجدد *صرفاً مراحل پایین‌دستی متأثر*، بدون دور ریختن خروجی‌های معتبر قبلی.

### ۳. سطوح سه‌گانه حافظه (Three-Tier Memory Architecture)
- **حافظه موقت (Working Memory):** نگهداری وضعیت زنده اجرای تسک و داده‌های میانی در Redis/RAM.
- **حافظه نتایج معتبر (Validated Store):** کش خروجی‌های تأییدشده با شناسه یکتا و تاریخچه نسخه در PostgreSQL.
- **حافظه تجربی (Experience Memory):** ذخیره الگوهای حل موفق/ناموفق و آمار قابلیت اطمینان مدل‌ها در پایگاه برداری (pgvector/Qdrant).

---

## معماری چندعاملی / Multi-Agent Architecture

```text
               +-------------------------------------------------+
               |                   کاربر / Client                 |
               +-------------------------------------------------+
                                        | (Input Request & Files)
                                        v
               +-------------------------------------------------+
               |         عامل تحلیلگر ورودی (Input Analyzer)       |
               | (Deep Inspection: Text/Scanned PDF, Code, Media)|
               +-------------------------------------------------+
                                        |
                                        v
               +-------------------------------------------------+
               |       عامل طبقه‌بند وظیفه (Task Classifier)       |
               |     (Complexity, Resource Needs, Graph Plan)    |
               +-------------------------------------------------+
                                        |
                                        v
               +-------------------------------------------------+
               |       مسیریاب هوشمند مدل‌ها (Smart Router)        |
               |  (Quota-Aware, Cost, Speed, Tier Optimization)  |
               +-------------------------------------------------+
                                        |
                                        v
               +-------------------------------------------------+
               |     هماهنگ‌کننده اجرا (Workflow Orchestrator)     |
               |       (Parallel DAG Execution, State Mgmt)       |
               +-------------------------------------------------+
                         /              |              \
                        v               v               v
                [عامل کدنویسی]   [عامل تحلیل داده]   [عامل استنتاج]
                        \               |              /
                         v               v             v
               +-------------------------------------------------+
               |      عامل اعتبارسنج و منتقد (Critic & Validator) |
               |     (Fact Check, Quality Score, Schema Check)   |
               +-------------------------------------------------+
                                        |
                    +-------------------+-------------------+
                    | (Valid Output)                        | (Detected Fault)
                    v                                       v
         +--------------------+             +-------------------------------+
         | حافظه نتایج معتبر |             | عامل بازیابی و ترمیم (Recovery) |
         |   & تحویل به کاربر |             | (Backward Diagnosis & Forward) |
         +--------------------+             +-------------------------------+
```

---

## ساختار مخزن / Project Structure

```
adaptive-ai-orchestrator/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                 # Automated testing, linting, commit signing verification
│   │   └── release-gate.yml       # >80% community approval rule & automated gate
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── architecture.md           # تفکیک دقیق لایه‌ها و رفتار عامل‌ها
│   ├── governance.md             # خط‌مشی حاکمیت، ثبت UTC و حفظ مالکیت تاریخی
│   └── requirements_fa.md        # سند جامع ۱۸ بندی نیازمندی‌ها (اصلی)
├── src/
│   └── orchestrator/
│       ├── __init__.py
│       ├── config.py             # تنظیمات و متغیرهای محیطی
│       ├── models.py             # ساختار داده‌های استاندارد (تسک‌ها، مراحل، خطاها)
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py           # کلاس پایه عامل‌ها
│       │   ├── input_analyzer.py # تحلیلگر قالب واقعی ورودی‌ها
│       │   ├── task_classifier.py# طبقه‌بندی پیچیدگی و منابع
│       │   ├── critic.py         # منتقد و اعتبارسنج خروجی
│       │   └── observer.py       # ناظر سلامت و تشخیص خطا
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py           # رابط اتصالات مدل‌ها
│       │   ├── quota_manager.py  # ردیابی سهمیه واقعی vs تخمینی و مدیریت جابه‌جایی
│       │   └── router.py         # مسیریابی چندمعیاره مدل
│       ├── recovery/
│       │   ├── __init__.py
│       │   └── engine.py         # موتور بازیابی پسرو و پیشرو (DAG مبتنی بر گراف)
│       └── memory/
│           ├── __init__.py
│           └── store.py          # لایه‌های سه‌گانه حافظه
├── tests/
│   ├── __init__.py
│   ├── test_quota_manager.py     # آزمون تفکیک سهمیه و جابه‌جایی خودکار
│   ├── test_router.py            # آزمون انتخاب بهینه مدل بر اساس پیچیدگی
│   └── test_recovery_engine.py   # آزمون ریشه‌یابی معکوس و اجرای مجدد پیشرو
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── CONTRIBUTING.md
├── SECURITY.md
└── LICENSE
```

---

## نصب و راه‌اندازی / Installation & Quickstart

### پیش‌نیازها
- Python 3.10 یا بالاتر
- Git

### مراحل نصب
```bash
# ۱. شبیه‌سازی مخزن یا دریافت کد
git clone https://github.com/FarzadTayefehnouri/adaptive-ai-orchestrator.git
cd adaptive-ai-orchestrator

# ۲. ایجاد محیط مجازی پایتون
python3 -m venv venv
source venv/bin/activate  # در ویندوز: venv\Scripts\activate

# ۳. نصب وابستگی‌ها
pip install -r requirements.txt

# ۴. تنظیم متغیرهای محیطی
cp .env.example .env
# کلیدهای مجاز API خود را در .env قرار دهید

# ۵. اجرای آزمون‌های خودکار
pytest tests/ -v
# یا بدون نیاز به پکیج خارجی:
python3 -m unittest discover tests/
```

---

## دستورالعمل ثبت در گیت‌هاب / Pushing to GitHub
برای انتقال این پروژه به مخزن گیت‌هاب خود:

```bash
# ۱. وارد پوشه پروژه شوید
cd adaptive-ai-orchestrator

# ۲. مقداردهی اولیه Git
git init
git checkout -b main

# ۳. افزودن فایل‌ها و ثبت کامیت اولیه
git add .
git commit -S -m "feat: initial release v0.1.0-alpha architecture and core scaffolding"

# ۴. متصل کردن به مخزن در گیت‌هاب
git remote add origin https://github.com/FarzadTayefehnouri/adaptive-ai-orchestrator.git

# ۵. انتشار در مخزن
git push -u origin main --force
```

---

## حاکمیت و مشارکت / Governance & Contribution
این پروژه بر مبنای شفافیت کامل، حسابرسی‌پذیری و حفظ سابقه تاریخی مشارکت‌ها اداره می‌شود:
- **خالق اولیه پروژه:** فرزاد طایفه نوری (Farzad Tayefehnouri)
- تمامی مشارکت‌ها ملزم به داشتن هویت پایدار و امضای دیجیتال Commit هستند.
- زمان تمامی رخدادها و تغییرات بر مبنای استاندارد **UTC با دقت ثانیه** ثبت می‌گردد.
- جزئیات دقیق قوانین در فایل‌های [CONTRIBUTING.md](CONTRIBUTING.md) و [docs/governance.md](docs/governance.md) آمده است.

---

## مجوز / License
این پروژه تحت مجوز [Apache 2.0](LICENSE) منتشر شده است.
