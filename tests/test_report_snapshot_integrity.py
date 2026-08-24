from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

from handlers.career import _build_and_send_career_assessment
from keyboards import snapshot_failure_keyboard
from services.career_assessment import build_deterministic_assessment, render_assessment_html
from services.report_snapshot import build_report_snapshot, structured_identity_summary, validate_report_consistency, validate_report_snapshot
from states import CareerFlow


ASSESSMENT_ID = "sergey-one-assessment"
STORY = (
    "Меня зовут Сергей, мне 46 лет. Живу в Брно, Чехия. Право на работу есть, переезжать не хочу. "
    "Я инженер-механик с 17-летним опытом производства медицинского оборудования. Руководил командой из 14 человек. "
    "Контролировал качество, анализировал причины брака, улучшал процессы, писал техническую документацию, "
    "готовился к аудитам; возвраты снизились на 20%. Получаю 42000 CZK net, минимум 45000 CZK, цель 55000-65000 CZK. "
    "Русский родной, чешский B1, английский B2."
)


def sergey_data(**updates):
    analysis = {
        "current_role": "Инженер-механик",
        "confirmed_functions": [
            "контроль качества", "анализ причин брака", "улучшение процессов",
            "техническая документация", "подготовка к аудитам",
        ],
        "goals": ["перейти в техническую роль без ночных смен"],
        "constraints": ["без ночных смен", "без увольнения до оффера"],
    }
    resume = {
        "confirmed_functions": analysis["confirmed_functions"],
        "achievements": ["снижение возвратов на 20%"],
        "current_role": "Инженер-механик",
    }
    data = {
        "assessment_id": ASSESSMENT_ID,
        "public_user_id": "telegram-ivan-access-only",
        "profile_version": "3b9ddd23a9ea47188b6779946d8c17e5",
        "user_mode": "fast",
        "story_text": STORY,
        "story_analysis": analysis,
        "resume_analysis": resume,
        "resume_parse_status": "completed",
        "cv_uploaded": True,
        "selected_preliminary_route": "Quality Engineer",
        "source_messages": [{"assessment_id": ASSESSMENT_ID, "message_id": "story", "text": STORY}],
        "uploaded_documents": [{"assessment_id": ASSESSMENT_ID, "document_id": "resume", "content": "CV Сергея"}],
        "qa_answers": [],
        "resolved_fact_types": ["country", "work_languages", "work_authorization", "minimum_income"],
    }
    data.update(updates)
    return data


def test_a_all_snapshot_sources_share_assessment_id():
    snapshot = build_report_snapshot(sergey_data())
    assert snapshot.assessment_id == ASSESSMENT_ID
    assert snapshot.source_status["source_assessment_ids"] == [ASSESSMENT_ID]


def test_b_story_name_wins_over_telegram_identity():
    snapshot = build_report_snapshot(sergey_data())
    assert snapshot.person_name == "Сергей"
    assert "Иван" not in str(snapshot.model_dump())


def test_c_country_and_city_survive_story_merge():
    snapshot = build_report_snapshot(sergey_data())
    assert snapshot.market_context["country"] == "Czech Republic"
    assert snapshot.market_context["city"] == "Brno"


def test_d_completed_resume_is_loaded_everywhere():
    snapshot = build_report_snapshot(sergey_data())
    assert snapshot.resume["loaded"] is True
    assert snapshot.source_status["resume_loaded"] is True


def test_e_fast_mode_is_preserved_as_quick_not_growth():
    snapshot = build_report_snapshot(sergey_data())
    assert snapshot.mode == "quick"
    assert "Growth" not in str(snapshot.model_dump())


def test_f_selected_quality_route_has_current_assessment_evidence():
    selected = build_report_snapshot(sergey_data()).routes["selected"]
    assert selected["status"] == "user_selected_hypothesis"
    assert len(selected["confirmed_functions"]) >= 2
    assert any("качест" in item.casefold() for item in selected["evidence"])


def test_f2_supported_selected_route_is_final_recommendation():
    snapshot = build_report_snapshot(sergey_data())
    facts = snapshot.facts
    profile = {
        **facts,
        "assessment_id": ASSESSMENT_ID,
        "country_name": facts["country"],
        "selected_route": snapshot.routes["selected"],
        "route_hypotheses": snapshot.routes["hypotheses"],
        "ready_for_report": True,
    }
    assessment = build_deterministic_assessment(
        profile, snapshot.story["analysis"], snapshot.resume["analysis"],
        assessment_id=ASSESSMENT_ID, session_id="session", profile_version=snapshot.profile_version,
    )
    recommended = assessment.routes.by_id(assessment.routes.recommended_route_id)
    assert recommended is not None
    assert recommended.title == "Quality Engineer"
    assert "SUPPORTED_SELECTED_ROUTE_DROPPED" not in validate_report_consistency(snapshot, assessment.to_dict())
    assert "SUPPORTED_SELECTED_ROUTE_NOT_RECOMMENDED" not in validate_report_consistency(snapshot, assessment.to_dict())


def test_f3_normalized_mode_and_non_czech_locations_are_preserved():
    cases = [
        ("quick", "Живу в Порту, Португалия.", "Portugal", "Porto"),
        ("deep", "Живу в Вильнюсе, Литва.", "Lithuania", "Vilnius"),
    ]
    for index, (mode, story, country, city) in enumerate(cases):
        data = sergey_data(
            assessment_id=f"location-{index}",
            user_mode=None,
            mode=mode,
            story_text=f"Меня зовут Сергей. {story} Контролировал качество и улучшал процессы.",
            source_messages=[],
            uploaded_documents=[],
        )
        snapshot = build_report_snapshot(data)
        assert snapshot.mode == mode
        assert snapshot.facts["country"] == country
        assert snapshot.facts["city"] == city
        assert validate_report_snapshot(snapshot, data["story_text"]) == []


def test_f4_location_claim_cannot_silently_lose_country_or_city():
    snapshot = build_report_snapshot(sergey_data())
    broken = snapshot.model_copy(update={"facts": {**snapshot.facts, "country": None, "city": None}})
    errors = validate_report_snapshot(broken, "Живу в Порту, Португалия.")
    assert "COUNTRY_LOST_FROM_STORY" in errors
    assert "CITY_LOST_FROM_STORY" in errors


def test_f5_semantic_validator_rejects_dropped_supported_selection():
    snapshot = build_report_snapshot(sergey_data())
    assessment = {
        "assessment_id": ASSESSMENT_ID,
        "metadata": {"report_mode": "quick", "resume_loaded": True},
        "routes": {
            "primary_routes": [{"route_id": "current", "title": "Инженер-механик"}],
            "transition_routes": [],
            "recommended_route_id": "current",
        },
    }
    errors = validate_report_consistency(snapshot, assessment)
    assert "SUPPORTED_SELECTED_ROUTE_DROPPED" in errors
    assert "SUPPORTED_SELECTED_ROUTE_NOT_RECOMMENDED" in errors


def test_g_production_assessment_renderer_is_single_contract():
    snapshot = build_report_snapshot(sergey_data())
    facts = snapshot.facts
    profile = {**facts, "assessment_id": ASSESSMENT_ID, "country_name": facts["country"], "ready_for_report": True}
    assessment = build_deterministic_assessment(
        profile, snapshot.story["analysis"], snapshot.resume["analysis"],
        assessment_id=ASSESSMENT_ID, session_id="session", profile_version=snapshot.profile_version,
    )
    html = render_assessment_html(assessment)
    assert "Подробный анализ по 15 блокам" not in html
    assert html.count("1. Короткое человеческое резюме") == 1


def test_h_valid_snapshot_has_no_empty_fallback_markers():
    snapshot = build_report_snapshot(sergey_data())
    blob = str(snapshot.model_dump())
    assert "Возможный маршрут" not in blob
    assert "данных недостаточно" not in blob.casefold()


def test_i_cross_section_validator_rejects_contradictions():
    snapshot = build_report_snapshot(sergey_data())
    assessment = {"assessment_id": ASSESSMENT_ID, "metadata": {"report_mode": "quick", "resume_loaded": True}, "note": "Критичных неизвестных нет; данных недостаточно"}
    assert "CONTRADICTORY_UNCERTAINTY" in validate_report_consistency(snapshot, assessment)


def test_j_raw_story_is_not_part_of_generator_snapshot_story():
    snapshot = build_report_snapshot(sergey_data())
    assert "text" not in snapshot.story
    assert STORY not in str(snapshot.story)
    summary = structured_identity_summary(snapshot)
    assert summary.startswith("Сергей — инженер-механик с 17-летним опытом")
    assert STORY not in summary


def test_k_empty_functions_make_snapshot_invalid_and_cross_assessment_is_rejected():
    data = sergey_data(
        story_analysis={}, resume_analysis={}, resume_parse_status="not_provided",
        uploaded_documents=[{"assessment_id": "foreign-assessment", "content": "foreign"}],
        selected_preliminary_route="",
    )
    errors = validate_report_snapshot(build_report_snapshot(data), STORY)
    assert "PROFESSIONAL_FUNCTIONS_MISSING" in errors
    assert "CROSS_ASSESSMENT_SOURCE" in errors


class FakeState:
    def __init__(self, data):
        self.data = dict(data)
        self.state = None

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, state):
        self.state = state


def test_l_invalid_snapshot_sends_short_recovery_instead_of_pdf():
    async def run():
        state = FakeState(sergey_data(story_analysis={}, resume_analysis={}, resume_parse_status="not_provided", selected_preliminary_route=""))
        message = SimpleNamespace(answer=AsyncMock(), from_user=SimpleNamespace(id=1), chat=SimpleNamespace(id=1))
        await _build_and_send_career_assessment(message, state, "ru", state.data)
        assert state.state == CareerFlow.REPORT_GENERATION_FAILED
        assert state.data["report_generation_status"] == "SNAPSHOT_INVALID"
        assert "Не буду показывать пустой шаблон" in message.answer.await_args.args[0]
        labels = [button.text for row in snapshot_failure_keyboard().keyboard for button in row]
        assert labels == ["Повторить сборку", "Проверить сохранённые факты", "Получить краткое заключение", "Поддержка"]
    asyncio.run(run())
