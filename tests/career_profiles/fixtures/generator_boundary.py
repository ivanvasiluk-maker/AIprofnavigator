from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from openai_client import CareerOpenAIClient


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


class OpenAICareerGenerator:
    def __init__(self, client: CareerOpenAIClient) -> None:
        self._client = client

    async def generate(
        self,
        input_profile: dict[str, Any],
        runtime_context: dict[str, Any],
    ) -> dict[str, Any]:
        payload = build_generation_payload(input_profile, runtime_context)
        return await self._client.build_report(**payload)