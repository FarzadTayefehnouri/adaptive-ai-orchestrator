```python
"""
هسته مرکزی سامانه هوش مصنوعی چندعاملی تطبیقی (Adaptive Multi-Agent AI Orchestration Platform)
پیاده‌سازی ۱۰۰٪ مستقل (Zero-Dependency) بر پایه کتابخانه استاندارد پایتون
شامل:
۱. تحلیلگر بایت ورودی و تشخیص PDF متنی از اسکن‌شده (InputAnalyzer)
۲. گراف وابستگی وظایف و زمان‌بند اجرا (DAGWorkflow & DAGNode)
۳. حافظه نتایج معتبر، حافظه تجربه و ثبت رویداد تغییرناپذیر در SQLite (StateAndMemoryStore)
۴. اعتبارسنج دومرحله‌ای مستقل (IndependentValidator)
۵. ناظر مرکزی و موتور بازیابی پس‌رو و پیش‌رو (BackwardForwardOrchestrator)
۶. ارزیاب دموکراتیک ارتقای نسخه از Beta به Stable (ReleaseGovernanceEvaluator)

تحت مجوز GNU AGPLv3
"""

import ast
import datetime
import hashlib
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# بارگذاری درگاه هوشمند از کنار فایل یا از پوشه providers
try:
    from gateway import GatewayResponse, QuotaSourceType, SmartRouterGateway, TaskComplexity
except ImportError:
    try:
        from providers.gateway import (  # type: ignore
            GatewayResponse,
            QuotaSourceType,
            SmartRouterGateway,
            TaskComplexity,
        )
    except ImportError:
        raise ImportError("فایل gateway.py یافت نشد. لطفاً مطمئن شوید gateway.py در کنار main.py یا در پوشه providers قرار دارد.")


def utc_now_iso() -> str:
    """ثبت زمان دقیق بر اساس UTC با دقت ثانیه (الزام بخش ۱۰.۱ سند)"""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =====================================================================
# بخش ۳.۱ سند: تحلیلگر ورودی و تشخیص محتوای واقعی از روی بایت‌ها
# =====================================================================

class ContentType(Enum):
    TEXT_PLAIN = "text/plain"
    SOURCE_CODE = "text/x-source-code"
    JSON_DATA = "application/json"
    CSV_DATA = "text/csv"
    PDF_TEXT_BASED = "application/pdf+text"       # دارای لایه متن قابل استخراج
    PDF_SCANNED_OCR = "application/pdf+scanned"   # فاقد لایه متن؛ نیازمند OCR
    IMAGE = "image/binary"
    AUDIO = "audio/binary"
    VIDEO = "video/binary"
    OFFICE_ZIP = "application/vnd.openxml"        # Word/Excel/PowerPoint (ZIP container)
    UNKNOWN_BINARY = "application/octet-stream"


@dataclass
class InputAnalysisResult:
    detected_type: ContentType
    required_capabilities: List[str]
    is_scanned_pdf: bool
    byte_size: int
    sha256_hash: str
    summary_notes: str


class InputAnalyzer:
    """
    تشخیص محتوای واقعی ورودی از روی امضای بایت‌ها (Magic Bytes) و ساختار درونی،
    نه صرفاً پسوند ظاهری فایل.
    """

    @staticmethod
    def analyze(raw_data: bytes, filename_hint: str = "") -> InputAnalysisResult:
        sha256_hash = hashlib.sha256(raw_data).hexdigest()
        size = len(raw_data)

        # ۱. بررسی امضای بایت‌های PDF (%PDF-)
        if raw_data.startswith(b"%PDF-"):
            # بررسی وجود لایه متنی واقعی (بلوک‌های BT...ET و فونت‌ها) در برابر اسکن تصویری
            has_font = b"/Font" in raw_data
            has_text_blocks = b"BT" in raw_data and b"ET" in raw_data
            has_image_stream = b"/Subtype /Image" in raw_data or b"/Image" in raw_data

            if has_font and has_text_blocks:
                return InputAnalysisResult(
                    detected_type=ContentType.PDF_TEXT_BASED,
                    required_capabilities=["pdf_text_extraction", "text_analysis"],
                    is_scanned_pdf=False,
                    byte_size=size,
                    sha256_hash=sha256_hash,
                    summary_notes="فایل PDF متنی تشخیص داده شد (قابل استخراج مستقیم بدون نیاز به OCR).",
                )
            return InputAnalysisResult(
                detected_type=ContentType.PDF_SCANNED_OCR,
                required_capabilities=["ocr_vision", "image_to_text", "text_analysis"],
                is_scanned_pdf=True,
                byte_size=size,
                sha256_hash=sha256_hash,
                summary_notes="فایل PDF اسکن‌شده یا تصویری تشخیص داده شد؛ نیازمند هدایت به مسیر OCR است.",
            )

        # ۲. بررسی امضای تصاویر (PNG, JPEG, GIF, WEBP)
        if (
            raw_data.startswith(b"\x89PNG\r\n\x1a\n")
            or raw_data.startswith(b"\xff\xd8\xff")
            or raw_data.startswith(b"GIF87a")
            or raw_data.startswith(b"GIF89a")
        ):
            return InputAnalysisResult(
                detected_type=ContentType.IMAGE,
                required_capabilities=["vision_understanding"],
                is_scanned_pdf=False,
                byte_size=size,
                sha256_hash=sha256_hash,
                summary_notes="تصویر باینری از روی امضای بایت‌ها شناسایی شد.",
            )

        # ۳. بررسی فایل‌های صوتی (WAV/RIFF, MP3/ID3, OGG)
        if raw_data.startswith(b"RIFF") or raw_data.startswith(b"ID3") or raw_data.startswith(b"OggS"):
            return InputAnalysisResult(
                detected_type=ContentType.AUDIO,
                required_capabilities=["speech_to_text", "audio_analysis"],
                is_scanned_pdf=False,
                byte_size=size,
                sha256_hash=sha256_hash,
                summary_notes="فایل صوتی شناسایی شد؛ نیازمند تبدیل گفتار به متن (STT).",
            )

        # ۴. بررسی اسناد آفیس (DOCX, XLSX, PPTX بر پایه ZIP)
        if raw_data.startswith(b"PK\x03\x04"):
            return InputAnalysisResult(
                detected_type=ContentType.OFFICE_ZIP,
                required_capabilities=["document_parsing", "structured_extraction"],
                is_scanned_pdf=False,
                byte_size=size,
                sha256_hash=sha256_hash,
                summary_notes="ساختار فشرده OpenXML (مانند Word، Excel یا PowerPoint) شناسایی شد.",
            )

        # ۵. تلاش برای رمزگشایی متنی (UTF-8)
        try:
            text_content = raw_data.decode("utf-8").strip()
        except UnicodeDecodeError:
            return InputAnalysisResult(
                detected_type=ContentType.UNKNOWN_BINARY,
                required_capabilities=["binary_inspection"],
                is_scanned_pdf=False,
                byte_size=size,
                sha256_hash=sha256_hash,
                summary_notes="داده باینری ناشناخته (غیرمتنی).",
            )

        # تشخیص JSON
        if (text_content.startswith("{") and text_content.endswith("}")) or (
            text_content.startswith("[") and text_content.endswith("]")
        ):
            try:
                json.loads(text_content)
                return InputAnalysisResult(
                    detected_type=ContentType.JSON_DATA,
                    required_capabilities=["structured_data_reasoning"],
                    is_scanned_pdf=False,
                    byte_size=size,
                    sha256_hash=sha256_hash,
                    summary_notes="ساختار داده معتبر JSON شناسایی شد.",
                )
            except Exception:
                pass

        # تشخیص کد منبع (پایتون، جاوااسکریپت و غیره)
        code_indicators = ("def ", "class ", "import ", "function ", "const ", "return ", "public static ")
        if any(ind in text_content for ind in code_indicators):
            return InputAnalysisResult(
                detected_type=ContentType.SOURCE_CODE,
                required_capabilities=["code_analysis", "syntax_verification"],
                is_scanned_pdf=False,
                byte_size=size,
                sha256_hash=sha256_hash,
                summary_notes="کد منبع برنامه‌نویسی از روی الگوهای دستوری شناسایی شد.",
            )

        # تشخیص CSV
        lines = text_content.splitlines()
        if len(lines) >= 2 and "," in lines[0] and lines[0].count(",") == lines[1].count(","):
            return InputAnalysisResult(
                detected_type=ContentType.CSV_DATA,
                required_capabilities=["tabular_analysis"],
                is_scanned_pdf=False,
                byte_size=size,
                sha256_hash=sha256_hash,
                summary_notes="داده جدولی CSV شناسایی شد.",
            )

        return InputAnalysisResult(
            detected_type=ContentType.TEXT_PLAIN,
            required_capabilities=["text_reasoning"],
            is_scanned_pdf=False,
            byte_size=size,
            sha256_hash=sha256_hash,
            summary_notes="متن استاندارد UTF-8 شناسایی شد.",
        )


# =====================================================================
# بخش ۵ و ۶ سند: معماری حافظه، کش نتایج معتبر و پایگاه داده رویدادها
# =====================================================================

class StateAndMemoryStore:
    """
    مدیریت پایدار وضعیت، کش نتایج تاییدشده، حافظه تجربه و دانشنامه مدل‌ها
    بر پایه SQLite داخلی پایتون (بدون نیاز به نصب سرویس خارجی در فاز اول)
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self.conn.cursor()
        # ۱. جدول تاریخچه تغییرناپذیر رویدادها (Event Sourcing)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details_json TEXT NOT NULL,
                event_hash TEXT NOT NULL
            )
        """)
        # ۲. جدول حافظه نتایج معتبر (بخش ۵.۱ سند)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS valid_results_cache (
                cache_key TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                method_version TEXT NOT NULL,
                output_content TEXT NOT NULL,
                provider_used TEXT NOT NULL,
                model_used TEXT NOT NULL,
                validated_at_utc TEXT NOT NULL
            )
        """)
        # ۳. جدول حافظه تجربه و بازیابی خطا (بخش ۵.۲ و ۶ سند)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS experience_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                task_type TEXT NOT NULL,
                model_used TEXT NOT NULL,
                outcome TEXT NOT NULL,
                root_cause TEXT,
                recovery_method TEXT,
                validation_method TEXT NOT NULL,
                confidence REAL NOT NULL
            )
        """)
        # ۴. جدول دانشنامه قابلیت مدل‌ها (بخش ۵.۳ سند)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_capabilities (
                model_name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                sample_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                avg_latency_ms REAL NOT NULL DEFAULT 0.0,
                confidence REAL NOT NULL DEFAULT 0.5,
                last_evaluated_utc TEXT NOT NULL,
                PRIMARY KEY (model_name, task_type)
            )
        """)
        self.conn.commit()

    @staticmethod
    def compute_cache_key(node_id: str, prompt: str, upstream_outputs: Dict[str, str], method_version: str = "v1.0") -> str:
        raw = json.dumps(
            {
                "node_id": node_id,
                "prompt": prompt,
                "upstream": upstream_outputs,
                "version": method_version,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def log_event(self, run_id: str, node_id: str, event_type: str, details: Dict[str, Any]) -> str:
        ts = utc_now_iso()
        details_str = json.dumps(details, ensure_ascii=False, sort_keys=True)
        ev_hash = hashlib.sha256(f"{ts}|{run_id}|{node_id}|{event_type}|{details_str}".encode("utf-8")).hexdigest()[:16]
        self.conn.execute(
            "INSERT INTO event_log (timestamp_utc, run_id, node_id, event_type, details_json, event_hash) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, run_id, node_id, event_type, details_str, ev_hash),
        )
        self.conn.commit()
        return ev_hash

    def get_cached_valid_result(self, cache_key: str) -> Optional[Dict[str, str]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT output_content, provider_used, model_used, validated_at_utc FROM valid_results_cache WHERE cache_key = ?",
            (cache_key,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "output_content": row[0],
            "provider_used": row[1],
            "model_used": row[2],
            "validated_at_utc": row[3],
        }

    def save_valid_result(
        self,
        cache_key: str,
        node_id: str,
        output_content: str,
        provider_used: str,
        model_used: str,
        method_version: str = "v1.0",
    ) -> None:
        """فقط و فقط پس از تایید اعتبارسنج مستقل فراخوانی می‌شود"""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO valid_results_cache
            (cache_key, node_id, method_version, output_content, provider_used, model_used, validated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (cache_key, node_id, method_version, output_content, provider_used, model_used, utc_now_iso()),
        )
        self.conn.commit()

    def invalidate_cache_key(self, cache_key: str) -> None:
        """حذف نتیجه نامعتبر در جریان بازیابی پس‌رو"""
        self.conn.execute("DELETE FROM valid_results_cache WHERE cache_key = ?", (cache_key,))
        self.conn.commit()

    def record_verified_experience(
        self,
        task_type: str,
        model_used: str,
        succeeded: bool,
        latency_ms: float,
        validation_method: str,
        confidence: float,
        root_cause: Optional[str] = None,
        recovery_method: Optional[str] = None,
    ) -> None:
        """ثبت تجربه تاییدشده و به‌روزرسانی پروفایل تجربی مدل (بخش ۶ سند)"""
        ts = utc_now_iso()
        outcome = "SUCCESS" if succeeded else "FAILURE"
        self.conn.execute(
            """
            INSERT INTO experience_memory
            (timestamp_utc, task_type, model_used, outcome, root_cause, recovery_method, validation_method, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, task_type, model_used, outcome, root_cause, recovery_method, validation_method, round(confidence, 3)),
        )

        cur = self.conn.cursor()
        cur.execute(
            "SELECT sample_count, success_count, avg_latency_ms FROM model_capabilities WHERE model_name = ? AND task_type = ?",
            (model_used, task_type),
        )
        row = cur.fetchone()
        if not row:
            samples = 1
            successes = 1 if succeeded else 0
            new_lat = latency_ms
        else:
            samples = row[0] + 1
            successes = row[1] + (1 if succeeded else 0)
            new_lat = ((row[2] * row[0]) + latency_ms) / samples

        # سطح اطمینان آماری با افزایش تعداد نمونه‌ها رشد می‌کند
        empirical_conf = min(0.99, round(0.4 + 0.6 * (1.0 - (1.0 / (samples + 1))), 3))
        self.conn.execute(
            """
            INSERT OR REPLACE INTO model_capabilities
            (model_name, task_type, sample_count, success_count, avg_latency_ms, confidence, last_evaluated_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (model_used, task_type, samples, successes, round(new_lat, 2), empirical_conf, ts),
        )
        self.conn.commit()


# =====================================================================
# بخش ۳.۶ سند: اعتبارسنج و منتقد مستقل (Two-Stage Independent Validator)
# =====================================================================

@dataclass
class ValidationReport:
    is_valid: bool
    confidence: float
    validation_method: str
    uncertainty_declared: bool = False
    issues: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None


class IndependentValidator:
    """
    بررسی مستقل صحت، سازگاری و کامل بودن خروجی قبل از اعلام موفقیت.
    مرحله اول: آزمون‌های قطعی ساختاری و کدی (بدون مصرف توکن).
    مرحله دوم: بررسی قوانین معنایی و اعلام عدم قطعیت در صورت نبود شواهد کافی.
    """

    @staticmethod
    def validate(
        output_text: str,
        expected_format: str = "text",
        required_keywords: Optional[List[str]] = None,
        min_length: int = 10,
    ) -> ValidationReport:
        issues: List[str] = []
        clean_text = (output_text or "").strip()

        if not clean_text:
            return ValidationReport(
                is_valid=False,
                confidence=1.0,
                validation_method="deterministic_empty_check",
                issues=["خروجی تولیدشده کاملاً خالی است."],
                suggested_fix="افزودن دستور صریح تولید محتوا و تغییر مدل در صورت تکرار.",
            )

        if len(clean_text) < min_length:
            issues.append(f"طول خروجی ({len(clean_text)} کاراکتر) کمتر از حداقل مجاز ({min_length}) است.")

        # آزمون قطعی ساختار JSON در صورت نیاز
        if expected_format == "json":
            try:
                parsed = json.loads(clean_text)
                if not isinstance(parsed, (dict, list)) or len(parsed) == 0:
                    issues.append("ساختار JSON معتبر است اما محتوای درونی آن خالی است.")
            except Exception as e:
                issues.append(f"خطای ساختاری در JSON: {e}")

        # آزمون قطعی صحت سینتکس کد پایتون با AST
        elif expected_format == "python_code":
            code_body = clean_text
            if "```python" in code_body:
                code_body = code_body.split("```python", 1)[1].split("```", 1)[0].strip()
            elif "```" in code_body:
                code_body = code_body.split("```", 1)[1].split("```", 1)[0].strip()
            try:
                ast.parse(code_body)
            except SyntaxError as e:
                issues.append(f"خطای سینتکس در کد پایتون تولیدشده (خط {e.lineno}): {e.msg}")

        # بررسی وجود کلیدواژه‌ها یا معیارهای الزامی مرحله
        if required_keywords:
            missing = [kw for kw in required_keywords if kw not in clean_text]
            if missing:
                issues.append(f"مفاهیم کلیدی زیر در خروجی رعایت نشده‌اند: {', '.join(missing)}")

        # تشخیص عبارات نشان‌دهنده خطا یا ناتوانی مدل
        failure_markers = ("ERROR_SIMULATION", "INVALID_OUTPUT", "I cannot fulfill")
        if any(marker in clean_text for marker in failure_markers):
            issues.append("الگوی شکست یا خروجی نامعتبر در متن شناسایی شد.")

        if issues:
            return ValidationReport(
                is_valid=False,
                confidence=0.95,
                validation_method=f"two_stage_validator({expected_format})",
                uncertainty_declared=False,
                issues=issues,
                suggested_fix="اصلاح پرامپت با درج دقیق خطاهای ساختاری و بازاجرای گره.",
            )

        return ValidationReport(
            is_valid=True,
            confidence=0.92,
            validation_method=f"two_stage_validator({expected_format})",
            uncertainty_declared=False,
            issues=[],
        )


# =====================================================================
# بخش ۳.۲، ۳.۳ و ۴ سند: گراف وابستگی (DAG) و بازیابی پس‌رو و پیش‌رو
# =====================================================================

class NodeStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"
    INVALIDATED_BY_RECOVERY = "INVALIDATED_BY_RECOVERY"


@dataclass
class DAGNode:
    node_id: str
    title: str
    prompt_template: str
    complexity: TaskComplexity = TaskComplexity.MODERATE
    depends_on: List[str] = field(default_factory=list)
    expected_format: str = "text"
    required_keywords: List[str] = field(default_factory=list)
    min_length: int = 10
    status: NodeStatus = NodeStatus.PENDING
    output: str = ""
    attempts: int = 0
    last_cache_key: str = ""
    last_error: Optional[str] = None
    corrupted_upstream_hint: Optional[str] = None


class BackwardForwardOrchestrator:
    """
    هماهنگ‌کننده مرکزی چرخه سه‌گانه:
    ۱. اجرای مراحل بر اساس گراف وابستگی (DAG)
    ۲. اعتبارسنجی مستقل هر گره و جلوگیری از اعلام موفقیت کاذب
    ۳. بازیابی پس‌رو (Backward) برای یافتن گره ریشه‌ای خطا و بازیابی پیش‌رو (Forward)
       برای اجرای مجدد فقط شاخه‌های متأثر با حفظ نتایج معتبر قبلی.
    """

    def __init__(
        self,
        gateway: SmartRouterGateway,
        store: StateAndMemoryStore,
        max_retries_per_node: int = 2,
        custom_executor: Optional[Callable[[DAGNode, str], GatewayResponse]] = None,
    ):
        self.gateway = gateway
        self.store = store
        self.max_retries_per_node = max_retries_per_node
        self.custom_executor = custom_executor

    @staticmethod
    def _validate_dag_acyclic(nodes: Dict[str, DAGNode]) -> None:
        """بررسی نبود دور (Cycle) در گراف وابستگی پیش از اجرا"""
        visited: Set[str] = set()
        visiting: Set[str] = set()

        def dfs(nid: str) -> None:
            if nid in visiting:
                raise ValueError(f"دور غیرمجاز در گراف وابستگی شناسایی شد در گره: {nid}")
            if nid in visited:
                return
            visiting.add(nid)
            for dep in nodes[nid].depends_on:
                if dep not in nodes:
                    raise ValueError(f"گره پیش‌نیاز '{dep}' برای '{nid}' تعریف نشده است.")
                dfs(dep)
            visiting.remove(nid)
            visited.add(nid)

        for node_id in nodes:
            dfs(node_id)

    @staticmethod
    def _get_downstream_dependents(nodes: Dict[str, DAGNode], root_node_id: str) -> List[str]:
        """یافتن تمام مراحلی که مستقیم یا غیرمستقیم به گره تغییریافته وابسته‌اند (برای بازیابی پیش‌رو)"""
        affected: Set[str] = set()
        queue = [root_node_id]
        while queue:
            current = queue.pop(0)
            for nid, node in nodes.items():
                if current in node.depends_on and nid not in affected:
                    affected.add(nid)
                    queue.append(nid)
        return list(affected)

    def _backward_locate_root_cause(
        self,
        nodes: Dict[str, DAGNode],
        failed_node_id: str,
        validation_report: ValidationReport,
    ) -> str:
        """
        بخش ۴.۱ سند: بازیابی پس‌رو (Backward Recovery)
        حرکت معکوس در گراف وابستگی برای تشخیص اینکه آیا خطا ناشی از خود گره فعلی است
        یا ورودی معیوب از گره بالادستی به آن تزریق شده است.
        """
        failed_node = nodes[failed_node_id]
        # اگر گره صراحتاً نشانه‌ای از نقص داده بالادستی داشته باشد یا خروجی بالادستی ناقص باشد
        if failed_node.corrupted_upstream_hint and failed_node.corrupted_upstream_hint in nodes:
            return failed_node.corrupted_upstream_hint

        for dep_id in failed_node.depends_on:
            dep_node = nodes[dep_id]
            if "CORRUPTED_DATA" in dep_node.output or not dep_node.output.strip():
                return dep_id

        return failed_node_id

    def execute_workflow(self, run_id: str, node_list: List[DAGNode]) -> Dict[str, Any]:
        nodes: Dict[str, DAGNode] = {n.node_id: n for n in node_list}
        self._validate_dag_acyclic(nodes)

        self.store.log_event(run_id, "SYSTEM", "WORKFLOW_STARTED", {"total_nodes": len(nodes)})
        recovery_events: List[Dict[str, Any]] = []

        while True:
            # بررسی اینکه آیا تمام گره‌ها معتبر شده‌اند
            if all(n.status == NodeStatus.VALIDATED for n in nodes.values()):
                break

            # یافتن گره‌های آماده اجرا (که تمام پیش‌نیازهایشان VALIDATED هستند)
            ready_nodes = [
                n for n in nodes.values()
                if n.status in (NodeStatus.PENDING, NodeStatus.INVALIDATED_BY_RECOVERY)
                and all(nodes[dep].status == NodeStatus.VALIDATED for dep in n.depends_on)
            ]

            if not ready_nodes:
                # هیچ گره‌ای قابل اجرا نیست و هنوز همه VALIDATED نشده‌اند -> شکست غیرقابل بازیابی
                break

            for node in ready_nodes:
                node.status = NodeStatus.RUNNING
                upstream_Context = {dep: nodes[dep].output for dep in node.depends_on}
                formatted_prompt = node.prompt_template.format(**upstream_Context) if upstream_Context else node.prompt_template

                cache_key = self.store.compute_cache_key(node.node_id, formatted_prompt, upstream_Context)
                node.last_cache_key = cache_key

                # ۱. بررسی حافظه نتایج معتبر (جلوگیری از محاسبه تکراری)
                cached = self.store.get_cached_valid_result(cache_key)
                if cached and node.attempts == 0:
                    node.output = cached["output_content"]
                    node.status = NodeStatus.VALIDATED
                    self.store.log_event(
                        run_id,
                        node.node_id,
                        "CACHE_HIT_VALIDATED",
                        {"provider": cached["provider_used"], "model": cached["model_used"]},
                    )
                    continue

                # ۲. اجرای گره توسط عامل / درگاه هوش مصنوعی
                node.attempts += 1
                if self.custom_executor:
                    resp = self.custom_executor(node, formatted_prompt)
                else:
                    resp = self.gateway.dispatch(prompt=formatted_prompt, complexity=node.complexity)

                # ۳. اعتبارسنجی مستقل خروجی (بخش ۳.۶ و ۳.۷: عدم اعلام موفقیت پیش از اعتبارسنجی)
                val_report = IndependentValidator.validate(
                    output_text=resp.content if resp.success else "",
                    expected_format=node.expected_format,
                    required_keywords=node.required_keywords,
                    min_length=node.min_length,
                )

                if resp.success and val_report.is_valid:
                    node.output = resp.content
                    node.status = NodeStatus.VALIDATED
                    node.last_error = None
                    self.store.save_valid_result(
                        cache_key=cache_key,
                        node_id=node.node_id,
                        output_content=resp.content,
                        provider_used=resp.provider_used,
                        model_used=resp.model_used,
                    )
                    self.store.record_verified_experience(
                        task_type=node.expected_format,
                        model_used=resp.model_used,
                        succeeded=True,
                        latency_ms=resp.latency_ms,
                        validation_method=val_report.validation_method,
                        confidence=val_report.confidence,
                    )
                    self.store.log_event(
                        run_id,
                        node.node_id,
                        "NODE_VALIDATED",
                        {"attempts": node.attempts, "model": resp.model_used},
                    )
                else:
                    # ۴. بروز خطا -> فعال‌سازی ناظر مرکزی و موتور بازیابی پس‌رو و پیش‌رو
                    error_msg = resp.error_details or "; ".join(val_report.issues)
                    node.last_error = error_msg

                    root_cause_node_id = self._backward_locate_root_cause(nodes, node.node_id, val_report)
                    root_node = nodes[root_cause_node_id]

                    self.store.record_verified_experience(
                        task_type=node.expected_format,
                        model_used=resp.model_used or "unknown",
                        succeeded=False,
                        latency_ms=resp.latency_ms,
                        validation_method=val_report.validation_method,
                        confidence=val_report.confidence,
                        root_cause=f"RootNode={root_cause_node_id}: {error_msg}",
                        recovery_method="backward_invalidate_and_forward_recompute",
                    )

                    if root_node.attempts > self.max_retries_per_node:
                        node.status = NodeStatus.FAILED
                        self.store.log_event(
                            run_id,
                            node.node_id,
                            "RECOVERY_BUDGET_EXHAUSTED",
                            {"root_cause_node": root_cause_node_id, "error": error_msg},
                        )
                        continue

                    # گام بازیابی پس‌رو: ابطال کش گره ریشه‌ای معیوب
                    if root_node.last_cache_key:
                        self.store.invalidate_cache_key(root_node.last_cache_key)

                    # اصلاح دستورالعمل گره ریشه‌ای برای تلاش بعدی
                    root_node.prompt_template += (
                        f"\n[اصلاحیه خودکار بازیابی: در تلاش قبلی خطای «{error_msg}» رخ داد. "
                        f"لطفاً خروجی کامل و منطبق با معیارها تولید کنید.]"
                    )
                    root_node.status = NodeStatus.INVALIDATED_BY_RECOVERY

                    # گام بازیابی پیش‌رو: علامت‌گذاری فقط گره‌های پایین‌دستی وابسته به گره ریشه‌ای
                    # سایر گره‌های معتبر قبلی که به این شاخه وابسته نیستند دست‌نخورده حفظ می‌شوند!
                    downstream_ids = self._get_downstream_dependents(nodes, root_cause_node_id)
                    preserved_nodes = [
                        nid for nid, n in nodes.items()
                        if n.status == NodeStatus.VALIDATED and nid != root_cause_node_id and nid not in downstream_ids
                    ]
                    for d_id in downstream_ids:
                        nodes[d_id].status = NodeStatus.INVALIDATED_BY_RECOVERY

                    rec_info = {
                        "failed_at_node": node.node_id,
                        "isolated_root_cause_node": root_cause_node_id,
                        "recomputed_downstream_nodes": downstream_ids,
                        "preserved_valid_nodes": preserved_nodes,
                        "reason": error_msg,
                        "timestamp_utc": utc_now_iso(),
                    }
                    recovery_events.append(rec_info)
                    self.store.log_event(run_id, node.node_id, "BACKWARD_FORWARD_RECOVERY_TRIGGERED", rec_info)

        # محاسبه درصد پیشرفت واقعی از وضعیت مراحل (الزام بخش ۷ سند)
        validated_count = sum(1 for n in nodes.values() if n.status == NodeStatus.VALIDATED)
        real_progress_pct = round((validated_count / max(1, len(nodes))) * 100.0, 2)
        overall_success = validated_count == len(nodes)

        return {
            "run_id": run_id,
            "overall_success": overall_success,
            "real_progress_percent": real_progress_pct,
            "completed_nodes": [n.node_id for n in nodes.values() if n.status == NodeStatus.VALIDATED],
            "failed_nodes": [n.node_id for n in nodes.values() if n.status == NodeStatus.FAILED],
            "recovery_history": recovery_events,
            "final_outputs": {n.node_id: n.output for n in nodes.values() if n.status == NodeStatus.VALIDATED},
        }


# =====================================================================
# بخش ۱۰.۲ سند: ارزیاب خودکار ارتقای نسخه از Beta به Stable
# =====================================================================

@dataclass
class UserVote:
    contributor_github_id: str
    email_verified: bool
    has_signed_commits: bool
    approve_promotion: bool
    timestamp_utc: str = field(default_factory=utc_now_iso)


class ReleaseGovernanceEvaluator:
    """
    سیاست ارتقای نسخه آزمایشی (Beta) به پایدار (Stable) طبق بخش ۱۰.۲ سند:
    ۱. بیش از ۸۰ درصد آرای معتبر کاربران موافق باشند (دقیقاً ۸۰.۰٪ کافی نیست: > 80.0%).
    ۲. آزمون‌های فنی و امنیتی موفق باشند.
    ۳. آرای تکراری یا فاقد ایمیل تاییدشده پالایش شوند.
    ۴. حداقل تعداد نمونه کافی رعایت شود (در غیر این صورت: وضعیت «شواهد ناکافی»).
    """

    @staticmethod
    def evaluate_beta_to_stable(
        version_tag: str,
        commit_hash: str,
        votes: List[UserVote],
        technical_tests_passed: bool,
        security_tests_passed: bool,
        min_valid_votes_required: int = 5,
    ) -> Dict[str, Any]:
        # حذف آرای نامعتبر (فاقد ایمیل تاییدشده) و حذف آرای تکراری بر اساس شناسه پایدار گیت‌هاب
        deduped_valid_votes: Dict[str, UserVote] = {}
        rejected_duplicate_or_unverified = 0

        for v in votes:
            if not v.email_verified or not v.contributor_github_id.strip():
                rejected_duplicate_or_unverified += 1
                continue
            if v.contributor_github_id in deduped_valid_votes:
                rejected_duplicate_or_unverified += 1
                continue
            deduped_valid_votes[v.contributor_github_id] = v

        total_valid = len(deduped_valid_votes)
        positive_votes = sum(1 for v in deduped_valid_votes.values() if v.approve_promotion)
        approval_pct = round((positive_votes / total_valid) * 100.0, 2) if total_valid > 0 else 0.0

        if total_valid < min_valid_votes_required:
            return {
                "version": version_tag,
                "commit_hash": commit_hash,
                "promoted_to_stable": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "reason": f"تعداد آرای معتبر ({total_valid}) کمتر از حداقل نصاب ({min_valid_votes_required}) است؛ نسخه در وضعیت Beta باقی می‌ماند.",
                "valid_votes_count": total_valid,
                "approval_percentage": approval_pct,
                "evaluated_at_utc": utc_now_iso(),
            }

        # شرط اکید بیش از ۸۰ درصد (> 80.0) به همراه موفقیت آزمون‌های فنی و امنیتی
        strictly_over_80 = approval_pct > 80.0
        can_promote = strictly_over_80 and technical_tests_passed and security_tests_passed

        new_tag = version_tag.replace("-beta", "-stable") if can_promote else version_tag
        return {
            "version": new_tag,
            "commit_hash": commit_hash,
            "promoted_to_stable": can_promote,
            "status": "PROMOTED_TO_STABLE" if can_promote else "RETAINED_IN_BETA",
            "valid_votes_count": total_valid,
            "filtered_invalid_or_duplicate_votes": rejected_duplicate_or_unverified,
            "approval_percentage": approval_pct,
            "strictly_over_80_percent": strictly_over_80,
            "technical_tests_passed": technical_tests_passed,
            "security_tests_passed": security_tests_passed,
            "evaluated_at_utc": utc_now_iso(),
        }


# =====================================================================
# اجرای خودآزمایی (Self-Test) کامل چرخه سه‌گانه بدون نیاز به اینترنت
# =====================================================================

def run_self_verification_suite() -> None:
    print("=================================================================")
    print("شروع خودآزمایی هسته سامانه هوش مصنوعی چندعاملی تطبیقی (Zero-Dependency)")
    print("=================================================================\n")

    # ۱. آزمایش تحلیلگر بایت ورودی (تفکیک PDF متنی از اسکن‌شده)
    text_pdf_bytes = b"%PDF-1.7\n1 0 obj << /Type /Page /Resources << /Font << /F1 2 0 R >> >> >>\nstream\nBT (Hello) Tj ET\nendstream"
    scanned_pdf_bytes = b"%PDF-1.7\n1 0 obj << /Type /XObject /Subtype /Image /Width 1200 >>\nstream\n\x00\x01\x02\nendstream"

    res_text_pdf = InputAnalyzer.analyze(text_pdf_bytes, "doc1.pdf")
    res_scan_pdf = InputAnalyzer.analyze(scanned_pdf_bytes, "doc2.pdf")

    print("[۱] آزمون تحلیلگر ورودی از روی بایت‌ها:")
    print(f"  - نمونه اول: {res_text_pdf.detected_type.value} | {res_text_pdf.summary_notes}")
    print(f"  - نمونه دوم: {res_scan_pdf.detected_type.value} | {res_scan_pdf.summary_notes}\n")

    # ۲. آزمایش گراف وابستگی، اعتبارسنج مستقل و بازیابی پس‌رو و پیش‌رو
    gateway = SmartRouterGateway()
    store = StateAndMemoryStore(":memory:")

    # شبیه‌ساز اجرای عامل که در تلاش اولِ مرحله ۲، خروجی معیوب تولید می‌کند تا موتور بازیابی آزمایش شود
    def simulated_agent_executor(node: DAGNode, prompt: str) -> GatewayResponse:
        if node.node_id == "step_2_draft_code" and node.attempts == 1:
            # ایجاد عمدی کد دارای خطای سینتکس در تلاش اول برای فعال‌سازی بازیابی
            return GatewayResponse(
                success=True,
                content="def broken_func(:\n    pass",
                provider_used="Groq_Cloud",
                model_used="llama-3.3-70b-versatile",
                tokens_used=45,
                quota_source=QuotaSourceType.ESTIMATED_LOCAL,
                latency_ms=110.0,
            )
        if node.node_id == "step_2_draft_code" and node.attempts >= 2:
            # پس از دریافت اصلاحیه از موتور بازیابی، کد سالم تولید می‌کند
            return GatewayResponse(
                success=True,
                content="def calculate_quota(used: int, limit: int) -> int:\n    return max(0, limit - used)",
                provider_used="Google_Gemini",
                model_used="gemini-1.5-pro",
                tokens_used=60,
                quota_source=QuotaSourceType.ESTIMATED_LOCAL,
                latency_ms=185.0,
            )
        return GatewayResponse(
            success=True,
            content=f"خروجی معتبر و تاییدشده برای مرحله {node.title} بر اساس معیارهای معماری.",
            provider_used="Google_Gemini",
            model_used="gemini-1.5-flash",
            tokens_used=50,
            quota_source=QuotaSourceType.ESTIMATED_LOCAL,
            latency_ms=95.0,
        )

    orchestrator = BackwardForwardOrchestrator(
        gateway=gateway,
        store=store,
        max_retries_per_node=2,
        custom_executor=simulated_agent_executor,
    )

    workflow_nodes = [
        DAGNode(
            node_id="step_1_analyze_spec",
            title="تحلیل نیازمندی‌ها",
            prompt_template="نیازمندی‌های سهمیه را استخراج کن.",
            expected_format="text",
        ),
        DAGNode(
            node_id="step_2_draft_code",
            title="تولید کد محاسبه‌گر سهمیه",
            prompt_template="بر اساس {step_1_analyze_spec} کد پایتون بنویس.",
            depends_on=["step_1_analyze_spec"],
            expected_format="python_code",
        ),
        DAGNode(
            node_id="step_3_final_summary",
            title="تدوین گزارش نهایی",
            prompt_template="کد زیر را مستندسازی کن: {step_2_draft_code}",
            depends_on=["step_2_draft_code"],
            expected_format="text",
        ),
    ]

    result = orchestrator.execute_workflow("run_2026_001", workflow_nodes)
    print("[۲] نتیجه اجرای گراف وابستگی (DAG) و بازیابی خودکار خطا:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    # ۳. آزمایش سیاست ارتقای نسخه از Beta به Stable (شرط اکید > ۸۰٪)
    sample_votes = [
        UserVote("user_alpha", email_verified=True, has_signed_commits=True, approve_promotion=True),
        UserVote("user_beta", email_verified=True, has_signed_commits=True, approve_promotion=True),
        UserVote("user_gamma", email_verified=True, has_signed_commits=True, approve_promotion=True),
        UserVote("user_delta", email_verified=True, has_signed_commits=True, approve_promotion=True),
        UserVote("user_epsilon", email_verified=True, has_signed_commits=False, approve_promotion=True),
        UserVote("user_zeta", email_verified=True, has_signed_commits=False, approve_promotion=False),
        # رأی تکراری که باید خودکار حذف شود
        UserVote("user_alpha", email_verified=True, has_signed_commits=True, approve_promotion=False),
    ]
    gov_report = ReleaseGovernanceEvaluator.evaluate_beta_to_stable(
        version_tag="v0.1.0-beta",
        commit_hash="a1b2c3d4e5f6",
        votes=sample_votes,
        technical_tests_passed=True,
        security_tests_passed=True,
        min_valid_votes_required=5,
    )
    print("[۳] نتیجه ارزیابی حاکمیتی ارتقای نسخه (Beta -> Stable):")
    print(json.dumps(gov_report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run_self_verification_suite()
```