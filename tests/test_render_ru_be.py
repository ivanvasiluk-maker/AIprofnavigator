import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch

from reportlab.pdfgen import canvas

from handlers.career import (
    SEGMENT_ENTREPRENEUR,
    SEGMENT_WORKER,
    _decode_resume_bytes,
    _detect_user_segment,
    _set_mvp_questions,
    _start_questions_module,
    format_final_report,
    format_follow_up_questions,
    format_story_snapshot,
)
from handlers import voice as voice_handlers
from keyboards import (
    INPUT_TEXT,
    INPUT_VOICE,
    LANG_RU,
    RESUME_SKIP,
    RESUME_UPLOAD,
    RESULT_MONTH_PLAN,
    SKILLER_DONE,
    RESULT_TODAY_STEP,
    input_method_keyboard,
    restart_keyboard,
    result_actions_keyboard,
    resume_choice_keyboard,
    skiller_check_keyboard,
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


class FakeMessage:
    def __init__(self) -> None:
        self.answer = AsyncMock()


class CareerGpsRenderTests(unittest.TestCase):
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
        self.assertIn("Career GPS", t("ru", "start_intro"))
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

        actions_dump = result_actions_keyboard().model_dump_json()
        self.assertIn("Делать шаги в боте", actions_dump)
        self.assertIn("со специалистом", actions_dump)
        self.assertIn("уточнить", actions_dump)
        self.assertNotIn("📄 Скачать PDF", actions_dump)

        skiller_dump = skiller_check_keyboard().model_dump_json()
        self.assertIn(SKILLER_DONE, skiller_dump)

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
        self.assertIn("Career GPS", t("ru", "start_intro"))

    def test_follow_up_questions_normalized_to_minimum(self) -> None:
        questions = ai_client._normalize_question_count([{"id": 1, "block": "financial_pressure", "question": "Один вопрос?", "type": "short_text", "options": []}], "ru")
        self.assertGreaterEqual(len(questions), 8)
        self.assertLessEqual(len(questions), 12)
        self.assertTrue(all(isinstance(item, dict) for item in questions))

    def test_admin_profile_normalizes_generic_roles(self) -> None:
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
        self.assertEqual(normalized["career_recommendations"][0]["title"], "Administrative Assistant")
        self.assertEqual(normalized["market_analysis"][0]["profession"], "Administrative Assistant")
        self.assertEqual(normalized["career_translation"][0]["market_term"], "Administrative Assistant")
        self.assertEqual(normalized["career_decision"]["recommended_main_path"], "Administrative Assistant / Back-office Specialist")

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
        self.assertIn("Что не обнулилось", chunks[0])
        self.assertIn("Источники энергии", chunks[0])
        self.assertIn("Карьерные приоритеты", chunks[0])
        self.assertIn("STAR-компетенции", chunks[0])
        self.assertIn("Уровень ресурса", chunks[0])
        self.assertIn("medium (средний)", chunks[0])
        self.assertIn("Уровень интеграции", chunks[0])
        self.assertIn("low (низкий)", chunks[0])
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

    def test_set_mvp_questions_includes_energy_and_priorities_blocks(self) -> None:
        analysis = {"follow_up_questions": []}

        result = _set_mvp_questions(
            analysis,
            limit=16,
            mode="calm_steps",
            story_text="",
            user_segment=SEGMENT_WORKER,
        )
        questions = result.get("follow_up_questions", [])
        texts = [str(row.get("question", "")).lower() for row in questions if isinstance(row, dict)]

        self.assertTrue(any("энерги" in text for text in texts))
        self.assertTrue(any("приоритет" in text or "важнее" in text for text in texts))


class CareerGpsVoiceFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_questions_module_moves_to_interview(self) -> None:
        state = FakeState(
            data={
                "language": "ru",
                "story_text": "Нужна работа, есть опыт администрирования и документов, польский A2.",
                "story_analysis": {},
                "user_mode": "calm_steps",
                "max_questions": 4,
                "cv_uploaded": False,
            },
            current_state=CareerFlow.waiting_for_resume.state,
        )
        message = FakeMessage()

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


if __name__ == "__main__":
    unittest.main()
