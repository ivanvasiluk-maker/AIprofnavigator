from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import evidence_fragments, make_score, semantic_signal


class EvidenceEvaluator:
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        expected_evidence = [str(item).strip() for item in expected_profile.get("evidence_fragments") or [] if str(item).strip()]
        if not expected_evidence:
            story_analysis = input_profile.get("story_analysis") if isinstance(input_profile.get("story_analysis"), dict) else {}
            expected_evidence = [
                str(item).strip()
                for item in story_analysis.get("confirmed_functions") or []
                if str(item).strip()
            ][:4]
        if not expected_evidence:
            return make_score(
                score=0,
                max_score=10,
                reason_codes=["EVIDENCE_EXPECTATION_MISSING"],
                missing_elements=["confirmed_functions"],
                evaluator_comment="Neither expected evidence nor input functions are available for evaluation.",
            )

        actual = evidence_fragments(generated_result)
        matched = 0
        supporting: list[str] = []
        missing: list[str] = []
        for expected in expected_evidence:
            hits = [fragment for fragment in actual if semantic_signal(expected, fragment, threshold=0.4)]
            if hits:
                matched += 1
                supporting.extend(hits[:2])
            else:
                missing.append(expected)
        score = round((matched / max(1, len(expected_evidence))) * 10)
        return make_score(
            score=score,
            max_score=10,
            reason_codes=["EVIDENCE_GAPS"] if missing else [],
            supporting_fragments=supporting,
            missing_elements=missing,
            evaluator_comment="Expected user evidence is checked against route evidence and facts-only fragments.",
        )
