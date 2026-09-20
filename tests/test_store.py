from pathlib import Path

from groundflip.store import ContentAddressedStore, canonical_json, redact, sha256_json


def test_canonical_hash_is_order_independent():
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})
    assert sha256_json({"b": 2, "a": 1}) == sha256_json({"a": 1, "b": 2})


def test_redaction_covers_keys_and_token_patterns():
    safe = redact({"api_key": "secret", "note": "Bearer abcdefghijklmnopqrstuvwxyz"})
    assert safe == {"api_key": "[REDACTED]", "note": "[REDACTED]"}


def test_content_addressed_store_round_trip(tmp_path: Path):
    store = ContentAddressedStore(tmp_path)
    digest = store.put_json({"x": 1, "token": "never-store"})
    assert store.get_json(digest) == {"token": "[REDACTED]", "x": 1}
    path = store.write_manifest("demo/run", {"digest": digest})
    assert path.name == "demo-run.json"
