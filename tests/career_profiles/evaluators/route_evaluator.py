from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import contains_contextual_route, extract_route_slots, make_score


_ROUTE_SLOT_MAP = {
    "main_route": "main_route",
    "transition_route": "transition_route",
    "quick_route": "quick_route",
    "emergency_route": "emergency_route",
}


class RouteEvaluator:
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        expectations = expected_profile.get("route_expectations") if isinstance(expected_profile.get("route_expectations"), dict) else {}
        if not expectations:
            return make_score(score=20, max_score=20, evaluator_comment="No route expectation configured.")

        slots = extract_route_slots(generated_result)
        supporting: list[str] = []
        missing: list[str] = []
        matched = 0
        configured = 0
        for expected_key, slot_name in _ROUTE_SLOT_MAP.items():
            expected_value = str(expectations.get(expected_key) or "").strip()
            if not expected_value:
                continue
            configured += 1
            has_match, fragments = contains_contextual_route(expected_value, slots[slot_name])
            if has_match:
                matched += 1
                supporting.extend(fragments)
            else:
                missing.append(f"{expected_key}:{expected_value}")

        score = round((matched / max(1, configured)) * 20)
        return make_score(
            score=score,
            max_score=20,
            reason_codes=["ROUTE_SLOT_MISMATCH"] if missing else [],
            supporting_fragments=supporting,
            missing_elements=missing,
            evaluator_comment="Routes are evaluated by slot: main, transition, quick income, and emergency bridge.",
        )