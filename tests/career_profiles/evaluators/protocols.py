from __future__ import annotations

from typing import Any, Protocol


class CareerGeneratorProtocol(Protocol):
    async def generate(
        self,
        input_profile: dict[str, Any],
        runtime_context: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class CareerEvaluatorProtocol(Protocol):
    async def evaluate(
        self,
        input_profile: dict[str, Any],
        generated_result: dict[str, Any],
        expected_profile: dict[str, Any],
    ) -> dict[str, Any]:
        ...