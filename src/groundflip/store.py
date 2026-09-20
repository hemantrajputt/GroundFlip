"""Canonical serialization, redaction, and local content-addressed storage."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_SENSITIVE_KEYS = re.compile(
    r"(?:api[-_]?key|authorization|password|passwd|secret|token|cookie|session)", re.I
)
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\blsv2_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.I),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{16,}\b"),
)


def redact(value: Any, *, key: str = "") -> Any:
    if key and _SENSITIVE_KEYS.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        result = value
        for pattern in _SECRET_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        return result
    return value


def canonical_json(value: Any, *, apply_redaction: bool = False) -> str:
    payload = redact(value) if apply_redaction else value
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )


def sha256_json(value: Any, *, apply_redaction: bool = False) -> str:
    return hashlib.sha256(
        canonical_json(value, apply_redaction=apply_redaction).encode("utf-8")
    ).hexdigest()


class ContentAddressedStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.blobs = self.root / "blobs" / "sha256"
        self.manifests = self.root / "manifests"

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".groundflip-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def put_json(self, value: Any) -> str:
        safe = redact(value)
        content = canonical_json(safe)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        target = self.blobs / digest[:2] / f"{digest}.json"
        if not target.exists():
            self._atomic_write(target, content + "\n")
        return digest

    def get_json(self, digest: str) -> Any:
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid SHA-256 digest")
        path = self.blobs / digest[:2] / f"{digest}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def write_manifest(self, name: str, value: Any) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", name).strip(".-")
        if not safe_name:
            raise ValueError("Manifest name has no safe characters")
        safe = redact(value)
        self.put_json(safe)
        path = self.manifests / f"{safe_name}.json"
        self._atomic_write(path, json.dumps(safe, indent=2, sort_keys=True) + "\n")
        return path
