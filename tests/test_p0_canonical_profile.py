from pathlib import Path

from services.canonical_profile import (
    build_canonical_profile,
    record_question_answer,
    select_clarifying_question,
)
from services.career_assessment import is_market_role_title
from services.career_assessment import build_deterministic_assessment, render_assessment_html, validate_career_assessment
from handlers.career import _build_profile_snapshot


TECHNICIAN = {
    "story_text": (
        "Я сервисный техник, 12 лет опыта. Живу в Porto. Право на работу есть. "
        "Русский — родной, португальский — A2-B1, английский — B1. "
        "Сейчас €1600 net, минимум €1800 net, цель €2200-2500 net. "
        "Пять-шесть выездов в день, болит спина, хочу уменьшить физическую нагрузку."
    ),
    "route_context": {
        "city": "Porto",
        "documents_and_work_rights": "Есть",
        "current_language_level": "Португальский A2-B1; английский B1",
        "minimum_monthly_income": "€1800 net / месяц",
        "desired_monthly_income": "€2200-2500 net / месяц",
        "income_urgency": "Нельзя увольняться до стабильного нового дохода",
        "work_preferences": "Найм или собственный сервис параллельно",
        "health_or_schedule_limits": "Уменьшить физическую нагрузку",
        "relocation_and_travel": "Без релокации, редкие командировки допустимы",
        "career_goal_type": "Остаться в технической области, изменить формат",
        "functions_to_preserve": "Диагностика и техническая экспертиза",
        "functions_to_avoid": "Постоянные выезды и тяжёлая физическая работа",
        "available_time_for_study": "До 6 часов в неделю",
    },
}


def test_complete_profile_does_not_ask_and_porto_resolves_portugal():
    profile = build_canonical_profile(TECHNICIAN, assessment_id="a-1")
    assert profile.latest_value("market_context")["country"] == "Portugal"
    assert profile.latest_value("market_context")["country_code"] == "PT"
    assert profile.latest_value("work_authorization") == "Есть"
    assert select_clarifying_question(profile) is None


def test_one_missing_critical_parameter_produces_one_concrete_question():
    profile = build_canonical_profile({"story_text": "Я бухгалтер с опытом."}, assessment_id="a-2")
    question = select_clarifying_question(profile)
    assert question is not None
    assert question.target_fact_type == "market_context"
    assert question.source_check_completed is True
    assert "стране проживания" in question.text
    assert "ещё" not in question.text


def test_country_and_income_are_not_asked_again_and_remain_structured():
    profile = build_canonical_profile(TECHNICIAN, assessment_id="a-3")
    assert "market_context" in profile.question_state.resolved_fact_types
    minimum = [f for f in profile.facts_of_type("income_requirement") if f.normalized_value.get("kind") == "minimum"]
    assert minimum
    assert all(f.assessment_id == "a-3" for f in profile.facts)
    assert all(f.fact_id and f.source_message_id and f.source_quote and f.created_at for f in profile.facts)


def test_unknown_is_skipped_and_never_repeated():
    profile = build_canonical_profile({"story_text": "Я бухгалтер."}, assessment_id="a-4")
    question = select_clarifying_question(profile)
    record_question_answer(profile, question, "не знаю")
    assert "target_market" in profile.question_state.skipped_gap_ids
    next_question = select_clarifying_question(profile)
    assert next_question is not None
    assert next_question.question_id != question.question_id


def test_five_question_limit_never_blocks_conclusion():
    profile = build_canonical_profile({}, assessment_id="a-5")
    profile.question_state.question_count = 5
    assert select_clarifying_question(profile) is None


def test_work_condition_and_undesirable_task_are_not_market_roles():
    assert not is_market_role_title("Специализация: пять-шесть выездов в день")
    assert not is_market_role_title("Не хочу вечерних звонков")
    assert is_market_role_title("Technical Support Specialist")


def test_original_long_message_is_not_truncated_in_fact_source_quote():
    story = "Porto " + ("очень подробный опыт " * 100)
    profile = build_canonical_profile({"story_text": story}, assessment_id="a-6")
    fact = profile.facts_of_type("market_context")[0]
    assert fact.source_quote == story


def test_old_gap_ledger_copy_is_removed_from_user_flow():
    source = Path("handlers/career.py").read_text(encoding="utf-8")
    assert "Для более точного заключения пока не хватает данных:" not in source
    assert "Я не буду блокировать результат" not in source
    assert "_missing_route_context_notice" not in source


def test_service_technician_gets_distinct_strategy_not_current_job_clones():
    data = {
        **TECHNICIAN,
        "assessment_id": "technician-e2e",
        "story_analysis": {
            "current_identity": "Сервисный техник",
            "confirmed_functions": ["Диагностика неисправностей", "Чтение электрических схем", "Объяснение технических решений"],
            "skills": ["Системная диагностика", "Коммуникация с клиентом"],
            "constraints": ["Нужно уменьшить физическую нагрузку", "Нельзя увольняться до стабильного нового дохода"],
            "functions_to_avoid": ["Постоянные выезды", "Тяжёлая физическая работа"],
            "target_roles": ["Technical Support Specialist", "Service Coordinator", "Technical Trainer", "Warranty Specialist"],
            "achievements": ["12 лет самостоятельной диагностики и ремонта оборудования"],
        },
    }
    snapshot = _build_profile_snapshot(data)
    assessment = build_deterministic_assessment(
        snapshot, data["story_analysis"], {}, assessment_id="technician-e2e",
        session_id="technician-session", profile_version="1",
    )
    assert validate_career_assessment(assessment, snapshot_country_code="PT", snapshot_currency="EUR").valid
    titles = [route.title for route in assessment.routes.all_routes()]
    assert len(titles) >= 4
    assert len(set(titles)) == len(titles)
    assert assessment.routes.primary_routes[0].title != "Сервисный техник"
    assert "Technical Support Specialist" in titles
    assert all("выездов в день" not in title.casefold() for title in titles)
    html = render_assessment_html(assessment)
    for section in ("Анализ по маршрутам", "Прогноз зарплаты или дохода", "Три сценария развития", "Что здесь легко не заметить"):
        assert section in html
