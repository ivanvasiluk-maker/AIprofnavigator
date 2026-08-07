from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tests.career_profiles.fixtures.change_governance import ChangeProposal, validate_change_proposal
from tests.career_profiles.fixtures.regression_matrix import build_regression_matrix, evaluate_regression_acceptance
from tests.career_profiles.validate_package import (
    EXPECTED_DATA_IN_INPUT,
    PACKAGE_INCOMPLETE,
    PACKAGE_VERSION_MISMATCH,
    validate_test_package,
)


ROOT = Path(__file__).resolve().parents[1]
CAREER_PROFILES_DIR = ROOT / "tests" / "career_profiles"


def _payload(profile_id: str, *, passed: bool, total_score: int, critical_codes: list[str], reason_codes: list[str], route: str) -> dict:
    critical_findings = [
        {
            "error_code": code,
            "decision": "confirmed",
        }
        for code in critical_codes
    ]
    return {
        "profile_id": profile_id,
        "generated_result": {
            "route_evidence_blocks": [
                {
                    "route": route,
                    "income_role": "primary",
                    "what_may_disprove_this_route": ["needs validation"],
                    "evidence_from_user": ["relevant experience"],
                }
            ]
        },
        "evaluation_result": {
            "passed": passed,
            "total_score": total_score,
            "reason_codes": reason_codes,
            "critical_findings": critical_findings,
            "score_breakdown": {
                "routes": {"score": 20},
                "evidence": {"score": 10},
                "professional_core": {"score": 15},
                "seniority": {"score": 15},
            },
        },
    }


class PackageValidatorTests(unittest.TestCase):
    def test_repository_package_currently_incomplete(self) -> None:
        report = validate_test_package(
            manifest_path=CAREER_PROFILES_DIR / "package_manifest.json",
            inputs_dir=CAREER_PROFILES_DIR / "inputs",
            expected_dir=CAREER_PROFILES_DIR / "expected",
            expected_package_version="career_profiles_v1",
        )
        self.assertEqual(report["status"], PACKAGE_INCOMPLETE)
        self.assertIn(PACKAGE_INCOMPLETE, report["statuses"])
        self.assertFalse(report["baseline_ready"])

    def test_validator_detects_expected_fields_inside_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = root / "inputs"
            expected = root / "expected"
            inputs.mkdir()
            expected.mkdir()

            manifest = {
                "package_version": "career_profiles_v1",
                "profile_count": 1,
                "files": [
                    {"path": "inputs", "required": True},
                    {"path": "expected", "required": True},
                ],
            }
            (root / "package_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            (inputs / "profile_1.json").write_text(
                json.dumps({"profile_id": "profile_1", "story": "x", "story_analysis": {}, "answers": "x", "expected_routes": ["bad"]}),
                encoding="utf-8",
            )
            (expected / "profile_1.json").write_text(json.dumps({"profile_id": "profile_1"}), encoding="utf-8")

            report = validate_test_package(
                manifest_path=root / "package_manifest.json",
                inputs_dir=inputs,
                expected_dir=expected,
                expected_package_version="career_profiles_v1",
            )
            self.assertIn(EXPECTED_DATA_IN_INPUT, report["statuses"])

    def test_validator_detects_package_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = root / "inputs"
            expected = root / "expected"
            inputs.mkdir()
            expected.mkdir()

            manifest = {
                "package_version": "career_profiles_v0",
                "profile_count": 0,
                "files": [
                    {"path": "inputs", "required": True},
                    {"path": "expected", "required": True},
                ],
            }
            (root / "package_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            report = validate_test_package(
                manifest_path=root / "package_manifest.json",
                inputs_dir=inputs,
                expected_dir=expected,
                expected_package_version="career_profiles_v1",
            )
            self.assertIn(PACKAGE_VERSION_MISMATCH, report["statuses"])


class ChangeProposalGateTests(unittest.TestCase):
    def test_change_proposal_requires_minimum_justification_and_feature_flag(self) -> None:
        proposal = ChangeProposal(
            change_id="chg-001",
            source_error_codes=["MAIN_ROUTE_MISSING"],
            affected_profiles_expected_to_improve=["profile_2", "profile_5"],
            profiles_at_regression_risk=["profile_7"],
            universal_rule_changed="Architecture: shared route validation before recommendation.",
            files_to_change=["handlers/career.py"],
            feature_flag="career_route_guardrails_v2",
            rollback_condition="Rollback if regression matrix shows any new critical error.",
            acceptance_condition="Testing reproducibility remains stable with no new critical issues.",
        )
        report = validate_change_proposal(
            proposal=proposal,
            systemic_errors=[],
            production_root=ROOT,
            inputs_dir=CAREER_PROFILES_DIR / "inputs",
        )
        self.assertTrue(report["allowed"])

    def test_change_proposal_rejects_profile_specific_hardcode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handlers_dir = root / "handlers"
            inputs = root / "inputs"
            handlers_dir.mkdir()
            inputs.mkdir()
            (inputs / "profile_1.json").write_text(json.dumps({"profile_id": "profile_1"}), encoding="utf-8")
            (handlers_dir / "career.py").write_text('if profile_id == "profile_1":\n    return "hack"\n', encoding="utf-8")

            proposal = ChangeProposal(
                change_id="chg-002",
                source_error_codes=["DIRECT_REFUSAL_VIOLATED"],
                affected_profiles_expected_to_improve=["profile_1"],
                profiles_at_regression_risk=["profile_9"],
                universal_rule_changed="Critical safety rule for direct refusal handling.",
                files_to_change=["handlers/career.py"],
                feature_flag="career_refusal_priority_v2",
                rollback_condition="Rollback on any new critical error.",
                acceptance_condition="No new criticals after full 9-profile matrix.",
            )
            report = validate_change_proposal(
                proposal=proposal,
                systemic_errors=[],
                production_root=root,
                inputs_dir=inputs,
            )
            self.assertFalse(report["allowed"])
            self.assertTrue(report["hardcode_violations"])


class RegressionMatrixTests(unittest.TestCase):
    def test_regression_matrix_detects_new_critical_and_failed_profile(self) -> None:
        baseline = {
            "profile_1": _payload(
                "profile_1",
                passed=True,
                total_score=90,
                critical_codes=[],
                reason_codes=[],
                route="operations specialist",
            )
        }
        current = {
            "profile_1": _payload(
                "profile_1",
                passed=False,
                total_score=65,
                critical_codes=["DIRECT_REFUSAL_VIOLATED"],
                reason_codes=["DIRECT_REFUSAL_VIOLATED"],
                route="operations specialist",
            )
        }

        matrix = build_regression_matrix(baseline_payloads=baseline, current_payloads=current)
        row = matrix["profiles"][0]
        self.assertTrue(row["regression_detected"])
        self.assertIn("DIRECT_REFUSAL_VIOLATED", row["new_critical_errors"])

        gate = evaluate_regression_acceptance(matrix=matrix, required_error_codes=["MAIN_ROUTE_MISSING"])
        self.assertFalse(gate["accepted"])


if __name__ == "__main__":
    unittest.main()
