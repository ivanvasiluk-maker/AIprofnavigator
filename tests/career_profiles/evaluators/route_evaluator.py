from __future__ import annotations

from typing import Any

from tests.career_profiles.evaluators._common import contains_contextual_route, extract_route_slots, make_score


_ROUTE_SLOT_MAP = {
    "main_route": "main_route",
    "transition_route": "transition_route",
    "quick_route": "quick_route",
    "emergency_route": "emergency_route",
}

_PACKAGED_ROUTE_MAP = {
    "main_route": "primary_routes",
    "transition_route": "transition_routes",
    "quick_route": "quick_income",
    "emergency_route": "emergency_routes",
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
            expectations = {
                slot_name: expected_profile.get(package_key) or []
                for slot_name, package_key in _PACKAGED_ROUTE_MAP.items()
                if expected_profile.get(package_key)
            }
        if not expectations:
            return make_score(
                score=0,
                max_score=20,
                reason_codes=["ROUTE_EXPECTATION_MISSING"],
                missing_elements=["route_expectations"],
                evaluator_comment="Expected profile has no route expectations; evaluation cannot award points.",
            )

        slots = extract_route_slots(generated_result)
        supporting: list[str] = []
        missing: list[str] = []
        matched = 0.0
        configured = 0
        for expected_key, slot_name in _ROUTE_SLOT_MAP.items():
            raw_expected = expectations.get(expected_key)
            expected_values = [
                str(value).strip()
                for value in (raw_expected if isinstance(raw_expected, list) else [raw_expected])
                if str(value or "").strip()
            ]
            if not expected_values:
                continue
            configured += 1
            fragments: list[str] = []
            has_match = False
            for expected_value in expected_values:
                current_match, current_fragments = contains_contextual_route(expected_value, slots[slot_name])
                has_match = has_match or current_match
                fragments.extend(current_fragments)
            if has_match:
                matched += 1.0
                supporting.extend(fragments)
            else:
                # Keep category precision, but give partial credit when the
                # correct professional direction exists in another route slot.
                # The active contract has one recommended primary route while
                # the specification can list several acceptable primary paths.
                anywhere_fragments: list[str] = []
                for expected_value in expected_values:
                    _, current_fragments = contains_contextual_route(expected_value, slots["all_titles"])
                    anywhere_fragments.extend(current_fragments)
                if anywhere_fragments:
                    matched += 0.5
                    supporting.extend(anywhere_fragments)
                    missing.append(f"misclassified:{expected_key}:{' | '.join(expected_values)}")
                else:
                    missing.append(f"{expected_key}:{' | '.join(expected_values)}")

        score = round((matched / max(1, configured)) * 20)
        return make_score(
            score=score,
            max_score=20,
            reason_codes=["ROUTE_SLOT_MISMATCH"] if missing else [],
            supporting_fragments=supporting,
            missing_elements=missing,
            evaluator_comment="Routes are evaluated by slot: main, transition, quick income, and emergency bridge.",
        )
