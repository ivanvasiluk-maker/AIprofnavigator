import asyncio
from unittest.mock import AsyncMock, patch

from bot import SessionCheckpointMiddleware


class FakeState:
    async def get_state(self):
        return "CareerFlow:INTERVIEW"

    async def get_data(self):
        return {
            "session_id": "session-1",
            "public_user_id": "user-1",
            "question_count": 3,
            "interview_context": {"current_question_id": "q-current"},
            "asked_question_signatures": ["signature-1"],
            "active_canonical_question": {"question_id": "canonical-current"},
            "question_state": {"question_count": 3},
            "route_context": {"country": "Lithuania"},
            "route_context_index": 2,
            "route_context_question_id": "route-current",
        }


def test_checkpoint_persists_active_question_identity_and_progress():
    asyncio.run(_checkpoint_persists_active_question_identity_and_progress())


async def _checkpoint_persists_active_question_identity_and_progress():
    handler = AsyncMock(return_value="handled")
    middleware = SessionCheckpointMiddleware()

    with patch("bot.touch_session"), patch("bot.save_profile_version") as save_profile:
        result = await middleware(handler, object(), {"state": FakeState()})

    assert result == "handled"
    checkpoint = save_profile.call_args.args[2]
    assert checkpoint["question_count"] == 3
    assert checkpoint["interview_context"]["current_question_id"] == "q-current"
    assert checkpoint["asked_question_signatures"] == ["signature-1"]
    assert checkpoint["active_canonical_question"]["question_id"] == "canonical-current"
    assert checkpoint["question_state"]["question_count"] == 3
    assert checkpoint["route_context_index"] == 2
    assert checkpoint["route_context_question_id"] == "route-current"
