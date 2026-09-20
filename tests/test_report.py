from groundflip.certificate import create_certificate
from groundflip.report import render_html, render_markdown


def sample_certificate(signing_key=None):
    return create_certificate(
        {
            "schema_version": "groundflip.result/v1",
            "scenario_name": "demo",
            "contract_name": "price <script>alert(1)</script> | # injected",
            "verdict": "PASS",
            "relation": "tracks_value",
            "target_path": "$.amount|unexpected",
            "evidence_tool": "quote",
            "evidence_path": "$.price",
            "original_value": 10,
            "mutated_value": 20,
            "target_success": {"estimate": 1, "lower": 0.7, "upper": 1},
            "controls_success": {"estimate": 1, "lower": 0.7, "upper": 1},
            "control_churn": 0,
            "paired_effect": 1,
            "runs": [
                {
                    "index": 0,
                    "target_control": "10 | <script>bad()</script>",
                    "target_intervention": 20,
                    "target_pass": True,
                    "controls_pass": True,
                    "control": {
                        "provider": "scripted",
                        "model": "fixture-v1",
                        "latency_ms": 0,
                        "usage": {},
                    },
                    "intervention": {
                        "provider": "scripted",
                        "model": "fixture-v1",
                        "latency_ms": 0,
                        "usage": {},
                    },
                }
            ],
            "hashes": {},
            "warnings": ["Synthetic sensitivity probe. | <script>warning()</script>"],
        },
        generated_at="2026-08-07T00:00:00Z",
        signing_key=signing_key,
    )


def test_html_is_self_contained_accessible_escaped_printable_and_has_matrix():
    output = render_html(sample_certificate())
    assert "<!doctype html>" in output
    assert "Content-Security-Policy" in output
    assert "<caption" in output
    assert 'scope="col"' in output
    assert 'scope="row"' in output
    assert "@media print" in output
    assert 'class="table-wrap"' in output
    assert "https://" not in output
    assert "<script>alert" not in output
    assert "<script>bad" not in output
    assert "&lt;script&gt;" in output
    assert "Claim/action x evidence-field influence matrix" in output
    assert "scripted / fixture-v1" in output
    assert "SHA-256 checksum" in output


def test_html_labels_hmac_without_claiming_world_truth():
    output = render_html(sample_certificate(signing_key="test-key"))
    assert "HMAC-SHA256" in output
    assert "proves evidence truth" in output


def test_markdown_escapes_html_and_table_delimiters_and_includes_matrix():
    output = render_markdown(sample_certificate())
    assert "## Paired executions" in output
    assert "## Claim/action x evidence-field influence matrix" in output
    assert "Synthetic sensitivity probe" in output
    assert r"SHA\-256 checksum" in output
    assert "does not prove real-world truth" in output
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
    assert "&#124;" in output or "\\|" in output

    certificate = sample_certificate()
    predicate = certificate["statement"]["predicate"]
    predicate["statistics"] = None
    predicate["runs"] = None
    html_output = render_html(certificate)
    markdown_output = render_markdown(certificate)
    assert "n/a" in html_output
    assert "n/a" in markdown_output
