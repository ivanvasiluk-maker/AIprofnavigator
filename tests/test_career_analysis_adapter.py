from __future__ import annotations

import unittest

from tests.career_profiles.fixtures.career_analysis_adapter import CareerAnalysisAdapter, CareerTestInput, RunContext


class _FakeGenerator:
    async def generate(self, input_profile, runtime_context):
        return {
            "career_decision": {
                "recommended_main_path": input_profile.get("story_analysis", {}).get("preferred_route", "Operations Specialist")
            }
        }


class CareerAnalysisAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_runs_profile_and_returns_trace(self) -> None:
        adapter = CareerAnalysisAdapter(_FakeGenerator())
        profile = CareerTestInput(
            profile_id="profile_1",
            payload={
                "profile_id": "profile_1",
                "story": "История",
                "story_analysis": {"preferred_route": "Route A"},
                "answers": "Ответ",
                "conversation_turns": [{"role": "user", "text": "История"}],
            },
        )
        context = RunContext(
            run_id="run-1",
            profile_id="profile_1",
            runtime_context={"language": "ru"},
        )

        result = await adapter.run_profile(profile, context)
        self.assertEqual(result.generated_result["career_decision"]["recommended_main_path"], "Route A")
        self.assertEqual(result.conversation_trace["conversation_turns"][0]["role"], "user")
        self.assertIn("final_result", result.conversation_trace)


if __name__ == "__main__":
    unittest.main()
