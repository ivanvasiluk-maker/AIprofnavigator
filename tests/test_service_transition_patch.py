import copy
import re

from services.career_assessment import build_deterministic_assessment, render_assessment_html, validate_career_assessment
from services.report_snapshot import build_report_snapshot


FUNCTIONS = [
    "диагностика неисправностей",
    "ремонт оборудования",
    "замена электрических и механических компонентов",
    "настройка оборудования",
    "организация 5–6 выездов в день",
    "взаимодействие с клиентами",
]


def _assessment():
    return build_deterministic_assessment(
        {
            "current_role": "Техник по ремонту профессиональных кофемашин и HoReCa-оборудования",
            "career_goal": "Уменьшить физическую нагрузку, сохранить технический опыт и не увольняться до стабильного дохода",
            "country_name": "Portugal",
            "work_authorization": {"country": "Portugal", "status": "confirmed"},
            "minimum_income": 1800,
            "target_income": "2200–2500",
            "currency": "EUR",
            "languages": ["English B1", "English B1", "Portuguese A2"],
        },
        {"current_role": "Техник по ремонту профессиональных кофемашин и HoReCa-оборудования", "confirmed_functions": FUNCTIONS},
        {}, assessment_id="service-transition", session_id="s", profile_version="1",
    )


def test_current_field_role_is_bridge_and_adjacent_routes_are_generated():
    assessment = _assessment()
    recommended = assessment.routes.by_id(assessment.routes.recommended_route_id)
    assert recommended.title != "Техник по ремонту профессиональных кофемашин и HoReCa-оборудования"
    assert recommended.title == "Service Coordinator / Service Dispatcher"
    adjacent = [route for route in assessment.routes.all_routes() if route.entry_path == "adjacent_transition"]
    assert len(adjacent) >= 2
    titles = {route.title for route in adjacent}
    assert "Technical Support Specialist" in titles
    assert "Maintenance Planner" in titles or "Warranty / Spare Parts Specialist" in titles
    assert all(len(route.transferable_functions) >= 2 for route in adjacent)
    assert assessment.identity.professional_core == ["Техник по ремонту профессиональных кофемашин и HoReCa-оборудования"]
    assert "5–6 выездов" not in " ".join(assessment.identity.professional_core)
    debug = assessment.metadata["route_generation_debug"]
    generated_titles = {row["title"] for row in debug["generated_route_candidates"]}
    assert {
        "Service Coordinator / Service Dispatcher",
        "Technical Support Specialist",
        "Maintenance Planner",
        "Warranty / Spare Parts Specialist",
        "Technical Sales Specialist",
    } <= generated_titles
    after_titles = [row["title"] for row in debug["route_candidates_after_filter"]]
    assert after_titles[:3] == [
        "Service Coordinator / Service Dispatcher",
        "Technical Support Specialist",
        "Maintenance Planner",
    ]
    scores = {row["title"]: row["score"] for row in debug["generated_route_candidates"]}
    assert scores["Service Coordinator / Service Dispatcher"] > scores["Техник по ремонту профессиональных кофемашин и HoReCa-оборудования"]


def test_authorization_language_renderer_and_scenarios_are_consistent():
    assessment = _assessment()
    assert not any("Юридическая доступность" in gap for route in assessment.routes.all_routes() for gap in route.missing)
    assert not any("право на работу" in question.casefold() for question in assessment.questions.unanswered_critical_questions)
    assert [item.language for item in assessment.context.current_languages].count("English B1") == 1
    assert len({scenario.route_id for scenario in assessment.scenarios}) == 3
    html = render_assessment_html(assessment)
    assert not any(phrase in html for phrase in ("применение функций", "маршрут использует подтверждённую основу", "модель оклад", "уровень поддержан", "профессиональная модель оплаты"))
    numbers = [int(value) for value in re.findall(r"<h2>(\d+)\.", html)]
    assert numbers == list(range(1, len(numbers) + 1))


def test_money_survives_resume_merge_into_snapshot():
    snapshot = build_report_snapshot({
        "assessment_id": "money-resume-merge",
        "assessment": {"current_income": "1600 EUR", "minimum_income": "1800 EUR", "target_income": "2200–2500 EUR", "currency": "EUR"},
        "resume_analysis": {"responsibilities": FUNCTIONS[:2]},
        "resume_parse_status": "completed",
    })
    assert snapshot.facts["current_income"] == 1600
    assert snapshot.facts["minimum_income"] == 1800
    assert snapshot.facts["target_income_min"] == 2200
    assert snapshot.facts["target_income_max"] == 2500


def test_route_diversity_failure_is_not_hidden_by_medium_confidence():
    assessment = _assessment()
    broken = copy.deepcopy(assessment)
    broken.routes.transition_routes = []
    broken.routes.alternative_route_ids = []
    result = validate_career_assessment(broken)
    assert any(issue.code == "ROUTE_DIVERSITY_FAILURE" for issue in result.errors)
