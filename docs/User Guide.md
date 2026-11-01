# User Guide — Adaptive AI Orchestrator

Comprehensive end-to-end user guide for installing, configuring, running, monitoring, and downloading AI-generated deliverables (available in English and Persian).

---

# Part 1: English Version

## 1. Prerequisites
1. **Python 3.10 or higher** installed ([Download from Python.org](https://www.python.org/downloads/)).
2. **At least one free AI provider API key**:
   - Free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/)
   - Or free and ultra-fast Groq API key from [Groq Console](https://console.groq.com/)
   - *(Optional)* [Ollama](https://ollama.com/) for 100% offline local models without internet or keys.

---

## 2. Download the Repository
* **Simple Method (No Git needed):**
  1. Navigate to the repository [FarzadTayefehnouri/adaptive-ai-orchestrator](https://github.com/FarzadTayefehnouri/adaptive-ai-orchestrator).
  2. Click the green **Code** button and select **Download ZIP** (or download the latest release from the Releases section).
  3. Extract the ZIP file to your preferred folder.
* **Using Git (in terminal):**
  ```bash
  git clone https://github.com/FarzadTayefehnouri/adaptive-ai-orchestrator.git
  cd adaptive-ai-orchestrator
  ```

---

## 3. One-Click Launch
No complicated commands are needed:
* **On Windows:** Double-click **`run.bat`**.
* **On macOS / Linux:** Open a terminal in the project directory and run:
  ```bash
  bash run.sh
  ```

The launcher script automatically creates and activates the Python virtual environment, verifies dependencies, starts the local server on `http://127.0.0.1:8000`, and automatically opens your web browser.

---

## 4. Setup via Web Dashboard (No Code Editing)
Once the dashboard opens in your browser:
1. Click the blue **"⚙️ Settings"** button in the header.
2. Paste your free Gemini or Groq API key into the input field and click **Save** (it will be saved securely to `.env`).
3. Click **"🔔 Enable Notifications"** to allow audio chimes and OS desktop alerts when tasks complete.

---

## 5. Submitting Tasks & Processing Files
In the task submission card at the top of the dashboard:
1. **Prompt:** Enter your question, coding request, or document analysis instruction.
2. **Attach File (Optional):** Attach any multi-modal file (text, audio, image, video, Python code, or scanned/text PDF). The system performs deep binary magic-bytes inspection.
3. **Select Deliverable Format:** Choose `.md` (Markdown report), `.txt` (plain text), `.py` (Python code), or `.json` (structured data).
4. Click **"🚀 Run Task"**.

---

## 6. Live Monitoring & Multitasking
* **Live Timeline:** Watch real-time execution steps, model assignments, and critic validations.
* **Mini-Widget Mode:** Click **"⤢ Mini-Widget Mode"** to shrink the dashboard into a compact corner widget so you can multitask while keeping an eye on progress.
* **Human-in-the-Loop:** Pause, resume, or manually override models on the fly.

---

## 7. Automatic Notifications & File Download
When the critic agent validates the output:
1. An audio chime plays and a desktop notification appears.
2. The deliverable is listed under **"📦 Finalized Deliverables"**.
3. Click **"📥 Download File"** to save the clean deliverable file directly to your computer.
4. Click **"📥 Export Audit Report"** to export an auditable execution report with UTC timestamps.

---

## 8. Stopping the Orchestrator
Press **`Ctrl + C`** in the terminal window to safely stop the server.

---
---

# بخش دوم: نسخه فارسی

## ۱. پیش‌نیازها
1. **پایتون ۳.۱۰ یا بالاتر** روی سیستم شما نصب باشد ([دانلود از Python.org](https://www.python.org/downloads/)).
2. **یک کلید API رایگان** از ارائه‌دهندگان هوش مصنوعی:
   - دریافت کلید رایگان Google Gemini از [Google AI Studio](https://aistudio.google.com/)
   - یا دریافت کلید رایگان و پرسرعت Groq از [Groq Console](https://console.groq.com/)
   - *(اختیاری)* اگر تمایل به اجرای کاملاً آفلاین دارید، نرم‌افزار [Ollama](https://ollama.com/) را نصب و اجرا کنید (بدون نیاز به اینترنت یا کلید).

---

## ۲. دریافت و دانلود پروژه
* **روش ساده (بدون نیاز به گیت):**
  1. به صفحه مخزن [FarzadTayefehnouri/adaptive-ai-orchestrator](https://github.com/FarzadTayefehnouri/adaptive-ai-orchestrator) بروید.
  2. روی دکمه سبز **Code** کلیک کرده و گزینه **Download ZIP** را بزنید (یا از بخش Releases آخرین نسخه را دانلود کنید).
  3. فایل فشرده را در پوشه‌ای دلخواه استخراج (Extract) کنید.
* **روش با گیت (در ترمینال):**
  ```bash
  git clone https://github.com/FarzadTayefehnouri/adaptive-ai-orchestrator.git
  cd adaptive-ai-orchestrator
  ```

---

## ۳. راه‌اندازی با یک کلیک
نیازی به نوشتن هیچ دستور پیچیده‌ای نیست:
* **در ویندوز:** روی فایل **`run.bat`** دو بار کلیک (دابل‌کلیک) کنید.
* **در مک یا لینوکس:** ترمینال را در پوشه پروژه باز کرده و دستور زیر را اجرا کنید:
  ```bash
  bash run.sh
  ```

اسکریپت به‌طور خودکار محیط مجازی پایتون را بررسی و فعال می‌کند، پیش‌نیازها را آماده می‌سازد، هسته سامانه را روی آدرس امن داخلی (`http://127.0.0.1:8000`) بالا می‌آورد و مرورگر سیستم را به طور خودکار باز می‌کند.

---

## ۴. تنظیم کلیدها از داخل مرورگر
پس از باز شدن خودکار داشبورد در مرورگر:
1. روی دکمه آبی **«⚙️ تنظیمات کلیدها»** در بالای صفحه کلیک کنید.
2. کلید API رایگان خود (مثلاً Gemini یا Groq) را در کادر مربوطه وارد کرده و دکمه **«ذخیره»** را بزنید (سامانه آن را به صورت امن ذخیره می‌کند).
3. روی دکمه **«🔔 فعال‌سازی اعلان دسکتاپ و صدا»** در بالای صفحه کلیک کنید تا مجوز هشدار صوتی و پیام دسکتاپ پس از اتمام کار صادر شود.

---

## ۵. ارسال کار و اجرای چندعاملی
در کادر بالای داشبورد:
1. **متن درخواست:** سوال، ایده، درخواست تحلیل یا برنامه‌نویسی خود را بنویسید.
2. **پیوست فایل (اختیاری):** اگر فایلی دارید (متن، صوت، تصویر، ویدئو، کد پایتون یا PDF متنی/اسکن‌شده)، آن را پیوست کنید. سامانه با تحلیل باینری محتوا نوع واقعی فایل را تشخیص می‌دهد.
3. **فرمت فایل خروجی:** فرمت نهایی فایل دلخواه خود را تعیین کنید:
   - گزارش جامع ساختاریافته (`.md`)
   - متن خام (`.txt`)
   - کد اسکریپت پایتون (`.py`)
   - داده ساختاریافته (`.json`)
4. دکمه سبز **«🚀 اجرای هوشمند و ساخت فایل»** را بزنید.

---

## ۶. نظارت زنده و مولتی‌تسکینگ
* **نظارت بر کارها:** در خط زمانی زنده، حرکت کار بین عامل‌ها، مدل استفاده‌شده و اعتبارسنجی خروجی را مشاهده کنید.
* **انجام کارهای شخصی هم‌زمان:** با کلیک روی دکمه **«⤢ حالت شناور مینیاتوری»**، داشبورد به یک ویجت کوچک در گوشه مانیتور تبدیل می‌شود تا بتوانید هم‌زمان با سایر نرم‌افزارهای خود کار کنید.
* **دخالت در صورت نیاز:** هر زمان خواستید می‌توانید با دکمه‌های بالای صفحه کار را متوقف (`Pause`) کنید یا مدل یک گام را به مدل قوی‌تر ارتقا دهید.

---

## ۷. اطلاع‌رسانی خودکار و دانلود فایل نهایی
به محض اتمام و تأیید کار توسط عامل منتقد:
1. صدای زنگ کوتاهی پخش می‌شود.
2. پیام اعلان روی دسکتاپ ویندوز ظاهر می‌شود.
3. فایل در کادر **«📦 فایل‌های نهایی‌شده»** قرار می‌گیرد و با کلیک روی دکمه **«📥 دانلود فایل»** مستقیماً روی سیستم شما ذخیره می‌شود.
4. در صورت نیاز به گزارش رسمی با زمان‌های دقیق UTC، می‌توانید از دکمه **«📥 گزارش کل (MD)»** استفاده کنید.

---

## ۸. توقف سامانه
برای خاموش کردن سرور، در پنجره ترمینالی که باز شده کلیدهای **`Ctrl + C`** را فشار دهید.
