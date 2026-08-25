from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import contains_contextual_route, extract_route_slots, make_score


class UserChoiceEvaluator:
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        story_analysis = input_profile.get("story_analysis") if isinstance(input_profile.get("story_analysis"), dict) else {}
        refusals = [
            str(item).strip()
            for item in [
                *(expected_profile.get("direct_refusals") or []),
                *(story_analysis.get("functions_to_avoid") or []),
            ]
            if str(item).strip()
        ]
        if not refusals:
            return make_score(score=10, max_score=10, evaluator_comment="No direct refusals configured.")

        slots = extract_route_slots(generated_result)
        supporting: list[str] = []
        critical_findings: list[dict[str, Any]] = []
        for refusal in refusals:
            has_match, fragments = contains_contextual_route(refusal, slots["main_route"])
            if has_match:
                supporting.extend(fragments)
                critical_findings.append(
                    {
                        "error_code": "DIRECT_REFUSAL_VIOLATED",
                        "rule_signal": True,
                        "semantic_signal": True,
                        "decision": "confirmed",
                        "evidence": fragments,
                    }
                )

        if critical_findings:
            return make_score(
                score=0,
                max_score=10,
                reason_codes=["DIRECT_REFUSAL_VIOLATED"],
                supporting_fragments=supporting,
                evaluator_comment="A direct refusal was recommended as a main route.",
                critical_findings=critical_findings,
            )
        return make_score(score=10, max_score=10, evaluator_comment="Direct refusals are respected in primary route selection.")
