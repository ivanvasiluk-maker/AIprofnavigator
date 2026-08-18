from handlers.career import _build_profile_snapshot
from services.career_assessment import (
    build_deterministic_assessment,
    render_assessment_html,
    render_telegram_map,
    validate_career_assessment,
)


PROFILES = {
    "porto_technician": {
        "story_text": "Я сервисный техник в Порту, 12 лет ремонтирую оборудование. Право на работу есть. English — B1.",
        "story_analysis": {
            "current_identity": "Сервисный техник",
            "confirmed_functions": ["диагностика оборудования", "ремонт оборудования", "консультация клиентов"],
            "constraints": ["боль в спине и необходимость уменьшить физическую нагрузку"],
            "target_roles": ["Специалист удалённой технической поддержки", "Координатор сервисных работ", "Технический тренер"],
            "seniority_hypotheses": ["Старший технический специалист"],
        },
        "route_context": {"city": "Porto", "minimum_monthly_income": "1800", "desired_monthly_income": "2200"},
    },
    "vilnius_psychologist": {
        "story_text": "Я психолог в Вильнюсе, веду частную практику и группы. Право на работу есть. English — B2.",
        "story_analysis": {
            "current_identity": "Психолог-консультант",
            "confirmed_functions": ["индивидуальные консультации", "ведение групп", "разработка образовательных программ"],
            "interests": ["частная практика", "обучение специалистов"],
            "target_roles": ["Психолог-консультант в корпоративной программе поддержки", "Ведущий психообразовательных программ", "Супервизор частной практики"],
            "seniority_hypotheses": ["Опытный практикующий специалист"],
        },
        "route_context": {"city": "Vilnius", "minimum_monthly_income": "2000", "desired_monthly_income": "3000"},
    },
    "it_marketer": {
        "story_text": "Восемь лет руковожу IT-маркетингом, исследую B2B-клиентов и отвечаю за позиционирование. English — B2.",
        "story_analysis": {
            "current_identity": "Руководитель IT-маркетинга",
            "confirmed_functions": ["исследование рынка", "позиционирование B2B-продуктов", "управление маркетинговой командой"],
            "target_roles": ["Product Marketing Manager", "Customer Insights Lead", "EdTech Program Manager"],
            "seniority_hypotheses": ["Senior / lead в маркетинге"],
        },
        "route_context": {"city": "Vilnius", "minimum_monthly_income": "2500", "desired_monthly_income": "3500"},
    },
}


def build(name: str):
    data = {**PROFILES[name], "assessment_id": name}
    snapshot = _build_profile_snapshot(data)
    assessment = build_deterministic_assessment(
        snapshot,
        data["story_analysis"],
        {},
        assessment_id=name,
        session_id=f"session-{name}",
        profile_version="p0",
        fallback_reason="p0_renderer_test",
    )
    assert validate_career_assessment(
        assessment,
        snapshot_country_code=str(snapshot["country_code"]),
        snapshot_currency=str(snapshot["currency"]),
    ).valid
    return assessment


def test_three_real_renderers_are_country_aware_distinct_and_isolated():
    assessments = {name: build(name) for name in PROFILES}
    rendered = {name: render_telegram_map(value) + render_assessment_html(value) for name, value in assessments.items()}

    assert "Portugal" in rendered["porto_technician"] and "EUR" in rendered["porto_technician"]
    assert "Lithuania" in rendered["vilnius_psychologist"] and "EUR" in rendered["vilnius_psychologist"]
    assert "Lithuania" in rendered["it_marketer"] and "EUR" in rendered["it_marketer"]
    assert "актуальный датированный источник не получен" in rendered["porto_technician"].casefold()

    for name, assessment in assessments.items():
        routes = assessment.routes.all_routes()
        assert len(routes) >= 3
        assert len({route.title.casefold() for route in routes}) == len(routes)
        assert len({route.why_it_fits for route in routes}) == len(routes)
        assert len({tuple(route.risks) for route in routes}) == len(routes)
        assert len({tuple(route.missing) for route in routes}) == len(routes)
        assert len({route.market_test for route in routes}) == len(routes)
        assert len({scenario.route_id for scenario in assessment.scenarios}) >= 2

    assert assessments["porto_technician"].routes.primary_routes[0].title != "Сервисный техник"
    assert assessments["vilnius_psychologist"].routes.primary_routes[0].title != "Психолог-консультант"
    assert assessments["it_marketer"].routes.primary_routes[0].title != "Руководитель IT-маркетинга"

    assert "Психолог-консультант" not in rendered["porto_technician"]
    assert "Сервисный техник" not in rendered["vilnius_psychologist"]
    assert "Product Marketing Manager" not in rendered["porto_technician"]
    assert "боль в спине" not in rendered["vilnius_psychologist"].casefold()


def test_html_table_has_mobile_card_labels_and_no_internal_enums():
    html = render_assessment_html(build("porto_technician"))
    assert 'data-label="Маршрут"' in html
    assert "td::before" in html
    for internal in ("direct_entry", "adjacent_transition", "bridge_project", "route_check_required"):
        assert internal not in html
