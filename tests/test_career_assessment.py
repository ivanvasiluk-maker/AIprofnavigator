from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from config import settings
from handlers.career import _build_and_send_career_assessment
from keyboards import first_step_selection_keyboard
from openai_client import CareerOpenAIClient
from services.career_assessment import (
    CAREER_ASSESSMENT_SCHEMA,
    build_preliminary_assessment,
    career_assessment_from_dict,
    render_assessment_html,
    render_first_step_instruction,
    render_route_comparison,
    render_telegram_map,
    validate_career_assessment,
)
from services.runtime_isolation import assert_expected_profiles_not_loaded
from tests.career_profiles.evaluators.assessment_evaluator import evaluate_career_assessment
from utils.reporting import generate_assessment_html_file


def profile_10_assessment_payload() -> dict:
    evidence = [
        {"evidence_id": "e1", "fact": "Восемь лет в IT-маркетинге", "source_type": "history", "source_reference": "story:1"},
        {"evidence_id": "e2", "fact": "Исследовал рынок и клиентов для запусков", "source_type": "resume", "source_reference": "resume:experience"},
        {"evidence_id": "e3", "fact": "Управлял маркетинговой командой", "source_type": "resume", "source_reference": "resume:leadership"},
        {"evidence_id": "e4", "fact": "Создавал курсы и вебинары", "source_type": "answer", "source_reference": "answer:education"},
    ]
    def route(route_id: str, title: str, category: str, evidence_ids: list[str]) -> dict:
        return {
            "route_id": route_id,
            "title": title,
            "category": category,
            "why_it_fits": "Сохраняет исследовательские, стратегические и маркетинговые функции.",
            "evidence_ids": evidence_ids,
            "preserves": ["исследование рынка", "позиционирование"],
            "risks": ["нужно проверить продуктовую ответственность"],
            "missing": ["продуктовый кейс"],
            "entry_level": "Senior в Product Marketing; отдельно оценить уровень в Product Management",
            "disconfirming_conditions": ["роль требует неподтверждённого владения продуктовой разработкой"],
            "market_test": "Сравнить требования десяти вакансий и получить обратную связь по одному кейсу.",
        }
    return {
        "assessment_id": "assessment-profile-10",
        "session_id": "session-profile-10",
        "profile_version": "1",
        "status": "full",
        "context": {"country_code": "LT", "country_name": "Литва", "city": "Вильнюс", "income_target": {"amount": 3000, "currency": "EUR", "period": "month"}},
        "identity": {
            "professional_core": ["Руководитель IT-маркетинга", "Product Marketing Specialist", "Специалист по исследованию рынка и клиентов"],
            "core_description": "Превращает исследования в позиционирование, стратегию запуска и координацию реализации.",
            "secondary_functions": ["Product Discovery", "Позиционирование продукта", "Образовательный контент", "Управление командой"],
            "seniority_current": "Senior / lead в маркетинге",
            "seniority_transition": "В Product Management оценивается отдельно",
            "seniority_notes": "Уровень преимущественно сохраняется в Product Marketing.",
            "professional_capital": ["восемь лет опыта", "подтверждённые запуски"],
            "transferable_functions": ["исследования", "позиционирование", "координация"],
        },
        "evidence": evidence,
        "user_choice": {"desired_change": "более осмысленная продуктовая роль", "preferred_directions": ["продукт", "образование"], "functions_to_preserve": ["исследования", "стратегию"], "functions_to_avoid": ["чистое продвижение"], "priorities": ["сохранить доход", "не обнулять опыт"], "acceptable_income_drop": "требует уточнения"},
        "constraints": [{"title": "Допустимое снижение дохода не определено", "impact": "Ограничивает выбор уровня входа.", "evidence_ids": ["e1"], "confirmed": True}],
        "routes": {
            "primary_routes": [route("pm-marketing", "Product Marketing Manager", "primary", ["e1", "e2"]), route("discovery", "Product Discovery / Customer Insights", "primary", ["e1", "e2"])],
            "transition_routes": [route("product-manager", "Product Manager через продуктовые кейсы", "transition", ["e2", "e3"]), route("edtech", "EdTech Product или Program Manager", "transition", ["e2", "e4"])],
            "quick_income_routes": [route("consulting", "Маркетинговый или продуктовый консалтинг", "quick_income", ["e1", "e2"])],
            "emergency_routes": [],
            "recommended_route_id": "pm-marketing",
            "alternative_route_ids": ["discovery", "edtech"],
        },
        "questions": {"answered_critical_questions": ["Какие функции сохранить"], "unanswered_critical_questions": ["Какое снижение дохода допустимо?", "Локальный или международный рынок?"], "optional_questions": []},
        "conclusions": {
            "mandatory_conclusions": ["Пользователь умеет превращать исследования в продуктовые и маркетинговые решения", "Безопасный переход не требует обнуления профессионального капитала", "Product Marketing и Product Discovery нужно проверить раньше полной смены сферы"],
            "main_conclusion": "Основной маршрут — Product Marketing Manager: он сохраняет senior-уровень, аналитические функции и доходный потенциал.",
            "what_may_change_conclusion": ["неподходящая продуктовая ответственность", "недопустимое снижение дохода"],
            "forbidden_recommendations_checked": ["административная работа", "психолог без квалификации"],
            "critical_errors_detected": [],
        },
        "first_steps": [
            {"step_id": "clarify", "title": "Быстрое прояснение", "purpose": "Отделить желаемые функции от условий текущей работы.", "action": "Выпишите три функции, которые хотите сохранить, и три, от которых хотите отказаться.", "expected_result": "Два списка по три функции.", "duration_minutes": 15, "related_route_id": "pm-marketing", "type": "quick_action"},
            {"step_id": "market", "title": "Проверка рынка", "purpose": "Сравнить три смежных направления.", "action": "Найдите по пять вакансий Product Marketing, Product Discovery и EdTech Product и отметьте повторяющиеся требования.", "expected_result": "Таблица требований по трём направлениям.", "duration_minutes": 45, "related_route_id": "pm-marketing", "type": "market_research"},
            {"step_id": "case", "title": "Портфолио", "purpose": "Показать продуктовую часть опыта.", "action": "Опишите один запуск: проблема, исследование, позиционирование, действия и результат.", "expected_result": "Один проверяемый продуктово-маркетинговый кейс.", "duration_minutes": 60, "related_route_id": "pm-marketing", "type": "portfolio"},
            {"step_id": "contact", "title": "Профессиональный контакт", "purpose": "Проверить кейс у специалиста.", "action": "Отправьте кейс одному Product Marketing Manager и попросите назвать один сильный и один слабый элемент.", "expected_result": "Одна предметная обратная связь.", "duration_minutes": 20, "related_route_id": "pm-marketing", "type": "networking"},
        ],
    }


class CareerAssessmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assessment = career_assessment_from_dict(profile_10_assessment_payload())

    def test_profile_10_is_valid(self) -> None:
        result = validate_career_assessment(self.assessment, snapshot_country_code="LT", snapshot_currency="EUR")
        self.assertTrue(result.is_valid, result.errors)

    def test_all_renderers_use_same_assessment(self) -> None:
        telegram = render_telegram_map(self.assessment)
        comparison = render_route_comparison(self.assessment)
        html = render_assessment_html(self.assessment)
        self.assertIn("Product Marketing Manager", telegram)
        self.assertIn("Product Marketing Manager", comparison)
        self.assertIn("assessment-profile-10", html)
        self.assertNotIn("SWOT", html)
        self.assertNotIn("Подробный анализ по 15 блокам", html)

    def test_select_one_step_keeps_other_options(self) -> None:
        instruction = render_first_step_instruction(self.assessment, "market")
        self.assertIn("45 минут", instruction)
        self.assertEqual(self.assessment.selected_first_step_id, "market")
        self.assertEqual(len(self.assessment.first_steps), 4)

    def test_html_filename_and_content_use_same_assessment_id(self) -> None:
        with TemporaryDirectory() as output_dir:
            path = generate_assessment_html_file(self.assessment, output_dir)
            self.assertIn(self.assessment.assessment_id, path.name)
            self.assertIn(self.assessment.assessment_id, path.read_text(encoding="utf-8"))

    def test_callback_contract_contains_assessment_and_step_ids(self) -> None:
        keyboard = first_step_selection_keyboard(self.assessment)
        callback_values = [row[0].callback_data for row in keyboard.inline_keyboard]
        self.assertEqual(
            callback_values[0],
            "select_first_step:assessment-profile-10:clarify",
        )
        self.assertTrue(all(value and len(value.encode("utf-8")) <= 64 for value in callback_values))

    def test_legacy_report_is_disabled_by_default(self) -> None:
        self.assertFalse(settings.legacy_career_report_enabled)

    def test_profile_10_golden_score_passes_without_critical_errors(self) -> None:
        golden_path = Path(__file__).parent / "career_profiles" / "expected" / "profile_10_it_marketing_transition_expected.json"
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        result = evaluate_career_assessment(self.assessment.to_dict(), golden)
        self.assertGreaterEqual(result["score"], 80, result)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["critical_errors"], [])
        self.assertTrue(result["first_steps_valid"])

    def test_evaluator_allows_own_justified_routes_and_extra_conclusions(self) -> None:
        payload = self.assessment.to_dict()
        payload["routes"]["primary_routes"][0]["title"] = "Стратегия продукта и выхода на рынок"
        payload["conclusions"]["mandatory_conclusions"].append(
            "Собственный дополнительный вывод, основанный на фактах пользователя"
        )
        golden_path = Path(__file__).parent / "career_profiles" / "expected" / "profile_10_it_marketing_transition_expected.json"
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        result = evaluate_career_assessment(payload, golden)
        self.assertGreaterEqual(result["score"], 80, result)
        self.assertTrue(result["passed"], result)

    def test_reference_library_contains_ten_complete_quality_orientations(self) -> None:
        expected_dir = Path(__file__).parent / "career_profiles" / "expected"
        references = [json.loads(path.read_text(encoding="utf-8")) for path in expected_dir.glob("*.json")]
        self.assertEqual(len(references), 10)
        self.assertEqual(len({item.get("profile_id") or item.get("id") for item in references}), 10)
        required_sections = {
            "professional_core",
            "secondary_functions",
            "seniority",
            "primary_routes",
            "transition_routes",
            "quick_income",
            "emergency_routes",
            "required_questions",
            "forbidden_recommendations",
            "mandatory_conclusions",
            "critical_errors",
            "logic_rules",
        }
        for reference in references:
            expected = reference.get("expected") or reference
            self.assertTrue(required_sections <= set(expected), reference.get("id"))
            self.assertTrue(expected["professional_core"], reference.get("id"))
            self.assertTrue(expected["primary_routes"], reference.get("id"))
            self.assertTrue(expected["mandatory_conclusions"], reference.get("id"))
            self.assertTrue(expected["logic_rules"], reference.get("id"))

    def test_invalid_full_build_can_fall_back_to_valid_preliminary_map(self) -> None:
        preliminary = build_preliminary_assessment(
            {
                "country_code": "LT",
                "country_name": "Литва",
                "city": "Вильнюс",
                "currency": "EUR",
                "story_text": "Восемь лет в IT-маркетинге и исследованиях рынка.",
                "career_goal": "Перейти ближе к продукту",
            },
            {
                "professional_core_hypotheses": ["IT-маркетинг"],
                "seniority_hypotheses": ["Senior в маркетинге"],
                "facts_extracted": ["Восемь лет опыта", "Исследовал рынок и клиентов"],
            },
            assessment_id="preliminary-10",
            session_id="session-10",
            profile_version="1",
        )
        result = validate_career_assessment(preliminary, snapshot_country_code="LT", snapshot_currency="EUR")
        self.assertTrue(result.is_valid, result.errors)
        self.assertEqual(preliminary.status, "preliminary")
        self.assertIn("IT-маркетинг", render_telegram_map(preliminary))

    def test_schema_is_strict_and_requires_all_top_level_fields(self) -> None:
        self.assertFalse(CAREER_ASSESSMENT_SCHEMA["additionalProperties"])
        self.assertEqual(
            set(CAREER_ASSESSMENT_SCHEMA["properties"]),
            set(CAREER_ASSESSMENT_SCHEMA["required"]),
        )


class CareerAssessmentBuildTest(unittest.IsolatedAsyncioTestCase):
    async def test_build_uses_exactly_one_structured_call(self) -> None:
        client = CareerOpenAIClient(api_key="test", model="test", transcribe_model="test")
        payload = profile_10_assessment_payload()
        client._run_json = AsyncMock(return_value=payload)  # type: ignore[method-assign]
        assessment = await client.build_career_assessment(
            {"country_code": "LT", "currency": "EUR"},
            assessment_id="assessment-profile-10",
            session_id="session-profile-10",
            profile_version="1",
        )
        self.assertEqual(assessment.assessment_id, "assessment-profile-10")
        client._run_json.assert_awaited_once()

    async def test_existing_assessment_is_reused_without_ai_call(self) -> None:
        class State:
            def __init__(self, payload: dict) -> None:
                self.data = {"career_assessment": payload}
                self.current_state = None

            async def update_data(self, **kwargs) -> None:
                self.data.update(kwargs)

            async def set_state(self, value) -> None:
                self.current_state = value

        state = State(profile_10_assessment_payload())
        message = type(
            "MessageStub",
            (),
            {
                "answer": AsyncMock(),
                "answer_document": AsyncMock(),
            },
        )()
        with unittest.mock.patch("handlers.career.ai_client.build_career_assessment", new=AsyncMock()) as build:
            with unittest.mock.patch("handlers.career._track_event", new=AsyncMock()):
                await _build_and_send_career_assessment(message, state, "ru", state.data)
        build.assert_not_awaited()
        self.assertEqual(state.data["report_generation_status"], "ASSESSMENT_REUSED")
        self.assertTrue(state.data["final_report_generated"])


class RuntimeIsolationTest(unittest.TestCase):
    def test_production_rejects_expected_profile_data(self) -> None:
        with self.assertRaises(AssertionError):
            assert_expected_profiles_not_loaded(
                "production",
                {"story": "Опыт в маркетинге", "expected_routes": ["Product Marketing"]},
            )

    def test_production_accepts_runtime_snapshot(self) -> None:
        assert_expected_profiles_not_loaded(
            "production",
            {"story_text": "Опыт в маркетинге", "country_code": "LT", "currency": "EUR"},
        )


if __name__ == "__main__":
    unittest.main()