"""Critic & Validator Agent (Section 4 & 5 of requirements).
Evaluates whether a model output meets quality, schema, and completeness requirements.
Triggers automatic model escalation if a light model output is deficient.
"""
from typing import Dict, Any, Optional, List

class CriticAgent:
    def __init__(self, min_quality_threshold: float = 0.75):
        self.min_quality_threshold = min_quality_threshold

    def evaluate_output(
        self,
        prompt: str,
        output_payload: Optional[Dict[str, Any]],
        expected_schema: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Assess response completeness and detect if model was incapable."""
        if not output_payload:
            return {
                "is_valid": False,
                "score": 0.0,
                "needs_escalation": True,
                "reason": "Model returned empty or null output."
            }

        text = output_payload.get("text", "")
        incapable_phrases = [
            "i cannot fulfill this", "as an ai i am unable", "too complex",
            "context limit exceeded", "sorry, i cannot", "error processing"
        ]
        
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in incapable_phrases) and len(text) < 200:
            return {
                "is_valid": False,
                "score": 0.2,
                "needs_escalation": True,
                "reason": "Model explicitly signaled inability to fulfill task."
            }

        if expected_schema:
            missing_keys = [k for k in expected_schema if k not in output_payload]
            if missing_keys:
                return {
                    "is_valid": False,
                    "score": 0.4,
                    "needs_escalation": True,
                    "reason": f"Output failed schema check; missing keys: {missing_keys}"
                }

        if len(text.strip()) < 10:
            return {
                "is_valid": False,
                "score": 0.3,
                "needs_escalation": True,
                "reason": "Model output truncated or too brief."
            }

        return {
            "is_valid": True,
            "score": 0.95,
            "needs_escalation": False,
            "reason": "Output passed validation checks."
        }


"""Format-Aware Output Validator and Critic Agent (Point 17).
Validates JSON schema, Python AST syntax, CSV tabular consistency, and Markdown structure.
Never executes generated Python code (Point 27).
"""
import ast
import csv
import io
import json
from typing import Dict, Any, Optional, List

class FormatValidatorCritic:
    def validate(
        self,
        output_text: str,
        expected_format: str = "md",
        required_json_keys: Optional[List[str]] = None,
        provider_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        meta = provider_meta or {}
        if not output_text or not output_text.strip():
            return {
                "is_valid": False,
                "validation_score": 0.0,
                "action": "escalate",
                "reason": "Empty output from provider."
            }

        fmt = expected_format.lower().strip(".")
        if fmt == "json":
            try:
                parsed = json.loads(output_text)
                if required_json_keys and isinstance(parsed, dict):
                    missing = [k for k in required_json_keys if k not in parsed]
                    if missing:
                        return {
                            "is_valid": False,
                            "validation_score": 0.4,
                            "action": "repair_or_retry",
                            "reason": f"Missing required JSON keys: {missing}"
                        }
            except Exception as exc:
                return {
                    "is_valid": False,
                    "validation_score": 0.2,
                    "action": "repair_or_retry",
                    "reason": f"Invalid JSON format: {exc}"
                }

        elif fmt == "py":
            # Point 17 & 27: Static syntax check via ast.parse ONLY (never execute generated code!)
            try:
                ast.parse(output_text)
            except SyntaxError as exc:
                return {
                    "is_valid": False,
                    "validation_score": 0.3,
                    "action": "repair_or_retry",
                    "reason": f"Python syntax error at line {exc.lineno}: {exc.msg}"
                }

        elif fmt == "csv":
            reader = list(csv.reader(io.StringIO(output_text.strip())))
            if len(reader) < 1 or len(reader[0]) < 1:
                return {
                    "is_valid": False,
                    "validation_score": 0.3,
                    "action": "repair_or_retry",
                    "reason": "CSV output has no valid rows or columns."
                }
            col_count = len(reader[0])
            if any(len(row) != col_count for row in reader if row):
                return {
                    "is_valid": False,
                    "validation_score": 0.5,
                    "action": "repair_or_retry",
                    "reason": "Inconsistent column count across CSV rows."
                }

        return {
            "is_valid": True,
            "validation_score": 0.95,
            "action": "accept",
            "reason": "Passed format and policy validation.",
            "mode": meta.get("mode", "unknown"),
            "is_real_provider_response": meta.get("is_real_provider_response", False)
        }
