"""GroundFlip command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .benchmark import run_benchmark, write_benchmark
from .certificate import create_certificate, read_certificate, verify_certificate, write_certificate
from .contracts import load_contract
from .demo import procurement_contracts, procurement_scenario
from .engine import ContractRunner
from .models import GroundFlipError, Verdict
from .providers.scripted import ScriptedProvider
from .report import write_report
from .scenario import load_scenario


def _provider(name: str, *, behavior: str = "grounded", model: str | None = None) -> Any:
    if name == "scripted":
        return ScriptedProvider(behavior=behavior)
    if name == "openai":
        from .providers.openai import OpenAIProvider

        return OpenAIProvider(model=model)
    raise ValueError(f"Unknown provider: {name}")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _demo(args: argparse.Namespace) -> int:
    behaviors = (
        ["grounded", "cached", "stale_cache", "cross_wired", "unsupported_persistence"]
        if args.behavior == "all" and args.provider == "scripted"
        else ["grounded" if args.provider == "openai" else args.behavior]
    )
    root = Path(args.out)
    rows: list[dict[str, Any]] = []
    for behavior in behaviors:
        provider = _provider(args.provider, behavior=behavior, model=args.model)
        scenario = procurement_scenario(behavior)
        runner = ContractRunner(provider)
        for contract in procurement_contracts(runs=args.runs):
            result = runner.run(contract, scenario)
            payload = result.to_dict()
            rows.append(
                {
                    "behavior": behavior,
                    "contract": contract.name,
                    "verdict": result.verdict.value,
                    "target_success": result.target_success.estimate,
                    "control_churn": result.control_churn,
                }
            )
            stem = f"{behavior}--{contract.name}"
            result_path = root / "results" / f"{stem}.json"
            certificate_path = root / "certificates" / f"{stem}.json"
            report_path = root / "reports" / f"{stem}.html"
            _write_json(result_path, payload)
            certificate = create_certificate(payload)
            write_certificate(certificate_path, certificate)
            write_report(report_path, certificate)

    _write_json(root / "demo-summary.json", {"schema_version": "groundflip.demo/v1", "rows": rows})
    print("GroundFlip procurement demo")
    print("behavior                 contract                               verdict")
    print("-----------------------  -------------------------------------  ------------")
    for row in rows:
        print(f"{row['behavior']:<23}  {row['contract']:<37}  {row['verdict']}")
    print(f"\nArtifacts: {root.resolve()}")
    return 0


def _test(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    scenario = load_scenario(contract.scenario)
    provider = _provider(args.provider, behavior=args.behavior, model=args.model)
    result = ContractRunner(provider).run(contract, scenario)
    payload = result.to_dict()
    target = Path(args.out) if args.out else Path(".groundflip") / f"{contract.name}.result.json"
    _write_json(target, payload)
    print(
        f"{result.verdict.value}: {contract.name} · target={result.target_success.estimate:.3f} "
        f"control_churn={result.control_churn:.3f}"
    )
    print(target.resolve())
    return 0 if result.verdict is Verdict.PASS else 2


def _certify(args: argparse.Namespace) -> int:
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    certificate = create_certificate(result)
    write_certificate(args.out, certificate)
    print(Path(args.out).resolve())
    return 0


def _report(args: argparse.Namespace) -> int:
    certificate = read_certificate(args.certificate)
    valid, reasons = verify_certificate(certificate)
    if not valid and not (len(reasons) == 1 and "no verification key" in reasons[0]):
        raise GroundFlipError("Certificate integrity check failed: " + "; ".join(reasons))
    write_report(args.out, certificate)
    print(Path(args.out).resolve())
    return 0


def _gate(args: argparse.Namespace) -> int:
    certificate = read_certificate(args.certificate)
    valid, reasons = verify_certificate(certificate)
    if not valid:
        print("INVALID: " + "; ".join(reasons), file=sys.stderr)
        return 3
    verdict = certificate.get("statement", {}).get("predicate", {}).get("verdict")
    print(str(verdict or "UNKNOWN"))
    return 0 if verdict == Verdict.PASS.value else 2


def _benchmark(args: argparse.Namespace) -> int:
    result = run_benchmark(tier=args.tier, seed=args.seed)
    write_benchmark(args.out, result)
    static = result["static_baseline"]
    causal = result["groundflip"]
    print(
        f"EvidenceWireBench {args.tier}: {result['cases']} cases · "
        f"static recall={static['recall']:.3f} · GroundFlip recall={causal['recall']:.3f} · "
        f"precision={causal['precision']:.3f}"
    )
    print(Path(args.out).resolve())
    return 0


def _proxy(args: argparse.Namespace) -> int:
    if not args.allow_command:
        raise GroundFlipError("Refusing to start a subprocess without --allow-command")
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise GroundFlipError("proxy needs an upstream command after --")
    from .mcp_proxy import main as proxy_main

    proxy_args = ["--cassette", args.cassette]
    if args.intervention:
        proxy_args.extend(["--intervention", args.intervention])
    proxy_args.extend(["--", *command])
    return int(proxy_main(proxy_args) or 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="groundflip",
        description="Test whether agent claims and actions obey the right MCP evidence.",
    )
    parser.add_argument("--version", action="version", version="GroundFlip 0.1.0")
    sub = parser.add_subparsers(dest="command_name", required=True)

    demo = sub.add_parser("demo", help="run the built-in procurement evidence-wiring demo")
    demo.add_argument("--provider", choices=["scripted", "openai"], default="scripted")
    demo.add_argument(
        "--behavior",
        choices=[
            "all",
            "grounded",
            "cached",
            "stale_cache",
            "cross_wired",
            "unsupported_persistence",
        ],
        default="all",
    )
    demo.add_argument("--model", help="OpenAI model override")
    demo.add_argument("--runs", type=int, default=5)
    demo.add_argument("--out", default=".groundflip/demo")
    demo.set_defaults(handler=_demo)

    test = sub.add_parser("test", help="execute one evidence contract")
    test.add_argument("contract")
    test.add_argument("--provider", choices=["scripted", "openai"], default="scripted")
    test.add_argument("--behavior", default="grounded")
    test.add_argument("--model")
    test.add_argument("--out")
    test.set_defaults(handler=_test)

    certify = sub.add_parser(
        "certify", help="create a checksummed or HMAC-authenticated certificate"
    )
    certify.add_argument("result")
    certify.add_argument("--out", required=True)
    certify.set_defaults(handler=_certify)

    report = sub.add_parser("report", help="render a self-contained HTML or Markdown report")
    report.add_argument("certificate")
    report.add_argument("--out", required=True)
    report.set_defaults(handler=_report)

    gate = sub.add_parser("gate", help="verify a certificate and return a CI-friendly exit code")
    gate.add_argument("certificate")
    gate.set_defaults(handler=_gate)

    benchmark = sub.add_parser("benchmark", help="run deterministic EvidenceWireBench")
    benchmark.add_argument("--tier", choices=["smoke", "full"], default="smoke")
    benchmark.add_argument("--seed", type=int, default=20260807)
    benchmark.add_argument("--out", default=".groundflip/benchmark.json")
    benchmark.set_defaults(handler=_benchmark)

    proxy = sub.add_parser("proxy", help="record or intervene on an MCP stdio server")
    proxy.add_argument("--cassette", required=True)
    proxy.add_argument("--intervention")
    proxy.add_argument("--allow-command", action="store_true")
    proxy.add_argument("command", nargs=argparse.REMAINDER)
    proxy.set_defaults(handler=_proxy)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (GroundFlipError, OSError, ValueError) as exc:
        print(f"groundflip: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
