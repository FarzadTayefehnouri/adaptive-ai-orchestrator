"""Data schemas and types for tasks, execution steps, errors, and recovery plans."""
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

class TaskComplexity(str, Enum):
    LIGHT = "light"          # Simple lookup, formatting, short text
    MODERATE = "moderate"    # Standard summarization, translation, single-step transform
    COMPLEX = "complex"      # Multi-step reasoning, coding, deep synthesis
    CRITICAL = "critical"    # Security audit, architectural verification

class QuotaType(str, Enum):
    REAL = "real"            # Verified exact quota from provider API/headers
    ESTIMATED = "estimated"  # Heuristic estimation when provider does not disclose exact quota

class ErrorCategory(str, Enum):
    INPUT_ERROR = "input_error"
    PROVIDER_ERROR = "provider_error"      # Rate limit, 429, timeout
    MODEL_ERROR = "model_error"            # Incoherence, hallucination, refusal, incapable
    TOOL_ERROR = "tool_error"              # Sandbox/library failure
    AGENT_FAULT = "agent_fault"            # Logic fault in agent code
    DEPENDENCY_ERROR = "dependency_error"  # Upstream step delivered bad data
    ESCALATION_TRIGGER = "escalation_trigger" # Model incapable, promoted to higher tier

class TokenUsage(dict):
    def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0):
        super().__init__(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens

class ExecutionStep:
    def __init__(
        self,
        step_id: str,
        name: str,
        assigned_agent: str,
        dependencies: Optional[List[str]] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        model_used: Optional[str] = None,
        complexity: TaskComplexity = TaskComplexity.LIGHT,
        duration_ms: Optional[float] = None,
        token_usage: Optional[TokenUsage] = None,
        max_token_budget: Optional[int] = None
    ):
        self.step_id = step_id
        self.name = name
        self.assigned_agent = assigned_agent
        self.dependencies = dependencies or []
        self.input_payload = input_payload or {}
        self.output_payload = output_payload
        self.status = status
        self.model_used = model_used
        self.complexity = complexity
        self.duration_ms = duration_ms
        self.token_usage = token_usage or TokenUsage(0, 0)
        self.max_token_budget = max_token_budget
        self.escalation_count = 0
        self.escalation_log: List[Dict[str, Any]] = []
        self.created_at_utc = datetime.now(timezone.utc).isoformat()

    def record_escalation(self, from_model: str, to_model: str, reason: str, triggered_by: str = "system"):
        self.escalation_count += 1
        self.escalation_log.append({
            "from_model": from_model,
            "to_model": to_model,
            "reason": reason,
            "triggered_by": triggered_by,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        })
        self.model_used = to_model

class ErrorRecord:
    def __init__(
        self,
        error_id: str,
        step_id: str,
        category: ErrorCategory,
        severity: str,
        message: str,
        confidence: float = 1.0,
        root_cause_step_id: Optional[str] = None,
        impacted_downstream_steps: Optional[List[str]] = None
    ):
        self.error_id = error_id
        self.step_id = step_id
        self.category = category
        self.severity = severity
        self.message = message
        self.confidence = confidence
        self.root_cause_step_id = root_cause_step_id
        self.impacted_downstream_steps = impacted_downstream_steps or []
        self.timestamp_utc = datetime.now(timezone.utc).isoformat()
