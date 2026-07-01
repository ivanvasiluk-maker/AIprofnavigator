import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.career import _build_and_send_report
from handlers.start import recover_without_fsm_state
from states import CareerFlow


class FakeState:
    def __init__(self, data: dict | None = None, current_state: str | None = None) -> None:
        self.data = dict(data or {})
        self.current_state = current_state

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = state.state if hasattr(state, "state") else state

    async def get_state(self) -> str | None:
        return self.current_state


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.answer = AsyncMock()
        self.from_user = SimpleNamespace(id=123456, first_name="Ivan", last_name="V")
        self.chat = SimpleNamespace(id=123456)


class RecoveryIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_generation_reuses_existing_by_idempotency_key(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "report_generation_id": "rid-123",
            },
            current_state=CareerFlow.waiting_for_answers.state,
        )
        message = FakeMessage()
        stored_report = {
            "digital_human": {"current_state": "Переходный этап"},
            "career_decision": {"recommended_main_path": "Administrative Assistant"},
            "action_plan": {"today": {"action": "Открыть 5 вакансий"}},
        }

        with patch("handlers.career.get_report_by_generation_id", return_value={"report": stored_report}):
            with patch("handlers.career.report_chunks", return_value={"summary": "ok"}):
                with patch("handlers.career._track_event", new=AsyncMock()) as track_event:
                    with patch("handlers.career._present_route_selection", new=AsyncMock()) as present:
                        await _build_and_send_report(message, state, "ru")

        self.assertTrue(state.data.get("final_report_generated"))
        self.assertEqual(state.data.get("report_generation_id"), "rid-123")
        self.assertEqual(state.data.get("final_report"), stored_report)
        track_event.assert_awaited_once()
        present.assert_awaited_once()

    async def test_recovery_restores_final_ready_state_from_sqlite_bundle(self) -> None:
        state = FakeState(data={}, current_state=None)
        message = FakeMessage(text="продолжить")

        bundle = {
            "session": {
                "session_id": "sess-1",
                "state_name": "FINAL_READY",
                "user_mode": "calm_steps",
                "language": "ru",
            },
            "profile": {
                "profile": {
                    "language": "ru",
                    "user_mode": "calm_steps",
                    "support_level": "medium",
                    "support_need": "medium",
                    "pace": "normal",
                    "detail_preference": "balanced",
                }
            },
            "report": {
                "report_generation_id": "rid-xyz",
                "html_report_path": "reports/r1.html",
                "pdf_report_path": "reports/r1.pdf",
                "report": {
                    "digital_human": {"current_state": "Профиль"},
                    "career_decision": {"recommended_main_path": "Administrative Assistant"},
                },
            },
        }

        with patch("handlers.start.ensure_public_user_id", return_value="pub-1"):
            with patch("handlers.start.load_recovery_bundle", return_value=bundle):
                await recover_without_fsm_state(message, state)

        self.assertEqual(state.current_state, CareerFlow.FINAL_READY.state)
        self.assertTrue(state.data.get("final_report_generated"))
        self.assertEqual(state.data.get("report_generation_id"), "rid-xyz")
        self.assertEqual(state.data.get("html_report_path"), "reports/r1.html")
        self.assertEqual(state.data.get("pdf_report_path"), "reports/r1.pdf")
        message.answer.assert_awaited()


if __name__ == "__main__":
    unittest.main()
