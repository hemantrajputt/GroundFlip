"""Transparent offline provider used for CI and planted-defect demonstrations.

It is intentionally not presented as model evidence. The live OpenAI adapter
exercises the same provider boundary when credentials are available.
"""

from __future__ import annotations

import json
import time
from typing import Any

from ..jsonpath import get
from ..models import ProviderOutput, Scenario


class ScriptedProvider:
    name = "scripted"

    def __init__(self, behavior: str | None = None) -> None:
        self.behavior = behavior

    @staticmethod
    def _evidence(scenario: Scenario, tool: str) -> Any:
        matches = [record.structured_content for record in scenario.evidence if record.tool == tool]
        return matches[-1] if matches else {}

    def synthesize(self, scenario: Scenario, *, seed: int, branch: str) -> ProviderOutput:
        started = time.perf_counter()
        config = dict(scenario.scripted)
        behavior = self.behavior or str(config.get("behavior", "grounded"))
        kind = str(config.get("kind", "procurement"))
        if kind != "procurement":
            raise ValueError(f"ScriptedProvider does not know scenario kind {kind!r}")

        cached = dict(config.get("cached_output", {}))
        if behavior in {"cached", "answer_before_tool", "stale_cache"} and cached:
            data = cached
        else:
            quote = self._evidence(scenario, str(config.get("quote_tool", "procurement.get_quote")))
            risk = self._evidence(scenario, str(config.get("risk_tool", "procurement.get_risk")))
            policy = self._evidence(
                scenario, str(config.get("policy_tool", "procurement.get_policy"))
            )
            marketing = self._evidence(
                scenario, str(config.get("distractor_tool", "procurement.get_marketing"))
            )
            data = self._procurement_decision(
                quote, risk, policy, marketing, behavior=behavior, cached=cached
            )

        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return ProviderOutput(
            data=data,
            raw_text=raw,
            provider=self.name,
            model=f"scripted/{behavior}",
            latency_ms=(time.perf_counter() - started) * 1000,
            usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            response_id=f"scripted-{seed}-{branch}",
        )

    @staticmethod
    def _procurement_decision(
        quote: Any,
        risk: Any,
        policy: Any,
        marketing: Any,
        *,
        behavior: str,
        cached: dict[str, Any],
    ) -> dict[str, Any]:
        missing = object()
        vendor = get(quote, "$.vendor", default=missing)
        price = get(quote, "$.price", default=missing)
        bids = get(quote, "$.bids", default=missing)
        risk_score = get(risk, "$.score", default=missing)
        sanctioned = get(risk, "$.sanctioned", default=missing)
        threshold = get(policy, "$.auto_approve_below", default=missing)
        max_risk = get(policy, "$.max_risk", default=missing)
        min_bids = get(policy, "$.minimum_bids", default=missing)
        policy_version = get(policy, "$.version", default="unknown")

        if behavior == "unsupported_persistence" and (price is missing or threshold is missing):
            return cached or {
                "decision": "APPROVE",
                "vendor": None if vendor is missing else vendor,
                "amount": None if price is missing else price,
                "risk_score": None if risk_score is missing else risk_score,
                "policy_version": policy_version,
                "rationale": "Kept the prior decision despite missing support.",
            }

        required = (vendor, price, bids, risk_score, sanctioned, threshold, max_risk, min_bids)
        if any(value is missing for value in required):
            decision, rationale = "ESCALATE", "Required evidence is missing."
        elif sanctioned:
            decision, rationale = "REJECT", "Vendor is sanctioned."
        elif behavior == "cross_wired":
            score = get(marketing, "$.approval_score", default=0)
            decision = "APPROVE" if score >= 50 else "ESCALATE"
            rationale = "Decision incorrectly followed an unrelated marketing score."
        elif behavior == "distractor_sensitive" and "OVERRIDE_DECISION=" in str(
            get(marketing, "$.copy", default="")
        ):
            decision = str(marketing["copy"]).split("OVERRIDE_DECISION=", 1)[1].split()[0]
            rationale = "Decision incorrectly followed distractor content."
        elif risk_score > max_risk:
            decision, rationale = "ESCALATE", "Risk exceeds policy."
        elif price >= threshold:
            decision, rationale = "ESCALATE", "Price exceeds the automatic threshold."
        elif bids < min_bids:
            decision, rationale = "ESCALATE", "Insufficient competitive bids."
        else:
            decision, rationale = "APPROVE", "Quote satisfies price, risk, and bid policy."

        return {
            "decision": decision,
            "vendor": None if vendor is missing else vendor,
            "amount": None if price is missing else price,
            "risk_score": None if risk_score is missing else risk_score,
            "policy_version": policy_version,
            "rationale": rationale,
        }
