from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import make_score, report_blob, semantic_signal


_SENIORITY_FIELDS = (
    "professional_maturity",
    "current_function_level",
    "new_function_entry_level",
    "local_market_readiness",
    "legal_access",
)


class SeniorityEvaluator:
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        expectations = expected_profile.get("seniority_expectations") if isinstance(expected_profile.get("seniority_expectations"), dict) else {}
        if not expectations:
            return make_score(score=15, max_score=15, evaluator_comment="No seniority expectation configured.")

        blob = report_blob(generated_result)
        supporting: list[str] = []
        missing: list[str] = []
        matched = 0
        configured = 0
        for field_name in _SENIORITY_FIELDS:
            expected_value = str(expectations.get(field_name) or "").strip()
            if not expected_value:
                continue
            configured += 1
            if semantic_signal(expected_value, blob, threshold=0.35):
                supporting.append(expected_value)
                matched += 1
            else:
                missing.append(field_name)

        score = round((matched / max(1, configured)) * 15)
        return make_score(
            score=score,
            max_score=15,
            reason_codes=["SENIORITY_DIMENSIONS_MISSING"] if missing else [],
            supporting_fragments=supporting,
            missing_elements=missing,
            evaluator_comment="Seniority is compared across professional maturity, functional level, entry level, market readiness, and legal access.",
        )