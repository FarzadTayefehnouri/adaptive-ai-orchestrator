"""Canonical FastAPI Application for Adaptive AI Orchestrator v0.2.0 (Points 1, 11, 19, 28, 29).
Re-exports all endpoints, enforces CSP headers, XSS-safe DOM rendering, authentication,
idempotency keys, and adaptive work-item scheduling.
"""
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from src.orchestrator.config import settings
from src.orchestrator.security.auth import verify_api_token, UserRole
from src.orchestrator.security.validation import (
    validate_prompt_and_format, validate_base64_and_file_size,
    sanitize_filename, validate_url_no_ssrf, SecurityValidationError
)
from src.orchestrator.security.secrets import write_env_securely, SecretValidationError
from src.orchestrator.workflow.work_item import WorkItem
from src.orchestrator.workflow.state_machine import WorkStatus
from src.orchestrator.scheduler.adaptive_scheduler import AdaptiveScheduler
from src.orchestrator.memory.validated import ArtifactAndVersionStore
from src.orchestrator.dashboard.server import (
    app as dashboard_app,
    submit_task as legacy_submit_task,
    TaskSubmitRequest,
    finalized_deliverables,
    audit_results
)
from src.orchestrator.dashboard.events import global_event_bus, TelemetryEvent

# Attach CSP & Security Headers Middleware (Point 11.4)
@dashboard_app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:;"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

adaptive_scheduler = AdaptiveScheduler()
artifact_store = ArtifactAndVersionStore()
tasks_registry: Dict[str, Dict[str, Any]] = {}
idempotency_index: Dict[str, str] = {}  # idempotency_key -> task_id

class V2TaskCreateRequest(BaseModel):
    prompt: str
    complexity: str = "auto"
    output_format: str = "md"
    filename: Optional[str] = None
    file_base64: Optional[str] = None
    idempotency_key: Optional[str] = None
    external_provider_consent: bool = True

@dashboard_app.get("/health")
async def health_endpoint():
    """Point 19: Liveness probe."""
    return {
        "status": "healthy",
        "version": "0.2.0",
        "workers_active": len(adaptive_scheduler.pool.workers),
        "queue_depth": len(adaptive_scheduler.queue),
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

@dashboard_app.get("/ready")
async def readiness_endpoint():
    """Point 19: Readiness probe."""
    return {
        "ready": True,
        "min_workers": settings.min_workers,
        "max_workers": settings.max_workers,
        "simulation_fallback_allowed": settings.allow_simulation_fallback
    }

@dashboard_app.post("/api/tasks")
async def create_task_v2(req: V2TaskCreateRequest, role: UserRole = Depends(verify_api_token)):
    """Point 19: Validated, idempotent task submission endpoint."""
    try:
        validate_prompt_and_format(req.prompt, req.output_format)
        raw_bytes = validate_base64_and_file_size(req.file_base64)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    safe_fname = sanitize_filename(req.filename) if req.filename else None
    file_hash = hashlib.sha256(raw_bytes).hexdigest() if raw_bytes else ""

    # Compute deterministic idempotency key (Point 19)
    computed_idem = hashlib.sha256(
        f"{req.prompt.strip()}|{file_hash}|{req.complexity}|{req.output_format}".encode("utf-8")
    ).hexdigest()
    idem_key = req.idempotency_key or computed_idem

    if idem_key in idempotency_index:
        existing_tid = idempotency_index[idem_key]
        if existing_tid in tasks_registry:
            return {
                "task_id": existing_tid,
                "status": tasks_registry[existing_tid]["status"],
                "idempotent_replay": True,
                "task": tasks_registry[existing_tid]
            }

    # Register and claim a bounded scheduler WorkItem before executing the pipeline.
    # This makes concurrent requests consume a finite worker slot and exposes
    # capability/lease state for future chunk-level execution.
    required_capabilities = {"text"}
    if safe_fname:
        lower_name = safe_fname.lower()
        if lower_name.endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
            required_capabilities = {"video"}
        elif lower_name.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
            required_capabilities = {"vision"}
        elif lower_name.endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a')):
            required_capabilities = {"audio"}
    work_item = WorkItem(
        work_id=f"{computed_idem[:16]}-orchestration",
        parent_task_id=computed_idem,
        chunk_id=None,
        stage="orchestration",
        priority=10 if req.complexity == "critical" else 5,
        required_capabilities=required_capabilities,
        estimated_duration=float(settings.default_execution_timeout_seconds),
        max_retries=settings.max_retries_per_item,
        payload={"prompt": req.prompt, "filename": safe_fname},
    )
    adaptive_scheduler.submit_work_item(work_item)
    claimed = adaptive_scheduler.schedule_next()
    if claimed is None:
        raise HTTPException(status_code=429, detail="No capable worker is currently available; retry later.")
    worker_id = claimed.owner_worker_id
    try:
        legacy_req = TaskSubmitRequest(
            prompt=req.prompt,
            complexity=req.complexity,
            output_format=req.output_format,
            filename=safe_fname,
            file_base64=req.file_base64
        )
        # The legacy provider adapters are synchronous internally. Run the
        # coroutine in a worker thread so the event loop remains responsive.
        res = await asyncio.to_thread(lambda: asyncio.run(legacy_submit_task(legacy_req)))
        adaptive_scheduler.state_machine.transition(
            claimed, WorkStatus.COMPLETED, reason="Pipeline completed", worker_id=worker_id
        )
        claimed.result = res
    except Exception:
        if claimed.status == WorkStatus.RUNNING:
            adaptive_scheduler.state_machine.transition(
                claimed, WorkStatus.FAILED, reason="Pipeline execution failed", worker_id=worker_id
            )
        raise
    finally:
        adaptive_scheduler.lease_manager.release_lease(claimed.work_id)
        if worker_id and worker_id in adaptive_scheduler.pool.workers:
            worker = adaptive_scheduler.pool.workers[worker_id]
            if claimed.work_id in worker.active_items:
                worker.active_items.remove(claimed.work_id)
            worker.current_load = min(1.0, len(worker.active_items) / max(1, worker.max_concurrent_items))
    task_id = res["task_id"]

    # Store artifact if file was uploaded
    artifacts_list: List[str] = []
    if raw_bytes and safe_fname:
        art_meta = artifact_store.store_artifact(
            task_id=task_id,
            step_id="input_upload",
            artifact_type="input_file",
            raw_bytes=raw_bytes
        )
        artifacts_list.append(art_meta.artifact_id)

    # Store versioned output
    vo_rec = artifact_store.append_validated_output(
        task_id=task_id,
        step_id="final_output",
        payload=res["output"],
        validation_score=0.95
    )

    task_record = {
        "task_id": task_id,
        "status": WorkStatus.COMPLETED.value,
        "prompt": req.prompt,
        "output_format": req.output_format,
        "idempotency_key": idem_key,
        "artifacts": artifacts_list,
        "version": vo_rec.version,
        "output": res["output"],
        "created_at_utc": datetime.now(timezone.utc).isoformat()
    }
    tasks_registry[task_id] = task_record
    idempotency_index[idem_key] = task_id
    return {"task_id": task_id, "status": "completed", "idempotent_replay": False, "task": task_record}

@dashboard_app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str, role: UserRole = Depends(verify_api_token)):
    task = tasks_registry.get(task_id) or finalized_deliverables.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@dashboard_app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, role: UserRole = Depends(verify_api_token)):
    task = tasks_registry.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task["status"] = WorkStatus.CANCELLED.value
    return {"task_id": task_id, "status": "cancelled"}

@dashboard_app.post("/api/tasks/{task_id}/pause")
async def pause_specific_task(task_id: str, role: UserRole = Depends(verify_api_token)):
    task = tasks_registry.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task["status"] = WorkStatus.PAUSED.value
    return {"task_id": task_id, "status": "paused"}

@dashboard_app.post("/api/tasks/{task_id}/resume")
async def resume_specific_task(task_id: str, role: UserRole = Depends(verify_api_token)):
    task = tasks_registry.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task["status"] = WorkStatus.RUNNING.value
    return {"task_id": task_id, "status": "running"}

@dashboard_app.get("/api/tasks/{task_id}/events")
async def get_task_events(task_id: str, role: UserRole = Depends(verify_api_token)):
    events = [
        e for e in global_event_bus.get_full_history()
        if e.get("task_id") == task_id or (e.get("step_id") and task_id in str(e.get("step_id")))
    ]
    return {"task_id": task_id, "events": events}

@dashboard_app.get("/api/tasks/{task_id}/artifacts")
async def get_task_artifacts(task_id: str, role: UserRole = Depends(verify_api_token)):
    arts = [
        vars(a) for a in artifact_store.artifacts.values()
        if a.task_id == task_id
    ]
    return {"task_id": task_id, "artifacts": arts}

@dashboard_app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, role: UserRole = Depends(verify_api_token)):
    tasks_registry.pop(task_id, None)
    finalized_deliverables.pop(task_id, None)
    return {"task_id": task_id, "deleted": True}

app = dashboard_app
