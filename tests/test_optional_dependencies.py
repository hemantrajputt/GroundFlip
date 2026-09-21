import runpy
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module", ["test_mcp_sdk_interop.py", "test_mcp_v2_modern_interop.py"]
)
def test_interop_module_skips_without_optional_mcp(monkeypatch, module):
    monkeypatch.setitem(sys.modules, "mcp", None)
    with pytest.raises(pytest.skip.Exception, match="mcp"):
        runpy.run_path(str(Path(__file__).with_name(module)))
