from __future__ import annotations

import sys
from typing import Any


_EXPECTED_KEYS = {
    "expected",
    "expected_routes",
    "expected_professional_core",
    "forbidden_recommendations",
    "critical_errors",
    "logic_rules",
}


def assert_expected_profiles_not_loaded(environment: str, runtime_payload: dict[str, Any]) -> None:
    if str(environment or "").strip().lower() != "production":
        return
    leaked_keys = _find_expected_keys(runtime_payload)
    expected_profiles_not_loaded = not leaked_keys and not any(
        "career_profiles" in module_name and "expected" in module_name
        for module_name in sys.modules
    )
    assert expected_profiles_not_loaded, "Expected eval profiles must not be loaded in production"


def _find_expected_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = {str(key) for key in value if str(key).strip().lower() in _EXPECTED_KEYS}
        for item in value.values():
            found.update(_find_expected_keys(item))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_find_expected_keys(item))
        return found
    return set()