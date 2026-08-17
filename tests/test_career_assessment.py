from __future__ import annotations

import copy
import unittest
from unittest.mock import AsyncMock
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from config import settings
from handlers.career import _build_and_send_career_assessment, _build_profile_snapshot
from keyboards import first_step_selection_keyboard, selected_step_actions_keyboard
from openai_client import CareerOpenAIClient
from services.career_assessment import (
    CAREER_ASSESSMENT_SCHEMA,
    CAREER_HTML_RENDERER_VERSION,
    CAREER_PIPELINE_VERSION,
    CAREER_TELEGRAM_RENDERER_VERSION,
    build_preliminary_assessment,
    career_assessment_from_dict,
    render_assessment_html,
    render_first_step_instruction,
    render_route_comparison,
    render_telegram_map,
    validate_career_assessment,
)
from services.runtime_isolation import assert_expected_profiles_not_loaded
from states import CareerFlow
from tests.career_profiles.evaluators.assessment_evaluator import evaluate_career_assessment
from utils.reporting import generate_assessment_html_file


def profile_10_assessment_payload() -> dict:
    evidence = [
        {"evidence_id": "e1", "fact": "Восемь лет в IT-маркетинге", "source_type": "history", "source_reference": "story:1"},
        {"evidence_id": "e2", "fact": "Исследовал рынок и клиентов для запусков", "source_type": "resume", "source_reference": "resume:experience"},
        {"evidence_id": "e3", "fact": "Управлял маркетинговой командой", "source_type": "resume", "source_reference": "resume:leadership"},
        {"evidence_id": "e4", "fact": "Отвечал за маркетинговую стратегию и бюджет", "source_type": "resume", "source_reference": "resume:strategy"},
        {"evidence_id": "e5", "fact": "Проводил интервью с клиентами", "source_type": "resume", "source_reference": "resume:interviews"},
        {"evidence_id": "e6", "fact": "Работал с B2B-продуктами", "source_type": "resume", "source_reference": "resume:b2b"},
        {"evidence_id": "e7", "fact": "Разрабатывал позиционирование продуктов", "source_type": "resume", "source_reference": "resume:positioning"},
        {"evidence_id": "e8", "fact": "Создавал образовательный контент и онлайн-курсы", "source_type": "resume", "source_reference": "resume:education"},
        {"evidence_id": "e9", "fact": "Проводил вебинары", "source_type": "resume", "source_reference": "resume:webinars"},
        {"evidence_id": "e10", "fact": "Увеличил входящие заявки на 35 процентов", "source_type": "resume", "source_reference": "resume:result"},
        {"evidence_id": "e11", "fact": "Прошёл Product Management Fundamentals", "source_type": "resume", "source_reference": "resume:education-product"},
        {"evidence_id": "e12", "fact": "Изучал Customer Development", "source_type": "resume", "source_reference": "resume:education-custdev"},
        {"evidence_id": "e13", "fact": "Английский язык B2", "source_type": "resume", "source_reference": "resume:language"},
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
            {"step_id": "market", "title": "Проверка рынка", "purpose": "Сравнить три смежных направления.", "action": "Найдите пять вакансий Product Marketing Manager и пять вакансий Product Discovery / Customer Insights.", "expected_result": "Таблица требований по двум направлениям.", "duration_minutes": 45, "related_route_id": "pm-marketing", "type": "market_research"},
            {"step_id": "case", "title": "Портфолио", "purpose": "Показать продуктовую часть опыта.", "action": "Опишите один запуск: проблема, исследование, позиционирование, действия и результат.", "expected_result": "Один проверяемый продуктово-маркетинговый кейс.", "duration_minutes": 60, "related_route_id": "pm-marketing", "type": "portfolio"},
            {"step_id": "contact", "title": "Профессиональный контакт", "purpose": "Проверить кейс у специалиста.", "action": "Отправьте кейс одному Product Marketing Manager и попросите назвать один сильный и один слабый элемент.", "expected_result": "Одна предметная обратная связь.", "duration_minutes": 20, "related_route_id": "pm-marketing", "type": "networking"},
            {"step_id": "consulting-test", "title": "Проверка консультирования", "purpose": "Проверить спрос без увольнения.", "action": "Сформулируйте одну услугу для маршрута Маркетинговый или продуктовый консалтинг и предложите её одному потенциальному клиенту.", "expected_result": "Один подтверждающий или опровергающий сигнал спроса.", "duration_minutes": 30, "related_route_id": "consulting", "type": "clarification"},
        ],
    }


def profile_10_e2e_fixture() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "career_assessment_profile_10.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


class CareerAssessmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assessment = career_assessment_from_dict(profile_10_assessment_payload())

    def test_profile_10_is_valid(self) -> None:
        result = validate_career_assessment(self.assessment, snapshot_country_code="LT", snapshot_currency="EUR")
        self.assertTrue(result.is_valid, result.errors)

    def test_validation_returns_structured_codes_and_field_paths(self) -> None:
        payload = profile_10_assessment_payload()
        payload["identity"]["professional_core"] = ["Пользователь имеет опыт в маркетинге и управлении командой."]
        payload["identity"]["seniority_current"] = "средний уровень seniority в маркетинге"
        payload["routes"]["primary_routes"][0]["title"] = "Смежные роли"
        invalid = career_assessment_from_dict(payload)
        result = validate_career_assessment(invalid, snapshot_country_code="LT", snapshot_currency="EUR")
        issues = {issue.code: issue for issue in result.errors}
        self.assertFalse(result.valid)
        self.assertEqual(issues["RAW_USER_SUMMARY_AS_TITLE"].field_path, "identity.professional_core[0]")
        self.assertEqual(issues["INVALID_SENIORITY"].field_path, "identity.seniority_current")
        self.assertEqual(issues["GENERIC_ROUTE_TITLE"].actual_value, "Смежные роли")
        self.assertEqual(invalid.metadata["resume_important_facts_count"], 12)

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
        self.assertEqual(len(self.assessment.first_steps), 5)

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
            "step_callback:assessment-profile-10:0",
        )
        self.assertTrue(all(value and len(value.encode("utf-8")) <= 64 for value in callback_values))
        selected_keyboard = selected_step_actions_keyboard(self.assessment, "clarify")
        self.assertEqual(
            [row[0].text for row in selected_keyboard.inline_keyboard],
            ["Показать другие варианты", "Отметить выполненным", "Сделать проще", "Вернуться к карте"],
        )

    def test_callback_data_stays_valid_with_long_model_step_and_profile_ids(self) -> None:
        self.assessment.profile_version = "profile-version-" + "x" * 80
        self.assessment.first_steps[0].step_id = "model-generated-step-" + "y" * 100
        keyboards = [
            first_step_selection_keyboard(self.assessment),
            selected_step_actions_keyboard(self.assessment, self.assessment.first_steps[0].step_id),
        ]
        callback_values = [button.callback_data for keyboard in keyboards for row in keyboard.inline_keyboard for button in row]
        self.assertTrue(all(value and len(value.encode("utf-8")) <= 64 for value in callback_values), callback_values)

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
    async def test_fixture_runs_snapshot_repair_validation_telegram_and_html_end_to_end(self) -> None:
        fixture = profile_10_e2e_fixture()
        state_data = fixture["state_data"]
        snapshot = _build_profile_snapshot(state_data)
        snapshot_text = json.dumps(snapshot, ensure_ascii=False).casefold()
        for expected_fact in (
            "восемь лет",
            "руководство маркетинговой командой",
            "исследования рынка, клиентов и конкурентов",
            "интервью с клиентами",
            "позиционирование b2b-продуктов",
            "продуктовые запуски",
            "маркетинговая стратегия и бюджет",
            "рост входящих заявок на 35%",
            "образовательного контента и онлайн-курсов",
            "проведение вебинаров",
            "product management fundamentals",
            "customer development",
            "вильнюс",
        ):
            self.assertIn(expected_fact, snapshot_text)
        self.assertEqual(snapshot["answers_text"].count("\n") + 1, 15)
        self.assertEqual(snapshot["country_code"], "LT")
        self.assertTrue(snapshot["resume_analysis"])

        invalid_payload = profile_10_assessment_payload()
        invalid_payload["assessment_id"] = fixture["assessment_id"]
        invalid_payload["session_id"] = fixture["session_id"]
        invalid_payload["profile_version"] = fixture["profile_version"]
        invalid_payload["identity"]["professional_core"] = ["Пользователь имеет опыт в маркетинге."]
        invalid_payload["identity"]["seniority_current"] = "средний"
        invalid_payload["routes"]["primary_routes"][0]["title"] = "Смежные роли"
        valid_payload = profile_10_assessment_payload()
        valid_payload["assessment_id"] = fixture["assessment_id"]
        valid_payload["session_id"] = fixture["session_id"]
        valid_payload["profile_version"] = fixture["profile_version"]

        client = CareerOpenAIClient(api_key="test", model="test", transcribe_model="test")
        client._run_json = AsyncMock(side_effect=[invalid_payload, valid_payload])  # type: ignore[method-assign]
        assessment = await client.build_career_assessment(
            snapshot,
            assessment_id=fixture["assessment_id"],
            session_id=fixture["session_id"],
            profile_version=fixture["profile_version"],
            story_analysis=snapshot["story_analysis"],
            resume_analysis=snapshot["resume_analysis"],
        )

        self.assertIsInstance(assessment, type(career_assessment_from_dict(valid_payload)))
        self.assertEqual(assessment.metadata["raw_model_output"], invalid_payload)
        self.assertEqual(assessment.metadata["parsed_before_repair"]["identity"]["seniority_current"], "средний")
        before_errors = {item["code"] for item in assessment.metadata["validation_before_repair"]["errors"]}
        self.assertTrue({"RAW_USER_SUMMARY_AS_TITLE", "INVALID_SENIORITY", "GENERIC_ROUTE_TITLE"} <= before_errors)
        self.assertTrue(assessment.metadata["repair_started"])
        self.assertEqual(assessment.metadata["recovered_by"], "repair")
        validation = validate_career_assessment(assessment, snapshot_country_code="LT", snapshot_currency="EUR")
        self.assertTrue(validation.valid, validation.errors)
        self.assertEqual(validation.errors, ())

        telegram = render_telegram_map(assessment)
        for forbidden in ("Пользователь имеет опыт", "Смежные роли", "{'", '"route_id"', "\n-\n"):
            self.assertNotIn(forbidden, telegram)
        with TemporaryDirectory() as output_dir:
            html_path = generate_assessment_html_file(assessment, output_dir)
            html = html_path.read_text(encoding="utf-8")
            self.assertTrue(html_path.is_file())
            self.assertIn(assessment.assessment_id, html_path.name)
            self.assertIn(assessment.assessment_id, html)
            self.assertIn(CAREER_HTML_RENDERER_VERSION, html)

    async def test_fixture_two_failed_repairs_fall_back_and_create_html(self) -> None:
        fixture = profile_10_e2e_fixture()
        snapshot = _build_profile_snapshot(fixture["state_data"])
        invalid_payload = profile_10_assessment_payload()
        invalid_payload["assessment_id"] = fixture["assessment_id"]
        invalid_payload["session_id"] = fixture["session_id"]
        invalid_payload["profile_version"] = fixture["profile_version"]
        invalid_payload["identity"]["professional_core"] = ["Пользователь имеет опыт в маркетинге."]
        invalid_payload["routes"]["primary_routes"][0]["route_id"] = ""
        invalid_payload["routes"]["primary_routes"][0]["title"] = "-"
        invalid_payload["conclusions"]["main_conclusion"] = ""

        client = CareerOpenAIClient(api_key="test", model="test", transcribe_model="test")
        client._run_json = AsyncMock(side_effect=[copy.deepcopy(invalid_payload) for _ in range(3)])  # type: ignore[method-assign]
        assessment = await client.build_career_assessment(
            snapshot,
            assessment_id=fixture["assessment_id"],
            session_id=fixture["session_id"],
            profile_version=fixture["profile_version"],
            story_analysis=snapshot["story_analysis"],
            resume_analysis=snapshot["resume_analysis"],
        )
        validation = validate_career_assessment(assessment, snapshot_country_code="LT", snapshot_currency="EUR")
        self.assertTrue(validation.valid, validation.errors)
        self.assertEqual(assessment.metadata["recovered_by"], "deterministic_fallback")
        self.assertEqual(client._run_json.await_count, 3)
        self.assertEqual(assessment.identity.professional_core[:3], [
            "Руководитель IT-маркетинга",
            "Product Marketing Specialist",
            "Специалист по исследованию рынка и клиентов",
        ])
        self.assertEqual(assessment.routes.primary_routes[0].title, "Product Marketing Manager")
        self.assertEqual(assessment.routes.primary_routes[1].title, "Product Discovery / Customer Insights")
        with TemporaryDirectory() as output_dir:
            html_path = generate_assessment_html_file(assessment, output_dir)
            self.assertTrue(html_path.is_file())
            self.assertIn(assessment.assessment_id, html_path.read_text(encoding="utf-8"))

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

    async def test_invalid_assessment_is_repaired_and_diagnostics_are_preserved(self) -> None:
        client = CareerOpenAIClient(api_key="test", model="test", transcribe_model="test")
        invalid_payload = profile_10_assessment_payload()
        invalid_payload["identity"]["professional_core"] = ["Пользователь имеет опыт в маркетинге."]
        valid_payload = profile_10_assessment_payload()
        client._run_json = AsyncMock(side_effect=[invalid_payload, valid_payload])  # type: ignore[method-assign]
        assessment = await client.build_career_assessment(
            {"country_code": "LT", "currency": "EUR"},
            assessment_id="assessment-profile-10",
            session_id="session-profile-10",
            profile_version="1",
        )
        self.assertEqual(client._run_json.await_count, 2)
        self.assertEqual(assessment.metadata["recovered_by"], "repair")
        self.assertEqual(assessment.metadata["successful_repair_attempt"], 1)
        self.assertEqual(
            assessment.metadata["validation_before_repair"]["errors"][0]["code"],
            "RAW_USER_SUMMARY_AS_TITLE",
        )
        self.assertTrue(assessment.metadata["repair_attempts"][0]["validation"]["valid"])

    async def test_two_failed_repairs_use_fact_only_deterministic_fallback(self) -> None:
        client = CareerOpenAIClient(api_key="test", model="test", transcribe_model="test")
        invalid_payload = profile_10_assessment_payload()
        invalid_payload["identity"]["professional_core"] = ["Пользователь имеет опыт в маркетинге."]
        invalid_payload["routes"]["primary_routes"][0]["title"] = "Смежные роли"
        client._run_json = AsyncMock(side_effect=[invalid_payload, invalid_payload, invalid_payload])  # type: ignore[method-assign]
        resume_analysis = {
            "tasks": [
                "8 лет в IT-маркетинге; руководитель отдела и управлял командой",
                "маркетинговая стратегия и бюджет",
                "исследования рынка, клиентов и конкурентов; интервью с клиентами",
                "B2B-продукты и позиционирование",
                "образовательный контент, онлайн-курсы и вебинары",
            ],
            "achievements": ["рост входящих заявок на 35 процентов"],
            "education": ["Product Management Fundamentals", "Customer Development"],
            "languages": ["английский B2"],
        }
        assessment = await client.build_career_assessment(
            {
                "country_code": "LT",
                "country_name": "Литва",
                "currency": "EUR",
                "career_goal": "Остаться в текущей профессии",
                "story_text": "Рассматриваю продукт, образование и консультирование без увольнения.",
            },
            assessment_id="assessment-profile-10",
            session_id="session-profile-10",
            profile_version="1",
            resume_analysis=resume_analysis,
        )
        validation = validate_career_assessment(assessment, snapshot_country_code="LT", snapshot_currency="EUR")
        self.assertTrue(validation.valid, validation.errors)
        self.assertEqual(client._run_json.await_count, 3)
        self.assertEqual(assessment.metadata["recovered_by"], "deterministic_fallback")
        self.assertGreaterEqual(assessment.metadata["resume_important_facts_count"], 8)
        self.assertEqual(assessment.identity.seniority_current, "Senior/lead в маркетинге")
        self.assertEqual(
            set(assessment.metadata["seniority_reason_codes"]),
            {"years_experience_8", "team_leadership", "strategy_ownership", "budget_responsibility", "measurable_result_35_percent"},
        )
        self.assertEqual(assessment.routes.by_id(assessment.routes.recommended_route_id).title, "Product Marketing Manager")
        self.assertEqual(len(assessment.first_steps), 5)
        self.assertIn("сохранить маркетинговый опыт", assessment.questions.unanswered_critical_questions[0])

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
        with TemporaryDirectory() as output_dir:
            html_path = Path(output_dir) / "career_assessment_assessment-profile-10.html"
            html_path.write_text(render_assessment_html(career_assessment_from_dict(profile_10_assessment_payload())), encoding="utf-8")
            with unittest.mock.patch("handlers.career.ai_client.build_career_assessment", new=AsyncMock()) as build, \
                 unittest.mock.patch("handlers.career.generate_assessment_html_file", return_value=html_path), \
                 unittest.mock.patch("handlers.career.update_report_files"), \
                 unittest.mock.patch("handlers.career._track_event", new=AsyncMock()):
                await _build_and_send_career_assessment(message, state, "ru", state.data)
        build.assert_not_awaited()
        self.assertEqual(state.data["report_generation_status"], "ASSESSMENT_REUSED")
        self.assertTrue(state.data["final_report_generated"])
        message.answer_document.assert_awaited_once()

    async def test_successful_repair_renders_html_and_sets_report_ready(self) -> None:
        class State:
            def __init__(self) -> None:
                self.data = {
                    "public_user_id": "public-test-user",
                    "session_id": "session-profile-10",
                    "assessment_id": "assessment-profile-10",
                    "profile_version": "1",
                }
                self.current_state = None

            async def update_data(self, **kwargs) -> None:
                self.data.update(kwargs)

            async def set_state(self, value) -> None:
                self.current_state = value

        state = State()
        message = type("MessageStub", (), {"answer": AsyncMock(), "answer_document": AsyncMock()})()
        repaired = career_assessment_from_dict(profile_10_assessment_payload())
        repaired.metadata["recovered_by"] = "repair"
        with TemporaryDirectory() as output_dir:
            html_path = Path(output_dir) / "career_assessment_assessment-profile-10.html"
            html_path.write_text(render_assessment_html(repaired), encoding="utf-8")
            with (
                unittest.mock.patch("handlers.career._build_profile_snapshot", return_value={"country_code": "LT", "country_name": "Литва", "currency": "EUR", "ready_for_report": True}),
                unittest.mock.patch("handlers.career._snapshot_is_ready_for_report", return_value=True),
                unittest.mock.patch("handlers.career.ai_client.build_career_assessment", new=AsyncMock(return_value=repaired)),
                unittest.mock.patch("handlers.career.generate_assessment_html_file", return_value=html_path),
                unittest.mock.patch("handlers.career._track_event", new=AsyncMock()) as track_event,
                unittest.mock.patch("handlers.career.save_profile_version", side_effect=OSError("database unavailable")),
                unittest.mock.patch("handlers.career.save_report_version", side_effect=OSError("database unavailable")),
                unittest.mock.patch("handlers.career.update_report_files"),
                unittest.mock.patch.dict("os.environ", {"RAILWAY_GIT_COMMIT_SHA": "5775a3abcd9f23ee2f2617fa0dd4390ce9c694c6"}),
            ):
                await _build_and_send_career_assessment(message, state, "ru", state.data)
        self.assertEqual(state.current_state, CareerFlow.REPORT_READY)
        self.assertEqual(state.data["report_generation_status"], "ASSESSMENT_REPAIRED")
        self.assertTrue(state.data["final_report_generated"])
        message.answer_document.assert_awaited_once()
        generated_meta = next(call.kwargs["meta"] for call in track_event.await_args_list if call.args[2] == "report_generated")
        self.assertEqual(generated_meta["commit_sha"], "5775a3abcd9f23ee2f2617fa0dd4390ce9c694c6")
        self.assertEqual(generated_meta["pipeline_version"], CAREER_PIPELINE_VERSION)
        self.assertEqual(generated_meta["telegram_renderer_version"], CAREER_TELEGRAM_RENDERER_VERSION)
        self.assertEqual(generated_meta["html_renderer_version"], CAREER_HTML_RENDERER_VERSION)
        self.assertEqual(generated_meta["assessment_id"], "assessment-profile-10")
        self.assertEqual(generated_meta["profile_version"], "1")

    async def test_incomplete_snapshot_warns_but_still_generates_assessment(self) -> None:
        class State:
            def __init__(self) -> None:
                self.data = {
                    "public_user_id": "public-test-user",
                    "session_id": "session-incomplete",
                    "assessment_id": "assessment-incomplete",
                    "profile_version": "1",
                    "route_context": {"country": "Литва"},
                }
                self.current_state = None

            async def update_data(self, **kwargs) -> None:
                self.data.update(kwargs)

            async def set_state(self, value) -> None:
                self.current_state = value

        state = State()
        message = type("MessageStub", (), {"answer": AsyncMock(), "answer_document": AsyncMock()})()
        assessment = career_assessment_from_dict(profile_10_assessment_payload())
        incomplete_snapshot = {
            "country_code": "LT",
            "country_name": "Литва",
            "currency": "EUR",
            "route_context": {"country": "Литва"},
            "ready_for_report": False,
        }
        with TemporaryDirectory() as output_dir:
            html_path = Path(output_dir) / "career_assessment_assessment-incomplete.html"
            html_path.write_text(render_assessment_html(assessment), encoding="utf-8")
            with (
                unittest.mock.patch("handlers.career._build_profile_snapshot", return_value=incomplete_snapshot),
                unittest.mock.patch("handlers.career._snapshot_is_ready_for_report", return_value=False),
                unittest.mock.patch("handlers.career.ai_client.build_career_assessment", new=AsyncMock(return_value=assessment)) as build,
                unittest.mock.patch("handlers.career.generate_assessment_html_file", return_value=html_path),
                unittest.mock.patch("handlers.career._track_event", new=AsyncMock()),
                unittest.mock.patch("handlers.career.save_profile_version"),
                unittest.mock.patch("handlers.career.save_report_version"),
                unittest.mock.patch("handlers.career.update_report_files"),
            ):
                await _build_and_send_career_assessment(message, state, "ru", state.data)

        build.assert_awaited_once()
        generated_snapshot = build.await_args.args[0]
        self.assertIn("city", generated_snapshot["missing_fields"])
        self.assertEqual(state.current_state, CareerFlow.REPORT_READY)
        self.assertTrue(state.data["final_report_generated"])
        self.assertFalse(state.data["awaiting_route_context"])
        self.assertTrue(any("не буду блокировать результат" in call.args[0] for call in message.answer.await_args_list))
        self.assertTrue(any("Основной маршрут:" in call.args[0] for call in message.answer.await_args_list))
        message.answer_document.assert_awaited_once()

    async def test_html_failure_keeps_assessment_and_offers_document_retry(self) -> None:
        class State:
            def __init__(self) -> None:
                self.data = {
                    "public_user_id": "public-test-user",
                    "session_id": "session-profile-10",
                    "assessment_id": "assessment-profile-10",
                    "profile_version": "1",
                }
                self.current_state = None

            async def update_data(self, **kwargs) -> None:
                self.data.update(kwargs)

            async def set_state(self, value) -> None:
                self.current_state = value

        state = State()
        message = type("MessageStub", (), {"answer": AsyncMock(), "answer_document": AsyncMock()})()
        assessment = career_assessment_from_dict(profile_10_assessment_payload())
        with (
            unittest.mock.patch("handlers.career._build_profile_snapshot", return_value={"country_code": "LT", "country_name": "Литва", "currency": "EUR", "ready_for_report": True}),
            unittest.mock.patch("handlers.career._snapshot_is_ready_for_report", return_value=True),
            unittest.mock.patch("handlers.career.ai_client.build_career_assessment", new=AsyncMock(return_value=assessment)),
            unittest.mock.patch("handlers.career.generate_assessment_html_file", side_effect=OSError("disk unavailable")),
            unittest.mock.patch("handlers.career._track_event", new=AsyncMock()),
            unittest.mock.patch("handlers.career.save_profile_version"),
            unittest.mock.patch("handlers.career.save_report_version"),
            unittest.mock.patch("handlers.career.update_report_files"),
        ):
            await _build_and_send_career_assessment(message, state, "ru", state.data)

        self.assertEqual(state.current_state, CareerFlow.REPORT_GENERATION_FAILED)
        self.assertTrue(state.data["final_report_generated"])
        self.assertEqual(state.data["career_assessment"]["assessment_id"], "assessment-profile-10")
        self.assertEqual(state.data["html_report_path"], "")
        self.assertGreaterEqual(message.answer.await_count, 3)
        failure_call = message.answer.await_args_list[-1]
        self.assertIn("HTML не собрался", failure_call.args[0])
        retry_labels = [button.text for row in failure_call.kwargs["reply_markup"].keyboard for button in row]
        self.assertIn("Повторить создание документа", retry_labels)
        message.answer_document.assert_not_awaited()


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