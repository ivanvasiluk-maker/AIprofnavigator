#!/usr/bin/env python
"""Read-only local checks used before the Railway deployment job.

The module intentionally does nothing on import so pytest can collect the
repository without creating analytics users or mutating report files.
"""

from __future__ import annotations

from pathlib import Path

from config import settings
from tests.career_profiles.validate_package import PACKAGE_COMPLETE, validate_test_package
from utils.reporting import ReportMeta, build_offer_text, render_report_html


ROOT = Path(__file__).resolve().parent
CAREER_PACKAGE = ROOT / "tests" / "career_profiles"


def run_checks() -> list[str]:
    """Run deterministic checks and return human-readable confirmations."""
    confirmations: list[str] = []

    settings.validate()
    confirmations.append("required configuration is present")

    offer = build_offer_text()
    if len(offer) <= 50:
        raise AssertionError("offer text is unexpectedly empty")

    test_report = {
        "digital_human": {"current_state": "Test"},
        "career_decision": {"recommended_main_path": "Test"},
        "action_plan": {"today": {"action": "Test"}},
        "closing_message": "Test",
    }
    html = render_report_html(
        test_report,
        ReportMeta("TestUser", "Test", "Growth", "2026-01-01", "local-check"),
    )
    if "NextYou" not in html:
        raise AssertionError("rendered HTML does not contain the report header")
    confirmations.append("report rendering is operational")

    package_result = validate_test_package(
        manifest_path=CAREER_PACKAGE / "package_manifest.json",
        inputs_dir=CAREER_PACKAGE / "inputs",
        expected_dir=CAREER_PACKAGE / "expected",
    )
    if package_result.get("status") != PACKAGE_COMPLETE:
        blockers = ", ".join(package_result.get("baseline_blockers") or [])
        raise AssertionError(f"career test package is incomplete: {blockers}")
    confirmations.append("career profile package is complete")

    return confirmations


def main() -> int:
    print("PRE-DEPLOYMENT CHECKS")
    for confirmation in run_checks():
        print(f"  OK: {confirmation}")
    print("Local deployment checks passed; CI test suite remains the release gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
