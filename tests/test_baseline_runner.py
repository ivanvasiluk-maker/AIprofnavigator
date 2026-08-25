from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from typing import Any

from tests.career_profiles.evaluators.baseline_evaluator import BaselineCareerEvaluator
from tests.career_profiles.fixtures.baseline_runner import generate_run_id, run_baseline_profiles
from tests.career_profiles.fixtures.generator_boundary import TEST_DATA_LEAKAGE


ROOT = Path(__file__).resolve().parents[1]
BASELINE_LOCK_PATH = ROOT / "tests" / "career_profiles" / "baseline" / "baseline_lock.json"


class RecordingGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate(self, input_profile: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"input_profile": dict(input_profile), "runtime_context": dict(runtime_context)})
        route = str(input_profile.get("story_analysis", {}).get("preferred_route") or "Operations Specialist")
        return {
            "career_decision": {"recommended_main_path": route},
            "career_recommendations": [{"title": route}],
            "route_evidence_blocks": [
                {
                    "route": route,
                    "income_role": "primary",
                    "why_it_fits": ["Есть релевантный опыт"],
                    "evidence_from_user": [f"Опыт в {route}"],
                    "missing_competencies": ["локальный язык"],
                    "entry_level": "transition",
                    "risks": ["конкуренция"],
                    "what_may_disprove_this_route": ["появятся новые ограничения"],
                },
                {
                    "route": "Temporary Bridge Role",
                    "income_role": "quick",
                    "why_it_fits": ["быстрый доход"],
                    "evidence_from_user": ["нужен быстрый доход"],
                    "missing_competencies": [],
                    "entry_level": "entry",
                    "risks": ["временный маршрут"],
                    "what_may_disprove_this_route": ["если доход не нужен срочно"],
                },
            ],
            "facts_only": {
                "explicit_facts": [f"Опыт в {route}"],
                "resume_facts": [],
                "inferences": ["Маршрут подтверждается опытом"],
                "unknowns": ["точный уровень языка"],
                "contradictions": [],
            },
        }


class FailingGenerator:
    async def generate(self, input_profile: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("synthetic generation failure")


def _input_payload(profile_id: str, preferred_route: str) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "language": "ru",
        "story": f"История {profile_id}",
        "story_analysis": {"current_identity": profile_id, "preferred_route": preferred_route},
        "answers": "Нужен стабильный доход",
        "resume_analysis": {"hard_skills": ["Excel"]},
        "selected_barriers": ["тревога"],
        "selected_psych_markers": ["страх ошибки"],
    }


def _expected_payload(profile_id: str, expected_route: str) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "route_expectations": {"main_route": expected_route, "quick_route": "Temporary Bridge Role"},
        "professional_core": [expected_route],
        "evidence_fragments": [f"Опыт в {expected_route}"],
        "must_show_uncertainty": True,
        "forbidden_recommendations": ["Clinical Psychologist"],
    }


class BaselineRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_execution_error_makes_release_gate_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            inputs_dir = base_dir / "inputs"
            expected_dir = base_dir / "expected"
            inputs_dir.mkdir()
            expected_dir.mkdir()
            (inputs_dir / "profile_1.json").write_text(json.dumps(_input_payload("profile_1", "Route 1")), encoding="utf-8")
            (expected_dir / "profile_1.json").write_text(json.dumps(_expected_payload("profile_1", "Route 1")), encoding="utf-8")

            summary = await run_baseline_profiles(
                generator=FailingGenerator(), evaluator=BaselineCareerEvaluator(),
                inputs_dir=inputs_dir, expected_dir=expected_dir, results_dir=base_dir / "results",
                baseline_lock_path=BASELINE_LOCK_PATH, required_profile_count=1, run_id="failed-profile",
                application_version="test", git_commit="commit", prompt_version="prompt",
                model="test", model_parameters={},
            )

            self.assertFalse(summary["baseline_complete"])
            self.assertEqual(summary["failed_count"], 1)
            self.assertEqual(summary["profiles"][0]["execution_error"]["error_type"], "RuntimeError")

    async def test_runner_executes_nine_profiles_with_separate_outputs(self) -> None:
        generator = RecordingGenerator()
        evaluator = BaselineCareerEvaluator()

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            inputs_dir = base_dir / "inputs"
            expected_dir = base_dir / "expected"
            results_dir = base_dir / "results"
            inputs_dir.mkdir()
            expected_dir.mkdir()

            for idx in range(1, 10):
                profile_id = f"profile_{idx}"
                route = f"Route {idx}"
                (inputs_dir / f"{profile_id}.json").write_text(
                    json.dumps(_input_payload(profile_id, route), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (expected_dir / f"{profile_id}.json").write_text(
                    json.dumps(_expected_payload(profile_id, route), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            summary = await run_baseline_profiles(
                generator=generator,
                evaluator=evaluator,
                inputs_dir=inputs_dir,
                expected_dir=expected_dir,
                results_dir=results_dir,
                baseline_lock_path=BASELINE_LOCK_PATH,
                required_profile_count=9,
                run_id="baseline_9_profiles",
                application_version="app-v1",
                git_commit="commit-123",
                prompt_version="prompts@sha256:test",
                model="gpt-4o-mini",
                model_parameters={"temperature": 0.2},
            )

            self.assertEqual(summary["profile_count"], 9)
            self.assertEqual(len(generator.calls), 9)

            run_dir = results_dir / "baseline_9_profiles"
            self.assertTrue((run_dir / "run_metadata.json").exists())
            self.assertTrue((run_dir / "summary.json").exists())
            self.assertTrue((run_dir / "judge_logs").exists())
            self.assertTrue((run_dir / "raw_responses").exists())
            for idx in range(1, 10):
                profile_id = f"profile_{idx}"
                profile_path = run_dir / "profiles" / f"{profile_id}.json"
                judge_path = run_dir / "judge_logs" / f"{profile_id}.judge.json"
                raw_path = run_dir / "raw_responses" / f"{profile_id}.raw.json"
                self.assertTrue(profile_path.exists())
                self.assertTrue(judge_path.exists())
                self.assertTrue(raw_path.exists())

                profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
                judge_payload = json.loads(judge_path.read_text(encoding="utf-8"))
                raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
                self.assertIn("generated_result", profile_payload)
                self.assertIn("evaluation_result", profile_payload)
                self.assertEqual(profile_payload["comparison"]["comparison_reliability"], "limited")
                self.assertIn("evaluation_result", judge_payload)
                self.assertIn("score_breakdown", judge_payload["evaluation_result"])
                self.assertIn("critical_errors", judge_payload["evaluation_result"]["score_breakdown"])
                self.assertIn("generated_result", raw_payload)
                self.assertNotIn("expected_routes", raw_payload)
                self.assertIn("retry_log", raw_payload)

            metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["run_id"], "baseline_9_profiles")
            self.assertEqual(metadata["application_version"], "app-v1")
            self.assertEqual(metadata["git_commit"], "commit-123")
            self.assertEqual(metadata["prompt_version"], "prompts@sha256:test")
            self.assertEqual(metadata["model"], "gpt-4o-mini")
            self.assertTrue(metadata["input_manifest_hash"])
            self.assertTrue(metadata["expected_manifest_hash"])
            self.assertTrue(metadata["completed_at"])
            self.assertTrue((run_dir / "baseline_summary.json").exists())
            self.assertTrue((run_dir / "baseline_summary.md").exists())
            self.assertTrue((run_dir / "systemic_errors.json").exists())
            self.assertTrue((run_dir / "profile_results").exists())

    async def test_runner_never_passes_expected_profile_to_generator(self) -> None:
        generator = RecordingGenerator()
        evaluator = BaselineCareerEvaluator()

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            inputs_dir = base_dir / "inputs"
            expected_dir = base_dir / "expected"
            results_dir = base_dir / "results"
            inputs_dir.mkdir()
            expected_dir.mkdir()

            (inputs_dir / "profile_1.json").write_text(
                json.dumps(_input_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (expected_dir / "profile_1.json").write_text(
                json.dumps(_expected_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            await run_baseline_profiles(
                generator=generator,
                evaluator=evaluator,
                inputs_dir=inputs_dir,
                expected_dir=expected_dir,
                results_dir=results_dir,
                baseline_lock_path=BASELINE_LOCK_PATH,
                required_profile_count=1,
                run_id="baseline_single",
                application_version="app-v1",
                git_commit="commit-123",
                prompt_version="prompts@sha256:test",
                model="gpt-4o-mini",
                model_parameters={"temperature": 0.2},
            )

            call = generator.calls[0]
            self.assertNotIn("expected_profile", call["input_profile"])
            self.assertNotIn("expected_profile", call["runtime_context"])
            self.assertNotIn("expected_routes", call["input_profile"])
            self.assertNotIn("forbidden_recommendations", call["runtime_context"])

    async def test_runner_fails_fast_on_leaked_expected_fields(self) -> None:
        generator = RecordingGenerator()
        evaluator = BaselineCareerEvaluator()

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            inputs_dir = base_dir / "inputs"
            expected_dir = base_dir / "expected"
            results_dir = base_dir / "results"
            inputs_dir.mkdir()
            expected_dir.mkdir()

            leaked_input = _input_payload("profile_1", "Operations Specialist")
            leaked_input["expected_result"] = {"route": "Forbidden leak"}
            (inputs_dir / "profile_1.json").write_text(json.dumps(leaked_input, ensure_ascii=False, indent=2), encoding="utf-8")
            (expected_dir / "profile_1.json").write_text(
                json.dumps(_expected_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, TEST_DATA_LEAKAGE):
                await run_baseline_profiles(
                    generator=generator,
                    evaluator=evaluator,
                    inputs_dir=inputs_dir,
                    expected_dir=expected_dir,
                    results_dir=results_dir,
                    baseline_lock_path=BASELINE_LOCK_PATH,
                    required_profile_count=1,
                    run_id="baseline_leak",
                    application_version="app-v1",
                    git_commit="commit-123",
                    prompt_version="prompts@sha256:test",
                    model="gpt-4o-mini",
                    model_parameters={"temperature": 0.2},
                )

    async def test_runner_requires_exact_profile_count_when_requested(self) -> None:
        generator = RecordingGenerator()
        evaluator = BaselineCareerEvaluator()

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            inputs_dir = base_dir / "inputs"
            expected_dir = base_dir / "expected"
            results_dir = base_dir / "results"
            inputs_dir.mkdir()
            expected_dir.mkdir()

            (inputs_dir / "profile_1.json").write_text(
                json.dumps(_input_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (expected_dir / "profile_1.json").write_text(
                json.dumps(_expected_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Expected 9 input profiles, found 1"):
                await run_baseline_profiles(
                    generator=generator,
                    evaluator=evaluator,
                    inputs_dir=inputs_dir,
                    expected_dir=expected_dir,
                    results_dir=results_dir,
                    baseline_lock_path=BASELINE_LOCK_PATH,
                    required_profile_count=9,
                    run_id="baseline_wrong_count",
                    application_version="app-v1",
                    git_commit="commit-123",
                    prompt_version="prompts@sha256:test",
                    model="gpt-4o-mini",
                    model_parameters={"temperature": 0.2},
                )

    async def test_run_directory_is_immutable_and_cannot_be_overwritten(self) -> None:
        generator = RecordingGenerator()
        evaluator = BaselineCareerEvaluator()

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            inputs_dir = base_dir / "inputs"
            expected_dir = base_dir / "expected"
            results_dir = base_dir / "results"
            inputs_dir.mkdir()
            expected_dir.mkdir()

            (inputs_dir / "profile_1.json").write_text(
                json.dumps(_input_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (expected_dir / "profile_1.json").write_text(
                json.dumps(_expected_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            kwargs = {
                "generator": generator,
                "evaluator": evaluator,
                "inputs_dir": inputs_dir,
                "expected_dir": expected_dir,
                "results_dir": results_dir,
                "baseline_lock_path": BASELINE_LOCK_PATH,
                "required_profile_count": 1,
                "run_id": "immutable_run",
                "application_version": "app-v1",
                "git_commit": "commit-123",
                "prompt_version": "prompts@sha256:test",
                "model": "gpt-4o-mini",
                "model_parameters": {"temperature": 0.2},
            }
            await run_baseline_profiles(**kwargs)
            with self.assertRaisesRegex(FileExistsError, "immutable"):
                await run_baseline_profiles(**kwargs)

    def test_generate_run_id_returns_unique_value(self) -> None:
        first = generate_run_id()
        second = generate_run_id()
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("career-test-run-"))


class RetryBehaviorGenerator:
    def __init__(self, *, fail_once: bool, retryable_message: str) -> None:
        self.fail_once = fail_once
        self.retryable_message = retryable_message
        self.calls = 0

    async def generate(self, input_profile: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise TimeoutError(self.retryable_message)
        return {
            "career_decision": {"recommended_main_path": "Operations Specialist"},
            "career_recommendations": [{"title": "Operations Specialist"}],
            "route_evidence_blocks": [
                {
                    "route": "Operations Specialist",
                    "income_role": "primary",
                    "why_it_fits": ["релевантный опыт"],
                    "evidence_from_user": ["операционный опыт"],
                    "missing_competencies": [],
                    "entry_level": "transition",
                    "risks": ["конкуренция"],
                    "what_may_disprove_this_route": ["изменится доступ к рынку"],
                }
            ],
            "facts_only": {
                "explicit_facts": ["операционный опыт"],
                "resume_facts": [],
                "inferences": [],
                "unknowns": ["уровень языка"],
                "contradictions": [],
            },
        }


class BaselineRunnerRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_retries_only_technical_errors_and_logs_retry(self) -> None:
        generator = RetryBehaviorGenerator(fail_once=True, retryable_message="timeout while calling model")
        evaluator = BaselineCareerEvaluator()

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            inputs_dir = base_dir / "inputs"
            expected_dir = base_dir / "expected"
            results_dir = base_dir / "results"
            inputs_dir.mkdir()
            expected_dir.mkdir()
            (inputs_dir / "profile_1.json").write_text(
                json.dumps(_input_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (expected_dir / "profile_1.json").write_text(
                json.dumps(_expected_payload("profile_1", "Operations Specialist"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            await run_baseline_profiles(
                generator=generator,
                evaluator=evaluator,
                inputs_dir=inputs_dir,
                expected_dir=expected_dir,
                results_dir=results_dir,
                baseline_lock_path=BASELINE_LOCK_PATH,
                required_profile_count=1,
                run_id="retry_run",
                application_version="app-v1",
                git_commit="commit-123",
                prompt_version="prompts@sha256:test",
                model="gpt-4o-mini",
                model_parameters={"temperature": 0.2},
            )

            raw_payload = json.loads((results_dir / "retry_run" / "raw_responses" / "profile_1.raw.json").read_text(encoding="utf-8"))
            self.assertEqual(generator.calls, 2)
            self.assertGreaterEqual(len(raw_payload.get("retry_log") or []), 2)


if __name__ == "__main__":
    unittest.main()
