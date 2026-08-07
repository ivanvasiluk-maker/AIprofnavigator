from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tests.career_profiles.evaluators.protocols import CareerGeneratorProtocol
from tests.career_profiles.fixtures.generator_boundary import assert_no_generator_leakage


@dataclass(slots=True)
class CareerTestInput:
    profile_id: str
    payload: dict[str, Any]


@dataclass(slots=True)
class RunContext:
    run_id: str
    profile_id: str
    runtime_context: dict[str, Any]


@dataclass(slots=True)
class GeneratedCareerResult:
    generated_result: dict[str, Any]
    conversation_trace: dict[str, Any]


class CareerAnalysisAdapter:
    def __init__(self, generator: CareerGeneratorProtocol) -> None:
        self._generator = generator

    async def run_profile(
        self,
        profile: CareerTestInput,
        run_context: RunContext,
    ) -> GeneratedCareerResult:
        input_profile = dict(profile.payload)
        runtime_context = dict(run_context.runtime_context)

        assert_no_generator_leakage(input_profile, "input_profile")
        assert_no_generator_leakage(runtime_context, "runtime_context")

        generated_result = await self._generator.generate(input_profile, runtime_context)

        # Trace fields are kept in artifacts to support conversational baseline debugging.
        conversation_trace = {
            "conversation_turns": list(input_profile.get("conversation_turns") or []),
            "questions_asked": list(input_profile.get("questions_asked") or []),
            "question_signatures": list(input_profile.get("question_signatures") or []),
            "evidence_profile_snapshots": list(input_profile.get("evidence_profile_snapshots") or []),
            "readiness_transitions": list(input_profile.get("readiness_transitions") or []),
            "preliminary_result": input_profile.get("preliminary_result"),
            "final_result": generated_result,
        }
        return GeneratedCareerResult(
            generated_result=generated_result,
            conversation_trace=conversation_trace,
        )
