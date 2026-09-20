"""GroundFlip: causal contract testing for MCP-grounded agents."""

from .engine import ContractRunner
from .models import Contract, ContractResult, Verdict

__all__ = ["Contract", "ContractResult", "ContractRunner", "Verdict"]
__version__ = "0.1.0"
