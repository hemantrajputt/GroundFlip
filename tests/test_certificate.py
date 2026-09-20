import hashlib
from copy import deepcopy

from groundflip.certificate import create_certificate, verify_certificate
from groundflip.demo import procurement_contracts, procurement_scenario
from groundflip.engine import ContractRunner
from groundflip.providers.scripted import ScriptedProvider
from groundflip.store import canonical_json


def result_payload():
    result = ContractRunner(ScriptedProvider()).run(
        next(iter(procurement_contracts(2))), procurement_scenario()
    )
    return result.to_dict()


def test_certificate_is_reproducible_for_the_same_artifact_and_verifies():
    kwargs = {
        "generated_at": "2026-08-07T00:00:00Z",
        "signing_key": "local-test-key",
        "signing_key_id": "test-key-v1",
    }
    payload = result_payload()
    first = create_certificate(payload, **kwargs)
    second = create_certificate(payload, **kwargs)
    assert first == second
    assert first["authentication_policy"]["key_id"] == "test-key-v1"
    assert verify_certificate(first, signing_key="local-test-key") == (True, [])


def test_tampered_certificate_fails_integrity():
    certificate = create_certificate(result_payload(), generated_at="x")
    tampered = deepcopy(certificate)
    tampered["statement"]["predicate"]["verdict"] = "PASS-WHEN-I-SAY-SO"
    valid, reasons = verify_certificate(tampered)
    assert not valid
    assert any("SHA-256" in reason for reason in reasons)


def test_timestamp_run_summaries_and_provider_metadata_are_covered():
    certificate = create_certificate(result_payload(), generated_at="2026-08-07T00:00:00Z")
    runs = certificate["statement"]["predicate"]["runs"]
    assert len(runs) == 2
    assert len(runs[0]["control_output_sha256"]) == 64
    assert len(runs[0]["intervention_output_sha256"]) == 64
    assert runs[0]["control_metadata"]["provider"] == "scripted"
    assert runs[0]["control_metadata"]["model"] == "scripted/grounded"

    tampered = deepcopy(certificate)
    tampered["generated_at"] = "1999-01-01T00:00:00Z"
    valid, reasons = verify_certificate(tampered)
    assert not valid
    assert any("SHA-256" in reason for reason in reasons)


def test_hmac_cannot_be_downgraded_to_recomputed_checksum():
    certificate = create_certificate(
        result_payload(), generated_at="2026-08-07T00:00:00Z", signing_key="secret-key"
    )
    downgraded = deepcopy(certificate)
    downgraded["authentication_policy"]["required_method"] = "sha256"
    downgraded["authentication"] = {"method": "sha256"}
    payload = {
        "schema_version": downgraded["schema_version"],
        "generated_at": downgraded["generated_at"],
        "authentication_policy": downgraded["authentication_policy"],
        "statement": downgraded["statement"],
    }
    downgraded["authentication"]["payload_sha256"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    valid, reasons = verify_certificate(downgraded, signing_key="secret-key")
    assert not valid
    assert any("required" in reason for reason in reasons)


def test_require_hmac_rejects_checksum_only_certificate():
    valid, reasons = verify_certificate(
        create_certificate(result_payload(), generated_at="x"), require_hmac=True
    )
    assert not valid
    assert any("required" in reason for reason in reasons)


def test_secrets_are_redacted_before_certification():
    payload = result_payload()
    payload["api_key"] = "sk-this-should-never-appear-123456"
    assert "sk-this" not in str(create_certificate(payload))
