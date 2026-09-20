from pathlib import Path

from groundflip.cli import main


def test_benchmark_cli_writes_artifact(tmp_path: Path):
    output = tmp_path / "benchmark.json"
    assert main(["benchmark", "--tier", "smoke", "--out", str(output)]) == 0
    assert output.exists()


def test_demo_cli_writes_results_certificates_and_reports(tmp_path: Path):
    assert main(["demo", "--behavior", "grounded", "--runs", "1", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "demo-summary.json").exists()
    assert len(list((tmp_path / "results").glob("*.json"))) == 4
    assert len(list((tmp_path / "reports").glob("*.html"))) == 4


def test_proxy_requires_explicit_command_permission(tmp_path: Path):
    exit_code = main(["proxy", "--cassette", str(tmp_path / "x.json"), "--", "python", "server.py"])
    assert exit_code == 1
