from services.career_assessment import (
    build_deterministic_assessment,
    is_valid_occupation_title,
    render_telegram_map,
)


MARIA_PROFILE = {
    "country_code": "PL",
    "country_name": "Польша",
    "current_role": "Начальник кредитного направления",
    "career_goal": "Найти новое направление",
    "languages": ["польский A2"],
    "story_text": "Мария два года живёт в Польше; вопрос 7: какое направление выбрать?",
}
MARIA_STORY = {
    "professional_core_hypotheses": ["Эмигрант в Польше, ищущий новое направление карьеры"],
    "confirmed_functions": [
        "организовывает работу кредитного отдела",
        "распределяет и контролирует задачи",
        "разрабатывает должностные обязанности",
        "управляет командой из 20 человек",
    ],
    "experience_snapshot": ["15 лет банковского опыта", "команда из 20 человек"],
    "seniority_hypotheses": ["руководитель, 15 лет опыта, команда 20 человек"],
    "explicit_refusals": ["Не хочу работать в польском банке"],
}


def build_maria():
    return build_deterministic_assessment(
        MARIA_PROFILE,
        MARIA_STORY,
        {},
        assessment_id="maria-pl",
        session_id="maria-session",
        profile_version="1",
    )


def test_life_context_is_not_occupation():
    assert not is_valid_occupation_title("Эмигрант в Польше, ищущий новое направление карьеры")
    assert not is_valid_occupation_title("Планирую найти новую карьеру")
    assert not is_valid_occupation_title("Хочу разобраться, кем работать дальше")
    assessment = build_maria()
    visible_roles = [*assessment.identity.professional_core, *(route.title for route in assessment.routes.all_routes())]
    assert all("эмигрант" not in value.casefold() and "ищущ" not in value.casefold() for value in visible_roles)


def test_explicit_rejection_blocks_route():
    assessment = build_maria()
    assert all(
        "банк" not in route.title.casefold() and "кредитн" not in route.title.casefold()
        for route in assessment.routes.all_routes()
    )
    assert assessment.routes.primary_routes[0].title in {
        "Operations Manager", "Business Operations Manager", "Process Improvement Specialist", "Team Operations Lead"
    }


def test_management_evidence_is_preserved():
    assessment = build_maria()
    assert any("20" in value for value in assessment.identity.professional_core)
    assert "15 лет" in assessment.identity.seniority_current
    assert "20" in assessment.identity.seniority_current


def test_report_has_decision_density():
    assessment = build_maria()
    titles = [route.title for route in assessment.routes.all_routes()]
    report = render_telegram_map(assessment).casefold()
    assert len(titles) >= 2 and all(is_valid_occupation_title(title) for title in titles)
    assert all(len(set(route.transferable_functions)) >= 2 for route in assessment.routes.all_routes())
    assert report.count(titles[0].casefold()) <= 3
    assert "вопрос 7" not in report
    assert all(claim not in report for claim in ("боюсь выглядеть глупо", "жду идеального плана", "откладываю"))
