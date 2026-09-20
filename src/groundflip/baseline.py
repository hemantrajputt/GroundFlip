"""Conventional static-output baseline for EvidenceWireBench."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def confusion(rows: Iterable[Mapping[str, Any]], prediction_key: str) -> dict[str, Any]:
    tp = fp = fn = tn = 0
    for row in rows:
        actual = bool(row["is_defect"])
        predicted = bool(row[prediction_key])
        if actual and predicted:
            tp += 1
        elif not actual and predicted:
            fp += 1
        elif actual and not predicted:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def static_detects(baseline_observation: Any, expected: Any) -> bool:
    """Static eval flags only an already-wrong unmodified answer."""
    return baseline_observation != expected
