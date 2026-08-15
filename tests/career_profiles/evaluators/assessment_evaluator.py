from __future__ import annotations

import re
from typing import Any


WEIGHTS = {
    "professional_identity": 20,
    "seniority": 15,
    "career_routes": 20,
    "constraints": 15,
    "evidence": 10,
    "respect_for_user_choice": 10,
    "logic_safety": 10,
}


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zа-яё]+", str(value or "").casefold())
        if len(token) > 3
    }


def _similar(left: str, right: str) -> bool:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens)) >= 0.4


def _coverage(actual: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    matched = sum(any(_similar(actual_item, expected_item) for actual_item in actual) for expected_item in expected)
    return matched / len(expected)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def evaluate_career_assessment(generated: dict[str, Any], golden: dict[str, Any]) -> dict[str, Any]:
    expected = golden.get("expected") if isinstance(golden.get("expected"), dict) else golden
    identity = generated.get("identity") if isinstance(generated.get("identity"), dict) else {}
    routes = generated.get("routes") if isinstance(generated.get("routes"), dict) else {}
    conclusions = generated.get("conclusions") if isinstance(generated.get("conclusions"), dict) else {}
    evidence = generated.get("evidence") if isinstance(generated.get("evidence"), list) else []
    constraints = generated.get("constraints") if isinstance(generated.get("constraints"), list) else []
    choice = generated.get("user_choice") if isinstance(generated.get("user_choice"), dict) else {}
    first_steps = generated.get("first_steps") if isinstance(generated.get("first_steps"), list) else []

    core_actual = [*identity.get("professional_core", []), *identity.get("secondary_functions", [])]
    core_expected = [*expected.get("professional_core", []), *expected.get("secondary_functions", [])]
    identity_quality = 0.0
    if identity.get("professional_core"):
        identity_quality += 5
    if identity.get("core_description"):
        identity_quality += 4
    if identity.get("secondary_functions"):
        identity_quality += 3
    identity_score = round(identity_quality + 8 * _coverage(core_actual, core_expected), 2)

    seniority_expected = expected.get("seniority") if isinstance(expected.get("seniority"), dict) else {}
    seniority_score = 0.0
    if identity.get("seniority_current"):
        seniority_score += 5
    if identity.get("seniority_notes"):
        seniority_score += 5
    if _similar(str(identity.get("seniority_current") or ""), str(seniority_expected.get("current") or "")):
        seniority_score += 3
    notes_text = " ".join(
        [
            str(identity.get("seniority_transition") or ""),
            str(identity.get("seniority_notes") or ""),
        ]
    )
    if _similar(notes_text, str(seniority_expected.get("notes") or "")):
        seniority_score += 2

    actual_route_titles = [
        str(item.get("title") or "")
        for category in ("primary_routes", "transition_routes", "quick_income_routes", "emergency_routes")
        for item in routes.get(category, [])
        if isinstance(item, dict)
    ]
    expected_route_titles = [
        *expected.get("primary_routes", []),
        *expected.get("transition_routes", []),
        *expected.get("quick_income", []),
    ]
    all_routes = [
        item
        for category in ("primary_routes", "transition_routes", "quick_income_routes", "emergency_routes")
        for item in routes.get(category, [])
        if isinstance(item, dict)
    ]
    route_quality = 0.0
    if routes.get("primary_routes"):
        route_quality += 4
    if routes.get("recommended_route_id") in {item.get("route_id") for item in all_routes}:
        route_quality += 4
    if all(
        item.get("why_it_fits")
        and item.get("entry_level")
        and item.get("market_test")
        and item.get("disconfirming_conditions")
        for item in all_routes
    ):
        route_quality += 4
    route_score = round(route_quality + 8 * _coverage(actual_route_titles, expected_route_titles), 2)

    constraint_score = 0.0
    if constraints:
        constraint_score += 5
    if any(item.get("confirmed") for item in constraints if isinstance(item, dict)):
        constraint_score += 5
    if all(item.get("evidence_ids") for item in constraints if isinstance(item, dict)):
        constraint_score += 5

    evidence_score = 0.0
    if len(evidence) >= 2:
        evidence_score += 4
    if all(item.get("fact") and item.get("source_reference") for item in evidence if isinstance(item, dict)):
        evidence_score += 3
    if all(item.get("source_type") in {"history", "resume", "answer"} for item in evidence if isinstance(item, dict)):
        evidence_score += 3

    choice_score = 0.0
    for field_name, points in (("functions_to_preserve", 3), ("functions_to_avoid", 3), ("priorities", 4)):
        if choice.get(field_name):
            choice_score += points

    mandatory_coverage = _coverage(
        conclusions.get("mandatory_conclusions", []),
        expected.get("mandatory_conclusions", []),
    )
    step_types = {item.get("type") for item in first_steps if isinstance(item, dict)}
    steps_valid = (
        3 <= len(first_steps) <= 5
        and len(step_types) == len(first_steps)
        and all(
            item.get("action")
            and item.get("expected_result")
            and int(item.get("duration_minutes") or 0) > 0
            and item.get("related_route_id")
            for item in first_steps
            if isinstance(item, dict)
        )
    )
    logic_score = round(4 * mandatory_coverage + (4 if steps_valid else 0) + (2 if not conclusions.get("critical_errors_detected") else 0), 2)

    critical_errors = list(conclusions.get("critical_errors_detected") or [])
    recommendation_surface = "\n".join(
        [
            *actual_route_titles,
            *[str(item.get("why_it_fits") or "") for item in all_routes],
            str(conclusions.get("main_conclusion") or ""),
        ]
    ).casefold()
    for forbidden in expected.get("forbidden_recommendations", []):
        if str(forbidden).casefold() in recommendation_surface:
            critical_errors.append(f"Forbidden recommendation: {forbidden}")

    category_scores = {
        "professional_identity": identity_score,
        "seniority": seniority_score,
        "career_routes": route_score,
        "constraints": constraint_score,
        "evidence": evidence_score,
        "respect_for_user_choice": choice_score,
        "logic_safety": logic_score,
    }
    total_score = round(sum(category_scores.values()), 2)
    return {
        "profile_id": str(golden.get("profile_id") or golden.get("id") or ""),
        "score": total_score,
        "threshold": 80,
        "passed": total_score >= 80 and not critical_errors,
        "category_scores": category_scores,
        "critical_errors": critical_errors,
        "first_steps_valid": steps_valid,
    }