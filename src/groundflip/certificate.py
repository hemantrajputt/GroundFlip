"""Portable, integrity-verifiable GroundFlip test certificates.

An unkeyed digest detects accidental changes when independently pinned. Optional
HMAC verification authenticates the artifact to holders of the shared key. Neither
mechanism establishes that evidence was true or exposes a model's internal cause.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .store import canonical_json, redact, sha256_json

PREDICATE_TYPE = "https://groundflip.dev/attestation/evidence-dependence/v1"


def _safe_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return dict(redact(result))


def _provider_metadata(branch: Any) -> dict[str, Any]:
    if not isinstance(branch, Mapping):
        return {}
    return {
        "provider": branch.get("provider"),
        "model": branch.get("model"),
        "latency_ms": branch.get("latency_ms"),
        "usage": branch.get("usage", {}),
        "response_id": branch.get("response_id"),
    }


def _branch_run_summaries(safe: Mapping[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    raw_runs = safe.get("runs", [])
    if not isinstance(raw_runs, list):
        return summaries
    for run in raw_runs:
        if not isinstance(run, Mapping):
            continue
        control = run.get("control", {})
        intervention = run.get("intervention", {})
        summaries.append(
            {
                "index": run.get("index"),
                "seed": run.get("seed"),
                "order": run.get("order"),
                "target_control": run.get("target_control"),
                "target_intervention": run.get("target_intervention"),
                "target_pass": run.get("target_pass"),
                "controls_pass": run.get("controls_pass"),
                "control_output_sha256": sha256_json(control),
                "intervention_output_sha256": sha256_json(intervention),
                "control_metadata": _provider_metadata(control),
                "intervention_metadata": _provider_metadata(intervention),
            }
        )
    return summaries


def _authenticated_payload(certificate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": certificate.get("schema_version"),
        "generated_at": certificate.get("generated_at"),
        "authentication_policy": certificate.get("authentication_policy"),
        "statement": certificate.get("statement"),
    }


def create_certificate(
    result: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    signing_key: str | bytes | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    safe = _safe_result(result)
    result_digest = sha256_json(safe)
    generated = generated_at or datetime.now(UTC).isoformat()
    run_summaries = _branch_run_summaries(safe)
    influence_entry = {
        "target": safe.get("target_path"),
        "evidence_tool": safe.get("evidence_tool"),
        "evidence_path": safe.get("evidence_path"),
        "relation": safe.get("relation"),
        "verdict": safe.get("verdict"),
    }
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": str(safe.get("scenario_name", "groundflip-run")),
                "digest": {"sha256": result_digest},
            }
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "schema_version": safe.get("schema_version", "groundflip.result/v1"),
            "contract": {
                "name": safe.get("contract_name"),
                "relation": safe.get("relation"),
                "target": safe.get("target_path"),
                "evidence": {
                    "tool": safe.get("evidence_tool"),
                    "path": safe.get("evidence_path"),
                    "original_value": safe.get("original_value"),
                    "mutated_value": safe.get("mutated_value"),
                },
            },
            "influence_matrix": [influence_entry],
            "verdict": safe.get("verdict"),
            "statistics": {
                "target_success": safe.get("target_success"),
                "controls_success": safe.get("controls_success"),
                "control_churn": safe.get("control_churn"),
                "paired_effect": safe.get("paired_effect"),
                "replications": len(run_summaries),
            },
            "snapshot_hashes": safe.get("hashes", {}),
            "warnings": safe.get("warnings", []),
            "runs": run_summaries,
            "run_digest": result_digest,
        },
    }
    key = signing_key if signing_key is not None else os.environ.get("GROUNDFLIP_SIGNING_KEY")
    method = "hmac-sha256" if key else "sha256"
    key_id = signing_key_id or os.environ.get("GROUNDFLIP_SIGNING_KEY_ID")
    policy: dict[str, Any] = {"required_method": method}
    if key_id and method == "hmac-sha256":
        policy["key_id"] = key_id
    certificate: dict[str, Any] = {
        "schema_version": "groundflip.certificate/v1",
        "generated_at": generated,
        "authentication_policy": policy,
        "statement": statement,
    }
    authenticated_payload = canonical_json(_authenticated_payload(certificate)).encode("utf-8")
    payload_digest = hashlib.sha256(authenticated_payload).hexdigest()
    authentication: dict[str, Any] = {
        "payload_sha256": payload_digest,
        "method": method,
    }
    if key:
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key
        authentication["hmac_sha256"] = hmac.new(
            key_bytes, authenticated_payload, hashlib.sha256
        ).hexdigest()
    certificate["authentication"] = authentication
    return certificate


def verify_certificate(
    certificate: Mapping[str, Any],
    *,
    signing_key: str | bytes | None = None,
    require_hmac: bool = False,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if certificate.get("schema_version") != "groundflip.certificate/v1":
        reasons.append("unsupported certificate schema")
    statement = certificate.get("statement")
    authentication = certificate.get("authentication")
    policy = certificate.get("authentication_policy")
    if not isinstance(statement, Mapping) or not isinstance(authentication, Mapping):
        return False, reasons + ["statement or authentication is missing"]
    if not isinstance(policy, Mapping):
        reasons.append("authentication policy is missing")
        policy = {}

    authenticated_payload = canonical_json(_authenticated_payload(certificate)).encode("utf-8")
    actual_digest = hashlib.sha256(authenticated_payload).hexdigest()
    expected_digest = str(authentication.get("payload_sha256", ""))
    if not hmac.compare_digest(actual_digest, expected_digest):
        reasons.append("payload SHA-256 does not match")

    method = authentication.get("method")
    required_method = policy.get("required_method")
    if method != required_method:
        reasons.append("authentication method does not match the signed policy")
    key = signing_key if signing_key is not None else os.environ.get("GROUNDFLIP_SIGNING_KEY")
    if (require_hmac or key is not None) and method != "hmac-sha256":
        reasons.append("HMAC authentication was required but is not present")

    if method == "hmac-sha256":
        if not key:
            reasons.append("certificate is HMAC-authenticated but no verification key was supplied")
        else:
            key_bytes = key.encode("utf-8") if isinstance(key, str) else key
            expected_hmac = hmac.new(key_bytes, authenticated_payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_hmac, str(authentication.get("hmac_sha256", ""))):
                reasons.append("HMAC does not match")
    elif method == "sha256":
        if "hmac_sha256" in authentication:
            reasons.append("checksum-only certificate unexpectedly contains an HMAC")
    else:
        reasons.append("unsupported authentication method")
    return not reasons, reasons


def write_certificate(path: str | Path, certificate: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(redact(certificate), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def read_certificate(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
