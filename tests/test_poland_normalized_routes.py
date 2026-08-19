from handlers.career import _build_profile_snapshot
from services.career_assessment import build_deterministic_assessment
from services.canonical_profile import build_canonical_profile


CASE = {
    "assessment_id": "krakow-quality-transition",
    "story_text": (
        "Живу в Кракове, Польше, право на работу есть. Переезжать не хочу, гибрид подходит. "
        "Сейчас 7200 PLN net, минимум 7000 PLN net, цель 9000–10500 PLN net. "
        "Польский B2, английский B1. У меня 9 лет опыта. Руководил сменой и командой. "
        "Использую Root Cause Analysis, Excel, ERP и базовый Power BI. "
        "Хочу больше аналитики и не хочу постоянно находиться в цехе. "
        "Интересуют Quality Engineer, Supplier Quality, Production Planner, Data Analyst и Project Coordinator."
    ),
    "story_analysis": {
        "current_role": "Специалист по контролю качества",
        "confirmed_functions": [
            "контроль качества", "Root Cause Analysis", "анализ повторяющихся дефектов",
            "улучшение процессов", "координация подразделений", "работа с производственными данными",
        ],
        "skills": ["Excel", "ERP", "Power BI"],
        "management_experience": ["управление сменой и командой"],
        "target_change": ["больше аналитики", "уйти от постоянной работы в цехе"],
        "functions_to_avoid": ["постоянная работа в цехе"],
        "target_roles": [
            "Quality Engineer", "Supplier Quality", "Production Planner",
            "Manufacturing Data Analyst", "Project Coordinator в промышленности",
        ],
    },
}


def test_poland_profile_is_scalar_normalized_and_complete():
    profile = build_canonical_profile(CASE, assessment_id=CASE["assessment_id"])
    normalized = profile.normalized_profile

    assert normalized.country == "Poland"
    assert normalized.city == "Краков"
    assert normalized.target_market == "Краков / Poland"
    assert len(normalized.target_market) < 40
    assert normalized.relocation_allowed is False
    assert normalized.hybrid_allowed is True
    assert normalized.work_rights is True
    assert normalized.current_income == 7200
    assert normalized.minimum_income == 7000
    assert normalized.target_income == "9000–10500"
    assert normalized.currency == "PLN"
    assert normalized.gross_net == "net"
    assert normalized.languages["Polish"] == "B2"
    assert normalized.languages["English"] == "B1"
    assert {"Excel", "ERP", "Power BI"} <= set(normalized.digital_tools)
    assert "управление сменой и командой" in normalized.management_experience


def test_skill_clusters_produce_distinct_ranked_transition_routes():
    snapshot = _build_profile_snapshot(CASE)
    assessment = build_deterministic_assessment(
        snapshot, CASE["story_analysis"], {},
        assessment_id=CASE["assessment_id"], session_id="session", profile_version="1",
    )
    routes = assessment.routes.all_routes()
    titles = [route.title for route in routes]

    assert len(routes) >= 3
    assert len({title.casefold() for title in titles}) == len(titles)
    assert assessment.routes.primary_routes[0].title != "Специалист по контролю качества"
    assert assessment.routes.primary_routes[0].ranking["desired_change_match"] == "high"
    assert any("Quality Engineer" in title or "Supplier Quality" in title for title in titles)
    assert any("Production Planner" in title or "Project Coordinator" in title for title in titles)
    assert any("Data Analyst" in title for title in titles)
    assert all({
        "experience_match", "desired_change_match", "income_risk", "training_gap",
        "physical_load_match", "language_risk", "location_match", "transition_speed",
        "overall_confidence",
    } <= set(route.ranking) for route in routes)
