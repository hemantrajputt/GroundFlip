import json
from copy import deepcopy

import pytest

from groundflip.cassette import (
    CassetteIntegrityError,
    CassetteRecorder,
    InterventionEngine,
    canonical_request_id,
    load_cassette,
    verify_cassette,
)


def test_request_ids_are_type_safe():
    assert canonical_request_id(1) != canonical_request_id("1")
    assert canonical_request_id(True) != canonical_request_id(1)


def test_cassette_preserves_unknown_fields_and_redacts_secrets(tmp_path):
    recorder = CassetteRecorder(["server", "--api-key", "sk-abcdefghijklmnop1234"])
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "lookup", "arguments": {"token": "secret", "x": 1}},
        "x-extra": 9,
    }
    raw = json.dumps(request) + "\r\n"
    frame, message = recorder.record_frame("client_to_server", raw)
    pending = recorder.begin_tool_call(frame, message)
    response = {"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": {"x": 1}}}
    response_frame, safe_response = recorder.record_frame(
        "server_to_client", json.dumps(response) + "\n"
    )
    recorder.finish_tool_call(response_frame, safe_response, pending)
    path = tmp_path / "cassette.json"
    document = recorder.write(path, 0)
    assert verify_cassette(document) == []
    serialized = path.read_text(encoding="utf-8")
    assert "sk-abcdefghijkl" not in serialized
    assert '"x-extra": 9' in serialized
    assert load_cassette(path)["calls"][0]["status"] == "completed"


def test_tampering_is_detected(tmp_path):
    recorder = CassetteRecorder(["server"])
    recorder.record_frame("client_to_server", '{"jsonrpc":"2.0"}\n')
    path = tmp_path / "cassette.json"
    document = recorder.write(path, 0)
    tampered = deepcopy(document)
    tampered["frames"][0]["raw"] = "tampered"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CassetteIntegrityError):
        load_cassette(path)


def test_intervention_only_mutates_result_and_records_hashes(tmp_path):
    rules = {
        "schema_version": "groundflip.interventions/v1",
        "interventions": [
            {
                "id": "flip-price",
                "tool": "lookup",
                "path": "$.structuredContent.price",
                "value": 17,
                "arguments": {"region": "West"},
            }
        ],
    }
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    engine = InterventionEngine.from_file(path)
    response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"structuredContent": {"price": 42}},
        "outside": {"price": 999},
    }
    changed, events = engine.apply_response(
        tool_name="lookup",
        arguments={"region": "West", "extra": True},
        request_id=1,
        response=response,
    )
    assert changed["result"]["structuredContent"]["price"] == 17
    assert changed["outside"]["price"] == 999
    assert events[0]["status"] == "replaced"
    assert "before_sha256" in events[0]
