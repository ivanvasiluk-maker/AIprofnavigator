from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import cautious_language_present, make_score, route_blocks


class UncertaintyEvaluator:
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        must_show_uncertainty = bool(expected_profile.get("must_show_uncertainty", True))
        if not must_show_uncertainty:
            return make_score(score=10, max_score=10, evaluator_comment="Uncertainty marking is optional for this profile.")

        blocks = route_blocks(generated_result)
        has_disproof = any(bool(block.get("what_may_disprove_this_route")) for block in blocks)
        facts_only = generated_result.get("facts_only") if isinstance(generated_result.get("facts_only"), dict) else {}
        questions = generated_result.get("questions") if isinstance(generated_result.get("questions"), dict) else {}
        has_unknowns = bool(facts_only.get("unknowns") or questions.get("unanswered_critical_questions"))
        cautious = cautious_language_present(generated_result)

        supporting: list[str] = []
        if has_disproof:
            supporting.append("route_evidence_blocks.what_may_disprove_this_route")
        if has_unknowns:
            supporting.append("facts_only.unknowns")
        if cautious:
            supporting.append("cautious_language")

        score = 10 if (has_disproof and has_unknowns) or (has_disproof and cautious) else 5 if supporting else 0
        missing: list[str] = []
        if not has_disproof:
            missing.append("route_disproof_markers")
        if not has_unknowns:
            missing.append("facts_only_unknowns")
        if not cautious:
            missing.append("cautious_language")
        return make_score(
            score=score,
            max_score=10,
            reason_codes=["UNCERTAINTY_UNDEREXPLAINED"] if score < 10 else [],
            supporting_fragments=supporting,
            missing_elements=missing,
            evaluator_comment="Uncertainty must be visible through disproof markers, unknowns, and cautious language.",
        )
