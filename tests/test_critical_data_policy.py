from services.evidence_profile import (
    MAX_ADDITIONAL_QUESTIONS,
    CareerEvidenceProfile,
    apply_answer_to_profile,
    classify_profile_gaps,
    next_question_from_profile,
)


def test_gaps_have_explicit_importance_and_target_market_is_blocking() -> None:
    profile = CareerEvidenceProfile(unresolved_gaps=["target_country", "minimum_income", "support_and_load"])
    classified = classify_profile_gaps(profile)
    assert classified["blocking"] == ["target_country"]
    assert "minimum_income" in classified["useful"]


def test_unknown_answer_is_saved_and_not_reasked() -> None:
    profile = CareerEvidenceProfile(unresolved_gaps=["target_country"])
    apply_answer_to_profile(profile, "target_country", "не знаю")
    assert profile.target_countries[0].statement == "unknown"
    assert "target_country" not in profile.unresolved_gaps


def test_six_questions_is_hard_limit_and_report_can_continue() -> None:
    profile = CareerEvidenceProfile(unresolved_gaps=["residence_country", "target_country", "legal_access"])
    asked = {f"gap-{index}" for index in range(MAX_ADDITIONAL_QUESTIONS)}
    assert next_question_from_profile(profile, asked_gap_keys=asked) is None


def test_useful_transition_answers_are_persisted() -> None:
    profile = CareerEvidenceProfile(unresolved_gaps=["work_format", "relocation", "salary_target", "learning_capacity", "income_stepdown", "change_scale"])
    answers = {
        "work_format": "гибрид",
        "relocation": "нет",
        "salary_target": "3000 EUR gross/month employment",
        "learning_capacity": "5 часов в неделю",
        "income_stepdown": "до 10% на три месяца",
        "change_scale": "смежная роль",
    }
    for key, value in answers.items():
        apply_answer_to_profile(profile, key, value)
    assert profile.work_format_preferences[0].statement == "гибрид"
    assert profile.relocation_possible and profile.relocation_possible.statement == "нет"
    assert profile.salary_target and "EUR" in profile.salary_target.statement
    assert profile.learning_capacity and profile.learning_capacity.statement.startswith("5")
    assert profile.acceptable_income_drop and "10%" in profile.acceptable_income_drop.statement
    assert profile.desired_change_scale and profile.desired_change_scale.statement == "смежная роль"
    assert not profile.unresolved_gaps
