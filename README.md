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
