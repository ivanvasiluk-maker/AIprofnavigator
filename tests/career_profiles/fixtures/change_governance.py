from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ChangeProposal(BaseModel):
    change_id: str = ""
    source_error_codes: list[str] = Field(default_factory=list)
    affected_profiles_expected_to_improve: list[str] = Field(default_factory=list)
    profiles_at_regression_risk: list[str] = Field(default_factory=list)
    universal_rule_changed: str = ""
    files_to_change: list[str] = Field(default_factory=list)
    feature_flag: str = ""
    rollback_condition: str = ""
    acceptance_condition: str = ""


_HARDCODE_PATTERNS = [
    re.compile(r"\bif\s+profile_id\s*==", re.IGNORECASE),
    re.compile(r"\bprofile_id\s*==", re.IGNORECASE),
    re.compile(r"\bif\s+.*\bprofile_\d+\b", re.IGNORECASE),
]

_EXPECTED_COUPLING_MARKERS = {
    "expected_profile",
    "expected_routes",
    "route_expectations",
    "forbidden_recommendations",
    "direct_refusals",
}


def load_change_proposal(path: Path) -> ChangeProposal:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return ChangeProposal.model_validate(payload)


def _collect_known_profile_ids(inputs_dir: Path | None) -> set[str]:
    if inputs_dir is None or not inputs_dir.exists() or not inputs_dir.is_dir():
        return set()
    ids: set[str] = set()
    for path in sorted(item for item in inputs_dir.glob("*.json") if item.is_file()):
        ids.add(path.stem.lower())
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                profile_id = str(payload.get("profile_id") or "").strip().lower()
                if profile_id:
                    ids.add(profile_id)
        except Exception:
            continue
    return ids


def _minimum_justification_checks(proposal: ChangeProposal, systemic_error_frequency: dict[str, int]) -> dict[str, bool]:
    source_codes = {code.strip().upper() for code in proposal.source_error_codes if code.strip()}
    universal_rule = proposal.universal_rule_changed.strip().lower()
    acceptance = proposal.acceptance_condition.strip().lower()
    rollback = proposal.rollback_condition.strip().lower()
    combined_text = " ".join([universal_rule, acceptance, rollback])

    condition_1 = any(systemic_error_frequency.get(code, 0) >= 2 for code in source_codes)
    condition_2 = (
        any(token in source_codes for token in {"CRITICAL", "CRITICAL_ERROR", "DIRECT_REFUSAL_VIOLATED"})
        or "безопас" in combined_text
        or "safety" in combined_text
        or "critical" in combined_text
    )
    condition_3 = any(marker in combined_text for marker in ["архитект", "architecture", "general rule", "universal"])
    condition_4 = any(marker in combined_text for marker in ["утеч", "leak", "expected"]) or any(
        marker in source_codes for marker in {"EXPECTED_DATA_IN_INPUT", "TEST_DATA_LEAKAGE"}
    )
    condition_5 = any(marker in combined_text for marker in ["reproduc", "воспроизвод", "test", "тест"])

    return {
        "system_error_in_multiple_profiles": condition_1,
        "critical_universal_safety_rule": condition_2,
        "architectural_defect": condition_3,
        "expected_data_leak_fix": condition_4,
        "reproducibility_or_testing": condition_5,
    }


def _hardcode_violations(
    *,
    files_to_change: list[str],
    production_root: Path,
    known_profile_ids: set[str],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for rel_path in files_to_change:
        path = Path(rel_path)
        abs_path = path if path.is_absolute() else (production_root / path)
        if not abs_path.exists() or not abs_path.is_file():
            violations.append({"file": str(path), "issue": "file_not_found"})
            continue

        normalized_parts = {part.lower() for part in abs_path.parts}
        if "tests" in normalized_parts:
            continue

        content = abs_path.read_text(encoding="utf-8", errors="ignore")
        lowered = content.lower()
        for pattern in _HARDCODE_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append(
                    {
                        "file": str(path),
                        "issue": "profile_hardcode_pattern",
                        "pattern": pattern.pattern,
                        "fragment": match.group(0),
                    }
                )
                break

        for marker in _EXPECTED_COUPLING_MARKERS:
            if marker in lowered:
                violations.append(
                    {
                        "file": str(path),
                        "issue": "expected_text_coupling",
                        "marker": marker,
                    }
                )

        for profile_id in known_profile_ids:
            if not profile_id:
                continue
            quoted_markers = [f'"{profile_id}"', f"'{profile_id}'"]
            if any(marker in lowered for marker in quoted_markers):
                violations.append(
                    {
                        "file": str(path),
                        "issue": "profile_id_literal",
                        "profile_id": profile_id,
                    }
                )
                break

    return violations


def validate_change_proposal(
    *,
    proposal: ChangeProposal,
    systemic_errors: list[dict[str, Any]] | None = None,
    production_root: Path,
    inputs_dir: Path | None = None,
) -> dict[str, Any]:
    systemic_errors = systemic_errors or []
    systemic_frequency: dict[str, int] = {}
    for item in systemic_errors:
        if not isinstance(item, dict):
            continue
        code = str(item.get("error_code") or "").strip().upper()
        freq = int(item.get("frequency") or 0)
        if code:
            systemic_frequency[code] = max(systemic_frequency.get(code, 0), freq)

    checks = _minimum_justification_checks(proposal, systemic_frequency)
    minimum_justification_passed = any(checks.values())

    known_profile_ids = _collect_known_profile_ids(inputs_dir)
    hardcode_violations = _hardcode_violations(
        files_to_change=proposal.files_to_change,
        production_root=production_root,
        known_profile_ids=known_profile_ids,
    )

    feature_flag_ok = bool(proposal.feature_flag.strip())
    universal_rule_ok = bool(proposal.universal_rule_changed.strip())
    acceptance_ok = bool(proposal.acceptance_condition.strip())
    rollback_ok = bool(proposal.rollback_condition.strip())

    allowed = (
        minimum_justification_passed
        and feature_flag_ok
        and universal_rule_ok
        and acceptance_ok
        and rollback_ok
        and not hardcode_violations
    )

    return {
        "change_id": proposal.change_id,
        "allowed": allowed,
        "minimum_justification_passed": minimum_justification_passed,
        "minimum_justification_checks": checks,
        "feature_flag_ok": feature_flag_ok,
        "universal_rule_ok": universal_rule_ok,
        "acceptance_condition_ok": acceptance_ok,
        "rollback_condition_ok": rollback_ok,
        "hardcode_violations": hardcode_violations,
        "source_error_codes": sorted({code.strip().upper() for code in proposal.source_error_codes if code.strip()}),
        "files_to_change": proposal.files_to_change,
        "feature_flag": proposal.feature_flag,
    }
