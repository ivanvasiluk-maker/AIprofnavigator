from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import cautious_language_present, extract_route_slots, make_score, route_blocks


class CriticalErrorEvaluator:
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        critical_findings: list[dict[str, Any]] = []
        reason_codes: list[str] = []

        slots = extract_route_slots(generated_result)
        if not slots["main_route"]:
            reason_codes.append("MAIN_ROUTE_MISSING")
            critical_findings.append(
                {
                    "error_code": "MAIN_ROUTE_MISSING",
                    "rule_signal": True,
                    "semantic_signal": False,
                    "decision": "confirmed",
                    "evidence": [],
                }
            )

        blocks = route_blocks(generated_result)
        has_primary_block = any(str(block.get("income_role") or "").strip().lower() == "primary" for block in blocks)
        if slots["main_route"] and not has_primary_block:
            reason_codes.append("PRIMARY_ROUTE_EVIDENCE_MISSING")
            critical_findings.append(
                {
                    "error_code": "PRIMARY_ROUTE_EVIDENCE_MISSING",
                    "rule_signal": True,
                    "semantic_signal": bool(slots["main_route"]),
                    "decision": "confirmed",
                    "evidence": slots["main_route"][:2],
                }
            )

        if not cautious_language_present(generated_result):
            reason_codes.append("UNCERTAINTY_NOT_MARKED")
            critical_findings.append(
                {
                    "error_code": "UNCERTAINTY_NOT_MARKED",
                    "rule_signal": True,
                    "semantic_signal": False,
                    "decision": "needs_review",
                    "evidence": [],
                }
            )

        if critical_findings:
            return make_score(
                score=0,
                max_score=10,
                reason_codes=reason_codes,
                evaluator_comment="Critical errors detected by rule and semantic checks.",
                critical_findings=critical_findings,
            )
        return make_score(score=10, max_score=10, evaluator_comment="No critical errors confirmed by the engine.")