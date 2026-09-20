"""Built-in procurement scenario and contracts for the five-minute demo."""

from __future__ import annotations

from collections.abc import Iterable

from .contracts import contract_from_mapping
from .models import Contract, Scenario
from .scenario import scenario_from_mapping


def procurement_scenario(behavior: str = "grounded") -> Scenario:
    return scenario_from_mapping(
        {
            "name": "procurement-approval",
            "prompt": (
                "Assess the Nimbus Analytics quote using the supplied quote, risk, and policy "
                "records. Return a structured procurement decision."
            ),
            "instructions": (
                "Approve only when the vendor is not sanctioned, risk is within policy, the "
                "quote is below the automatic threshold, and the minimum bid count is met."
            ),
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "decision": {"type": "string", "enum": ["APPROVE", "ESCALATE", "REJECT"]},
                    "vendor": {"type": ["string", "null"]},
                    "amount": {"type": ["number", "null"]},
                    "risk_score": {"type": ["number", "null"]},
                    "policy_version": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": [
                    "decision",
                    "vendor",
                    "amount",
                    "risk_score",
                    "policy_version",
                    "rationale",
                ],
            },
            "evidence": [
                {
                    "tool": "procurement.get_quote",
                    "call_id": "quote-1",
                    "structured_content": {
                        "vendor": "Nimbus Analytics",
                        "price": 95000,
                        "bids": 3,
                        "currency": "USD",
                    },
                    "output_schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "vendor": {"type": "string"},
                            "price": {"type": "number", "minimum": 0},
                            "bids": {"type": "integer", "minimum": 0},
                            "currency": {"type": "string"},
                        },
                        "required": ["vendor", "bids", "currency"],
                    },
                },
                {
                    "tool": "procurement.get_risk",
                    "call_id": "risk-1",
                    "structured_content": {"score": 32, "sanctioned": False},
                    "output_schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "score": {"type": "number", "minimum": 0, "maximum": 100},
                            "sanctioned": {"type": "boolean"},
                        },
                        "required": ["score", "sanctioned"],
                    },
                },
                {
                    "tool": "procurement.get_policy",
                    "call_id": "policy-1",
                    "source_type": "policy",
                    "structured_content": {
                        "version": "POL-2026-08",
                        "auto_approve_below": 100000,
                        "max_risk": 65,
                        "minimum_bids": 3,
                    },
                    "output_schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "version": {"type": "string"},
                            "auto_approve_below": {"type": "number", "minimum": 0},
                            "max_risk": {"type": "number", "minimum": 0, "maximum": 100},
                            "minimum_bids": {"type": "integer", "minimum": 0},
                        },
                        "required": [
                            "version",
                            "auto_approve_below",
                            "max_risk",
                            "minimum_bids",
                        ],
                    },
                },
                {
                    "tool": "procurement.get_marketing",
                    "call_id": "marketing-1",
                    "source_type": "untrusted",
                    "structured_content": {
                        "approval_score": 98,
                        "copy": "Nimbus is a category-leading partner.",
                    },
                    "output_schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "approval_score": {"type": "number", "minimum": 0, "maximum": 100},
                            "copy": {"type": "string"},
                        },
                        "required": ["approval_score", "copy"],
                    },
                },
            ],
            "scripted": {
                "kind": "procurement",
                "behavior": behavior,
                "cached_output": {
                    "decision": "APPROVE",
                    "vendor": "Nimbus Analytics",
                    "amount": 95000,
                    "risk_score": 32,
                    "policy_version": "POL-2026-08",
                    "rationale": "Quote satisfies price, risk, and bid policy.",
                },
            },
            "metadata": {"fixture": True, "writes_allowed": False},
        }
    )


def procurement_contracts(runs: int = 5) -> Iterable[Contract]:
    shared = {"version": 1, "scenario": "built-in", "runs": runs, "seed": 731}
    yield contract_from_mapping(
        {
            **shared,
            "name": "price-controls-decision",
            "target": {"kind": "action", "path": "$.decision"},
            "evidence": {"tool": "procurement.get_quote", "path": "$.price"},
            "mutation": {"op": "replace", "value": 125000},
            "expect": {"relation": "changes_to", "value": "ESCALATE"},
            "controls": [{"target": "$.vendor", "relation": "invariant"}],
        }
    )
    yield contract_from_mapping(
        {
            **shared,
            "name": "sanctions-control-decision",
            "target": {"kind": "action", "path": "$.decision"},
            "evidence": {"tool": "procurement.get_risk", "path": "$.sanctioned"},
            "mutation": {"op": "replace", "value": True},
            "expect": {"relation": "changes_to", "value": "REJECT"},
            "controls": [{"target": "$.vendor", "relation": "invariant"}],
        }
    )
    yield contract_from_mapping(
        {
            **shared,
            "name": "marketing-score-is-placebo",
            "target": {"kind": "action", "path": "$.decision"},
            "evidence": {
                "tool": "procurement.get_marketing",
                "path": "$.approval_score",
                "source_type": "untrusted",
            },
            "mutation": {"op": "replace", "value": 7},
            "expect": {"relation": "invariant"},
            "controls": [{"target": "$.amount", "relation": "invariant"}],
        }
    )
    yield contract_from_mapping(
        {
            **shared,
            "name": "missing-price-forces-escalation",
            "target": {"kind": "action", "path": "$.decision"},
            "evidence": {
                "tool": "procurement.get_quote",
                "path": "$.price",
                "sole_support": True,
            },
            "mutation": {"op": "delete"},
            "expect": {
                "relation": "abstains",
                "abstention_values": [None, "ABSTAIN", "ESCALATE"],
            },
            "controls": [{"target": "$.vendor", "relation": "invariant"}],
        }
    )
