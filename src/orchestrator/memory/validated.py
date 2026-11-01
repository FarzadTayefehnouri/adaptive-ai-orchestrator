"""Immutable Versioned Validated Outputs & Artifact Store (Points 15 & 20.2).
Never overwrites previous versions; links new versions via supersedes_id and stores SHA-256 hashes.
"""
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

@dataclass
class ArtifactMetadata:
    artifact_id: str
    artifact_type: str
    size_bytes: int
    sha256_hash: str
    task_id: str
    step_id: str
    version: int
    created_at_utc: str
    dependencies: List[str] = field(default_factory=list)
    is_valid: bool = True

@dataclass
class VersionedOutputRecord:
    record_id: str
    task_id: str
    step_id: str
    version: int
    output_hash: str
    validation_score: float
    payload: Dict[str, Any]
    created_at_utc: str
    supersedes_id: Optional[str] = None

class ArtifactAndVersionStore:
    def __init__(self):
        self.artifacts: Dict[str, ArtifactMetadata] = {}
        self.artifact_blobs: Dict[str, bytes] = {}
        self.versioned_outputs: List[VersionedOutputRecord] = []

    def store_artifact(
        self,
        task_id: str,
        step_id: str,
        artifact_type: str,
        raw_bytes: bytes,
        dependencies: Optional[List[str]] = None,
        version: int = 1
    ) -> ArtifactMetadata:
        digest = hashlib.sha256(raw_bytes).hexdigest()
        aid = f"art_{task_id}_{step_id}_v{version}_{digest[:8]}"
        meta = ArtifactMetadata(
            artifact_id=aid,
            artifact_type=artifact_type,
            size_bytes=len(raw_bytes),
            sha256_hash=digest,
            task_id=task_id,
            step_id=step_id,
            version=version,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            dependencies=dependencies or [],
            is_valid=True
        )
        self.artifacts[aid] = meta
        self.artifact_blobs[aid] = raw_bytes
        return meta

    def append_validated_output(
        self,
        task_id: str,
        step_id: str,
        payload: Dict[str, Any],
        validation_score: float
    ) -> VersionedOutputRecord:
        """Point 20.2: Never overwrite previous outputs; create a new versioned record linked by supersedes_id."""
        prior = [
            r for r in self.versioned_outputs
            if r.task_id == task_id and r.step_id == step_id
        ]
        prev_record = prior[-1] if prior else None
        next_version = (prev_record.version + 1) if prev_record else 1
        supersedes_id = prev_record.record_id if prev_record else None

        raw_str = repr(sorted(payload.items())).encode("utf-8")
        out_hash = hashlib.sha256(raw_str).hexdigest()
        rec = VersionedOutputRecord(
            record_id=f"vo_{uuid.uuid4().hex[:10]}",
            task_id=task_id,
            step_id=step_id,
            version=next_version,
            output_hash=out_hash,
            validation_score=validation_score,
            payload=payload,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            supersedes_id=supersedes_id
        )
        self.versioned_outputs.append(rec)
        return rec
