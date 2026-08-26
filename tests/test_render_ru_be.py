import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from reportlab.pdfgen import canvas

from handlers.career import (
    SEGMENT_ENTREPRENEUR,
    SEGMENT_WORKER,
    ROUTE_CHOICE_HELP,
    ROUTE_CHOICE_RETRAIN,
    ROUTE_CHOICE_STABLE,
    _detect_crisis_risk,
    _validate_route_divergence,
    complete_barriers,
    _apply_route_choice_to_report,
    _build_route_comparison_rows,
    _construction_final_case_block,
    _reconcile_country_duration,
    validate_final_report,
    _decode_resume_bytes,
    _detect_user_segment,
    _question_count_for_mode,
    _ROUTE_CONTEXT_FIELDS,
    _route_context_question,
    _apply_strategy_outputs,
    _build_alternative_routes,
    handle_route_context_input,
    _question_reply_markup,
    _present_route_selection,
    _send_final_map_bundle,
    handle_route_selection_actions,
    handle_answer_review_actions,
    process_answers_input,
    process_story_input,
    _set_mvp_questions,
    _questions_calm,
    _questions_support,
    _segment_common_questions,
    _start_questions_module,
    _is_restart_intent,
    restart_from_any_state,
    barriers_fallback,
    _short_conclusion_7_lines,
    _full_conclusion_one_screen,
    _written_conclusion_from_report,
    _question_prompt,
    format_final_report,
    format_follow_up_questions,
    format_story_snapshot,
)
from handlers import voice as voice_handlers
from keyboards import (
    ALL_ROUTE_SELECTION_ACTIONS,
    CAREER_STRATEGY_HELP,
    ANSWER_CONTEXT_NO,
    ANSWER_CONTEXT_YES,
    INPUT_TEXT,
    INPUT_VOICE,
    LANG_RU,
    RESUME_SKIP,
    RESUME_UPLOAD,
    RESULT_MONTH_PLAN,
    RESULT_OPEN_FULL_REPORT,
    SKILLER_DONE,
    RESULT_TODAY_STEP,
    input_method_keyboard,
    story_confirmation_keyboard,
    pdf_fallback_keyboard,
    map_validation_keyboard,
    restart_keyboard,
    result_actions_keyboard,
    resume_choice_keyboard,
    skiller_check_keyboard,
    career_strategy_keyboard,
    step_tracking_keyboard,
)
from localization import t
from openai_client import ai_client
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

    async def clear(self) -> None:
        self.data = {}
        self.current_state = None


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.answer = AsyncMock()
        self.answer_document = AsyncMock()
        self.from_user = None
        self.chat = SimpleNamespace(id=123456)
        self.bot = SimpleNamespace()


class CareerGpsRenderTests(unittest.TestCase):
    def test_detect_crisis_risk_for_explicit_functioning_loss(self) -> None:
        self.assertTrue(_detect_crisis_risk("Я не могу есть, не могу спать и не могу работать уже несколько дней"))
        self.assertFalse(_detect_crisis_risk("Я устал и хочу более щадящий темп"))

    def test_validate_route_divergence_threshold(self) -> None:
        route_a = {
            "target_roles_6_months": ["Administrative Assistant", "Document Controller"],
            "training_plan_12_weeks": {"0_4_weeks": ["Собрать вакансии"]},
            "required_tools_and_skills": ["Excel", "CRM"],
            "recommended_certificates": ["Excel basic"],
            "income_at_start": {"assistant": "5000 PLN"},
            "today_action": {"action": "Открыть 10 вакансий"},
        }
        route_b = {
            "target_roles_6_months": ["Administrative Assistant", "Document Controller"],
            "training_plan_12_weeks": {"0_4_weeks": ["Собрать вакансии"]},
            "required_tools_and_skills": ["Excel", "CRM"],
            "recommended_certificates": ["Excel basic"],
            "income_at_start": {"assistant": "5000 PLN"},
            "today_action": {"action": "Собрать CV"},
        }
        is_divergent, score, compare = _validate_route_divergence(route_a, route_b)
        self.assertFalse(is_divergent)
        self.assertEqual(score, 1)
        self.assertTrue(compare["today_action"])

        route_c = {
            "new_career_options": ["HR operations", "Compliance"],
            "time_to_entry": {"HR operations": "6-12 months"},
            "gap_analysis": ["Labour law", "B2 language"],
            "training_cost": {"HR operations": "medium"},
            "income_growth_potential": {"HR operations": "high"},
            "today_action": {"action": "Сравнить 20 вакансий по HR"},
        }
        is_divergent_hi, score_hi, _ = _validate_route_divergence(route_a, route_c)
        self.assertTrue(is_divergent_hi)
        self.assertGreaterEqual(score_hi, 4)

    def test_question_count_for_mode_is_fixed_by_default(self) -> None:
        self.assertEqual(_question_count_for_mode("fast"), 5)
        self.assertEqual(_question_count_for_mode("calm_steps"), 8)
        self.assertEqual(_question_count_for_mode("deep_route"), 15)

    def test_question_count_for_mode_is_clamped_by_tz_bounds(self) -> None:
        self.assertEqual(_question_count_for_mode("fast", 1), 5)
        self.assertEqual(_question_count_for_mode("fast", 9), 5)

        self.assertEqual(_question_count_for_mode("calm_steps", 6), 8)
        self.assertEqual(_question_count_for_mode("calm_steps", 12), 10)

        self.assertEqual(_question_count_for_mode("deep_route", 10), 12)
        self.assertEqual(_question_count_for_mode("deep_route", 20), 15)

    def test_reconcile_country_duration_prefers_story_value_on_conflict(self) -> None:
        story = "Живу в Польше полтора года, работал в сметах и хочу вернуться в сферу."
        data = {
            "qa_answers": [
                {
                    "question": "Сколько времени вы живете в этой стране?",
                    "answer": "меньше 6 месяцев",
                }
            ]
        }
        answers = "1. Сколько времени вы живете в этой стране?: меньше 6 месяцев"

        merged, note, story_label = _reconcile_country_duration(story, data, answers)

        self.assertEqual(story_label, "1–2 года")
        self.assertIn("Вижу расхождение", note)
        self.assertIn("Срок проживания в стране (основной): 1–2 года", merged)

    def test_validate_final_report_for_construction_passes_with_required_terms(self) -> None:
        text = (
            "План: Assistant Cost Estimator и Junior Quantity Surveyor. "
            "Фокус на проектной документации и construction вакансиях."
        )
        validate_final_report(
            "construction_engineering_cost_estimation",
            "Assistant Cost Estimator / Junior Quantity Surveyor",
            "найти 10 construction вакансий",
            text,
        )

    def test_validate_final_report_for_construction_fails_on_forbidden_template(self) -> None:
        with self.assertRaises(ValueError):
            validate_final_report(
                "construction_engineering_cost_estimation",
                "любая офисная работа",
                "первый шаг",
                "Это route про sales-метрики и удержание клиентов",
            )

    def test_construction_final_case_block_contains_expected_roles_and_step(self) -> None:
        block = _construction_final_case_block()
        self.assertIn("Assistant Cost Estimator", block)
        self.assertIn("Junior Quantity Surveyor", block)
        self.assertIn("Technical Assistant Construction", block)
        self.assertIn("Construction Documentation Specialist", block)
        self.assertIn("Construction Project Assistant", block)
        self.assertIn("за 15 минут найдите 10 вакансий", block)

    def test_resume_pdf_is_decoded_for_analysis(self) -> None:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(72, 800, "Ivan Ivanov")
        pdf.drawString(72, 780, "Sales manager with 5 years of B2B experience and CRM pipeline ownership")
        pdf.drawString(72, 760, "Achievements: grew revenue by 30 percent and launched outbound process")
        pdf.save()

        extracted = _decode_resume_bytes(buffer.getvalue(), "resume.pdf")

        self.assertIn("Ivan Ivanov", extracted)
        self.assertIn("B2B experience", extracted)

    def test_resume_legacy_doc_is_decoded_for_analysis(self) -> None:
        text = "Ivan Ivanov Sales manager B2B pipeline revenue growth achievements CRM ownership"
        raw = ("\x00\x01DOC".encode("latin-1") + text.encode("utf-16le") + b"\x02\x03")

        extracted = _decode_resume_bytes(raw, "resume.doc")

        self.assertIn("Ivan Ivanov", extracted)
        self.assertIn("CRM ownership", extracted)

    def test_russian_start_flow_text(self) -> None:
        self.assertIn("NextYou", t("ru", "start_intro"))
        self.assertEqual(
            t("ru", "questions_cta"),
            "Отвечайте по одному. Если есть кнопки вариантов, можно нажать кнопку или ответить своим текстом/голосом.",
        )
        self.assertEqual(LANG_RU, "ru")

    def test_restart_keyboard_uses_russian_button(self) -> None:
        ru_keyboard = restart_keyboard("ru")
        self.assertIn("🔁 Пройти заново", ru_keyboard.model_dump_json())
        self.assertNotIn("🔁 Новая кар'ерная карта", ru_keyboard.model_dump_json())

    def test_input_method_keyboard_has_text_and_voice(self) -> None:
        keyboard = input_method_keyboard()
        dumped = keyboard.model_dump_json()
        self.assertIn(INPUT_TEXT, dumped)
        self.assertIn(INPUT_VOICE, dumped)

    def test_resume_and_result_keyboards(self) -> None:
        resume_dump = resume_choice_keyboard().model_dump_json()
        self.assertIn(RESUME_UPLOAD, resume_dump)
        self.assertIn(RESUME_SKIP, resume_dump)

        story_confirm_dump = story_confirmation_keyboard().model_dump_json()
        self.assertIn("поняли верно", story_confirm_dump)
        self.assertIn("Хочу поправить", story_confirm_dump)

        actions_dump = result_actions_keyboard().model_dump_json()
        self.assertIn("Делать шаги в боте", actions_dump)
        self.assertIn("со специалистом", actions_dump)
        self.assertIn("уточнить", actions_dump)
        self.assertNotIn("📄 Скачать PDF", actions_dump)

        skiller_dump = skiller_check_keyboard().model_dump_json()
        self.assertIn(SKILLER_DONE, skiller_dump)

        pdf_fallback_dump = pdf_fallback_keyboard().model_dump_json()
        self.assertIn(RESULT_OPEN_FULL_REPORT, pdf_fallback_dump)
        self.assertIn("Продолжить по шагам", pdf_fallback_dump)
        self.assertIn("Уточнить карту", pdf_fallback_dump)
        self.assertIn("Разобрать со специалистом", pdf_fallback_dump)

        map_validation_dump = map_validation_keyboard().model_dump_json()
        self.assertIn("Всё похоже на правду", map_validation_dump)
        self.assertIn("Исправить один факт", map_validation_dump)
        self.assertIn("Изменить приоритет", map_validation_dump)
        self.assertIn("не согласен с маршрутом", map_validation_dump)

    def test_career_strategy_keyboard_contains_requested_options(self) -> None:
        keyboard_dump = career_strategy_keyboard().model_dump_json()
        self.assertIn("Нужен доход в ближайшие 1–2 месяца", keyboard_dump)
        self.assertIn("Готов(а) готовиться 3–6 месяцев ради работы ближе к моему опыту", keyboard_dump)

    def test_route_selection_action_set_includes_strategy_buttons(self) -> None:
        self.assertIn("Нужен доход в ближайшие 1–2 месяца", ALL_ROUTE_SELECTION_ACTIONS)
        self.assertIn("Готов(а) готовиться 3–6 месяцев ради работы ближе к моему опыту", ALL_ROUTE_SELECTION_ACTIONS)
        self.assertIn("Не уверен(а), помоги выбрать", ALL_ROUTE_SELECTION_ACTIONS)


class CareerGpsRouteSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_selection_requires_strategy_choice_before_comparison(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Administrative Assistant", "backup_path": "Document Controller"},
            "career_recommendations": [
                {
                    "title": "Administrative Assistant",
                    "income_range": "5000-7500 PLN brutto",
                    "entry_timeline": "быстрый",
                    "risks": ["базовый польский"],
                    "pros": ["быстрый вход"],
                    "why_fit": "Сильное совпадение по административному опыту.",
                    "first_step": "Сравнить 5 вакансий по требованиям и сроку входа.",
                },
                {
                    "title": "Document Controller",
                    "income_range": "6000-9000 PLN brutto",
                    "entry_timeline": "средний",
                    "risks": ["аккуратный письменный польский"],
                    "pros": ["системность"],
                    "why_fit": "Подходит для опыта документооборота.",
                    "first_step": "Сравнить 5 вакансий по требованиям и сроку входа.",
                },
            ],
            "development_map": {},
            "weekly_plan": [],
            "action_plan": {"today": {"action": "Открыть 5 вакансий"}},
        }
        state = FakeState(
            data={
                "language": "ru",
                "public_user_id": "pub-1",
                "session_id": "sess-1",
                "user_mode": "calm_steps",
                "report_generation_id": "rid-1",
                "final_report": report,
            },
            current_state=CareerFlow.FINAL_READY.state,
        )
        message = FakeMessage()

        with patch("handlers.career.save_profile_version") as save_profile:
            with patch("handlers.career._track_event", new=AsyncMock()):
                await _present_route_selection(message, state, "ru", report)
                self.assertTrue(state.data.get("awaiting_career_strategy_choice"))
                self.assertEqual(state.current_state, CareerFlow.ROUTE_SELECTION.state)
                self.assertIn("несколько реалистичных путей", message.answer.await_args_list[0].args[0])

                message.text = "Нужен доход в ближайшие 1–2 месяца"
                await handle_route_selection_actions(message, state)

        self.assertEqual(state.data.get("career_strategy"), "fast_income")
        self.assertEqual(state.data.get("career_strategy_label"), "Нужен доход в ближайшие 1–2 месяца")
        self.assertFalse(state.data.get("awaiting_career_strategy_choice"))
        self.assertIn("fast_income", state.data.get("final_report", {}))
        self.assertTrue(save_profile.called)
        self.assertEqual(save_profile.call_args.args[1], "career_strategy_selected")
        self.assertEqual(save_profile.call_args.args[2]["career_strategy"], "fast_income")

    async def test_route_selection_accepts_ascii_hyphen_strategy_text(self) -> None:
        report = {"career_decision": {"recommended_main_path": "Administrative Assistant"}, "action_plan": {"today": {"action": "Открыть 5 вакансий"}}}
        state = FakeState(
            data={
                "language": "ru",
                "public_user_id": "pub-2",
                "session_id": "sess-2",
                "user_mode": "calm_steps",
                "report_generation_id": "rid-2",
                "final_report": report,
                "awaiting_career_strategy_choice": True,
            },
            current_state=CareerFlow.ROUTE_SELECTION.state,
        )
        message = FakeMessage(text="Готов(а) готовиться 3-6 месяцев ради работы ближе к моему опыту")

        with patch("handlers.career.save_profile_version") as save_profile:
            with patch("handlers.career._track_event", new=AsyncMock()):
                await handle_route_selection_actions(message, state)

        self.assertEqual(state.data.get("career_strategy"), "upskill_for_profile")
        self.assertEqual(state.data.get("career_strategy_label"), "Готов(а) готовиться 3–6 месяцев ради работы ближе к моему опыту")
        self.assertFalse(state.data.get("awaiting_career_strategy_choice"))
        self.assertTrue(save_profile.called)

    async def test_route_selection_saves_new_report_version(self) -> None:
        report = {
            "profile_domain": "construction_engineering_cost_estimation",
            "career_decision": {
                "recommended_main_path": "Assistant Cost Estimator / Junior Quantity Surveyor",
                "backup_path": "Site Office Assistant / Construction Documentation Assistant",
                "decision_summary": "",
            },
            "action_plan": {"today": {"action": "", "timebox": "", "result": ""}},
        }
        state = FakeState(
            data={
                "language": "ru",
                "public_user_id": "pub-2",
                "session_id": "sess-2",
                "user_mode": "calm_steps",
                "report_generation_id": "rid-old",
                "final_report": report,
            },
            current_state=CareerFlow.FINAL_READY.state,
        )
        message = FakeMessage(text=ROUTE_CHOICE_STABLE)

        with patch("handlers.career.save_report_version") as save_report:
            with patch("handlers.career.save_profile_version") as save_profile:
                with patch("handlers.career._send_final_map_bundle", new=AsyncMock()):
                    with patch("handlers.career._track_event", new=AsyncMock()):
                        await handle_route_selection_actions(message, state)

        self.assertTrue(save_report.called)
        self.assertTrue(save_profile.called)
        self.assertEqual(save_profile.call_args.args[1], "route_selected_report_regenerated")
        self.assertNotEqual(state.data.get("report_generation_id"), "rid-old")
        self.assertTrue(str(state.data.get("report_generation_id") or "").strip())

    async def test_final_bundle_rebuilds_construction_report_when_validator_fails(self) -> None:
        report = {
            "profile_domain": "construction_engineering_cost_estimation",
            "route_type": "route_upskill",
            "career_decision": {
                "recommended_main_path": "любая офисная работа",
                "backup_path": "-",
                "decision_summary": "",
            },
            "action_plan": {
                "today": {
                    "action": "Плитка и гипсокартон как первый шаг",
                    "timebox": "10 минут",
                    "result": "-",
                }
            },
        }
        state = FakeState(
            data={
                "language": "ru",
                "report_generation_id": "rid-final-1",
                "final_report": report,
            },
            current_state=CareerFlow.FINAL_READY.state,
        )
        message = FakeMessage()

        with patch("handlers.career.generate_html_report_file", return_value="reports/nextyou_report_example.html"):
            with patch("handlers.career.generate_docx_report_file", return_value=("", "")):
                with patch("handlers.career.update_report_files"):
                    with patch("handlers.career._run_pdf_generation_background", new=AsyncMock()):
                        with patch("handlers.career._track_event", new=AsyncMock()) as track_event:
                            await _send_final_map_bundle(message, state, "ru", report)

        selected = str((report.get("career_decision") or {}).get("recommended_main_path") or "")
        self.assertIn("Assistant Cost Estimator", selected)
        self.assertIn("Construction", _written_conclusion_from_report(report))
        self.assertTrue(
            any(
                len(call.args) >= 3 and str(call.args[2]) == "final_report_validated_after_rebuild"
                for call in track_event.await_args_list
            )
        )

    async def test_crisis_text_switches_to_crisis_support(self) -> None:
        state = FakeState(data={"language": "ru"}, current_state=CareerFlow.WAITING_STORY.state)
        message = FakeMessage(text="Я не могу есть, спать и не могу работать, совсем не справляюсь")

        with patch("handlers.career._track_event", new=AsyncMock()):
            await process_story_input(message, state, message.text)

        self.assertEqual(state.current_state, CareerFlow.CRISIS_SUPPORT.state)
        self.assertTrue(state.data.get("career_planning_paused"))
        self.assertTrue(message.answer.called)

    async def test_need_decision_flow_asks_three_questions_before_strategy(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Administrative Assistant", "backup_path": "Document Controller"},
            "career_recommendations": [{"title": "Administrative Assistant"}],
            "development_map": {},
            "weekly_plan": [],
            "action_plan": {"today": {"action": "Открыть 5 вакансий"}},
        }
        state = FakeState(
            data={
                "language": "ru",
                "public_user_id": "pub-1",
                "session_id": "sess-1",
                "user_mode": "calm_steps",
                "report_generation_id": "rid-1",
                "final_report": report,
            },
            current_state=CareerFlow.FINAL_READY.state,
        )
        message = FakeMessage()

        with patch("handlers.career.save_profile_version") as save_profile:
            with patch("handlers.career._track_event", new=AsyncMock()):
                await _present_route_selection(message, state, "ru", report)
                message.text = CAREER_STRATEGY_HELP
                await handle_route_selection_actions(message, state)

                self.assertTrue(state.data.get("awaiting_need_decision_questions"))
                self.assertIn("Мини-сравнение путей", message.answer.await_args_list[-2].args[0])
                self.assertIn("1/3.", message.answer.await_args_list[-1].args[0])

                message.text = "Проживу максимум 1-2 месяца без стабильного дохода"
                await handle_route_selection_actions(message, state)
                message.text = "Важно сохранить профессиональный статус"
                await handle_route_selection_actions(message, state)
                message.text = "Сейчас не готов(а) учиться регулярно"
                await handle_route_selection_actions(message, state)

        self.assertFalse(state.data.get("awaiting_need_decision_questions"))
        self.assertIn(state.data.get("career_strategy"), {"fast_income", "upskill_for_profile", "long_transition"})
        self.assertTrue(save_profile.called)

    async def test_missing_route_context_does_not_block_report_generation(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "selected_psych_markers": ["Боюсь отказов"],
                "selected_barriers": ["Боюсь отказов"],
                "selected_fears": ["Боюсь отказов"],
            },
            current_state=CareerFlow.waiting_for_barriers.state,
        )
        message = FakeMessage()

        with patch("handlers.career._start_route_context_intake", new=AsyncMock()) as start_route_context:
            with patch("handlers.career._build_and_send_report", new=AsyncMock()) as build_report:
                await complete_barriers(message, state)

        self.assertEqual(state.current_state, CareerFlow.waiting_for_barriers.state)
        start_route_context.assert_not_awaited()
        build_report.assert_awaited_once()

    async def test_route_context_last_answer_continues_to_report(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "route_context_index": len(_ROUTE_CONTEXT_FIELDS) - 1,
                "route_context": {
                    "country": "Польша",
                    "city": "Варшава",
                    "current_language_level": "A2",
                    "target_language": "польский B1",
                    "income_urgency": "срочно",
                    "minimum_monthly_income": "3500",
                    "desired_monthly_income": "5000",
                    "training_budget": "200",
                    "available_time_for_study": "5 часов",
                    "career_goal_type": "близкая сфера",
                    "work_preferences": "офис",
                    "health_or_schedule_limits": "без ночных смен",
                    "documents_and_work_rights": "есть право на работу",
                    "diploma_status": "диплом есть",
                },
            },
            current_state=CareerFlow.ROUTE_CONTEXT.state,
        )
        message = FakeMessage(text="Есть портфолио и рекомендации")

        with patch("handlers.career.save_profile_version") as save_profile:
            with patch("handlers.career._build_and_send_report", new=AsyncMock()) as build_report:
                await handle_route_context_input(message, state)

        self.assertEqual(state.data.get("route_context", {}).get("portfolio_or_references"), "Есть портфолио и рекомендации")
        self.assertFalse(state.data.get("awaiting_route_context"))
        build_report.assert_awaited_once()
        self.assertTrue(save_profile.called)

    def test_fast_income_strategy_bundle_has_application_plan(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Administrative Assistant", "backup_path": "Document Controller"},
            "market_analysis": [
                {"profession": "Administrative Assistant", "requirements": ["Excel", "документооборот", "базовый польский"]},
                {"profession": "Back-office Specialist", "requirements": ["точность", "процессы", "Sheets"]},
            ],
            "career_recommendations": [{"title": "Operations Coordinator"}],
            "action_plan": {"today": {"action": ""}},
        }
        route_context = {
            "country": "Польша",
            "city": "Варшава",
            "current_language_level": "A2",
            "target_language": "польский B1",
            "documents_and_work_rights": "есть право на работу",
            "work_preferences": "офис, без смен",
        }

        _apply_strategy_outputs(report, route_context, "fast_income")

        bundle = report.get("fast_income", {}) if isinstance(report.get("fast_income"), dict) else {}
        self.assertEqual(report.get("career_strategy"), "fast_income")
        self.assertIn("Закрепиться на одной из быстрых входных ролей", str(bundle.get("goal_30_days", "")))
        self.assertGreaterEqual(len(bundle.get("realistic_entry_roles", [])), 2)
        self.assertGreaterEqual(len(bundle.get("application_plan_7_days", [])), 7)
        self.assertIn("15 минут", str(bundle.get("today_action", {}).get("timebox", "")))

    def test_fast_income_uses_professional_bridge_for_5plus_years_return_case(self) -> None:
        report = {
            "profile_domain": "construction_engineering_cost_estimation",
            "career_decision": {
                "recommended_main_path": "Administrative Assistant / Back-office Specialist",
                "backup_path": "Document Controller",
                "why_this_path": "Пользователь хочет вернуться в профессию.",
            },
            "market_analysis": [
                {"profession": "Administrative Assistant", "requirements": ["Excel", "документооборот"]},
                {"profession": "Assistant Cost Estimator", "requirements": ["сметы", "проектная документация"]},
            ],
            "career_recommendations": [{"title": "Junior Quantity Surveyor"}],
            "facts_only": {
                "explicit_facts": [
                    "17 лет в строительстве",
                    "Хочет вернуться в профессию инженера-сметчика",
                ]
            },
        }
        route_context = {
            "country": "Польша",
            "city": "Варшава",
            "career_goal_type": "вернуться в профессию",
            "current_language_level": "A2",
            "target_language": "польский B1",
            "documents_and_work_rights": "есть право на работу",
            "work_preferences": "офис, строительная компания",
        }

        _apply_strategy_outputs(report, route_context, "fast_income")

        bundle = report.get("fast_income", {}) if isinstance(report.get("fast_income"), dict) else {}
        self.assertEqual(bundle.get("route_type"), "professional_bridge_with_income")
        self.assertEqual(bundle.get("short_term_goal"), "сохранить доход и начать возвращение в строительную сферу")
        self.assertEqual(
            bundle.get("main_goal_3_6_months"),
            "выйти на assistant / junior роль рядом со сметами, строительной документацией или project coordination",
        )
        roles_blob = " ".join(str(item) for item in bundle.get("realistic_entry_roles", []))
        self.assertIn("Assistant Cost Estimator", roles_blob)
        self.assertNotIn("Administrative Assistant", roles_blob)

    def test_fast_income_uses_generic_professional_bridge_for_non_construction(self) -> None:
        report = {
            "career_decision": {
                "recommended_main_path": "Administrative Assistant / Back-office Specialist",
                "backup_path": "Operations Coordinator",
                "why_this_path": "Хочет вернуться по специальности.",
            },
            "market_analysis": [
                {"profession": "Administrative Assistant", "requirements": ["Excel"]},
                {"profession": "Procurement Assistant", "requirements": ["тендеры", "документы"]},
            ],
            "career_recommendations": [{"title": "Junior Procurement Specialist"}],
            "facts_only": {
                "explicit_facts": [
                    "8 лет в закупках",
                    "Хочет вернуться в профессию",
                ]
            },
        }
        route_context = {
            "country": "Польша",
            "city": "Краков",
            "career_goal_type": "вернуться в профессию",
            "work_preferences": "офис, закупки",
        }

        _apply_strategy_outputs(report, route_context, "fast_income")

        bundle = report.get("fast_income", {}) if isinstance(report.get("fast_income"), dict) else {}
        self.assertEqual(bundle.get("route_type"), "professional_bridge_with_income")
        self.assertEqual(bundle.get("short_term_goal"), "сохранить доход и начать возвращение в профессиональную сферу")
        self.assertEqual(
            bundle.get("main_goal_3_6_months"),
            "выйти на assistant / junior роль рядом с профильными задачами, документацией или project coordination",
        )
        roles_blob = " ".join(str(item) for item in bundle.get("realistic_entry_roles", []))
        self.assertNotIn("Administrative Assistant", roles_blob)
        self.assertIn("Procurement Assistant", roles_blob)

    def test_upskill_strategy_bundle_has_gap_analysis(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Document Controller", "backup_path": "Operations Coordinator"},
            "market_analysis": [
                {"profession": "Operations Coordinator", "requirements": ["Excel", "workflows", "language"]},
                {"profession": "Document Control Specialist", "requirements": ["GDPR", "attention to detail", "documents"]},
            ],
            "what_not_reset": [
                "Опыт работы с документами",
                "Контроль сроков",
                "Координация задач",
            ],
        }
        route_context = {
            "current_language_level": "A2",
            "target_language": "польский B1",
            "diploma_status": "диплом требует проверки",
        }

        _apply_strategy_outputs(report, route_context, "upskill_for_profile")

        bundle = report.get("upskill_for_profile", {}) if isinstance(report.get("upskill_for_profile"), dict) else {}
        self.assertEqual(report.get("career_strategy"), "upskill_for_profile")
        self.assertGreaterEqual(len(bundle.get("target_roles_6_months", [])), 2)
        self.assertEqual(len(bundle.get("gap_analysis", [])), 4)
        self.assertGreaterEqual(len(bundle.get("training_plan_12_weeks", {}).keys()), 4)
        self.assertIn("данных недостаточно", str(bundle.get("recommended_certificates", [""])[0]))

    def test_long_transition_bundle_has_required_fields_and_table(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Project Coordinator", "backup_path": "HR Operations"},
            "market_analysis": [
                {"profession": "Project Coordinator", "salary_range": "7000-9500 PLN", "competition": "средняя"},
                {"profession": "Compliance Specialist", "salary_range": "8500-12000 PLN", "competition": "высокая"},
                {"profession": "HR Operations", "salary_range": "6500-9000 PLN", "competition": "средняя"},
            ],
        }
        route_context = {
            "country": "Польша",
            "city": "Варшава",
            "current_language_level": "A2",
            "target_language": "B1",
            "documents_and_work_rights": "есть право на работу",
            "diploma_status": "есть диплом",
        }

        _apply_strategy_outputs(report, route_context, "long_transition")

        bundle = report.get("long_transition", {}) if isinstance(report.get("long_transition"), dict) else {}
        self.assertEqual(report.get("career_strategy"), "long_transition")
        self.assertGreaterEqual(len(bundle.get("new_career_options", [])), 3)
        self.assertGreaterEqual(len(bundle.get("comparison_table", [])), 3)
        self.assertIn("15–20", str(bundle.get("decision_checkpoint", "")))
        self.assertIn("15 минут", str(bundle.get("today_action", {}).get("timebox", "")))

    def test_need_decision_bundle_has_mini_table_and_questions(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Administrative Assistant"},
        }
        route_context = {
            "country": "Польша",
            "city": "Варшава",
        }

        _apply_strategy_outputs(report, route_context, "need_decision")

        bundle = report.get("need_decision", {}) if isinstance(report.get("need_decision"), dict) else {}
        self.assertEqual(report.get("career_strategy"), "need_decision")
        self.assertEqual(len(bundle.get("comparison_table", [])), 3)
        self.assertEqual(len(bundle.get("decision_questions", [])), 3)
        self.assertIn("Ответьте на 3 коротких вопроса", str(bundle.get("today_action", {}).get("action", "")))

    def test_story_snapshot_and_questions_render(self) -> None:
        analysis = {
            "current_identity": "Мигрант с опытом управления и коммуникации.",
            "skills": ["коммуникация", "управление", "переговоры"],
            "constraints": ["язык", "быстрый доход"],
            "goals": ["найти работу", "выйти на стабильный доход"],
            "follow_up_questions": [
                {
                    "id": 1,
                    "block": "financial_pressure",
                    "question": "Какой минимальный доход нужен в месяц?",
                    "type": "short_text",
                    "options": [],
                },
                {
                    "id": 2,
                    "block": "financial_pressure",
                    "question": "Как быстро нужен доход?",
                    "type": "single_choice",
                    "options": ["в течение 2-4 недель", "в течение 1-3 месяцев"],
                },
            ],
        }
        snapshot = format_story_snapshot(analysis, "ru")
        questions = format_follow_up_questions(analysis, "ru")

        self.assertIn("Кто вы сейчас", snapshot)
        self.assertIn("Навыки", snapshot)
        self.assertIn("1. Какой минимальный доход нужен в месяц?", questions)
        self.assertIn("Если есть кнопки вариантов", questions)
        self.assertIn("NextYou", t("ru", "start_intro"))

    def test_question_prompt_hides_inline_options_text(self) -> None:
        analysis = {
            "follow_up_questions": [
                {
                    "id": 5,
                    "question": "Сколько ресурса и времени у вас сейчас на поиск и действия?",
                    "options": [
                        "Низкий ресурс, до 15 минут в день",
                        "Средний ресурс, 30-60 минут",
                        "Хороший ресурс, 1-2 часа",
                    ],
                }
            ]
        }
        text = _question_prompt(analysis, 0, "ru")
        self.assertIn("Сколько ресурса и времени у вас сейчас на поиск и действия?", text)
        self.assertNotIn("=== Вопрос", text)
        self.assertNotIn("Варианты:", text)
        self.assertNotIn("Можно ответить своими словами", text)

    def test_align_report_switches_poland_to_lithuania_markers(self) -> None:
        report = {
            "market_analysis": [{"profession": "Role", "salary_range": "6000-9000 PLN brutto"}],
            "career_recommendations": [{"title": "Role", "income_range": "5000 PLN netto", "why_fit": "Подходит для рынка Польши"}],
            "career_decision": {"recommended_main_path": "Role", "why_this_path": "Рынок Польши"},
            "real_solutions": [{"title": "Role", "why": "Переход в Польше", "first_step": "Тест"}],
        }
        aligned = ai_client._align_report_with_story(
            report,
            story_analysis={"current_identity": "Живу в Литве"},
            answers_text="Сейчас в Литве",
            story_text="Переехал в Литву",
        )
        text_blob = str(aligned)
        self.assertIn("EUR", text_blob)
        self.assertIn("Литв", text_blob)
        self.assertNotIn("PLN", text_blob)
        self.assertNotIn("Польш", text_blob)

    def test_follow_up_questions_normalized_to_minimum(self) -> None:
        questions = ai_client._normalize_question_count([{"id": 1, "block": "financial_pressure", "question": "Один вопрос?", "type": "short_text", "options": []}], "ru")
        self.assertGreaterEqual(len(questions), 8)
        self.assertLessEqual(len(questions), 12)
        self.assertTrue(all(isinstance(item, dict) for item in questions))

    def test_set_mvp_questions_respects_exact_limit_for_normal_mode(self) -> None:
        result = _set_mvp_questions({"follow_up_questions": []}, limit=8, mode="calm_steps", story_text="", user_segment=SEGMENT_WORKER)
        self.assertEqual(len(result.get("follow_up_questions", [])), 8)

    def test_set_mvp_questions_pins_required_diagnostics(self) -> None:
        result = _set_mvp_questions(
            {"follow_up_questions": []},
            limit=8,
            mode="calm_steps",
            story_text="",
            user_segment=SEGMENT_WORKER,
        )
        rows = result.get("follow_up_questions", [])
        keys = {str(row.get("multi_key") or "").strip() for row in rows if isinstance(row, dict)}
        self.assertIn("psych", keys)
        self.assertIn("integration", keys)
        self.assertIn("energy", keys)
        self.assertIn("priorities", keys)

    def test_admin_profile_does_not_replace_model_roles_from_catalog(self) -> None:
        story_analysis = {
            "current_identity": "Женщина с административным опытом, документооборотом и координацией процессов в Польше.",
            "experience_snapshot": ["Документооборот", "Контроль сроков", "Координация задач"],
            "skills": ["Excel", "организация", "formal procedures"],
        }
        report = {
            "digital_human": {"current_state": "", "previous_identity": ""},
            "market_analysis": [{"profession": "B2B Sales"}, {"profession": "Customer Success"}],
            "career_recommendations": [{"title": "Customer Support Specialist"}, {"title": "Office Manager"}],
            "career_translation": [{"market_term": "Офис-менеджер", "source_experience": "", "suitable_roles": []}],
            "career_decision": {
                "recommended_main_path": "Customer Success Entry",
                "backup_path": "Sales Support",
            },
            "action_plan": {"today": {"action": "язык каждый день", "timebox": "20 минут", "result": "прогресс"}},
            "what_not_reset": [],
            "experience_layers": [],
        }

        normalized = ai_client._align_report_with_story(report, story_analysis)

        self.assertEqual(normalized["digital_human"]["current_state"], story_analysis["current_identity"])
        self.assertEqual(normalized["career_recommendations"][0]["title"], "Customer Support Specialist")
        self.assertEqual(normalized["market_analysis"][0]["profession"], "B2B Sales")
        self.assertEqual(normalized["career_translation"][0]["market_term"], "Офис-менеджер")
        self.assertEqual(normalized["career_decision"]["recommended_main_path"], "Customer Success Entry")

    def test_construction_domain_does_not_force_catalog_route(self) -> None:
        story_analysis = {
            "current_identity": "Инженер-сметчик в строительной сфере.",
            "experience_snapshot": [
                "Сметы",
                "Проектная документация",
                "Объёмы работ",
                "Взаимодействие с подрядчиками и проектировщиками",
            ],
            "skills": ["строительные нормы", "материалы", "construction"],
        }
        report = {
            "digital_human": {"current_state": "", "previous_identity": ""},
            "market_analysis": [{"profession": "Administrative Assistant"}, {"profession": "Generic Back-office Specialist"}],
            "career_recommendations": [{"title": "Administrative Assistant"}, {"title": "Back-office Specialist"}],
            "career_decision": {
                "recommended_main_path": "Administrative Assistant / Back-office Specialist",
                "backup_path": "Courier",
                "why_this_path": "",
                "why_not_other_paths": [],
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "career_bridges": [{"role": "Administrative Assistant", "why_bridge": "", "first_market_test": ""}],
            "real_solutions": [{"title": "Administrative Assistant", "first_step": ""}],
            "action_plan": {"today": {"action": "Открыть вакансии", "timebox": "15 минут", "result": "Список"}},
            "what_not_reset": [],
            "experience_layers": [],
            "social_integration": {},
            "facts_only": {
                "explicit_facts": ["Профиль инженера-сметчика"],
                "inferences": ["Похоже, у вас есть профильный опыт в строительстве."],
                "unknowns": [],
                "contradictions": [],
            },
        }

        normalized = ai_client._align_report_with_story(report, story_analysis)

        self.assertEqual(normalized.get("profile_domain"), "construction_engineering_cost_estimation")
        self.assertEqual(normalized["career_decision"]["recommended_main_path"], "Administrative Assistant / Back-office Specialist")
        self.assertEqual(normalized["market_analysis"][0]["profession"], "Administrative Assistant")
        self.assertEqual(normalized["career_recommendations"][0]["title"], "Administrative Assistant")
        self.assertEqual(normalized["action_plan"]["today"]["timebox"], "15 минут")

    def test_construction_overwhelm_step_uses_estimator_examples(self) -> None:
        story_analysis = {
            "current_identity": "Инженер-сметчик в строительстве.",
            "experience_snapshot": ["Сметы", "Проектная документация", "Объёмы работ"],
            "skills": ["строительные нормы"],
        }
        report = {
            "digital_human": {
                "current_state": "",
                "previous_identity": "",
                "strategy_mode": "Growth",
                "career_readiness": {
                    "urgency": "высокая",
                    "learning_capacity": "средняя",
                    "risk_tolerance": "умеренная",
                    "language_readiness": "средняя",
                    "mobility": "средняя",
                },
            },
            "market_analysis": [],
            "career_recommendations": [],
            "career_translation": [],
            "career_decision": {
                "recommended_main_path": "Administrative Assistant / Back-office Specialist",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "action_plan": {"today": {"action": "Открыть вакансии", "timebox": "15 минут", "result": "Список"}},
            "what_not_reset": [],
            "experience_layers": [],
            "social_integration": {},
            "facts_only": {
                "explicit_facts": ["Инженер-сметчик"],
                "inferences": ["Похоже, у вас есть профильный строительный опыт."],
                "unknowns": [],
                "contradictions": [],
            },
        }

        decision_layers = {
            "career_profile": ["Профиль инженера-сметчика"],
            "constraints": ["Данных о изменении ограничений пока недостаточно"],
            "psychological_state": ["signal: overwhelm", "не знаю, с чего начать"],
            "action_capacity": ["Темп: slow"],
        }

        normalized = ai_client._align_report_with_story(
            report,
            story_analysis,
            answers_text="Не знаю, с чего начать",
            decision_layers=decision_layers,
        )

        today_action = normalized["action_plan"]["today"]["action"].lower()
        self.assertIn("смет", today_action)
        self.assertIn("проектн", today_action)
        self.assertNotIn("плитк", today_action)

    def test_facts_only_removes_unconfirmed_admin_claims(self) -> None:
        story_analysis = {
            "current_identity": "Работал в сервисных подработках и общался с клиентами.",
            "experience_snapshot": ["Подработки", "Коммуникация с клиентами"],
            "skills": ["коммуникация"],
        }
        report = {
            "digital_human": {"current_state": "", "previous_identity": ""},
            "what_not_reset": [
                "Умение работать с документами и формальными процедурами.",
                "Навык контроля сроков и поручений.",
            ],
            "experience_layers": [
                "Административный слой: документы, сроки, поручения, контроль и офисные процессы.",
            ],
            "competency_signals": ["Организация процессов"],
            "social_integration": {},
            "market_analysis": [],
            "career_recommendations": [],
            "career_translation": [],
            "career_decision": {},
            "real_solutions": [],
            "action_plan": {"today": {"action": "", "timebox": "", "result": ""}},
            "facts_only": {
                "explicit_facts": ["Работал в сервисных подработках", "Коммуникация с клиентами"],
                "inferences": ["Похоже, у вас есть опыт коммуникации и взаимодействия с людьми в рабочих задачах."],
                "unknowns": [
                    "Пока не хватает данных, чтобы понять, насколько вы знакомы с местным рынком и какие документы уже есть. Это можно уточнить позже.",
                ],
                "contradictions": [],
            },
        }

        normalized = ai_client._align_report_with_story(report, story_analysis)

        self.assertFalse(any("документ" in str(item).lower() for item in normalized["what_not_reset"]))
        self.assertFalse(any("документ" in str(item).lower() for item in normalized["experience_layers"]))
        self.assertFalse(any("срок" in str(item).lower() for item in normalized["what_not_reset"]))
        self.assertIn("facts_only", normalized)

    def test_align_report_does_not_inject_segment_routes(self) -> None:
        story_analysis = {
            "current_identity": "Работал водителем и на складе",
            "experience_snapshot": ["Логистика", "Склад"],
        }
        report = {
            "digital_human": {"current_state": "", "previous_identity": ""},
            "career_decision": {
                "recommended_main_path": "",
                "why_this_path": "",
                "decision_summary": "",
            },
            "real_solutions": [],
            "what_not_reset": [],
            "experience_layers": [],
            "action_plan": {"today": {"action": "", "timebox": "", "result": ""}},
            "social_integration": {},
            "facts_only": {
                "explicit_facts": ["Опыт в логистике"],
                "inferences": ["Похоже, есть прикладной операционный опыт."],
                "unknowns": [],
                "contradictions": [],
            },
        }

        normalized = ai_client._align_report_with_story(
            report,
            story_analysis,
            answers_text="",
            decision_layers={},
            user_segment="logistics_transport",
            user_segment_label="Логистика и транспорт",
        )

        decision = normalized.get("career_decision", {})
        self.assertEqual(decision.get("recommended_main_path"), "")
        self.assertEqual(normalized.get("real_solutions"), [])

    def test_final_report_chunks_render(self) -> None:
        report = {
            "digital_human": {
                "summary": "Профиль собран.",
                "current_state": "Переходный этап.",
                "main_asset": "Опыт продаж.",
                "main_risk": "Финансовый стресс.",
                "main_barrier": "Тревога.",
                "main_fear": "Не найти работу.",
                "hidden_strengths": ["устойчивость"],
                "fastest_path_to_income": "Смежная роль.",
                "psychological_profile": {
                    "dominant_barriers": ["тревога"],
                    "dominant_fears": ["не найти работу"],
                    "coping_style": "структурный",
                    "support_needed": "план",
                },
                "skills": {"professional": ["коммуникация", "продажи"]},
                "barriers": {"critical": ["язык", "документы"]},
            },
            "market_analysis": [
                {
                    "profession": "B2B Sales",
                    "fit_percent": 91,
                    "demand": "высокий",
                    "entry_speed": "высокая",
                    "competition": "средняя",
                    "requirements": ["CRM"],
                    "salary_range": "$1400-$3000",
                    "profile_match_reason": "сильный бэкграунд",
                }
            ],
            "career_translation": [
                {
                    "source_experience": "Документооборот",
                    "market_term": "Document management",
                    "suitable_roles": ["Back-office Specialist"],
                }
            ],
            "career_bridges": [
                {
                    "role": "Back-office Specialist",
                    "why_bridge": "Минимальный разрыв",
                    "first_market_test": "Проверить 10 вакансий",
                }
            ],
            "what_not_reset": ["Навык работы с документами"],
            "experience_layers": ["Административный слой"],
            "career_recommendations": [
                {
                    "title": "Customer Support Specialist",
                    "match_percent": 80,
                    "why_fit": "Быстрый вход.",
                    "pros": ["быстрый старт"],
                    "risks": ["нужен язык"],
                    "entry_timeline": "1-3 месяца",
                    "income_range": "$900-$1800",
                }
            ],
            "real_solutions": [
                {
                    "title": "Решение №1",
                    "recommendation_level": "рекомендуемое",
                    "success_probability": "высокая",
                    "timeline": "1-3 месяца",
                    "why": "быстрый доход",
                    "first_step": "собрать вакансии",
                }
            ],
            "career_decision": {
                "recommended_main_path": "Customer Support Specialist",
                "why_this_path": "Быстрый вход.",
                "why_not_other_paths": ["Дольше по времени"],
                "backup_path": "Sales Support",
                "avoid_for_now": "Долгий свитч",
                "decision_summary": "Сначала быстрый трек",
            },
            "development_map": {
                "current_state": "Без локального CV.",
                "goal": "Получить первую работу.",
                "gap": ["язык", "CV"],
                "route": [{"stage": "Подготовка", "objective": "Обновить CV", "actions": ["Собрать достижения"], "output": "Черновик CV", "timeline": "2 дня"}],
                "first_month": [{"week": 1, "focus": "Старт", "tasks": ["CV"], "output": "готово"}],
            },
            "action_plan": {
                "today": {"action": "Открыть 5 вакансий", "timebox": "15 минут", "result": "Список требований"},
                "this_week": ["обновить CV"],
                "this_month": ["получить интервью"],
            },
            "weekly_plan": [
                {"day": 1, "focus": "Профиль", "task": "Обновить LinkedIn.", "time": "20 минут", "result": "Есть профиль.", "why": "Это базовый вход в рынок"}
            ],
            "career_barriers": [
                {
                    "barrier": "Страх ошибиться",
                    "severity": 80,
                    "mechanism": "Долго думает и не отправляет отклики",
                    "recommended_skill": "Принятие решений",
                    "first_exercise": "7 дней без смены маршрута",
                }
            ],
            "barrier_landscape": {
                "external": ["язык"],
                "internal": ["страх"],
                "behavioral_risk": "не отправляет отклики",
                "first_counter_action": "отправить 3 отклика",
            },
            "resource_level": "medium",
            "integration_level": "low",
            "energy_sources": ["Организация процессов", "Работа с людьми"],
            "career_priorities": ["Быстро выйти на доход", "Работать по специальности"],
            "competency_signals": ["Коммуникация", "Организация процессов", "Решение проблем"],
            "closing_message": "Сконцентрируйтесь на первом работающем маршруте.",
        }
        chunks = format_final_report(report, "ru")
        self.assertEqual(len(chunks), 3)
        self.assertIn("Ваш профиль ситуации", chunks[0])
        self.assertIn("Ваше профессиональное ядро", chunks[0])
        self.assertIn("Что не обнулилось", chunks[0])
        self.assertIn("Источники энергии", chunks[0])
        self.assertIn("Карьерные приоритеты", chunks[0])
        self.assertIn("STAR-компетенции", chunks[0])
        self.assertIn("Ресурс и рабочий темп", chunks[0])
        self.assertIn("Сейчас ресурс частично ограничен", chunks[0])
        self.assertIn("Состояние интеграции", chunks[0])
        self.assertIn("Интеграция пока начальная", chunks[0])
        self.assertIn("Перевод вашего опыта на язык рынка Польши", chunks[0])
        self.assertIn("Карьерные мосты", chunks[0])
        self.assertIn("Почему вы застряли", chunks[0])
        self.assertIn("Решение по карте перехода", chunks[1])
        self.assertIn("Сегодня (до 15 минут)", chunks[2])

    def test_detect_user_segment_for_worker_profile(self) -> None:
        story = "Работал сварщиком на производстве, умею работать на станке и вести смену бригады."

        segment = _detect_user_segment(story)

        self.assertEqual(segment, SEGMENT_WORKER)

    def test_detect_user_segment_for_entrepreneur_profile(self) -> None:
        story = "Я предприниматель, развивал свой бизнес и управлял продажами как founder."

        segment = _detect_user_segment(story)

        self.assertEqual(segment, SEGMENT_ENTREPRENEUR)

    def test_set_mvp_questions_includes_worker_specific_questions(self) -> None:
        analysis = {"follow_up_questions": []}

        result = _set_mvp_questions(
            analysis,
            limit=16,
            mode="calm_steps",
            story_text="",
            user_segment=SEGMENT_WORKER,
        )
        questions = result.get("follow_up_questions", [])
        texts = [str(row.get("question", "")) for row in questions if isinstance(row, dict)]

        self.assertTrue(any("руках" in text.lower() or "руками" in text.lower() or "производственн" in text.lower() for text in texts))
        self.assertTrue(any("оборудован" in text.lower() or "техник" in text.lower() or "инструмент" in text.lower() for text in texts))

    def test_set_mvp_questions_fast_mode_is_max_five_and_compact(self) -> None:
        analysis = {"follow_up_questions": []}

        result = _set_mvp_questions(
            analysis,
            limit=15,
            mode="fast",
            story_text="",
            user_segment=SEGMENT_WORKER,
        )
        questions = result.get("follow_up_questions", [])
        texts = [str(row.get("question", "")).lower() for row in questions if isinstance(row, dict)]

        self.assertLessEqual(len(questions), 5)
        self.assertTrue(any("главная цель" in text for text in texts))
        self.assertTrue(any("главный барьер" in text for text in texts))
        self.assertTrue(any("правом работать" in text or "документ" in text for text in texts))
        self.assertTrue(any("живете в этой стране" in text for text in texts))
        self.assertTrue(any("ресурса и времени" in text for text in texts))
        self.assertFalse(any("энерги" in text for text in texts))
        self.assertFalse(any("интеграц" in text for text in texts))
        self.assertFalse(any("приоритет" in text for text in texts))

    def test_set_mvp_questions_deep_route_mode_has_12_to_15(self) -> None:
        analysis = {"follow_up_questions": []}

        result = _set_mvp_questions(
            analysis,
            limit=15,
            mode="deep_route",
            story_text="",
            user_segment=SEGMENT_WORKER,
        )
        questions = result.get("follow_up_questions", [])

        self.assertGreaterEqual(len(questions), 12)
        self.assertLessEqual(len(questions), 15)

    def test_set_mvp_questions_has_alignment_metadata(self) -> None:
        analysis = {"follow_up_questions": []}

        result = _set_mvp_questions(
            analysis,
            limit=5,
            mode="fast",
            story_text="",
            user_segment=SEGMENT_WORKER,
        )
        questions = result.get("follow_up_questions", [])
        self.assertTrue(questions)
        first = questions[0]
        self.assertIn("question_id", first)
        self.assertIn("allowed_button_ids", first)
        self.assertIn("expected_answer_type", first)
        self.assertIn("semantic_intent", first)
        self.assertIn("source", first)
        self.assertIn("validity_status", first)

    def test_money_and_time_templates_use_interval_buttons(self) -> None:
        calm = _questions_calm()
        support = _questions_support()
        common = _segment_common_questions()

        calm_income = next((row for row in calm if "минимальный доход" in str(row.get("question", "")).lower()), {})
        support_income = next((row for row in support if "минимальный доход" in str(row.get("question", "")).lower()), {})
        support_hours = next((row for row in support if "сколько часов" in str(row.get("question", "")).lower()), {})
        common_hours = next((row for row in common if "сколько часов" in str(row.get("question", "")).lower()), {})

        self.assertIn("Минимум: €1200–1500 EUR net/мес", list(calm_income.get("options", [])))
        self.assertIn("Минимум: €1200–1500 EUR net/мес", list(support_income.get("options", [])))
        self.assertIn("3-5 часов в неделю", list(support_hours.get("options", [])))
        self.assertIn("3-5 часов в неделю", list(common_hours.get("options", [])))

    def test_set_mvp_questions_injects_interval_options_for_free_text_income_time(self) -> None:
        analysis = {
            "follow_up_questions": [
                {
                    "id": 101,
                    "question": "Какой минимальный доход в месяц нужен вам сейчас?",
                    "options": [],
                },
                {
                    "id": 102,
                    "question": "Сколько часов в неделю готовы уделять обучению?",
                    "options": [],
                },
            ]
        }

        result = _set_mvp_questions(
            analysis,
            limit=15,
            mode="deep_route",
            story_text="",
            user_segment=SEGMENT_WORKER,
        )
        questions = result.get("follow_up_questions", [])

        income_row = next((row for row in questions if "минимальный доход в месяц" in str(row.get("question", "")).lower()), {})
        hours_row = next((row for row in questions if "сколько часов в неделю готовы уделять обучению" in str(row.get("question", "")).lower()), {})

        self.assertIn("Минимум: €1200–1500 EUR net/мес", list(income_row.get("options", [])))
        self.assertIn("6-10 часов в неделю", list(hours_row.get("options", [])))

    def test_question_reply_markup_fallback_uses_intervals_for_income_and_time(self) -> None:
        income_analysis = {
            "follow_up_questions": [
                {
                    "id": 1,
                    "question": "Какой минимальный доход нужен в месяц?",
                    "options": [],
                }
            ]
        }
        income_keyboard = _question_reply_markup(income_analysis, 0)
        self.assertIsNotNone(income_keyboard)
        income_dump = str(getattr(income_keyboard, "keyboard", ""))
        self.assertIn("Минимум: €1200–1500 EUR net/мес", income_dump)
        self.assertNotIn("PLN", income_dump)

        hours_analysis = {
            "follow_up_questions": [
                {
                    "id": 1,
                    "question": "Сколько часов в неделю реально готовы уделять поиску или обучению?",
                    "options": [],
                }
            ]
        }
        hours_keyboard = _question_reply_markup(hours_analysis, 0)
        self.assertIsNotNone(hours_keyboard)
        hours_dump = str(getattr(hours_keyboard, "keyboard", ""))
        self.assertIn("3-5 часов в неделю", hours_dump)
        self.assertIn("10+ часов в неделю", hours_dump)

    def test_written_conclusion_covers_all_required_dimensions(self) -> None:
        report = {
            "digital_human": {
                "current_state": "Специалист с опытом координации и клиентских задач",
                "main_asset": "Сильная организационная дисциплина и коммуникация",
                "main_barrier": "Тревога перед отказами",
                "career_readiness": {"urgency": "высокая"},
                "barriers": {"internal": ["Страх отказов"], "external": ["Язык"]},
            },
            "career_decision": {"recommended_main_path": "Administrative Assistant / Back-office Specialist"},
            "action_plan": {"today": {"action": "Собрать 10 вакансий и отправить 3 отклика"}},
            "resource_level": "medium",
            "integration_level": "low",
        }

        text = _written_conclusion_from_report(report)
        short_text = _short_conclusion_7_lines(report)
        one_screen_text = _full_conclusion_one_screen(report)

        self.assertIn("Кто вы как профессионал", text)
        self.assertIn("ценность на рынке труда", text)
        self.assertIn("Ограничения и ресурсы", text)
        self.assertIn("Готовность к изменениям", text)
        self.assertIn("Интеграция в новой стране", text)
        self.assertIn("Рекомендованный маршрут", text)
        self.assertIn("Следующий шаг", text)
        self.assertGreaterEqual(len(short_text.splitlines()), 7)
        self.assertIn("Полное заключение (1 экран)", one_screen_text)
        self.assertIn("Письменное заключение (полное по ТЗ)", text)

    def test_route_choice_is_joint_not_bot_assigned(self) -> None:
        report = {
            "career_decision": {
                "recommended_main_path": "Частные заказы",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "Строительная компания",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "career_recommendations": [
                {
                    "title": "Частные заказы",
                    "match_percent": 78,
                    "why_fit": "",
                    "pros": ["портфолио", "гибкость"],
                    "risks": ["выше неопределенность"],
                    "entry_timeline": "2-4 месяца",
                    "income_range": "7000-12000 PLN brutto",
                },
                {
                    "title": "Строительная компания",
                    "match_percent": 82,
                    "why_fit": "",
                    "pros": ["резюме", "отклики"],
                    "risks": ["ниже риск"],
                    "entry_timeline": "1-3 месяца",
                    "income_range": "5500-8000 PLN brutto",
                },
            ],
            "real_solutions": [
                {
                    "title": "Переобучение в смежный трек",
                    "recommendation_level": "долгосрочное",
                    "success_probability": "средняя",
                    "timeline": "6-12 месяцев",
                    "why": "",
                    "first_step": "",
                }
            ],
        }

        rows = _build_route_comparison_rows(report)
        selected = _apply_route_choice_to_report(report, ROUTE_CHOICE_STABLE, rows)

        self.assertTrue(selected)
        self.assertEqual(report["career_decision"]["recommended_main_path"], selected)
        self.assertIn("совместно", report["career_decision"]["decision_summary"].lower())

    def test_construction_route_choice_stable_applies_domain_pack(self) -> None:
        report = {
            "profile_domain": "construction_engineering_cost_estimation",
            "career_decision": {
                "recommended_main_path": "Assistant Cost Estimator / Junior Quantity Surveyor",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "action_plan": {"today": {"action": "", "timebox": "", "result": ""}},
        }

        rows = _build_route_comparison_rows(report)
        selected = _apply_route_choice_to_report(report, ROUTE_CHOICE_STABLE, rows)

        self.assertEqual(report.get("route_type"), "route_stable")
        self.assertIn("Site Office Assistant", selected)
        self.assertIn("строительных компаниях", str(report["action_plan"]["today"]["action"]))
        self.assertEqual(str(report["route_stable"]["timeline"]), "1-3 месяца")

    def test_construction_route_choice_retrain_applies_upskill_pack(self) -> None:
        report = {
            "profile_domain": "construction_engineering_cost_estimation",
            "career_decision": {
                "recommended_main_path": "Site Office Assistant / Construction Documentation Assistant",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "action_plan": {"today": {"action": "", "timebox": "", "result": ""}},
        }

        rows = _build_route_comparison_rows(report)
        selected = _apply_route_choice_to_report(report, ROUTE_CHOICE_RETRAIN, rows)

        self.assertEqual(report.get("route_type"), "route_upskill")
        self.assertIn("Assistant Cost Estimator", selected)
        self.assertEqual(str(report["route_upskill"]["timeline"]), "3-6 месяцев")
        self.assertEqual(
            str(report["route_upskill"]["first_step"]),
            "собрать 10 вакансий и выписать требования",
        )

    def test_construction_route_help_returns_comparison_without_auto_selection(self) -> None:
        report = {
            "profile_domain": "construction_engineering_cost_estimation",
            "career_decision": {
                "recommended_main_path": "Assistant Cost Estimator / Junior Quantity Surveyor",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "",
                "avoid_for_now": "",
                "decision_summary": "",
            },
        }
        initial_path = report["career_decision"]["recommended_main_path"]

        rows = _build_route_comparison_rows(report)
        selected = _apply_route_choice_to_report(report, ROUTE_CHOICE_HELP, rows)

        self.assertEqual(selected, "")
        self.assertEqual(report.get("route_type"), "route_comparison")
        self.assertEqual(report["career_decision"]["recommended_main_path"], initial_path)
        comparison = report.get("route_comparison", [])
        self.assertEqual(len(comparison), 3)
        self.assertEqual(str(comparison[0].get("name")), "Быстрый вход в строительную компанию")
        self.assertEqual(str(comparison[1].get("name")), "Возврат к сметам через обучение")

    def test_alternative_routes_rotation_for_construction_has_four_distinct_items(self) -> None:
        report = {
            "profile_domain": "construction_engineering_cost_estimation",
            "career_decision": {
                "recommended_main_path": "Assistant Cost Estimator / Junior Quantity Surveyor",
                "backup_path": "Site Office Assistant / Construction Documentation Assistant",
            },
        }
        rows = _build_route_comparison_rows(report)
        alternatives = _build_alternative_routes(report, rows)

        self.assertEqual(len(alternatives), 4)
        names = [str(item.get("name") or "") for item in alternatives if isinstance(item, dict)]
        self.assertEqual(len(set(names)), 4)
        self.assertTrue(all(str(item.get("first_step") or "").strip() for item in alternatives if isinstance(item, dict)))

    def test_language_documents_question_uses_only_language_document_buttons(self) -> None:
        analysis = {
            "follow_up_questions": [
                {
                    "id": 3,
                    "question": "Что у вас сейчас с языком, документами и правом работать?",
                    "options": [],
                    "semantic_intent": "language_documents_work_right",
                }
            ]
        }

        keyboard = _question_reply_markup(analysis, 0)
        self.assertIsNotNone(keyboard)
        dump = str(getattr(keyboard, "keyboard", ""))
        self.assertIn("Польский A1-A2, право работать есть", dump)
        self.assertIn("Польский B1+, право работать есть", dump)
        self.assertIn("Отвечу текстом", dump)
        self.assertNotIn("Больше с людьми", dump)
        self.assertNotIn("Лучше без активных продаж", dump)
        self.assertNotIn("офис", dump.lower())

    def test_language_documents_question_text_match_still_uses_language_buttons(self) -> None:
        analysis = {
            "follow_up_questions": [
                {
                    "id": 3,
                    "question": "Что у вас сейчас с языком, документами и правом работать?",
                    "options": ["случайная кнопка"],
                }
            ]
        }

        keyboard = _question_reply_markup(analysis, 0)
        self.assertIsNotNone(keyboard)
        dump = str(getattr(keyboard, "keyboard", ""))
        self.assertIn("Польский A1-A2, право работать есть", dump)
        self.assertIn("Нужно уточнить право на работу", dump)
        self.assertNotIn("Больше с людьми", dump)
        self.assertNotIn("Лучше без активных продаж", dump)

    def test_written_conclusion_contains_construction_route_blocks(self) -> None:
        report = {
            "profile_domain": "construction_engineering_cost_estimation",
            "digital_human": {
                "current_state": "Инженер-сметчик",
                "main_asset": "Опыт в сметах и строительной документации",
                "main_barrier": "Язык и локальные нормы",
                "career_readiness": {"urgency": "высокая"},
                "barriers": {"internal": ["Тревога"], "external": ["Язык"]},
            },
            "career_decision": {
                "recommended_main_path": "Assistant Cost Estimator / Junior Quantity Surveyor",
                "why_this_path": "Ближе к профессии",
                "why_not_other_paths": [],
                "backup_path": "Site Office Assistant / Construction Documentation Assistant",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "action_plan": {"today": {"action": "собрать 10 вакансий и выписать требования", "timebox": "15 минут", "result": "Список требований"}},
            "resource_level": "medium",
            "integration_level": "medium",
        }

        text = _written_conclusion_from_report(report)

        self.assertIn("route_stable", text)
        self.assertIn("route_upskill", text)
        self.assertIn("route_comparison", text)
        self.assertIn("Site Office Assistant", text)
        self.assertIn("Junior Quantity Surveyor", text)

    def test_overwhelm_changes_step_not_route(self) -> None:
        story_analysis = {
            "current_identity": "Административный специалист с опытом документооборота и координации.",
            "experience_snapshot": ["Документооборот", "Координация процессов"],
            "skills": ["Excel", "организация"],
        }
        report = {
            "digital_human": {
                "current_state": "",
                "previous_identity": "",
                "strategy_mode": "Growth",
                "career_readiness": {"urgency": "средняя", "learning_capacity": "средняя", "risk_tolerance": "умеренная", "language_readiness": "средняя", "mobility": "средняя"},
            },
            "market_analysis": [],
            "career_recommendations": [],
            "career_translation": [],
            "career_decision": {
                "recommended_main_path": "Строительный рабочий",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "action_plan": {"today": {"action": "Открыть вакансии", "timebox": "15 минут", "result": "Список"}},
            "what_not_reset": [],
            "experience_layers": [],
            "social_integration": {},
            "facts_only": {
                "explicit_facts": ["Опыт документооборота"],
                "inferences": ["Похоже, у вас есть опыт координации задач."],
                "unknowns": [],
                "contradictions": [],
            },
        }
        decision_layers = {
            "career_profile": ["Текущая идентичность: административный профиль"],
            "constraints": ["Данных о изменении ограничений пока недостаточно"],
            "psychological_state": ["Эмоциональный перегруз/неопределенность", "signal: overwhelm"],
            "action_capacity": ["Темп: slow"],
        }

        normalized = ai_client._align_report_with_story(
            report,
            story_analysis,
            answers_text="Не знаю, с чего начать",
            decision_layers=decision_layers,
        )

        self.assertNotEqual(
            normalized["career_decision"]["recommended_main_path"],
            "Administrative Assistant / Back-office Specialist",
            "Overwhelm must NOT change the route to admin defaults",
        )
        self.assertNotEqual(
            normalized.get("digital_human", {}).get("strategy_mode"),
            "Survival",
            "Overwhelm must NOT set strategy_mode to Survival",
        )
        self.assertEqual(normalized["action_plan"]["today"]["timebox"], "10 минут")
        self.assertIn("три вида работ", normalized["action_plan"]["today"]["action"].lower())
        self.assertNotIn("плитка", normalized["action_plan"]["today"]["action"].lower())
        self.assertIn("decision_layers", normalized)

    def test_private_orders_anchor_preserved_under_overwhelm(self) -> None:
        story_analysis = {
            "current_identity": "Работаю через частные заказы по ремонту.",
            "experience_snapshot": ["Плитка", "Гипсокартон", "Мебель"],
            "skills": ["ремонт"],
        }
        report = {
            "digital_human": {
                "current_state": "",
                "previous_identity": "",
                "strategy_mode": "Growth",
                "career_readiness": {"urgency": "высокая", "learning_capacity": "средняя", "risk_tolerance": "умеренная", "language_readiness": "средняя", "mobility": "средняя"},
            },
            "market_analysis": [],
            "career_recommendations": [],
            "career_translation": [],
            "career_decision": {
                "recommended_main_path": "Строительный рабочий",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "action_plan": {"today": {"action": "Открыть вакансии", "timebox": "15 минут", "result": "Список"}},
            "what_not_reset": [],
            "experience_layers": [],
            "social_integration": {},
            "facts_only": {
                "explicit_facts": ["Частные заказы по ремонту"],
                "inferences": ["Похоже, у вас есть прикладной опыт в отделочных работах."],
                "unknowns": [],
                "contradictions": [],
            },
        }
        decision_layers = {
            "career_profile": ["Опыт: частные заказы"],
            "constraints": ["Данных о изменении ограничений пока недостаточно"],
            "psychological_state": ["не знаю, с чего начать"],
            "action_capacity": ["Темп: slow"],
        }

        normalized = ai_client._align_report_with_story(
            report,
            story_analysis,
            answers_text="Не знаю, с чего начать",
            decision_layers=decision_layers,
        )

        self.assertIn("частные заказы", normalized["career_decision"]["recommended_main_path"].lower())

    def test_fear_of_rejection_barrier_overrides_today_step(self) -> None:
        story_analysis = {
            "current_identity": "Работаю в отделке и беру частные заказы.",
            "experience_snapshot": ["Плитка", "Гипсокартон", "Покраска"],
            "skills": ["ремонт"],
        }
        report = {
            "digital_human": {
                "current_state": "Мастер отделочных работ",
                "main_barrier": "Страх отказа",
                "main_fear": "Получить отказ и остановиться",
                "strategy_mode": "Growth",
                "career_readiness": {
                    "urgency": "высокая",
                    "learning_capacity": "средняя",
                    "risk_tolerance": "умеренная",
                    "language_readiness": "средняя",
                    "mobility": "средняя",
                },
            },
            "market_analysis": [],
            "career_recommendations": [],
            "career_translation": [],
            "career_decision": {
                "recommended_main_path": "Частные заказы",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "action_plan": {
                "today": {
                    "action": "Открыть 5 вакансий",
                    "timebox": "15 минут",
                    "result": "Список требований",
                }
            },
            "what_not_reset": ["Плитка", "Гипсокартон"],
            "experience_layers": [],
            "social_integration": {},
            "facts_only": {
                "explicit_facts": ["Делал отделку квартир"],
                "inferences": ["Похоже, у вас есть прикладной опыт."],
                "unknowns": [],
                "contradictions": [],
            },
        }

        normalized = ai_client._align_report_with_story(
            report,
            story_analysis,
            answers_text="Боюсь отказа от клиентов",
            decision_layers={},
        )

        today = normalized["action_plan"]["today"]
        self.assertEqual(today["timebox"], "10 минут")
        self.assertIn("Ищу работу по направлению", today["action"])
        self.assertIn("Частные заказы", today["action"])
        self.assertIn("Скопировать текст", today["action"])

    def test_fear_of_rejection_does_not_inject_construction_for_office_route(self) -> None:
        story_analysis = {
            "current_identity": "Административный профиль в госсекторе.",
            "experience_snapshot": ["Документооборот", "Координация процессов"],
            "skills": ["office"],
        }
        report = {
            "digital_human": {
                "current_state": "Административный специалист",
                "main_barrier": "Страх отказа",
                "main_fear": "Получить отказ и остановиться",
                "strategy_mode": "Growth",
                "career_readiness": {
                    "urgency": "высокая",
                    "learning_capacity": "средняя",
                    "risk_tolerance": "умеренная",
                    "language_readiness": "средняя",
                    "mobility": "средняя",
                },
            },
            "market_analysis": [],
            "career_recommendations": [],
            "career_translation": [],
            "career_decision": {
                "recommended_main_path": "Administrative Assistant / Back-office Specialist",
                "why_this_path": "",
                "why_not_other_paths": [],
                "backup_path": "",
                "avoid_for_now": "",
                "decision_summary": "",
            },
            "action_plan": {
                "today": {
                    "action": "Открыть 5 вакансий",
                    "timebox": "15 минут",
                    "result": "Список требований",
                }
            },
            "what_not_reset": ["Документооборот", "Координация"],
            "experience_layers": [],
            "social_integration": {},
            "facts_only": {
                "explicit_facts": ["Опыт в департаменте"],
                "inferences": ["Похоже, у вас сильный административный профиль."],
                "unknowns": [],
                "contradictions": [],
            },
        }

        normalized = ai_client._align_report_with_story(
            report,
            story_analysis,
            answers_text="Боюсь отказа на отклики",
            decision_layers={},
        )

        today = normalized["action_plan"]["today"]
        self.assertEqual(today["timebox"], "10 минут")
        self.assertIn("Administrative Assistant / Back-office Specialist", today["action"])
        self.assertNotIn("плитка", today["action"].lower())
        self.assertNotIn("гипсокартон", today["action"].lower())


class CareerGpsVoiceFlowTests(unittest.IsolatedAsyncioTestCase):
    def test_stable_income_answer_is_not_restart_intent(self) -> None:
        self.assertFalse(_is_restart_intent(ROUTE_CHOICE_STABLE))
        self.assertTrue(_is_restart_intent("🔁 Пройти заново"))

    async def test_process_story_input_moves_to_story_confirmation(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "user_mode": "calm_steps",
            },
            current_state=CareerFlow.waiting_for_story.state,
        )
        message = FakeMessage()

        with patch("handlers.career._track_event", new=AsyncMock()):
            with patch.object(ai_client, "analyze_story", new=AsyncMock(return_value={
                "story_summary": "Есть опыт администрирования и нужен доход.",
                "current_identity": "Специалист с административным опытом.",
                "experience_snapshot": ["Документы", "Координация"],
                "skills": ["Организация"],
                "constraints": ["Язык"],
                "goals": ["Стабильный доход"],
                "missing_data": [],
                "follow_up_questions": [],
                "confidence_note": "",
            })):
                await process_story_input(message, state, "Работала с документами и координацией, нужен стабильный доход.")

        self.assertEqual(state.current_state, CareerFlow.confirming_story.state)
        self.assertEqual(state.data.get("promised_question_count"), 4)
        self.assertGreaterEqual(message.answer.await_count, 3)

    async def test_start_questions_module_moves_to_interview(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "story_text": "Нужна работа, есть опыт администрирования и документов, польский A2.",
                "story_analysis": {},
                "user_mode": "calm_steps",
                "promised_question_count": 4,
                "cv_uploaded": False,
            },
            current_state=CareerFlow.waiting_for_resume.state,
        )
        message = FakeMessage()

        with patch("handlers.career._track_event", new=AsyncMock()):
            await _start_questions_module(message, state, "ru")

        self.assertEqual(state.current_state, CareerFlow.waiting_for_answers.state)
        self.assertEqual(state.data.get("qa_index"), 0)
        self.assertEqual(state.data.get("qa_answers"), [])
        self.assertFalse(state.data.get("quick_report_after_questions"))
        self.assertGreaterEqual(len((state.data.get("story_analysis") or {}).get("follow_up_questions", [])), 1)
        self.assertEqual(message.answer.await_count, 2)

    async def test_confirmed_voice_answer_returns_to_answers_state(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "transcribed_text": "все подряд",
                "voice_target": "answers",
            },
            current_state=CareerFlow.confirming_transcription.state,
        )
        message = FakeMessage()

        with patch.object(voice_handlers, "process_answers_input", new=AsyncMock()) as process_answers:
            await voice_handlers.confirm_transcription_yes(message, state)

        self.assertEqual(state.current_state, CareerFlow.waiting_for_answers.state)
        process_answers.assert_awaited_once_with(message, state, "все подряд")
        self.assertEqual(state.data.get("transcribed_text"), "")
        self.assertEqual(state.data.get("voice_target"), "story")
        message.answer.assert_not_awaited()

    async def test_soft_voice_confirmation_uses_existing_transcript(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "transcribed_text": "У меня опыт в администрировании и документах.",
                "voice_target": "story",
            },
            current_state=CareerFlow.confirming_transcription.state,
        )
        message = FakeMessage(text="она уже есть, используй это")

        with patch.object(voice_handlers, "process_story_input", new=AsyncMock()) as process_story:
            await voice_handlers.confirm_transcription_fallback(message, state)

        process_story.assert_awaited_once_with(message, state, "У меня опыт в администрировании и документах.")
        self.assertEqual(state.data.get("transcribed_text"), "")
        self.assertEqual(state.data.get("voice_target"), "story")
        message.answer.assert_not_awaited()

    async def test_voice_confirmation_handles_soft_confirm_when_user_responds_by_voice(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "transcribed_text": "У меня опыт в администрировании и документах.",
                "voice_target": "story",
            },
            current_state=CareerFlow.confirming_transcription.state,
        )
        message = FakeMessage()
        message.voice = SimpleNamespace(file_id="voice-1")
        message.bot = SimpleNamespace(get_file=AsyncMock(return_value=SimpleNamespace(file_path="voice-1.ogg")), download=AsyncMock())

        with patch.object(ai_client, "transcribe_voice", new=AsyncMock(return_value="она уже есть, используй это")):
            with patch.object(voice_handlers, "confirm_transcription_yes", new=AsyncMock()) as confirm_yes:
                await voice_handlers.confirm_transcription_voice(message, state)

        confirm_yes.assert_awaited_once_with(message, state)
        message.answer.assert_not_awaited()

    async def test_restart_intent_resets_to_initial_menu_from_step_tracking(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "public_user_id": "pub-1",
                "execution_steps": [{"day": 1, "task": "Тест"}],
                "current_execution_day": 1,
            },
            current_state=CareerFlow.STEP_TRACKING.state,
        )
        message = FakeMessage(text="Хочу пройти сначала")

        await restart_from_any_state(message, state)

        self.assertEqual(state.current_state, CareerFlow.SELECTING_PACE.state)
        self.assertGreaterEqual(message.answer.await_count, 3)
        self.assertIn("нужно", str(message.answer.await_args_list[-1].args[0]))

    def test_step_tracking_keyboard_exposes_restart(self) -> None:
        dumped = step_tracking_keyboard().model_dump_json()
        self.assertIn("Пройти заново", dumped)
        self.assertIn("Следующий день", dumped)

    async def test_previous_question_button_is_not_recorded_as_current_answer(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "story_analysis": {
                    "follow_up_questions": [
                        {
                            "id": 1,
                            "question": "Первый вопрос",
                            "options": ["Вариант 1", "Вариант 2"],
                            "expected_answer_type": "single_select",
                            "semantic_intent": "first",
                        },
                        {
                            "id": 2,
                            "question": "Второй вопрос",
                            "options": ["Ответ A", "Ответ B"],
                            "expected_answer_type": "single_select",
                            "semantic_intent": "what helps under stress",
                        },
                    ]
                },
                "qa_index": 1,
                "qa_answers": [{"question": "Первый вопрос", "answer": "Вариант 1"}],
                "user_mode": "calm_steps",
                "quick_report_after_questions": False,
                "interaction_profile": {},
                "interaction_turn": 0,
            },
            current_state=CareerFlow.waiting_for_answers.state,
        )
        message = FakeMessage()

        with patch("handlers.career._track_event", new=AsyncMock()):
            await process_answers_input(message, state, "Вариант 2")

        pending = state.data.get("pending_answer_review") or {}
        self.assertEqual(pending.get("review_type"), "context_mismatch")
        self.assertEqual(state.data.get("qa_index"), 1)
        self.assertEqual(len(state.data.get("qa_answers", [])), 1)

    async def test_context_review_recovers_snapshot_and_exits_yes_no_keyboard(self) -> None:
        review = {
            "index": 1,
            "question": "Второй вопрос",
            "question_id": 2,
            "answer": "Старая кнопка",
            "review_type": "context_mismatch",
            "normalized_answer": "ответ по текущему вопросу: Старая кнопка",
        }
        state = FakeState(data={
            "language": "ru",
            "story_analysis": {"follow_up_questions": [
                {"id": 1, "question": "Первый вопрос", "options": ["Старая кнопка"]},
                {"id": 2, "question": "Второй вопрос", "options": ["Новый ответ"]},
            ]},
            "qa_index": 1,
            "qa_answers": [{"question": "Первый вопрос", "answer": "Старая кнопка"}],
            "pending_answer_review": {},
            "answer_review_snapshot": review,
        }, current_state=CareerFlow.waiting_for_answers.state)
        message = FakeMessage(ANSWER_CONTEXT_NO)

        with patch("handlers.career._track_event", new=AsyncMock()):
            await handle_answer_review_actions(message, state)

        self.assertEqual(state.data.get("pending_answer_review"), {})
        self.assertEqual(state.data.get("answer_review_snapshot"), {})
        sent_text = str(message.answer.await_args.args[0])
        self.assertIn("Второй вопрос", sent_text)

    async def test_late_multi_select_tap_is_merged_without_context_review(self) -> None:
        questions = [
            {
                "id": 1,
                "question": "Что уже есть в новой стране?",
                "options": ["Есть друзья", "Есть профессиональные контакты", "✅ Готово"],
                "multi_key": "integration",
                "done_text": "✅ Готово",
                "max_select": 5,
            },
            {"id": 2, "question": "Что сейчас мешает?", "options": ["Страх", "Нет ясности"]},
        ]
        state = FakeState(data={
            "language": "ru",
            "story_analysis": {"follow_up_questions": questions},
            "qa_index": 1,
            "qa_answers": [{"question": questions[0]["question"], "answer": "Есть друзья"}],
            "recent_completed_multi": {
                "question_index": 0,
                "answer_index": 0,
                "multi_key": "integration",
                "options": ["Есть друзья", "Есть профессиональные контакты"],
                "selected_values": ["Есть друзья"],
                "max_select": 5,
            },
            "user_mode": "calm_steps",
            "interaction_profile": {},
            "interaction_turn": 0,
        }, current_state=CareerFlow.waiting_for_answers.state)
        message = FakeMessage()

        with patch("handlers.career._track_event", new=AsyncMock()):
            await process_answers_input(message, state, "Есть профессиональные контакты")

        self.assertEqual(state.data["qa_index"], 1)
        self.assertEqual(
            state.data["qa_answers"][0]["answer"],
            "Есть друзья, Есть профессиональные контакты",
        )
        self.assertEqual(
            state.data["selected_integration_state"],
            ["Есть друзья", "Есть профессиональные контакты"],
        )
        self.assertFalse(state.data.get("pending_answer_review"))
        self.assertIn("Текущий вопрос остаётся активным", str(message.answer.await_args.args[0]))

    async def test_duplicate_context_confirmation_restores_active_question(self) -> None:
        state = FakeState(data={
            "language": "ru",
            "story_analysis": {"follow_up_questions": [
                {"id": 1, "question": "Текущий вопрос", "options": ["Да", "Нет"]},
            ]},
            "qa_index": 0,
            "pending_answer_review": {},
            "answer_review_snapshot": {},
        }, current_state=CareerFlow.waiting_for_answers.state)
        message = FakeMessage(ANSWER_CONTEXT_YES)

        await handle_answer_review_actions(message, state)

        sent_text = str(message.answer.await_args.args[0])
        self.assertIn("Текущий вопрос", sent_text)
        self.assertNotIn("Ответьте одним сообщением", sent_text)

    async def test_free_text_overwhelm_signal_is_classified(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "story_analysis": {
                    "follow_up_questions": [
                        {
                            "id": 1,
                            "question": "Опишите текущую ситуацию",
                            "options": [],
                            "expected_answer_type": "free_text",
                            "semantic_intent": "current_state",
                        }
                    ]
                },
                "qa_index": 0,
                "qa_answers": [],
                "user_mode": "calm_steps",
                "quick_report_after_questions": False,
                "interaction_profile": {},
                "interaction_turn": 0,
            },
            current_state=CareerFlow.waiting_for_answers.state,
        )
        message = FakeMessage()

        with patch("handlers.career._track_event", new=AsyncMock()):
            with patch("handlers.career.advance_assessment", new=AsyncMock(return_value="GENERATE_REPORT")) as advance:
                await process_answers_input(message, state, "Не знаю, с чего начать")

        qa = state.data.get("qa_answers", [])
        self.assertEqual(len(qa), 1)
        self.assertEqual(qa[0].get("signal"), "overwhelm")
        self.assertEqual(qa[0].get("not_equal_to"), "новая карьерная цель")
        advance.assert_awaited_once()

    async def test_priorities_career_switch_collects_reason(self) -> None:
        done_text = "✅ Приоритеты: готово"
        state = FakeState(
            data={
                "language": "ru",
                "story_analysis": {
                    "follow_up_questions": [
                        {
                            "id": 1,
                            "question": "Что для вас сейчас важнее всего в карьере?",
                            "options": ["Быстро выйти на доход", "Сменить профессию", done_text],
                            "multi_key": "priorities",
                            "done_text": done_text,
                            "max_select": 4,
                            "force_options_keyboard": True,
                            "expected_answer_type": "multi_select",
                            "semantic_intent": "career_priorities",
                        }
                    ]
                },
                "qa_index": 0,
                "qa_answers": [],
                "selected_choice_reasons": {},
                "pending_choice_reason": {},
                "user_mode": "calm_steps",
                "quick_report_after_questions": False,
                "interaction_profile": {},
                "interaction_turn": 0,
            },
            current_state=CareerFlow.waiting_for_answers.state,
        )
        message = FakeMessage()

        with patch("handlers.career._track_event", new=AsyncMock()):
            with patch("handlers.career.advance_assessment", new=AsyncMock(return_value="GENERATE_REPORT")) as advance:
                await process_answers_input(message, state, "Сменить профессию")
                self.assertEqual((state.data.get("pending_choice_reason") or {}).get("choice_label"), "Сменить профессию")

                await process_answers_input(message, state, "Кажется, что здесь мало денег")
                self.assertEqual((state.data.get("selected_choice_reasons") or {}).get("Сменить профессию"), "Кажется, что здесь мало денег")
                self.assertEqual(state.data.get("qa_index"), 0)

                await process_answers_input(message, state, done_text)

        qa = state.data.get("qa_answers", [])
        self.assertEqual(state.data.get("qa_index"), 1)
        self.assertEqual(len(qa), 2)
        self.assertIn("Сменить профессию", qa[0].get("answer", ""))
        self.assertEqual(qa[1].get("question"), "Почему выбрана смена профессии")
        self.assertIn("мало денег", qa[1].get("answer", "").lower())
        advance.assert_awaited_once()

    async def test_fast_mode_finishes_without_mandatory_diagnostics_phase(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "story_analysis": {
                    "follow_up_questions": [
                        {
                            "id": 1,
                            "question": "Короткий вопрос",
                            "options": [],
                            "expected_answer_type": "free_text",
                            "semantic_intent": "main_goal",
                        }
                    ]
                },
                "qa_index": 0,
                "qa_answers": [],
                "user_mode": "fast",
                "interaction_profile": {},
                "interaction_turn": 0,
                "mandatory_diagnostics_in_progress": False,
                "mandatory_diagnostics_done": False,
            },
            current_state=CareerFlow.waiting_for_answers.state,
        )
        message = FakeMessage()

        with patch("handlers.career._track_event", new=AsyncMock()):
            with patch("handlers.career.advance_assessment", new=AsyncMock(return_value="GENERATE_REPORT")) as advance:
                await process_answers_input(message, state, "Ответ")

        self.assertFalse(bool(state.data.get("mandatory_diagnostics_in_progress")))
        self.assertFalse(bool(state.data.get("mandatory_diagnostics_done")))
        self.assertEqual(state.data.get("qa_index"), 1)
        advance.assert_awaited_once()

    async def test_barriers_repeat_choice_from_previous_group_does_not_stall(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "barrier_current_group": "🚶 Поведение",
                "selected_psych_markers": ["Боюсь отказов", "Боюсь выглядеть глупо"],
            },
            current_state=CareerFlow.waiting_for_barriers.state,
        )
        message = FakeMessage()
        message.text = "Боюсь отказов"
        await barriers_fallback(message, state)

        self.assertEqual(state.current_state, CareerFlow.waiting_for_barriers.state)
        self.assertGreaterEqual(message.answer.await_count, 1)
        payload = message.answer.await_args_list[-1].args[0]
        self.assertIn("уже выбран", payload.lower())


if __name__ == "__main__":
    unittest.main()
