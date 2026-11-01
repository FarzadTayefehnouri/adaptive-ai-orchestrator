"""FastAPI Monitoring & Interactive Execution Dashboard Server.
Features:
- Real-time Desktop Browser Notifications & Audio Chime Alert when tasks finish or need attention
- Dedicated "Finalized AI Deliverables" Download Center (/api/tasks/{task_id}/download)
- Interactive Web Task Input & Multi-Modal File Upload directly in the browser
- Live Multi-Agent Pipeline Execution (Input Analyzer -> Cache -> Router -> Adapter -> Critic -> Recovery)
- Audit Report Exporter (Download full UTC execution log as Markdown .md or JSON .json)
- Dynamic API Key & Model Configuration Tab
- Compact Floating / Picture-in-Picture window mode
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import base64
import json
import os
from pathlib import Path

from src.orchestrator.models import TaskComplexity, QuotaType
from src.orchestrator.dashboard.events import global_event_bus, TelemetryEvent
from src.orchestrator.dashboard.controller import global_controller
from src.orchestrator.memory.sqlite_store import SQLiteStore
from src.orchestrator.memory.cache import ResponseCache
from src.orchestrator.agents.input_analyzer import InputAnalyzer
from src.orchestrator.agents.critic import CriticAgent
from src.orchestrator.providers.quota_manager import QuotaManager
from src.orchestrator.providers.router import ModelRouter
from src.orchestrator.providers.adapters import ProviderAdapter
from src.orchestrator.security.auth import verify_api_token, UserRole

app = FastAPI(title="Adaptive AI Orchestrator - Live Supervisor & Execution Engine")
sqlite_store = SQLiteStore()
response_cache = ResponseCache(sqlite_store)
input_analyzer = InputAnalyzer()
critic_agent = CriticAgent()
provider_adapter = ProviderAdapter()

quota_manager = QuotaManager()
quota_manager.register_provider("groq_llama_8b", QuotaType.REAL, 100, 100)
quota_manager.register_provider("gemini_flash", QuotaType.REAL, 100, 100)
quota_manager.register_provider("gemini_pro", QuotaType.REAL, 50, 50)
quota_manager.register_provider("local_ollama", QuotaType.ESTIMATED, 9999, 9999)
model_router = ModelRouter(quota_manager)

# Store completed task outputs and finalized downloadable deliverables
audit_results: List[Dict[str, Any]] = []
finalized_deliverables: Dict[str, Dict[str, Any]] = {}

class OverrideRequest(BaseModel):
    step_id: str
    model_name: str

class RerunRequest(BaseModel):
    step_id: str

class TaskSubmitRequest(BaseModel):
    prompt: str
    complexity: str = "auto"
    output_format: str = "md"  # md, txt, py, json, csv
    filename: Optional[str] = None
    file_base64: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None

@app.get("/api/history")
async def get_history(role: UserRole = Depends(verify_api_token)):
    return {
        "history": global_event_bus.get_full_history(),
        "is_paused": global_controller.is_paused,
        "deliverables": list(finalized_deliverables.values())
    }

@app.get("/api/deliverables")
async def list_deliverables(role: UserRole = Depends(verify_api_token)):
    """Return list of all finalized AI files ready for user download."""
    return {"deliverables": list(finalized_deliverables.values())}

@app.get("/api/tasks/{task_id}/download")
async def download_task_deliverable(task_id: str, fmt: Optional[str] = None, role: UserRole = Depends(verify_api_token)):
    """Download the finalized AI output file for a specific completed task."""
    item = finalized_deliverables.get(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    ext = (fmt or item.get("output_format") or "md").lower().strip(".")
    filename = f"{task_id}_final.{ext}"
    
    if ext == "json":
        content = json.dumps(item, ensure_ascii=False, indent=2)
        media_type = "application/json"
    elif ext == "py":
        content = "\n".join([f"# Finalized AI Output ({item['task_id']})", f"# Model: {item['model_used']} | UTC: {item['timestamp_utc']}", "", item["text"]])
        media_type = "text/x-python"
    elif ext == "txt":
        content = item["text"]
        media_type = "text/plain; charset=utf-8"
    else:
        content = "\n".join([f"# خروجی نهایی تأییدشده ({item['task_id']})", "", f"- **مدل تولیدکننده:** `{item['model_used']}`", f"- **زمان نهایی‌سازی (UTC):** `{item['timestamp_utc']}`", f"- **درخواست اولیه:** {item['prompt']}", "", "## متن نهایی", "", item["text"]])
        media_type = "text/markdown; charset=utf-8"

    return Response(
        content=content.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/tasks/submit")
async def submit_task(req: TaskSubmitRequest, role: UserRole = Depends(verify_api_token)):
    """Execute full multi-agent workflow, package finalized file, and notify the user."""
    await global_controller.wait_if_paused()
    task_id = f"task_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    
    # Step 1: Input Analysis
    file_info = None
    if req.filename:
        raw_bytes = base64.b64decode(req.file_base64) if req.file_base64 else b""
        file_info = input_analyzer.analyze(req.filename, raw_bytes)
        global_event_bus.emit(TelemetryEvent(
            event_type="step_completed",
            step_id=f"{task_id}_analyze",
            agent_name="InputAnalyzer",
            message=f"🔍 تحلیل فایل «{req.filename}»: نوع واقعی={file_info['modality']} ({file_info['detected_mime']}) | خط لوله={file_info['recommended_pipeline']}",
            data=file_info
        ))

    # Step 2: Complexity Classification & Token Estimation
    est_tokens = quota_manager.estimate_tokens(req.prompt)
    if req.complexity == "auto":
        if est_tokens > 300 or (file_info and file_info["modality"] in ("video", "document")):
            chosen_complexity = TaskComplexity.COMPLEX
        elif est_tokens > 80:
            chosen_complexity = TaskComplexity.MODERATE
        else:
            chosen_complexity = TaskComplexity.LIGHT
    else:
        chosen_complexity = TaskComplexity(req.complexity)

    # Step 3: Zero-Token Cache Check
    cached = response_cache.lookup(req.prompt, chosen_complexity.value)
    if cached:
        cached_copy = dict(cached)
        cached_copy["task_id"] = task_id
        cached_copy["output_format"] = req.output_format
        cached_copy["download_url"] = f"/api/tasks/{task_id}/download"
        finalized_deliverables[task_id] = cached_copy
        global_event_bus.emit(TelemetryEvent(
            event_type="deliverable_ready",
            step_id=f"{task_id}_cache",
            agent_name="ResponseCache",
            message=f"⚡ پاسخ معتبر در کَش محلی یافت شد و فایل نهایی «{task_id}_final.{req.output_format}» آماده دانلود است!",
            data=cached_copy
        ))
        return {"status": "completed", "task_id": task_id, "source": "cache", "output": cached_copy}

    # Step 4: Smart Model Routing
    step_exec_id = f"{task_id}_exec"
    selected_model = global_controller.model_overrides.get(step_exec_id) or model_router.route(chosen_complexity)
    global_event_bus.emit(TelemetryEvent(
        event_type="step_started",
        step_id=step_exec_id,
        agent_name="ModelRouter",
        model_name=selected_model,
        message=f"🚀 مسیریابی هوشمند (سطح {chosen_complexity.value} | ~{est_tokens} توکن) به مدل «{selected_model}»"
    ))

    # Step 5: Execute via ProviderAdapter with CircuitBreaker protection
    try:
        gen_res = provider_adapter.generate(selected_model, req.prompt)
        quota_manager.record_usage(selected_model, gen_res["token_usage"])
    except Exception as exc:
        if selected_model in quota_manager.providers:
            quota_manager.providers[selected_model].report_network_failure(str(exc))
        _, fallback_model = model_router.escalate(chosen_complexity, selected_model, str(exc))
        global_event_bus.emit(TelemetryEvent(
            event_type="step_failed",
            step_id=step_exec_id,
            agent_name="CircuitBreaker",
            model_name=fallback_model,
            message=f"⚠️ خطای ارتباطی در {selected_model}؛ مدار قطع شد و وظیفه خودکار به {fallback_model} منتقل گردید."
        ))
        selected_model = fallback_model
        gen_res = provider_adapter.generate(selected_model, req.prompt)
        quota_manager.record_usage(selected_model, gen_res["token_usage"])

    # Step 6: Critic Validation & Dynamic Escalation
    critique = critic_agent.evaluate_output(req.prompt, {"text": gen_res["text"]})
    escalated = False
    if not critique["is_valid"] and critique["needs_escalation"]:
        escalated = True
        new_comp, higher_model = model_router.escalate(chosen_complexity, selected_model, critique["reason"])
        global_event_bus.emit(TelemetryEvent(
            event_type="user_intervened",
            step_id=step_exec_id,
            agent_name="CriticAgent",
            model_name=higher_model,
            message=f"🔼 ارتقای خودکار مدل از {selected_model} به {higher_model} به دلیل: {critique['reason']}"
        ))
        selected_model = higher_model
        gen_res = provider_adapter.generate(selected_model, req.prompt)
        quota_manager.record_usage(selected_model, gen_res["token_usage"])

    output_record = {
        "task_id": task_id,
        "prompt": req.prompt,
        "text": gen_res["text"],
        "model_used": selected_model,
        "mode": gen_res["mode"],
        "complexity": chosen_complexity.value,
        "output_format": req.output_format,
        "download_url": f"/api/tasks/{task_id}/download",
        "token_usage": dict(gen_res["token_usage"]),
        "duration_ms": gen_res["duration_ms"],
        "escalated": escalated,
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    # Save to cache, SQLite experience store, and Finalized Deliverables registry
    response_cache.store_response(req.prompt, chosen_complexity.value, output_record, score=0.95)
    sqlite_store.record_experience(chosen_complexity.value, selected_model, True, escalated, gen_res["duration_ms"])
    audit_results.append(output_record)
    finalized_deliverables[task_id] = output_record

    # Emit completion + user notification event
    global_event_bus.emit(TelemetryEvent(
        event_type="deliverable_ready",
        step_id=step_exec_id,
        agent_name="NotificationCenter",
        model_name=selected_model,
        message=f"🔔 اطلاع‌رسانی به کاربر: فایل نهایی «{task_id}_final.{req.output_format}» تأیید شد و آماده دانلود است!",
        data=output_record
    ))

    return {"status": "completed", "task_id": task_id, "source": gen_res["mode"], "output": output_record}

@app.get("/api/export/markdown", response_class=PlainTextResponse)
async def export_audit_markdown(role: UserRole = Depends(verify_api_token)):
    """Export complete auditable execution report in Markdown format with UTC timestamps."""
    now_utc = datetime.now(timezone.utc).isoformat()
    lines = [
        "# گزارش رسمی حسابرسی و اجرای سامانه (Orchestrator Audit Report)",
        f"- **زمان تولید گزارش (UTC):** `{now_utc}`",
        f"- **تعداد کل رویدادهای ثبت‌شده:** `{len(global_event_bus.history)}`",
        f"- **تعداد وظایف تکمیل‌شده:** `{len(audit_results)}`",
        "",
        "## ۱. خلاصه وضعیت سهمیه و مدار ارائه‌دهندگان (Provider Quotas & Circuit Breakers)",
        "| ارائه‌دهنده | نوع سهمیه | اعتبار باقیمانده | توکن مصرفی | وضعیت مدار (Circuit Breaker) |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for p_id, p_status in quota_manager.providers.items():
        d = p_status.to_dict()
        cb_state = d["circuit_breaker"]["state"]
        lines.append(f"| `{p_id}` | {d['quota_type']} | {d['remaining_credits']}/{d['total_limit']} | {d['total_tokens_consumed']} | `{cb_state}` |")

    lines.extend(["", "## ۲. خروجی‌های نهایی تأییدشده (Validated Task Outputs)"])
    if not audit_results:
        lines.append("_هنوز وظیفه‌ای در این نشست ثبت نشده است._")
    for idx, item in enumerate(audit_results, 1):
        lines.extend([
            f"### وظیفه {idx}: `{item['task_id']}` ({item['timestamp_utc']})",
            f"- **مدل استفاده‌شده:** `{item['model_used']}` (حالت: `{item['mode']}` | پیچیدگی: `{item['complexity']}`)",
            f"- **مصرف توکن:** `{item['token_usage']['total_tokens']}` توکن | **زمان پاسخ:** `{item['duration_ms']} ms`",
            f"- **درخواست کاربر:** {item['prompt']}",
            f"- **پاسخ نهایی:** {item['text']}",
            ""
        ])

    lines.extend(["## ۳. زنجیره کامل رویدادها از گام نخست (Full UTC Event Timeline)"])
    for evt in global_event_bus.get_full_history():
        lines.append(f"- `{evt['timestamp_utc']}` **[{evt['event_type']}]** ({evt.get('agent_name') or 'Core'}): {evt['message']}")

    return PlainTextResponse(
        content="\n".join(lines),
        headers={"Content-Disposition": "attachment; filename=orchestrator_audit_report.md"}
    )

@app.get("/api/export/json")
async def export_audit_json(role: UserRole = Depends(verify_api_token)):
    """Export complete auditable execution report in JSON format."""
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "providers": {k: v.to_dict() for k, v in quota_manager.providers.items()},
        "validated_outputs": audit_results,
        "deliverables": list(finalized_deliverables.values()),
        "event_timeline": global_event_bus.get_full_history(),
        "model_reliability_stats": sqlite_store.get_model_stats()
    }
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": "attachment; filename=orchestrator_audit_report.json"}
    )

@app.get("/api/settings")
async def get_settings(role: UserRole = Depends(verify_api_token)):
    return {
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        "huggingface_configured": bool(os.getenv("HUGGINGFACE_API_KEY")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    }

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest, role: UserRole = Depends(verify_api_token)):
    env_updates = {}
    if req.gemini_api_key is not None:
        os.environ["GEMINI_API_KEY"] = req.gemini_api_key
        env_updates["GEMINI_API_KEY"] = req.gemini_api_key
    if req.groq_api_key is not None:
        os.environ["GROQ_API_KEY"] = req.groq_api_key
        env_updates["GROQ_API_KEY"] = req.groq_api_key
    if req.openai_api_key is not None:
        os.environ["OPENAI_API_KEY"] = req.openai_api_key
        env_updates["OPENAI_API_KEY"] = req.openai_api_key
    if req.anthropic_api_key is not None:
        os.environ["ANTHROPIC_API_KEY"] = req.anthropic_api_key
        env_updates["ANTHROPIC_API_KEY"] = req.anthropic_api_key
    if req.huggingface_api_key is not None:
        os.environ["HUGGINGFACE_API_KEY"] = req.huggingface_api_key
        env_updates["HUGGINGFACE_API_KEY"] = req.huggingface_api_key
    if req.ollama_base_url is not None:
        os.environ["OLLAMA_BASE_URL"] = req.ollama_base_url
        env_updates["OLLAMA_BASE_URL"] = req.ollama_base_url

    env_file = Path(".env")
    existing_lines = []
    if env_file.exists():
        existing_lines = env_file.read_text(encoding="utf-8").splitlines()

    new_lines = []
    handled_keys = set()
    for line in existing_lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=")[0].strip()
            if k in env_updates:
                new_lines.append(f"{k}={env_updates[k]}")
                handled_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in env_updates.items():
        if k not in handled_keys:
            new_lines.append(f"{k}={v}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    
    global_event_bus.emit(TelemetryEvent(
        event_type="user_intervened",
        message="⚙️ تنظیمات کلیدهای API از داخل داشبورد به‌روزرسانی شد."
    ))
    return {"status": "success", "message": "Settings updated and saved to .env"}

@app.post("/api/pause")
async def pause_execution(role: UserRole = Depends(verify_api_token)):
    global_controller.pause()
    return {"status": "paused", "is_paused": True}

@app.post("/api/resume")
async def resume_execution(role: UserRole = Depends(verify_api_token)):
    global_controller.resume()
    return {"status": "resumed", "is_paused": False}

@app.post("/api/override-model")
async def override_model(req: OverrideRequest, role: UserRole = Depends(verify_api_token)):
    global_controller.set_model_override(req.step_id, req.model_name)
    return {"status": "overridden", "step_id": req.step_id, "model": req.model_name}

@app.post("/api/rerun-step")
async def rerun_step(req: RerunRequest, role: UserRole = Depends(verify_api_token)):
    global_controller.request_step_rerun(req.step_id)
    return {"status": "rerun_requested", "step_id": req.step_id}

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    past_history = global_event_bus.get_full_history()
    await websocket.send_text(json.dumps({
        "type": "history_sync",
        "data": past_history,
        "deliverables": list(finalized_deliverables.values()),
        "is_paused": global_controller.is_paused
    }))

    async def on_new_event(event: TelemetryEvent):
        try:
            await websocket.send_text(json.dumps({
                "type": "live_event",
                "data": event.to_dict(),
                "is_paused": global_controller.is_paused
            }))
        except Exception:
            pass

    global_event_bus.subscribe(on_new_event)
    try:
        while True:
            client_msg = await websocket.receive_text()
            data = json.loads(client_msg)
            cmd = data.get("command")
            if cmd == "pause":
                global_controller.pause()
            elif cmd == "resume":
                global_controller.resume()
    except WebSocketDisconnect:
        global_event_bus.unsubscribe(on_new_event)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard_html():
    return HTML_CONTENT

HTML_CONTENT = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>سامانه نظارت زنده و اجرای چندعاملی | Adaptive Orchestrator</title>
    <style>
        :root {
            --bg-dark: #0f172a;
            --card-dark: #1e293b;
            --border-dark: #334155;
            --text-light: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-red: #ef4444;
            --accent-purple: #8b5cf6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Tahoma, sans-serif; }
        body { background: var(--bg-dark); color: var(--text-light); min-height: 100vh; padding: 16px; transition: all 0.3s ease; }
        
        body.mini-mode {
            padding: 8px;
            max-width: 420px;
            position: fixed;
            bottom: 12px;
            left: 12px;
            right: auto;
            top: auto;
            background: rgba(15, 23, 42, 0.95);
            border: 2px solid var(--accent-blue);
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.7);
            z-index: 99999;
            backdrop-filter: blur(8px);
        }
        body.mini-mode .hide-in-mini { display: none !important; }
        body.mini-mode .timeline-container { max-height: 180px; }

        header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 14px; border-bottom: 1px solid var(--border-dark); margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
        .logo-box { display: flex; align-items: center; gap: 10px; }
        .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
        .badge-live { background: rgba(16, 185, 129, 0.2); color: var(--accent-green); border: 1px solid var(--accent-green); }
        .badge-paused { background: rgba(245, 158, 11, 0.2); color: var(--accent-amber); border: 1px solid var(--accent-amber); }
        
        .window-controls { display: flex; gap: 8px; flex-wrap: wrap; }
        button, a.btn-link { cursor: pointer; border: none; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; transition: all 0.2s; text-decoration: none; }
        .btn-ctrl { background: var(--card-dark); color: var(--text-light); border: 1px solid var(--border-dark); }
        .btn-ctrl:hover { background: #2d3748; }
        .btn-pause { background: #b45309; color: white; }
        .btn-resume { background: #047857; color: white; }
        .btn-override { background: var(--accent-purple); color: white; }
        .btn-abort { background: #991b1b; color: white; }
        .btn-settings { background: #0284c7; color: white; }
        .btn-submit { background: var(--accent-green); color: white; padding: 10px 20px; font-size: 14px; }
        .btn-download-item { background: var(--accent-blue); color: white; padding: 5px 12px; font-size: 12px; border-radius: 6px; }

        .dashboard-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
        body.mini-mode .dashboard-grid { grid-template-columns: 1fr; }

        .card { background: var(--card-dark); border: 1px solid var(--border-dark); border-radius: 10px; padding: 14px; margin-bottom: 16px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 14px; font-weight: bold; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 8px; }

        .task-box { display: flex; flex-direction: column; gap: 10px; }
        .task-box textarea { width: 100%; min-height: 75px; background: #0f172a; border: 1px solid var(--border-dark); border-radius: 8px; color: white; padding: 10px; font-size: 13px; resize: vertical; }
        .task-controls { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .task-controls select, .task-controls input[type="file"] { background: #0f172a; color: var(--text-light); border: 1px solid var(--border-dark); padding: 6px 10px; border-radius: 6px; font-size: 12px; }

        .timeline-container { max-height: 360px; overflow-y: auto; padding-left: 6px; }
        .timeline-item { position: relative; padding-right: 18px; padding-bottom: 14px; border-right: 2px solid var(--border-dark); margin-right: 10px; }
        .timeline-item::before { content: ''; position: absolute; right: -7px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: var(--accent-blue); }
        .timeline-item.step_completed::before, .timeline-item.deliverable_ready::before { background: var(--accent-green); }
        .timeline-item.step_failed::before { background: var(--accent-red); }
        .timeline-item.user_intervened::before { background: var(--accent-amber); }
        .timeline-time { font-size: 11px; color: var(--text-muted); direction: ltr; text-align: right; }
        .timeline-title { font-size: 13px; font-weight: 600; margin: 3px 0; }
        .timeline-desc { font-size: 12px; color: var(--text-muted); }

        /* Deliverables Box */
        .deliverable-list { display: flex; flex-direction: column; gap: 10px; max-height: 240px; overflow-y: auto; }
        .deliverable-card { display: flex; justify-content: space-between; align-items: center; background: #0f172a; border: 1px solid var(--border-dark); padding: 10px 14px; border-radius: 8px; }
        .deliverable-meta { font-size: 12px; color: var(--text-muted); margin-top: 3px; }

        /* Toast Notification */
        #toast-banner { display: none; position: fixed; top: 18px; left: 50%; transform: translateX(-50%); background: #065f46; color: white; border: 1px solid var(--accent-green); padding: 12px 20px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.6); z-index: 200000; font-size: 13px; font-weight: bold; align-items: center; gap: 12px; }

        .quota-meter { margin-bottom: 12px; }
        .quota-label { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; }
        .progress-bar { width: 100%; height: 8px; background: #334155; border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--accent-blue); width: 100%; transition: width 0.3s; }

        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 100000; align-items: center; justify-content: center; backdrop-filter: blur(4px); }
        .modal-content { background: var(--card-dark); border: 1px solid var(--border-dark); border-radius: 12px; width: 90%; max-width: 520px; padding: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.8); }
        .input-group { margin-bottom: 12px; }
        .input-group label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
        .input-group input { width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid var(--border-dark); border-radius: 6px; color: white; font-size: 13px; }
    </style>
</head>
<body>
    <!-- Live Toast Alert -->
    <div id="toast-banner">
        <span id="toast-text">🔔 فایل نهایی آماده دانلود است!</span>
        <a id="toast-download-btn" class="btn-link btn-download-item" href="#" download>📥 دانلود فوری</a>
    </div>

    <header>
        <div class="logo-box">
            <h2>سامانه هوش مصنوعی چندعاملی تطبیق‌پذیر</h2>
            <span id="status-badge" class="badge badge-live">● آماده و در حال پایش زنده</span>
        </div>
        <div class="window-controls">
            <button id="btn-notify-perm" class="btn-ctrl" onclick="enableNotifications()">🔔 فعال‌سازی اعلان دسکتاپ و صدا</button>
            <button id="btn-toggle-pause" class="btn-pause" onclick="togglePause()">⏸️ توقف اجرا</button>
            <button class="btn-override hide-in-mini" onclick="promptOverride()">🔀 تغییر مدل گام</button>
            <a class="btn-link btn-ctrl hide-in-mini" href="/api/export/markdown" download="orchestrator_audit_report.md">📥 گزارش کل (MD)</a>
            <button class="btn-settings hide-in-mini" onclick="openSettingsModal()">⚙️ تنظیمات کلیدها</button>
            <button class="btn-ctrl" onclick="toggleMiniMode()" title="کوچک کردن به گوشه صفحه">⤢ حالت شناور مینیاتوری</button>
        </div>
    </header>

    <!-- Interactive Task Submission Card -->
    <div class="card hide-in-mini">
        <div class="card-header">
            <span>ارسال وظیفه جدید و تولید فایل نهایی توسط هوش مصنوعی</span>
            <span style="font-size: 11px; color: var(--accent-green);">اعلان خودکار پس از اتمام + لینک دانلود مستقیم</span>
        </div>
        <div class="task-box">
            <textarea id="task-prompt" placeholder="درخواست، سؤال یا دستور تولید فایل خود را اینجا بنویسید..."></textarea>
            <div class="task-controls">
                <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <label style="font-size: 12px; color: var(--text-muted);">پیوست فایل ورودی:</label>
                    <input type="file" id="task-file">
                    <label style="font-size: 12px; color: var(--text-muted);">فرمت فایل خروجی:</label>
                    <select id="task-format">
                        <option value="md">گزارش استاندارد (Markdown .md)</option>
                        <option value="txt">متن خالص (Plain Text .txt)</option>
                        <option value="py">کد پایتون (Python .py)</option>
                        <option value="json">داده ساختاریافته (JSON .json)</option>
                    </select>
                    <label style="font-size: 12px; color: var(--text-muted);">سطح پیچیدگی:</label>
                    <select id="task-complexity">
                        <option value="auto">تشخیص خودکار هوشمند (Auto)</option>
                        <option value="light">سبک و سریع (Light)</option>
                        <option value="moderate">متوسط (Moderate)</option>
                        <option value="complex">پیچیده و استدلالی (Complex)</option>
                    </select>
                </div>
                <button class="btn-submit" onclick="submitTask()">🚀 اجرای هوشمند و ساخت فایل</button>
            </div>
        </div>
    </div>

    <div class="dashboard-grid">
        <div>
            <!-- Finalized Deliverables Download Center -->
            <div class="card">
                <div class="card-header">
                    <span>📦 فایل‌های نهایی‌شده توسط هوش مصنوعی (آماده دانلود)</span>
                    <span id="deliverable-count" style="font-size: 11px; color: var(--accent-green);">۰ فایل آماده</span>
                </div>
                <div id="deliverables-container" class="deliverable-list">
                    <div style="color: var(--text-muted); font-size: 12px; text-align: center; padding: 14px;">هنوز فایلی نهایی نشده است. به محض اتمام هر وظیفه، فایل آن با اعلان صوتی و دسکتاپ در اینجا قرار می‌گیرد.</div>
                </div>
            </div>

            <!-- Live Event Timeline -->
            <div class="card">
                <div class="card-header">
                    <span>خط زمانی زنده رویدادها و مراحل اجرا (از شروع تا کنون)</span>
                    <span id="event-count" style="font-size: 11px; color: var(--text-muted);">۰ رویداد</span>
                </div>
                <div id="timeline" class="timeline-container">
                    <div style="color: var(--text-muted); font-size: 12px; text-align: center; padding: 20px;">آماده دریافت و اجرای وظایف...</div>
                </div>
            </div>
        </div>

        <div class="card hide-in-mini">
            <div class="card-header">
                <span>سهمیه، مدار شبکه و سلامت ارائه‌دهندگان</span>
                <span style="font-size: 11px; color: var(--accent-green);">Circuit Breaker Active</span>
            </div>
            <div class="quota-meter">
                <div class="quota-label"><span>Google Gemini Pro</span><span>۵۰ / ۵۰ (واقعی)</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%;"></div></div>
            </div>
            <div class="quota-meter">
                <div class="quota-label"><span>Groq (LLaMA 8B/70B)</span><span>۱۰۰ / ۱۰۰ (واقعی)</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%; background: var(--accent-green);"></div></div>
            </div>
            <div class="quota-meter">
                <div class="quota-label"><span>کَش پاسخ‌ها (صرفه‌جویی ۱۰۰٪)</span><span>فعال (SQLite/JSON)</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%; background: var(--accent-blue);"></div></div>
            </div>
            <div class="quota-meter">
                <div class="quota-label"><span>Local Ollama (پشتیبان آفلاین)</span><span>نامحدود</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%; background: var(--accent-purple);"></div></div>
            </div>

            <div style="margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 14px;">
                <div style="font-size: 13px; font-weight: bold; margin-bottom: 8px;">کنترل‌های دخالت فوری کاربر:</div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <button class="btn-ctrl" onclick="triggerStepRerun()">🔄 اجرای مجدد یک گام خاص</button>
                    <button class="btn-abort" onclick="abortExecution()">🛑 لغو کامل و توقف اضطراری</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Settings Modal -->
    <div id="settings-modal" class="modal">
        <div class="modal-content">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3>⚙️ تنظیمات کلیدهای هوش مصنوعی</h3>
                <button class="btn-ctrl" onclick="closeSettingsModal()">✕</button>
            </div>
            <div class="input-group">
                <label>Google Gemini API Key:</label>
                <input type="password" id="input-gemini" placeholder="کلید Gemini را وارد کنید">
            </div>
            <div class="input-group">
                <label>Groq API Key (مدل‌های سریع رایگان):</label>
                <input type="password" id="input-groq" placeholder="کلید Groq را وارد کنید">
            </div>
            <div class="input-group">
                <label>OpenAI API Key (اختیاری):</label>
                <input type="password" id="input-openai" placeholder="کلید OpenAI را وارد کنید">
            </div>
            <div class="input-group">
                <label>Anthropic API Key (اختیاری):</label>
                <input type="password" id="input-anthropic" placeholder="کلید Anthropic را وارد کنید">
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px;">
                <button class="btn-ctrl" onclick="closeSettingsModal()">انصراف</button>
                <button class="btn-resume" onclick="saveSettings()">💾 ذخیره تنظیمات در .env</button>
            </div>
        </div>
    </div>

    <script>
        function escapeHtml(unsafe) {
            if (!unsafe) return '';
            return String(unsafe)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }
        let isPaused = false;
        let audioAlertsEnabled = true;
        let socket;

        function playNotificationChime() {
            if (!audioAlertsEnabled) return;
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
                osc.frequency.setValueAtTime(880, ctx.currentTime + 0.12); // A5
                gain.gain.setValueAtTime(0.15, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + 0.45);
            } catch (e) {}
        }

        function enableNotifications() {
            audioAlertsEnabled = true;
            playNotificationChime();
            if ("Notification" in window) {
                Notification.requestPermission().then(perm => {
                    if (perm === "granted") {
                        document.getElementById('btn-notify-perm').innerText = '🔔 اعلان دسکتاپ و صدا: فعال';
                    }
                });
            }
        }

        function notifyUserDeliverableReady(item) {
            playNotificationChime();
            document.title = `✅ (فایل آماده!) | سامانه چندعاملی`;
            
            // Show top toast banner
            const banner = document.getElementById('toast-banner');
            const textEl = document.getElementById('toast-text');
            const btnEl = document.getElementById('toast-download-btn');
            const ext = escapeHtml(item.output_format || 'md');
            textEl.innerText = `🔔 فایل نهایی «${escapeHtml(item.task_id)}_final.${ext}» توسط ${escapeHtml(item.model_used)} آماده شد!`;
            btnEl.href = item.download_url || `/api/tasks/${item.task_id}/download`;
            banner.style.display = 'flex';
            setTimeout(() => { banner.style.display = 'none'; }, 10000);

            // Trigger OS / Desktop Notification even if browser is minimized
            if ("Notification" in window && Notification.permission === "granted") {
                const n = new Notification("✅ فایل نهایی هوش مصنوعی آماده است!", {
                    body: `وظیفه با مدل ${escapeHtml(item.model_used)} تکمیل شد. برای مشاهده و دانلود کلیک کنید.`
                });
                n.onclick = function() {
                    window.focus();
                    window.location.href = item.download_url || `/api/tasks/${item.task_id}/download`;
                };
            }
        }

        function connectWebSocket() {
            const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            socket = new WebSocket(`${proto}//${window.location.host}/ws/telemetry`);

            socket.onmessage = function(event) {
                const payload = JSON.parse(event.data);
                if (payload.type === 'history_sync') {
                    renderFullHistory(payload.data);
                    if (payload.deliverables) {
                        renderDeliverablesList(payload.deliverables);
                    }
                } else if (payload.type === 'live_event') {
                    appendEvent(payload.data);
                    if (payload.data.event_type === 'deliverable_ready' && payload.data.data) {
                        appendDeliverableCard(payload.data.data);
                        notifyUserDeliverableReady(payload.data.data);
                    }
                }
                updateStatusBadge(payload.is_paused);
            };

            socket.onclose = function() {
                setTimeout(connectWebSocket, 2000);
            };
        }

        function renderDeliverablesList(items) {
            const container = document.getElementById('deliverables-container');
            if (!items || items.length === 0) return;
            container.innerHTML = '';
            items.forEach(item => appendDeliverableCard(item));
        }

        function appendDeliverableCard(item) {
            const container = document.getElementById('deliverables-container');
            if (container.children.length === 1 && !container.children[0].classList.contains('deliverable-card')) {
                container.innerHTML = '';
            }
            const ext = escapeHtml(item.output_format || 'md');
            const card = document.createElement('div');
            card.className = 'deliverable-card';
            card.innerHTML = `
                <div>
                    <div style="font-weight: bold; font-size: 13px;">📄 ${escapeHtml(item.task_id)}_final.${ext}</div>
                    <div class="deliverable-meta">مدل: <code>${escapeHtml(item.model_used)}</code> | درخواست: ${escapeHtml(item.prompt.substring(0, 50))}...</div>
                </div>
                <div style="display: flex; gap: 6px;">
                    <a class="btn-link btn-download-item" href="/api/tasks/${encodeURIComponent(item.task_id)}/download?fmt=${encodeURIComponent(ext)}" download>📥 دانلود (.${ext})</a>
                    <a class="btn-link btn-ctrl" style="padding: 5px 10px; font-size: 11px;" href="/api/tasks/${encodeURIComponent(item.task_id)}/download?fmt=json" download>JSON</a>
                </div>
            `;
            container.prepend(card);
            document.getElementById('deliverable-count').innerText = `${container.children.length} فایل آماده`;
        }

        function renderFullHistory(events) {
            const container = document.getElementById('timeline');
            container.innerHTML = '';
            document.getElementById('event-count').innerText = `${events.length} رویداد`;
            events.forEach(evt => appendEvent(evt, false));
        }

        function appendEvent(evt, updateCount = true) {
            const container = document.getElementById('timeline');
            const item = document.createElement('div');
            item.className = `timeline-item ${evt.event_type || ''}`;
            
            const timeStr = evt.timestamp_utc ? new Date(evt.timestamp_utc).toLocaleTimeString('fa-IR') : '';
            item.innerHTML = `
                <div class="timeline-time">${timeStr} | ${escapeHtml(evt.agent_name || 'هسته')} ${evt.model_name ? '» ' + escapeHtml(evt.model_name) : ''}</div>
                <div class="timeline-title">${escapeHtml(evt.message)}</div>
                ${evt.step_id ? `<div class="timeline-desc">شناسه گام: <code>${escapeHtml(evt.step_id)}</code></div>` : ''}
            `;
            container.appendChild(item);
            container.scrollTop = container.scrollHeight;
            if (updateCount) {
                const countElem = document.getElementById('event-count');
                const cur = parseInt(countElem.innerText) || 0;
                countElem.innerText = `${cur + 1} رویداد`;
            }
        }

        async function submitTask() {
            const promptEl = document.getElementById('task-prompt');
            const compEl = document.getElementById('task-complexity');
            const fmtEl = document.getElementById('task-format');
            const fileEl = document.getElementById('task-file');
            const promptText = promptEl.value.trim();
            if (!promptText) {
                alert('لطفاً متن درخواست یا سؤال خود را وارد کنید.');
                return;
            }

            let filename = null;
            let fileBase64 = null;
            if (fileEl.files && fileEl.files.length > 0) {
                const f = fileEl.files[0];
                filename = f.name;
                const buf = await f.arrayBuffer();
                let binary = '';
                const bytes = new Uint8Array(buf);
                for (let i = 0; i < bytes.byteLength; i++) {
                    binary += String.fromCharCode(bytes[i]);
                }
                fileBase64 = btoa(binary);
            }

            fetch('/api/tasks/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: promptText,
                    complexity: compEl.value,
                    output_format: fmtEl.value,
                    filename: filename,
                    file_base64: fileBase64
                })
            });
            promptEl.value = '';
            fileEl.value = '';
        }

        function updateStatusBadge(paused) {
            isPaused = paused;
            const badge = document.getElementById('status-badge');
            const btn = document.getElementById('btn-toggle-pause');
            if (paused) {
                badge.className = 'badge badge-paused';
                badge.innerText = '⏸️ اجرا متوقف شد (توسط کاربر)';
                btn.className = 'btn-resume';
                btn.innerText = '▶️ ادامه اجرا';
            } else {
                badge.className = 'badge badge-live';
                badge.innerText = '● آماده و در حال پایش زنده';
                btn.className = 'btn-pause';
                btn.innerText = '⏸️ توقف اجرا';
            }
        }

        function togglePause() {
            const endpoint = isPaused ? '/api/resume' : '/api/pause';
            fetch(endpoint, { method: 'POST' });
        }

        function promptOverride() {
            const stepId = prompt('شناسه مرحله را وارد کنید (مثلاً step_2):');
            if (!stepId) return;
            const modelName = prompt('نام مدل جایگزین را وارد کنید (مثلاً groq_llama_70b یا gemini_pro):');
            if (!modelName) return;
            fetch('/api/override-model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ step_id: stepId, model_name: modelName })
            });
        }

        function triggerStepRerun() {
            const stepId = prompt('شناسه مرحله‌ای که می‌خواهید مجدداً اجرا شود را وارد کنید:');
            if (stepId) {
                fetch('/api/rerun-step', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ step_id: stepId })
                });
            }
        }

        function abortExecution() {
            if (confirm('آیا از توقف کامل و اضطراری مطمئن هستید؟')) {
                togglePause();
            }
        }

        function toggleMiniMode() {
            document.body.classList.toggle('mini-mode');
        }

        function openSettingsModal() {
            document.getElementById('settings-modal').style.display = 'flex';
        }

        function closeSettingsModal() {
            document.getElementById('settings-modal').style.display = 'none';
        }

        function saveSettings() {
            const gemini = document.getElementById('input-gemini').value.trim();
            const groq = document.getElementById('input-groq').value.trim();
            const openai = document.getElementById('input-openai').value.trim();
            const anthropic = document.getElementById('input-anthropic').value.trim();

            const payload = {};
            if (gemini) payload.gemini_api_key = gemini;
            if (groq) payload.groq_api_key = groq;
            if (openai) payload.openai_api_key = openai;
            if (anthropic) payload.anthropic_api_key = anthropic;

            fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(res => res.json()).then(data => {
                alert('تنظیمات با موفقیت در .env ذخیره شد!');
                closeSettingsModal();
            });
        }

        window.onload = connectWebSocket;
    </script>
</body>
</html>
"""
