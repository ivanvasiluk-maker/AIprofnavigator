from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from openai_client import CareerOpenAIClient
from services.career_assessment import build_deterministic_assessment
from services.report_snapshot import build_generator_snapshot, build_report_snapshot


TEST_DATA_LEAKAGE = "TEST_DATA_LEAKAGE"

FORBIDDEN_GENERATOR_FIELDS = {
    "expected_result",
    "expected_routes",
    "forbidden_recommendations",
    "critical_errors",
    "expected_professional_core",
    "expected_seniority",
    "evaluation_score",
}


class GeneratorDataLeakageError(RuntimeError):
    def __init__(self, field_path: str) -> None:
        self.code = TEST_DATA_LEAKAGE
        self.field_path = field_path
        super().__init__(f"{TEST_DATA_LEAKAGE}: forbidden field leaked into generator payload at {field_path}")


def assert_no_generator_leakage(payload: Any, path: str = "payload") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in FORBIDDEN_GENERATOR_FIELDS:
                raise GeneratorDataLeakageError(child_path)
            assert_no_generator_leakage(value, child_path)
        return

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for index, item in enumerate(payload):
            assert_no_generator_leakage(item, f"{path}[{index}]")


def build_generation_payload(
    input_profile: dict[str, Any],
    runtime_context: dict[str, Any],
) -> dict[str, Any]:
    assert_no_generator_leakage(input_profile, "input_profile")
    assert_no_generator_leakage(runtime_context, "runtime_context")

    return {
        "story": str(input_profile.get("story") or ""),
        "story_analysis": dict(input_profile.get("story_analysis") or {}),
        "answers": str(input_profile.get("answers") or ""),
        "decision_layers": dict(runtime_context.get("decision_layers") or {}),
        "resume_analysis": dict(input_profile.get("resume_analysis") or {}),
        "selected_barriers": list(runtime_context.get("selected_barriers") or []),
        "selected_fears": list(runtime_context.get("selected_fears") or []),
        "selected_psych_markers": list(runtime_context.get("selected_psych_markers") or []),
        "selected_energy_sources": list(runtime_context.get("selected_energy_sources") or []),
        "selected_career_priorities": list(runtime_context.get("selected_career_priorities") or []),
        "user_segment": str(runtime_context.get("user_segment") or ""),
        "user_segment_label": str(runtime_context.get("user_segment_label") or ""),
        "language": str(runtime_context.get("language") or input_profile.get("language") or "ru"),
    }


def build_active_pipeline_payload(
    input_profile: dict[str, Any],
    runtime_context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Translate one independent fixture into the active production contract."""
    assert_no_generator_leakage(input_profile, "input_profile")
    assert_no_generator_leakage(runtime_context, "runtime_context")
    assessment_id = str(input_profile.get("profile_id") or runtime_context.get("profile_id") or "").strip()
    data = {
        **input_profile,
        "assessment_id": assessment_id,
        "profile_version": str(runtime_context.get("profile_version") or "baseline-v1"),
        "public_user_id": f"baseline-{assessment_id}",
        "story_text": str(input_profile.get("story") or ""),
        "answers_text": str(input_profile.get("answers") or ""),
        "user_mode": str(runtime_context.get("user_mode") or "deep"),
        "selected_barriers": list(runtime_context.get("selected_barriers") or []),
        "selected_fears": list(runtime_context.get("selected_fears") or []),
        "selected_psych_markers": list(runtime_context.get("selected_psych_markers") or []),
        "selected_energy_sources": list(runtime_context.get("selected_energy_sources") or []),
        "selected_career_priorities": list(runtime_context.get("selected_career_priorities") or []),
    }
    report_snapshot = build_report_snapshot(data)
    generator_snapshot = build_generator_snapshot(report_snapshot)
    return generator_snapshot, dict(input_profile.get("story_analysis") or {}), dict(input_profile.get("resume_analysis") or {})


class OpenAICareerGenerator:
    def __init__(self, client: CareerOpenAIClient) -> None:
        self._client = client

    async def generate(
        self,
        input_profile: dict[str, Any],
        runtime_context: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot, story_analysis, resume_analysis = build_active_pipeline_payload(input_profile, runtime_context)
        assessment = await self._client.build_career_assessment(
            snapshot,
            assessment_id=str(snapshot["assessment_id"]),
            session_id=str(runtime_context.get("run_id") or "baseline"),
            profile_version=str(snapshot["profile_version"]),
            story_analysis=story_analysis,
            resume_analysis=resume_analysis,
            language=str(runtime_context.get("language") or input_profile.get("language") or "ru"),
        )
        return assessment.to_dict()


class DeterministicCareerGenerator:
    """Reproducible CI generator for the active production fallback path."""

    async def generate(
        self,
        input_profile: dict[str, Any],
        runtime_context: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot, story_analysis, resume_analysis = build_active_pipeline_payload(input_profile, runtime_context)
        assessment = build_deterministic_assessment(
            snapshot,
            story_analysis,
            resume_analysis,
            assessment_id=str(snapshot["assessment_id"]),
            session_id=str(runtime_context.get("run_id") or "baseline"),
            profile_version=str(snapshot["profile_version"]),
            fallback_reason="baseline_active_pipeline",
        )
        return assessment.to_dict()
