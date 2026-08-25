from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import evidence_fragments, make_score, semantic_signal


class ProfessionalCoreEvaluator:
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        expected_core = [
            str(item).strip()
            for item in expected_profile.get("professional_core") or expected_profile.get("expected_professional_core") or []
            if str(item).strip()
        ]
        if not expected_core:
            return make_score(
                score=0,
                max_score=15,
                reason_codes=["PROFESSIONAL_CORE_EXPECTATION_MISSING"],
                missing_elements=["professional_core"],
                evaluator_comment="Expected profile has no professional-core expectation; evaluation cannot award points.",
            )

        actual_fragments = evidence_fragments(generated_result)
        supporting: list[str] = []
        missing: list[str] = []
        for expected_item in expected_core:
            matched = [fragment for fragment in actual_fragments if semantic_signal(expected_item, fragment, threshold=0.4)]
            if matched:
                supporting.extend(matched[:2])
            else:
                missing.append(expected_item)

        matched_count = len(expected_core) - len(missing)
        score = round((matched_count / max(1, len(expected_core))) * 15)
        reason_codes = ["PROFESSIONAL_CORE_PARTIAL"] if missing else []
        return make_score(
            score=score,
            max_score=15,
            reason_codes=reason_codes,
            supporting_fragments=supporting,
            missing_elements=missing,
            evaluator_comment="Professional core is evaluated by semantic overlap with evidence and route-support fragments.",
        )
