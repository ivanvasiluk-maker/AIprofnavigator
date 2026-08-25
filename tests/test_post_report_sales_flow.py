from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from handlers.career import handle_post_result_actions
from keyboards import (
    ALL_RESULT_ACTIONS,
    RESULT_AI_PROMPT,
    RESULT_GROUP_EXPLICIT,
    RESULT_HYBRID_SUPPORT,
    RESULT_SELF_EXPLORE,
    RESULT_SPECIALIST_EXPLICIT,
    RESULT_SUPPORT,
    post_report_support_keyboard,
)
from services.career_assessment import build_personal_ai_prompt
from states import CareerFlow


class FakeState:
    def __init__(self, data: dict):
        self.data = dict(data)
        self.state = None

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, value):
        self.state = value


def _result() -> dict:
    return {
        "professional_core": ["анализирует дефекты", "улучшает процесс"],
        "primary_route": {"title": "Quality Engineer"},
        "alternative_routes": [{"title": "Process Improvement Specialist"}],
        "critical_unknowns": ["актуальный диапазон дохода"],
        "first_steps": [{"action": "Сравнить пять актуальных вакансий"}],
    }


def test_sales_keyboard_exposes_every_requested_continuation_and_all_buttons_are_routed() -> None:
    labels = [button.text for row in post_report_support_keyboard().keyboard for button in row]
    required = {
        RESULT_SUPPORT,
        RESULT_SPECIALIST_EXPLICIT,
        RESULT_GROUP_EXPLICIT,
        RESULT_AI_PROMPT,
        RESULT_HYBRID_SUPPORT,
        RESULT_SELF_EXPLORE,
    }
    assert required <= set(labels)
    assert set(labels) <= ALL_RESULT_ACTIONS


def test_personal_prompt_is_fact_bound_and_requires_sources_for_market_claims() -> None:
    prompt = build_personal_ai_prompt(_result())
    assert "Quality Engineer" in prompt
    assert "анализирует дефекты" in prompt
    assert "не придумывай" in prompt
    assert "только с датой и источником" in prompt


class PostReportSalesHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_ai_prompt_button_returns_copy_ready_prompt_and_keeps_menu_alive(self) -> None:
        state = FakeState({
            "language": "ru",
            "final_report_generated": True,
            "validated_assessment_result": _result(),
        })
        message = SimpleNamespace(text=RESULT_AI_PROMPT, answer=AsyncMock())

        with patch("handlers.career._track_event", new=AsyncMock()):
            await handle_post_result_actions(message, state)

        message.answer.assert_awaited_once()
        text = message.answer.await_args.args[0]
        self.assertIn("Скопируйте этот промт", text)
        self.assertIn("Quality Engineer", text)
        self.assertEqual(state.state, CareerFlow.FINAL_READY)

    async def test_support_group_missing_link_is_honest_and_keeps_sales_menu(self) -> None:
        state = FakeState({"language": "ru", "final_report_generated": True})
        message = SimpleNamespace(text=RESULT_GROUP_EXPLICIT, answer=AsyncMock())

        with patch("handlers.career.settings.support_group_telegram_url", ""), patch(
            "handlers.career._track_event", new=AsyncMock()
        ):
            await handle_post_result_actions(message, state)

        self.assertEqual(message.answer.await_count, 2)
        self.assertIn("не настро", message.answer.await_args_list[-1].args[0].casefold())
        self.assertEqual(state.state, CareerFlow.FINAL_READY)

    async def test_support_group_configured_link_uses_inline_button_without_echoing_url(self) -> None:
        state = FakeState({"language": "ru", "final_report_generated": True})
        message = SimpleNamespace(text=RESULT_GROUP_EXPLICIT, answer=AsyncMock())
        url = "https://t.me/example_support"

        with patch("handlers.career.settings.support_group_telegram_url", url), patch(
            "handlers.career._track_event", new=AsyncMock()
        ):
            await handle_post_result_actions(message, state)

        self.assertEqual(message.answer.await_count, 2)
        self.assertNotIn(url, message.answer.await_args_list[-1].args[0])
        markup = message.answer.await_args_list[-1].kwargs["reply_markup"]
        self.assertEqual(markup.inline_keyboard[0][0].url, url)
