"""Provider-neutral synthesis boundary."""

from __future__ import annotations

from typing import Protocol

from ..models import ProviderOutput, Scenario


class SynthesisProvider(Protocol):
    name: str

    def synthesize(self, scenario: Scenario, *, seed: int, branch: str) -> ProviderOutput:
        """Synthesize one structured observation from a frozen scenario snapshot."""
        ...
