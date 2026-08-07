from __future__ import annotations

import inspect
from pathlib import Path
import unittest

from openai_client import CareerOpenAIClient
from openai_client import FINAL_REPORT_PROMPT, RESUME_ANALYSIS_PROMPT, STORY_ANALYSIS_PROMPT, SYSTEM_PROMPT
from tests.career_profiles.evaluators.protocols import CareerEvaluatorProtocol, CareerGeneratorProtocol
from tests.career_profiles.fixtures.generator_boundary import (
    FORBIDDEN_GENERATOR_FIELDS,
    TEST_DATA_LEAKAGE,
    GeneratorDataLeakageError,
    assert_no_generator_leakage,
    build_generation_payload,
)


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_GLOBS = ("*.py", "handlers/*.py", "services/*.py", "utils/*.py")
FORBIDDEN_IMPORT_MARKERS = (
    "tests.career_profiles.expected",
    "tests.career_profiles.evaluators",
    "career_profiles.expected",
    "career_profiles.evaluators",
    "tests/career_profiles/expected",
    "tests\\career_profiles\\expected",
)
FORBIDDEN_PROMPT_MARKERS = tuple(FORBIDDEN_GENERATOR_FIELDS) + (
    "expected_profile",
    "expected profile",
    "expected route",
    "expected matrix",
    "evaluation_score",
    "эталон",
    "ожидаем",
)
REQUIRED_PROFILE_DIRS = (
    "inputs",
    "expected",
    "schemas",
    "evaluators",
    "fixtures",
    "results",
    "baseline",
)


def _production_files() -> list[Path]:
    files: list[Path] = []
    for pattern in PRODUCTION_GLOBS:
        files.extend(ROOT.glob(pattern))
    return sorted({path for path in files if path.is_file()})


class GeneratorEvaluatorIsolationTests(unittest.TestCase):
    def test_required_career_profiles_directories_exist(self) -> None:
        base_dir = ROOT / "tests" / "career_profiles"
        for name in REQUIRED_PROFILE_DIRS:
            self.assertTrue((base_dir / name).exists(), f"Missing required directory: tests/career_profiles/{name}")

    def test_generator_protocol_has_no_expected_profile_argument(self) -> None:
        signature = inspect.signature(CareerGeneratorProtocol.generate)
        self.assertEqual(list(signature.parameters.keys()), ["self", "input_profile", "runtime_context"])
        self.assertNotIn("expected_profile", signature.parameters)

    def test_real_generator_signature_has_no_expected_profile_argument(self) -> None:
        signature = inspect.signature(CareerOpenAIClient.build_report)
        self.assertNotIn("expected_profile", signature.parameters)
        for field_name in FORBIDDEN_GENERATOR_FIELDS:
            self.assertNotIn(field_name, signature.parameters)

    def test_evaluator_protocol_is_the_only_side_with_expected_profile(self) -> None:
        signature = inspect.signature(CareerEvaluatorProtocol.evaluate)
        self.assertEqual(
            list(signature.parameters.keys()),
            ["self", "input_profile", "generated_result", "expected_profile"],
        )

    def test_generator_has_no_expected_dependency(self) -> None:
        offenders: list[str] = []
        for file_path in _production_files():
            content = file_path.read_text(encoding="utf-8")
            for marker in FORBIDDEN_IMPORT_MARKERS:
                if marker in content:
                    offenders.append(f"{file_path.relative_to(ROOT)} -> {marker}")
        self.assertEqual(offenders, [], "Production code must not import expected/evaluator test modules")

    def test_generator_config_has_no_expected_path_reference(self) -> None:
        offenders: list[str] = []
        for file_path in _production_files():
            content = file_path.read_text(encoding="utf-8")
            if "career_profiles/expected" in content or "career_profiles\\expected" in content:
                offenders.append(str(file_path.relative_to(ROOT)))
        self.assertEqual(offenders, [], "Generator configuration must not point at expected fixtures")

    def test_runtime_guard_blocks_forbidden_generator_fields(self) -> None:
        with self.assertRaises(GeneratorDataLeakageError) as ctx:
            assert_no_generator_leakage({"story": "x", "expected_routes": ["role"]})
        self.assertEqual(getattr(ctx.exception, "code", ""), TEST_DATA_LEAKAGE)

    def test_runtime_guard_blocks_nested_forbidden_generator_fields(self) -> None:
        with self.assertRaises(GeneratorDataLeakageError) as ctx:
            assert_no_generator_leakage({"story_analysis": {"critical_errors": ["bad"]}})
        self.assertEqual(getattr(ctx.exception, "code", ""), TEST_DATA_LEAKAGE)

    def test_generation_payload_has_no_expected_fields(self) -> None:
        payload = build_generation_payload(
            {
                "story": "Опыт в админке",
                "story_analysis": {"current_identity": "admin"},
                "answers": "Нужен доход",
                "resume_analysis": {"hard_skills": ["Excel"]},
            },
            {
                "selected_barriers": ["тревога"],
                "selected_psych_markers": ["страх"],
                "language": "ru",
            },
        )
        self.assertFalse(any(key in payload for key in FORBIDDEN_GENERATOR_FIELDS))

    def test_build_generation_payload_rejects_expected_fields_in_runtime_context(self) -> None:
        with self.assertRaises(GeneratorDataLeakageError) as ctx:
            build_generation_payload(
                {"story": "Опыт", "story_analysis": {}, "answers": "-"},
                {"expected_result": {"route": "X"}},
            )
        self.assertEqual(getattr(ctx.exception, "code", ""), TEST_DATA_LEAKAGE)

    def test_prompts_do_not_contain_expected_or_matrix_markers(self) -> None:
        prompts = [SYSTEM_PROMPT, STORY_ANALYSIS_PROMPT, FINAL_REPORT_PROMPT, RESUME_ANALYSIS_PROMPT]
        joined = "\n".join(str(item) for item in prompts).lower()
        for marker in FORBIDDEN_PROMPT_MARKERS:
            self.assertNotIn(marker.lower(), joined)


if __name__ == "__main__":
    unittest.main()