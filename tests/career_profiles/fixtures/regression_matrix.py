from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _get_eval(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("evaluation_result")
    return value if isinstance(value, dict) else {}


def _score(payload: dict[str, Any]) -> int:
    return int(_get_eval(payload).get("total_score") or 0)


def _passed(payload: dict[str, Any]) -> bool:
    return bool(_get_eval(payload).get("passed"))


def _critical_codes(payload: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    findings = _get_eval(payload).get("critical_findings") or []
    for item in findings:
        if not isinstance(item, dict):
            continue
        if str(item.get("decision") or "").strip() != "confirmed":
            continue
        code = str(item.get("error_code") or "").strip().upper()
        if code:
            codes.add(code)
    return codes


def _system_codes(payload: dict[str, Any]) -> set[str]:
    return {
        str(code).strip().upper()
        for code in (_get_eval(payload).get("reason_codes") or [])
        if str(code).strip()
    }


def _breakdown_score(payload: dict[str, Any], key: str) -> int:
    breakdown = _get_eval(payload).get("score_breakdown")
    if not isinstance(breakdown, dict):
        return 0
    evaluator_result = breakdown.get(key)
    if not isinstance(evaluator_result, dict):
        return 0
    return int(evaluator_result.get("score") or 0)


def _extract_route_groups(generated_result: dict[str, Any]) -> tuple[set[str], set[str]]:
    primary: set[str] = set()
    quick: set[str] = set()
    blocks = generated_result.get("route_evidence_blocks") if isinstance(generated_result.get("route_evidence_blocks"), list) else []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        route = str(block.get("route") or "").strip().lower()
        if not route:
            continue
        income_role = str(block.get("income_role") or "").strip().lower()
        if income_role == "primary":
            primary.add(route)
        elif income_role == "quick":
            quick.add(route)
    return primary, quick


def build_profile_regression_row(
    *,
    profile_id: str,
    baseline_payload: dict[str, Any],
    current_payload: dict[str, Any],
) -> dict[str, Any]:
    baseline_score = _score(baseline_payload)
    current_score = _score(current_payload)
    baseline_passed = _passed(baseline_payload)
    current_passed = _passed(current_payload)

    baseline_critical = _critical_codes(baseline_payload)
    current_critical = _critical_codes(current_payload)
    new_critical_errors = sorted(current_critical - baseline_critical)
    resolved_critical_errors = sorted(baseline_critical - current_critical)

    baseline_system = _system_codes(baseline_payload)
    current_system = _system_codes(current_payload)
    new_system_codes = sorted(current_system - baseline_system)
    resolved_system_codes = sorted(baseline_system - current_system)

    regression_reasons: list[str] = []
    if new_critical_errors:
        regression_reasons.append("new_critical_error")

    direct_refusal_violation_new = "DIRECT_REFUSAL_VIOLATED" in (set(new_critical_errors) | set(new_system_codes))
    if direct_refusal_violation_new:
        regression_reasons.append("direct_refusal_not_respected")

    baseline_route_score = _breakdown_score(baseline_payload, "routes")
    current_route_score = _breakdown_score(current_payload, "routes")
    baseline_evidence_score = _breakdown_score(baseline_payload, "evidence")
    current_evidence_score = _breakdown_score(current_payload, "evidence")
    baseline_core_score = _breakdown_score(baseline_payload, "professional_core")
    current_core_score = _breakdown_score(current_payload, "professional_core")
    if (current_route_score < baseline_route_score) or (current_evidence_score < baseline_evidence_score) or (current_core_score < baseline_core_score):
        regression_reasons.append("main_route_less_evidenced")

    baseline_primary, baseline_quick = _extract_route_groups(
        baseline_payload.get("generated_result") if isinstance(baseline_payload.get("generated_result"), dict) else {}
    )
    current_primary, _ = _extract_route_groups(
        current_payload.get("generated_result") if isinstance(current_payload.get("generated_result"), dict) else {}
    )
    if baseline_quick and current_primary and (baseline_quick & current_primary):
        regression_reasons.append("quick_route_became_primary")

    baseline_seniority_score = _breakdown_score(baseline_payload, "seniority")
    current_seniority_score = _breakdown_score(current_payload, "seniority")
    seniority_error_new = "SENIORITY_DIMENSIONS_MISSING" in new_system_codes
    if seniority_error_new or (baseline_seniority_score > 0 and current_seniority_score == 0):
        regression_reasons.append("seniority_overstated_or_zeroed")

    uncertainty_error_new = (
        "UNCERTAINTY_UNDEREXPLAINED" in new_system_codes or "UNCERTAINTY_NOT_MARKED" in set(new_critical_errors)
    )
    if uncertainty_error_new:
        regression_reasons.append("uncertainty_marker_lost")

    if baseline_passed and not current_passed:
        regression_reasons.append("passed_profile_now_failed")

    regression_detected = bool(regression_reasons)
    return {
        "profile_id": profile_id,
        "baseline_score": baseline_score,
        "current_score": current_score,
        "score_delta": current_score - baseline_score,
        "baseline_passed": baseline_passed,
        "current_passed": current_passed,
        "new_critical_errors": new_critical_errors,
        "resolved_critical_errors": resolved_critical_errors,
        "new_system_error_codes": new_system_codes,
        "resolved_system_error_codes": resolved_system_codes,
        "regression_detected": regression_detected,
        "regression_reasons": regression_reasons,
    }


def load_profile_payloads(profile_results_dir: Path) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    if not profile_results_dir.exists() or not profile_results_dir.is_dir():
        return payloads

    for path in sorted(profile_results_dir.glob("*.json")):
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        profile_id = str(payload.get("profile_id") or "").strip()
        if profile_id:
            payloads[profile_id] = payload
    return payloads


def build_regression_matrix(
    *,
    baseline_payloads: dict[str, dict[str, Any]],
    current_payloads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing_in_baseline: list[str] = []

    for profile_id, current_payload in sorted(current_payloads.items()):
        baseline_payload = baseline_payloads.get(profile_id)
        if baseline_payload is None:
            missing_in_baseline.append(profile_id)
            continue
        rows.append(
            build_profile_regression_row(
                profile_id=profile_id,
                baseline_payload=baseline_payload,
                current_payload=current_payload,
            )
        )

    regressions = [row for row in rows if bool(row.get("regression_detected"))]
    new_critical_total = sum(len(row.get("new_critical_errors") or []) for row in rows)

    return {
        "profiles": rows,
        "summary": {
            "profile_count_compared": len(rows),
            "regression_profiles": [row.get("profile_id") for row in regressions],
            "regression_count": len(regressions),
            "new_critical_total": new_critical_total,
            "missing_in_baseline": missing_in_baseline,
        },
    }


def evaluate_regression_acceptance(
    *,
    matrix: dict[str, Any],
    required_error_codes: list[str] | None = None,
) -> dict[str, Any]:
    required_codes = {str(code).strip().upper() for code in (required_error_codes or []) if str(code).strip()}
    profiles = matrix.get("profiles") if isinstance(matrix.get("profiles"), list) else []

    regressions: list[dict[str, Any]] = []
    resolved_any_required = not required_codes
    for row in profiles:
        if not isinstance(row, dict):
            continue
        if bool(row.get("regression_detected")):
            regressions.append(row)
        resolved_codes = {str(code).strip().upper() for code in row.get("resolved_system_error_codes") or [] if str(code).strip()}
        resolved_codes.update({str(code).strip().upper() for code in row.get("resolved_critical_errors") or [] if str(code).strip()})
        if required_codes and (required_codes & resolved_codes):
            resolved_any_required = True

    new_critical_total = sum(len(row.get("new_critical_errors") or []) for row in regressions)
    accepted = (len(regressions) == 0) and (new_critical_total == 0) and resolved_any_required
    return {
        "accepted": accepted,
        "regression_count": len(regressions),
        "new_critical_total": new_critical_total,
        "regression_profiles": [row.get("profile_id") for row in regressions],
        "resolved_required_error": resolved_any_required,
        "required_error_codes": sorted(required_codes),
    }
