from handlers.career import _build_profile_snapshot
from services.career_assessment import (
    build_deterministic_assessment,
    render_telegram_map,
)
from services.evidence_profile import CareerEvidenceProfile, apply_answer_to_profile


def test_long_multifactor_answers_are_routed_to_schema_fields_and_real_renderer():
    assessment_id = "berlin-runtime-regression"
    profile = CareerEvidenceProfile()
    profile = apply_answer_to_profile(
        profile,
        "residence_country",
        "Сейчас я живу в Берлине, в Германии, переезжать не хочу; работаю удалённо и могу работать гибридно.",
    )
    profile = apply_answer_to_profile(
        profile,
        "target_country",
        "И так и так: в Германии и на международном удалённом рынке.",
    )
    data = {
        "assessment_id": assessment_id,
        "evidence_profile": profile.model_dump(mode="json"),
        "story_text": "Работаю с документацией, базой знаний и обучением пользователей.",
        "story_analysis": {
            "current_role": "Customer Support Specialist",
            "confirmed_functions": [
                "создание документации и инструкций",
                "ведение базы знаний",
                "обучение пользователей",
                "структурирование сложной информации",
            ],
            "skills": ["troubleshooting", "межфункциональная коммуникация"],
            "desired_changes": ["уйти от потока однотипных обращений"],
            "career_hypotheses": [
                "Technical Writer / Documentation Specialist",
                "Knowledge Manager / Knowledge Base Manager",
                "Customer Education / Learning Content",
            ],
        },
        "minimum_income": "45000 EUR net / month",
        "target_income": "65000-80000 EUR net / year",
    }

    snapshot = _build_profile_snapshot(data)
    assessment = build_deterministic_assessment(
        snapshot,
        data["story_analysis"],
        {},
        assessment_id=assessment_id,
        session_id="runtime-test",
        profile_version="runtime-test-v1",
    )
    rendered = render_telegram_map(assessment)
    route_titles = [route.title for route in assessment.routes.all_routes()]

    assert snapshot["residence_country"] == "Germany"
    assert snapshot["city"] == "Berlin"
    assert snapshot["target_countries"] == ["Germany"]
    assert "и так и так" not in " ".join(snapshot["target_countries"]).casefold()
    assert len(route_titles) >= 3
    assert any("Technical Writer" in title for title in route_titles)
    assert assessment.context.market_data_confidence == "low"
    assert assessment.income_forecasts
    assert "Текущая профессиональная специализация" not in rendered
    assert "Текущая профессиональная специализация" not in str(assessment.to_dict())
