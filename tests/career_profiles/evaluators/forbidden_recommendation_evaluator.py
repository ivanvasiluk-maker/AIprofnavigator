from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import contains_contextual_route, extract_route_slots, make_score


class ForbiddenRecommendationEvaluator:
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        forbidden = [str(item).strip() for item in expected_profile.get("forbidden_recommendations") or [] if str(item).strip()]
        direct_refusals = [str(item).strip() for item in expected_profile.get("direct_refusals") or [] if str(item).strip()]
        forbidden_targets = forbidden + [item for item in direct_refusals if item not in forbidden]
        if not forbidden_targets:
            return make_score(score=10, max_score=10, evaluator_comment="No forbidden recommendations configured.")

        slots = extract_route_slots(generated_result)
        primary_titles = slots["main_route"]
        temporary_titles = slots["transition_route"] + slots["quick_route"] + slots["emergency_route"]

        critical_findings: list[dict[str, Any]] = []
        supporting: list[str] = []
        reason_codes: list[str] = []
        for forbidden_route in forbidden_targets:
            primary_hit, primary_fragments = contains_contextual_route(forbidden_route, primary_titles)
            temporary_hit, temporary_fragments = contains_contextual_route(forbidden_route, temporary_titles)
            if primary_hit:
                reason_codes.append("FORBIDDEN_ROLE_RECOMMENDED")
                supporting.extend(primary_fragments)
                critical_findings.append(
                    {
                        "error_code": "FORBIDDEN_ROLE_RECOMMENDED",
                        "rule_signal": True,
                        "semantic_signal": True,
                        "decision": "confirmed",
                        "evidence": primary_fragments,
                    }
                )
            elif temporary_hit:
                reason_codes.append("FORBIDDEN_ROLE_ONLY_TEMPORARY")
                supporting.extend(temporary_fragments)

        if critical_findings:
            return make_score(
                score=0,
                max_score=10,
                reason_codes=reason_codes,
                supporting_fragments=supporting,
                evaluator_comment="Forbidden role appeared in a primary recommendation context.",
                critical_findings=critical_findings,
            )

        score = 8 if reason_codes else 10
        return make_score(
            score=score,
            max_score=10,
            reason_codes=reason_codes,
            supporting_fragments=supporting,
            evaluator_comment="Forbidden routes appear only as temporary bridges or do not appear at all.",
        )