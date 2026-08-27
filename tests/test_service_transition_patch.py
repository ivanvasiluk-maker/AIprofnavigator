import copy
import re

from services.career_assessment import (
    CareerScenario,
    build_deterministic_assessment,
    render_assessment_html,
    render_personalized_ai_prompt,
    render_short_conclusion,
    validate_career_assessment,
    validated_assessment_result,
)
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


def test_sergey_routes_income_and_contamination_regression():
    assessment = build_deterministic_assessment(
        {
            "current_role": "Operations / Project Manager",
            "career_goal": (
                "Хочу выбрать между project management, business analysis, L&D, HR, "
                "AI/automation и собственным консалтингом. Цель 3500-4000 EUR net через 12-24 months."
            ),
            "country_name": "Литва",
            "city": "Вильнюс",
            "currency": "EUR",
            "current_income": "2300 EUR net",
            "minimum_income": "3000 EUR net",
            "target_income": "3500-4000 EUR net через 12-24 months",
            "languages": ["Russian C2", "English B2"],
            "target_roles": [
                "Project Management",
                "Business Analysis",
                "L&D",
                "HR",
                "AI/automation",
                "собственный консалтинг",
            ],
            "selected_career_priorities": ["Не обнулять опыт", "Рост дохода"],
        },
        {
            "current_role": "Operations / Project Manager",
            "confirmed_functions": [
                "анализ рабочих процессов",
                "структурирование хаотичной работы",
                "координация команды",
                "обучение пользователей",
                "автоматизация рутинных операций",
            ],
            "skills": ["business analysis", "project management", "L&D", "AI automation"],
            "tasks_to_avoid": ["много созвонов без результата"],
            "interests": [
                "Project Management",
                "Business Analysis",
                "L&D",
                "HR",
                "AI/automation",
                "собственный консалтинг",
            ],
        },
        {},
        assessment_id="sergey-routes",
        session_id="sergey-session",
        profile_version="1",
    )

    assert assessment.metadata["income"]["current_income"] == 2300
    assert assessment.metadata["income"]["target_income_low"] == 3500
    assert assessment.metadata["income"]["target_income_high"] == 4000
    assert assessment.metadata["income"]["target_income_type"] == "net"
    assert len(assessment.routes.candidate_routes) >= 8
    assert assessment.routes.excluded_routes
    assert assessment.questions.unanswered_critical_questions

    result = validated_assessment_result(assessment)
    user_titles = {item["title"] for item in result["user_proposed_routes"]}
    ai_titles = {item["title"] for item in result["ai_discovered_routes"]}
    assert {"Project Management", "Business Analysis", "L&D", "HR", "AI/automation"} <= user_titles
    assert not {"Project Management", "Business Analysis", "L&D"} & ai_titles

    short = render_short_conclusion(result)
    assert "Варианты, которые назвали вы" in short
    assert "Оценка ваших вариантов" in short
    assert "Новых гипотез ИИ нет" not in short

    prompt = render_personalized_ai_prompt(result)
    assert "3500–4000 EUR / month" in prompt
    assert "Weekly workflow" in prompt

    html = render_assessment_html(assessment).casefold()
    assert "целевой доход" in html
    assert "3500 eur / month" in html
    assert "источник — ваш вариант" in html
    assert "источник — гипотеза ии" in html
    assert "<p><strong>совпавшие функции:</strong></p><ul></ul>" not in html
    assert "ежедневная проверяемая работа здесь — ежедневная работа" not in html
    assert "не заявлен без сопоставимого источника" not in html
    for forbidden in ("physical work", "travel", "production planner", "физическ", "выезд", "производственн"):
        assert forbidden not in html


def test_unsupported_personal_claim_guardrail_rejects_contamination():
    assessment = build_deterministic_assessment(
        {"current_role": "Operations Manager", "target_income": "3500 EUR", "currency": "EUR"},
        {
            "current_role": "Operations Manager",
            "confirmed_functions": ["анализ процессов", "координация команды", "обучение пользователей"],
        },
        {},
        assessment_id="unsupported-claim",
        session_id="s",
        profile_version="1",
    )
    assessment.scenarios = [
        CareerScenario(
            "safe",
            assessment.routes.recommended_route_id,
            "1 месяц",
            "Проверить маршрут",
            "Найм",
            ["анализ процессов"],
            ["Меньше physical work and travel"],
            "Доход проверить",
            "4 часа",
            "Минимальные",
            ["проверить вакансии"],
            ["10 вакансий"],
            "есть спрос",
            "нет спроса",
            "вернуться к текущей роли",
        )
    ]

    validation = validate_career_assessment(assessment)
    assert any(issue.code == "UNSUPPORTED_PERSONAL_CLAIM" for issue in validation.errors)
