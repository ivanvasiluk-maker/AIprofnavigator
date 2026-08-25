from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators.critical_error_evaluator import CriticalErrorEvaluator
from tests.career_profiles.evaluators.evidence_evaluator import EvidenceEvaluator
from tests.career_profiles.evaluators.forbidden_recommendation_evaluator import ForbiddenRecommendationEvaluator
from tests.career_profiles.evaluators.professional_core_evaluator import ProfessionalCoreEvaluator
from tests.career_profiles.evaluators.route_evaluator import RouteEvaluator
from tests.career_profiles.evaluators.seniority_evaluator import SeniorityEvaluator
from tests.career_profiles.evaluators.uncertainty_evaluator import UncertaintyEvaluator
from tests.career_profiles.evaluators.user_choice_evaluator import UserChoiceEvaluator


class BaselineCareerEvaluator:
    def __init__(self) -> None:
        self._evaluators = {
            "critical_errors": CriticalErrorEvaluator(),
            "forbidden_recommendations": ForbiddenRecommendationEvaluator(),
            "professional_core": ProfessionalCoreEvaluator(),
            "seniority": SeniorityEvaluator(),
            "routes": RouteEvaluator(),
            "user_choice": UserChoiceEvaluator(),
            "uncertainty": UncertaintyEvaluator(),
            "evidence": EvidenceEvaluator(),
        }

    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        # Distributed packages use an ``expected`` envelope, while older unit
        # fixtures use top-level fields.  Evaluators must see one normalized
        # contract; silently treating the envelope as "no expectations" used to
        # award full points to an unevaluated result.
        nested = expected_profile.get("expected") if isinstance(expected_profile.get("expected"), dict) else {}
        normalized_expected = {**expected_profile, **nested}
        normalized_expected["profile_id"] = str(
            expected_profile.get("profile_id") or expected_profile.get("id") or input_profile.get("profile_id") or ""
        ).strip()

        results: dict[str, dict[str, Any]] = {}
        total_score = 0
        max_score = 0
        critical_findings: list[dict[str, Any]] = []
        reason_codes: list[str] = []
        supporting_fragments: list[str] = []
        missing_elements: list[str] = []

        for key, evaluator in self._evaluators.items():
            result = await evaluator.evaluate(input_profile, generated_result, normalized_expected)
            results[key] = result
            total_score += int(result.get("score") or 0)
            max_score += int(result.get("max_score") or 0)
            critical_findings.extend(result.get("critical_findings") or [])
            reason_codes.extend(str(code) for code in result.get("reason_codes") or [])
            supporting_fragments.extend(str(item) for item in result.get("supporting_fragments") or [])
            missing_elements.extend(str(item) for item in result.get("missing_elements") or [])

        critical_error_detected = any(str(item.get("decision") or "") == "confirmed" for item in critical_findings)
        passed = total_score >= 80 and not critical_error_detected
        return {
            "profile_id": str(input_profile.get("profile_id") or normalized_expected.get("profile_id") or "").strip(),
            "evaluation_status": "passed" if passed else "failed",
            "passed": passed,
            "critical_error_detected": critical_error_detected,
            "total_score": total_score,
            "max_score": max_score,
            "score_breakdown": results,
            "reason_codes": sorted(set(reason_codes)),
            "supporting_fragments": supporting_fragments[:20],
            "missing_elements": sorted(set(missing_elements)),
            "critical_findings": critical_findings,
            "evaluator_comment": "Multi-signal evaluation combines deterministic and semantic signals across route structure, evidence, seniority, refusals, and uncertainty.",
        }
