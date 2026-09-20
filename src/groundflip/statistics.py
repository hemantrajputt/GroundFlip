"""Small statistical helpers with no numerical runtime dependency."""

from __future__ import annotations

import math
from statistics import NormalDist

from .models import Interval


def wilson_interval(successes: int, total: int, alpha: float = 0.05) -> Interval:
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Expected 0 <= successes <= total")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    if total == 0:
        return Interval(estimate=0.0, lower=0.0, upper=1.0, confidence=1 - alpha)
    z = NormalDist().inv_cdf(1 - alpha / 2)
    estimate = successes / total
    denominator = 1 + (z * z / total)
    center = (estimate + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt((estimate * (1 - estimate) / total) + z * z / (4 * total * total))
        / denominator
    )
    return Interval(
        estimate=estimate,
        lower=max(0.0, center - margin),
        upper=min(1.0, center + margin),
        confidence=1 - alpha,
    )


def churn(values: list[object]) -> float:
    """Return one minus the modal exact-value share."""
    if not values:
        return 0.0
    counts: dict[str, int] = {}
    import json

    for value in values:
        key = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        counts[key] = counts.get(key, 0) + 1
    return 1 - max(counts.values()) / len(values)
