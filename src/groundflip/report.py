"""Self-contained HTML and Markdown certificate reports."""

from __future__ import annotations

import html
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .store import redact


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _plain(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value).replace("\r", " ").replace("\n", " ")


def _escape(value: Any) -> str:
    return html.escape(_plain(value), quote=True)


def _md_text(value: Any) -> str:
    text = _plain(value).replace("\\", "\\\\")
    for character in "`*_{}[]()#+-.!|>":
        text = text.replace(character, f"\\{character}")
    return html.escape(text, quote=True)


def _md_code(value: Any) -> str:
    escaped = html.escape(_plain(value), quote=True)
    escaped = escaped.replace("|", "&#124;").replace("`", "&#96;")
    return f"<code>{escaped}</code>"


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def _integrity_label(certificate: Mapping[str, Any]) -> str:
    authentication = _mapping(certificate.get("authentication"))
    method = authentication.get("method")
    if method == "hmac-sha256":
        return "HMAC-SHA256; verification key required"
    if method == "sha256":
        return "SHA-256 checksum; independently pin digest"
    return "Unknown integrity method"


def _run_model(run: Mapping[str, Any]) -> str:
    metadata = _mapping(run.get("control_metadata"))
    provider = metadata.get("provider") or "unknown"
    model = metadata.get("model") or "unknown"
    return f"{provider} / {model}"


def _matrix_entries(
    predicate: Mapping[str, Any],
    contract: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> list[dict[str, str]]:
    raw = predicate.get("influence_matrix")
    entries: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            entries.append(
                {
                    "target": _plain(item.get("target")),
                    "evidence": _plain(
                        f"{_plain(item.get('evidence_tool'))} {_plain(item.get('evidence_path'))}"
                    ),
                    "relation": _plain(item.get("relation")),
                    "verdict": _plain(item.get("verdict")),
                }
            )
    if not entries:
        entries.append(
            {
                "target": _plain(contract.get("target")),
                "evidence": _plain(
                    f"{_plain(evidence.get('tool'))} {_plain(evidence.get('path'))}"
                ),
                "relation": _plain(contract.get("relation")),
                "verdict": _plain(predicate.get("verdict")),
            }
        )
    return entries


def _matrix_axes(
    entries: list[dict[str, str]],
) -> tuple[list[str], list[str], dict[tuple[str, str], list[str]]]:
    targets: list[str] = []
    evidences: list[str] = []
    cells: dict[tuple[str, str], list[str]] = {}
    for entry in entries:
        target = entry["target"]
        evidence = entry["evidence"]
        if target not in targets:
            targets.append(target)
        if evidence not in evidences:
            evidences.append(evidence)
        value = f"{entry['relation']} / {entry['verdict']}"
        cells.setdefault((target, evidence), []).append(value)
    return targets, evidences, cells


def _matrix_html(entries: list[dict[str, str]]) -> str:
    targets, evidences, cells = _matrix_axes(entries)
    headings = "".join(f'<th scope="col">{_escape(item)}</th>' for item in evidences)
    rows = []
    for target in targets:
        values = "".join(
            f"<td>{_escape('; '.join(cells.get((target, evidence), [])) or 'not tested')}</td>"
            for evidence in evidences
        )
        rows.append(f'<tr><th scope="row">{_escape(target)}</th>{values}</tr>')
    return (
        '<div class="table-wrap"><table><caption class="label">'
        "Claim/action x evidence-field influence matrix</caption>"
        f'<thead><tr><th scope="col">Claim / action</th>{headings}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _matrix_markdown(entries: list[dict[str, str]]) -> list[str]:
    targets, evidences, cells = _matrix_axes(entries)
    lines = [
        "## Claim/action x evidence-field influence matrix",
        "",
        "| Claim / action | " + " | ".join(_md_code(item) for item in evidences) + " |",
        "|---|" + "---|" * len(evidences),
    ]
    for target in targets:
        values = [
            _md_text("; ".join(cells.get((target, evidence), [])) or "not tested")
            for evidence in evidences
        ]
        lines.append(f"| {_md_code(target)} | " + " | ".join(values) + " |")
    lines.append("")
    return lines


def render_html(certificate: Mapping[str, Any]) -> str:
    safe = _mapping(redact(certificate))
    statement = _mapping(safe.get("statement"))
    predicate = _mapping(statement.get("predicate"))
    contract = _mapping(predicate.get("contract"))
    evidence = _mapping(contract.get("evidence"))
    stats = _mapping(predicate.get("statistics"))
    verdict = _plain(predicate.get("verdict", "UNKNOWN"))
    target_success = _mapping(stats.get("target_success"))
    controls_success = _mapping(stats.get("controls_success"))
    verdict_class = (
        verdict.lower() if verdict.lower() in {"pass", "fail", "inconclusive"} else "unknown"
    )
    integrity = _integrity_label(safe)
    matrix = _matrix_html(_matrix_entries(predicate, contract, evidence))

    raw_runs = predicate.get("runs", [])
    run_rows = ""
    for run in raw_runs if isinstance(raw_runs, list) else []:
        if not isinstance(run, Mapping):
            continue
        run_rows += (
            "<tr>"
            f"<td>{_escape(run.get('index'))}</td>"
            f"<td>{_escape(run.get('target_control'))}</td>"
            f"<td>{_escape(run.get('target_intervention'))}</td>"
            f"<td>{'PASS' if run.get('target_pass') else 'FAIL'}</td>"
            f"<td>{'PASS' if run.get('controls_pass') else 'FAIL'}</td>"
            f"<td>{_escape(_run_model(run))}</td>"
            "</tr>"
        )
    if not run_rows:
        run_rows = (
            f"<tr><td colspan='6'>{_escape(stats.get('replications', 0))} paired runs are "
            "referenced by branch-output hashes in the certificate.</td></tr>"
        )

    warnings = predicate.get("warnings", [])
    warning_html = "".join(
        f"<li>{_escape(item)}</li>" for item in warnings if isinstance(warnings, list)
    )
    if not warning_html:
        warning_html = "<li>No warnings recorded.</li>"

    authentication = _mapping(safe.get("authentication"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<title>GroundFlip - {_escape(contract.get("name", "certificate"))}</title>
<style>
:root{{--ink:#15211c;--muted:#61706a;--paper:#f5f4ed;--card:#fff;--line:#d9ded8;
--accent:#146b52;--pass:#0b704e;--fail:#a13030;--warn:#8b5d00}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1080px;margin:auto;padding:48px 24px 72px}} .eyebrow{{text-transform:uppercase;
letter-spacing:.13em;font-size:12px;color:var(--muted)}} h1{{font-size:clamp(34px,6vw,62px);
line-height:1;margin:.18em 0}} h2{{font-size:20px;margin:0 0 16px}} .lede{{font-size:18px;
max-width:760px;color:var(--muted)}} .status{{display:inline-flex;align-items:center;gap:8px;
border:1px solid currentColor;border-radius:999px;padding:7px 12px;font-weight:750}}
.status.pass{{color:var(--pass)}} .status.fail{{color:var(--fail)}}
.status.inconclusive{{color:var(--warn)}} .grid{{display:grid;grid-template-columns:repeat(12,1fr);
gap:16px;margin-top:26px}} .card{{grid-column:span 3;background:var(--card);border:1px solid var(--line);
border-radius:16px;padding:22px;box-shadow:0 8px 28px rgba(20,40,31,.05)}} .wide{{grid-column:1/-1}}
.metric{{font-size:31px;font-weight:760;letter-spacing:-.03em}} .label{{color:var(--muted)}}
.path{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;background:#edf1ed;
padding:3px 6px;border-radius:6px;overflow-wrap:anywhere}} .wire{{display:grid;
grid-template-columns:1fr auto 1fr;gap:18px;align-items:center}} .arrow{{font-size:26px;color:var(--accent)}}
.table-wrap{{overflow-x:auto}} table{{width:100%;border-collapse:collapse;min-width:720px}}
th,td{{padding:11px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}
ul{{margin-bottom:0}} footer{{margin-top:30px;color:var(--muted);font-size:13px}}
@media(max-width:860px){{.card{{grid-column:span 6}}}}
@media(max-width:600px){{main{{padding:30px 16px 48px}}.card{{grid-column:1/-1}}.wire{{grid-template-columns:1fr}}
.arrow{{transform:rotate(90deg)}}}}
@media print{{body{{background:#fff}}main{{max-width:none;padding:12mm}}.card{{box-shadow:none;break-inside:avoid}}
.table-wrap{{overflow:visible}}footer{{overflow-wrap:anywhere}}}}
</style>
</head>
<body><main>
<div class="eyebrow">GroundFlip evidence-dependence certificate</div>
<h1>{_escape(contract.get("name", "Unnamed contract"))}</h1>
<p class="lede">A controlled evidence intervention tested whether a downstream claim or action
obeyed its declared MCP evidence relationship. This is behavioral evidence, not proof of world truth.</p>
<p><span class="status {verdict_class}">{_escape(verdict)}</span></p>
<section class="grid" aria-label="Summary metrics">
<article class="card"><div class="label">Target success</div><div class="metric">{_pct(target_success.get("estimate"))}</div>
<div class="label">{_pct(target_success.get("lower"))}-{_pct(target_success.get("upper"))} interval</div></article>
<article class="card"><div class="label">Control success</div><div class="metric">{_pct(controls_success.get("estimate"))}</div>
<div class="label">Unchanged-field checks</div></article>
<article class="card"><div class="label">Identical-control churn</div><div class="metric">{_pct(stats.get("control_churn"))}</div>
<div class="label">Noise floor across repeats</div></article>
<article class="card"><div class="label">Integrity mode</div><div class="metric" style="font-size:18px">{_escape(integrity)}</div>
<div class="label">Verify before using as a release gate</div></article>
<article class="card wide"><h2>Claim-to-evidence circuit</h2><div class="wire">
<div><div class="label">Evidence</div><strong>{_escape(evidence.get("tool"))}</strong><br>
<span class="path">{_escape(evidence.get("path"))}</span><br>{_escape(evidence.get("original_value"))} -&gt; {_escape(evidence.get("mutated_value"))}</div>
<div class="arrow" aria-hidden="true">-&gt;</div>
<div><div class="label">{_escape(contract.get("relation"))}</div><strong class="path">{_escape(contract.get("target"))}</strong></div>
</div></article>
<article class="card wide"><h2>Influence matrix</h2>{matrix}</article>
<article class="card wide"><h2>Paired executions</h2><div class="table-wrap"><table><caption class="label">Control and one-field intervention branches</caption>
<thead><tr><th scope="col">Run</th><th scope="col">Control</th><th scope="col">Intervention</th><th scope="col">Target</th><th scope="col">Controls</th><th scope="col">Provider / model</th></tr></thead>
<tbody>{run_rows}</tbody></table></div></article>
<article class="card wide"><h2>Interpretation limits</h2><ul>{warning_html}</ul></article>
</section>
<footer>Integrity: {_escape(integrity)}<br>Payload digest: <span class="path">{_escape(authentication.get("payload_sha256"))}</span><br>
Generated {_escape(safe.get("generated_at"))}. Hashes cover redacted, canonicalized artifacts. A checksum detects changes only when its digest is independently pinned; neither checksum nor HMAC proves evidence truth.</footer>
</main></body></html>"""


def render_markdown(certificate: Mapping[str, Any]) -> str:
    safe = _mapping(redact(certificate))
    statement = _mapping(safe.get("statement"))
    predicate = _mapping(statement.get("predicate"))
    contract = _mapping(predicate.get("contract"))
    evidence = _mapping(contract.get("evidence"))
    stats = _mapping(predicate.get("statistics"))
    target = _mapping(stats.get("target_success"))
    controls = _mapping(stats.get("controls_success"))
    evidence_label = f"{_plain(evidence.get('tool'))} {_plain(evidence.get('path'))}"
    lines = [
        f"# GroundFlip: {_md_text(contract.get('name', 'Unnamed contract'))}",
        "",
        f"**Verdict:** {_md_text(predicate.get('verdict', 'UNKNOWN'))}",
        "",
        f"- Evidence: {_md_code(evidence_label)}",
        f"- Mutation: {_md_code(evidence.get('original_value'))} -> {_md_code(evidence.get('mutated_value'))}",
        f"- Target: {_md_code(contract.get('target'))} must {_md_code(contract.get('relation'))}",
        f"- Target success: {_pct(target.get('estimate'))} ({_pct(target.get('lower'))}-{_pct(target.get('upper'))})",
        f"- Control success: {_pct(controls.get('estimate'))}",
        f"- Control churn: {_pct(stats.get('control_churn'))}",
        f"- Paired effect: {_pct(stats.get('paired_effect'))}",
        f"- Paired replications: {_plain(stats.get('replications', 0))}",
        f"- Integrity: {_md_text(_integrity_label(safe))}",
        "",
    ]
    lines.extend(_matrix_markdown(_matrix_entries(predicate, contract, evidence)))

    runs = predicate.get("runs", [])
    if isinstance(runs, list) and runs:
        lines.extend(
            [
                "## Paired executions",
                "",
                "| Run | Control | Intervention | Target | Controls | Provider / model |",
                "|---:|---|---|---|---|---|",
            ]
        )
        for run in runs:
            if not isinstance(run, Mapping):
                continue
            lines.append(
                f"| {_md_text(run.get('index'))} | {_md_code(run.get('target_control'))} | "
                f"{_md_code(run.get('target_intervention'))} | "
                f"{'PASS' if run.get('target_pass') else 'FAIL'} | "
                f"{'PASS' if run.get('controls_pass') else 'FAIL'} | "
                f"{_md_text(_run_model(run))} |"
            )
        lines.append("")

    lines.extend(["## Warnings and limits", ""])
    warnings = predicate.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        lines.extend(f"- {_md_text(item)}" for item in warnings)
    else:
        lines.append("- No warnings recorded.")
    authentication = _mapping(safe.get("authentication"))
    lines.extend(
        [
            "",
            "> This certificate records behavioral dependence under controlled interventions. "
            "It does not prove real-world truth or reveal hidden model reasoning.",
            "",
            f"Payload SHA-256: {_md_code(authentication.get('payload_sha256'))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(path: str | Path, certificate: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = (
        render_markdown(certificate)
        if target.suffix.lower() in {".md", ".markdown"}
        else render_html(certificate)
    )
    target.write_text(content, encoding="utf-8")
    return target
