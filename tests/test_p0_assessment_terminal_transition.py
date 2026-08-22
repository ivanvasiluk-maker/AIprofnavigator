import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.career import (
    ASSESSMENT_ASK_ONE_QUESTION,
    ASSESSMENT_GENERATE_REPORT,
    _build_evidence_questions,
    _real_route_titles,
    _resolved_fact_types,
    _ensure_preliminary_report,
    advance_assessment,
    handle_post_result_actions,
    process_answers_input,
    should_finalize_assessment,
)
from services.evidence_profile import build_evidence_profile_from_analysis
from services.hypothesis_engine import CareerHypothesis, ConversationTurn, format_conversation_turn
from keyboards import REPORT_CONTACT_SUPPORT, REPORT_RETRY, REPORT_SHORT_FALLBACK, report_failure_keyboard


SERGEY_ANALYSIS = {
    "current_role": "инженер-механик",
    "confirmed_functions": [
        "управление качеством",
        "анализ дефектов",
        "улучшение производственных процессов",
        "ведение технической документации",
    ],
    "experience_snapshot": ["17 лет инженерного и управленческого опыта"],
    "goals": ["перейти в техническую роль без people management"],
    "constraints": ["без ночных смен и увольнения до оффера"],
    "missing_data": [],
}


def sergey_data(**overrides):
    data = {
        "assessment_id": "sergey-assessment",
        "public_user_id": "sergey-user",
        "session_id": "sergey-session",
        "user_mode": "fast",
        "story_text": (
            "Живу в Брно, право на работу есть. Русский родной, чешский B1, английский B2. "
            "Минимум 45000 CZK, цель 55000-65000 CZK. Не готов к переезду, без ночных смен."
        ),
        "story_analysis": dict(SERGEY_ANALYSIS),
        "route_context": {
            "country": "Czech Republic",
            "city": "Brno",
            "documents_and_work_rights": "право на работу есть",
            "current_language_level": "Russian native; Czech B1; English B2",
            "minimum_monthly_income": "45000 CZK",
            "desired_monthly_income": "55000-65000 CZK",
            "work_preferences": "локально и удалённо по Европе",
            "health_or_schedule_limits": "без ночных смен",
            "available_time_for_study": "5-6 часов",
            "training_budget": "25000 CZK за 6 месяцев",
        },
        "question_count": 0,
        "final_report": {},
    }
    data.update(overrides)
    return data


class FakeState:
    def __init__(self, data):
        self.data = data
        self.state = None

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, value):
        self.state = value

    async def get_state(self):
        return self.state


class AssessmentTerminalTests(unittest.IsolatedAsyncioTestCase):
    def test_a_sufficient_initial_story_can_finalize(self):
        self.assertTrue(should_finalize_assessment(sergey_data()))

    async def test_b_resume_completed_step_generates_report(self):
        state = FakeState(sergey_data(resume_analysis={"confirmed_functions": ["quality", "process"]}))
        message = SimpleNamespace(answer=AsyncMock())
        with patch("handlers.career._maybe_trigger_career_finalization", new=AsyncMock()) as generate:
            action = await advance_assessment(message, state, trigger="resume_parsed")
        self.assertEqual(action, ASSESSMENT_GENERATE_REPORT)
        generate.assert_awaited_once()

    def test_c_known_facts_are_resolved(self):
        resolved = _resolved_fact_types(sergey_data())
        self.assertTrue({"country", "city", "work_authorization", "work_languages", "minimum_income", "target_market"} <= resolved)

    async def test_d_quick_mode_does_not_start_diagnostics(self):
        from handlers.career import _maybe_offer_extended_diagnostics
        state = FakeState(sergey_data())
        self.assertFalse(await _maybe_offer_extended_diagnostics(SimpleNamespace(), state, "ru"))

    async def test_e_route_selection_is_terminal(self):
        state = FakeState(sergey_data())
        message = SimpleNamespace(answer=AsyncMock())
        with patch("handlers.career._maybe_trigger_career_finalization", new=AsyncMock()) as generate:
            action = await advance_assessment(message, state, trigger="route_selected")
        self.assertEqual(action, ASSESSMENT_GENERATE_REPORT)
        generate.assert_awaited_once()

    async def test_f_psychology_done_sends_and_generates(self):
        state = FakeState(sergey_data(psychology_step="completed"))
        message = SimpleNamespace(answer=AsyncMock())
        with patch("handlers.career._maybe_trigger_career_finalization", new=AsyncMock()) as generate:
            action = await advance_assessment(message, state, trigger="psychology_done")
        self.assertEqual(action, ASSESSMENT_GENERATE_REPORT)
        message.answer.assert_awaited()
        generate.assert_awaited_once()

    def test_g_psychology_is_not_required(self):
        self.assertTrue(should_finalize_assessment(sergey_data(psychology_step="optional")))

    async def test_h_no_silent_terminal_transition(self):
        state = FakeState(sergey_data())
        message = SimpleNamespace(answer=AsyncMock())
        with patch("handlers.career._maybe_trigger_career_finalization", new=AsyncMock()):
            await advance_assessment(message, state, trigger="questions_completed")
        self.assertGreater(message.answer.await_count, 0)

    def test_i_routes_are_real_role_titles(self):
        self.assertEqual(
            _real_route_titles(SERGEY_ANALYSIS)[:3],
            ["Quality Engineer", "Process Improvement Specialist", "Quality Systems / Documentation Specialist"],
        )

    def test_j_quick_mode_has_one_question_limit(self):
        profile = build_evidence_profile_from_analysis({"missing_data": ["страна", "язык", "доход"]})
        self.assertLessEqual(len(_build_evidence_questions(profile, "ru", "fast")), 1)

    def test_k_deep_mode_has_five_question_limit(self):
        profile = build_evidence_profile_from_analysis({"missing_data": ["страна", "язык", "доход", "документы", "ограничения", "формат"]})
        self.assertLessEqual(len(_build_evidence_questions(profile, "ru", "deep_route")), 5)

    def test_l_question_has_no_duplicate_confirmation_prefix(self):
        turn = ConversationTurn(
            action="confirm_hypothesis",
            reason="test",
            hypothesis=CareerHypothesis(statement="Сильная сторона — качество", evidence=[], confidence="probable"),
        )
        self.assertEqual(format_conversation_turn(turn, next_question_text="Какой доход вам нужен?", lang="ru"), "Какой доход вам нужен?")

    async def test_m_ask_one_question_is_executed_by_orchestrator(self):
        state = FakeState({
            "assessment_id": "incomplete",
            "user_mode": "fast",
            "story_analysis": {"missing_data": ["профессиональное ядро"]},
            "evidence_profile": build_evidence_profile_from_analysis({"missing_data": ["профессиональное ядро"]}).model_dump(),
            "question_count": 0,
        })
        message = SimpleNamespace(answer=AsyncMock())
        action = await advance_assessment(message, state, trigger="assessment_started")
        self.assertEqual(action, ASSESSMENT_ASK_ONE_QUESTION)
        self.assertEqual(state.data["question_count"], 1)
        message.answer.assert_awaited_once()

    async def test_n_real_psychology_handler_calls_orchestrator(self):
        state = FakeState({
            "language": "ru",
            "story_analysis": {"follow_up_questions": [{
                "id": 1,
                "question": "Что мешает?",
                "options": ["Страх", "✅ Психология: готово"],
                "multi_key": "psych",
                "done_text": "✅ Психология: готово",
                "max_select": 3,
            }]},
            "qa_index": 0,
            "qa_answers": [],
            "psych_selected": ["Страх"],
            "user_mode": "fast",
            "interaction_profile": {},
        })
        message = SimpleNamespace(answer=AsyncMock(), chat=SimpleNamespace(id=42), from_user=SimpleNamespace(id=42), message_id=7)
        with patch("handlers.career._update_evidence_after_answer", return_value=({}, False)), \
             patch("handlers.career._sync_interview_context_after_answer", new=AsyncMock()), \
             patch("handlers.career.advance_assessment", new=AsyncMock(return_value=ASSESSMENT_GENERATE_REPORT)) as advance:
            await process_answers_input(message, state, "✅ Психология: готово")
        self.assertEqual(state.data["psychology_step"], "completed")
        advance.assert_awaited_once()

    def test_o_report_failure_keyboard_has_exact_actions(self):
        labels = [button.text for row in report_failure_keyboard().keyboard for button in row]
        self.assertEqual(labels, [REPORT_RETRY, REPORT_SHORT_FALLBACK, REPORT_CONTACT_SUPPORT])

    async def test_p_short_fallback_action_always_replies(self):
        report = {"career_decision": {"recommended_main_path": "Quality Engineer"}}
        state = FakeState({"language": "ru", "final_report": report, "final_report_generated": True})
        message = SimpleNamespace(answer=AsyncMock(), text=REPORT_SHORT_FALLBACK)
        await handle_post_result_actions(message, state)
        message.answer.assert_awaited_once()

    def test_q_failure_fallback_replaces_descriptive_sentence_with_real_route(self):
        data = sergey_data(resume_analysis={
            "confirmed_functions": ["контроль качества", "улучшение процессов", "техническая документация"]
        })
        report = {"career_decision": {"recommended_main_path": "Сергей имеет опыт в управлении и контроле качества на производстве."}}
        fallback = _ensure_preliminary_report(report, data)
        self.assertEqual(fallback["career_decision"]["recommended_main_path"], "Quality Engineer")
        self.assertEqual(fallback["career_decision"]["backup_path"], "Process Improvement Specialist")

    async def test_r_retry_uses_exception_safe_finalization_wrapper(self):
        state = FakeState(sergey_data(final_report={"status": "preliminary"}, final_report_generated=True))
        message = SimpleNamespace(
            answer=AsyncMock(),
            text=REPORT_RETRY,
            from_user=SimpleNamespace(id=42),
            chat=SimpleNamespace(id=42),
        )
        with patch("handlers.career.finalize_career_flow", new=AsyncMock()) as finalize, \
             patch("handlers.career._build_and_send_report", new=AsyncMock()) as direct_build:
            await handle_post_result_actions(message, state)
        finalize.assert_awaited_once_with("sergey-user", "sergey-session", "user_retry")
        direct_build.assert_not_awaited()
        self.assertFalse(state.data["report_generation_in_progress"])


if __name__ == "__main__":
    unittest.main()
