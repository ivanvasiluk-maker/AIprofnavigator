from services.evidence_profile import (
    CareerEvidenceProfile,
    MAX_ADDITIONAL_QUESTIONS,
    apply_answer_to_profile,
    next_question_from_profile,
)
from services.market_strategy import (
    humanize_internal_values,
    income_calculator,
    preliminary_market_plan,
    validate_market_strategy,
)
from utils.reporting import build_meta, render_report_html


def _forecast(country="Lithuania", currency="EUR"):
    return {
        "route_id": "route-1", "country": country, "currency": currency,
        "amount_type": "gross", "period": "month", "contract_type": "employment",
        "data_date": "2026-08-18", "confidence": "medium",
        "conditions": ["подтверждённый уровень роли"],
        "sources": [
            {"source_url": "https://survey.example/a", "source_name": "Survey", "country": country, "data_type": "salary_survey", "confidence": "medium", "publication_date": "2026-06-01"},
            {"source_url": "https://jobs.example/b", "source_name": "Jobs", "country": country, "data_type": "vacancies", "confidence": "medium", "retrieved_at": "2026-08-18"},
        ],
        "estimates": {"conservative": 1000, "base": 1500, "optimistic": 2200},
    }


def _scenario(kind):
    return {
        "kind": kind, "market": "Lithuania", "horizon": "1-3 месяца", "goal": "Проверить модель",
        "employment_model": "гибрид", "income_forecast": "по подтверждённому прогнозу",
        "preserves": ["текущий доход"], "adds": ["новую модель"],
        "investment": "до 100 EUR", "hours_per_week": "5", "actions": ["один тест"],
        "checkpoints": ["10 откликов"], "success_criterion": "2 ответа",
        "stop_criterion": "0 ответов после серии", "risks": ["спрос"], "fallback": "сохранить текущий доход",
    }


def test_missing_country_is_asked_before_conclusion_and_limit_is_five():
    profile = CareerEvidenceProfile(unresolved_gaps=["residence_country", "target_country"])
    question = next_question_from_profile(profile)
    assert question and question["gap_key"] == "residence_country"
    assert MAX_ADDITIONAL_QUESTIONS == 5


def test_known_or_unknown_country_is_not_repeated():
    profile = CareerEvidenceProfile(unresolved_gaps=["residence_country", "target_country"])
    apply_answer_to_profile(profile, "residence_country", "Литва")
    assert next_question_from_profile(profile, asked_gap_keys={"residence_country"})["gap_key"] == "target_country"
    apply_answer_to_profile(profile, "target_country", "не знаю")
    assert not profile.unresolved_gaps


def test_no_live_market_data_never_invents_salary_or_source():
    result = preliminary_market_plan(None, "Instructional Designer")
    assert "зарплата не оценивалась" in result["limitation"]
    assert "source_url" not in result


def test_country_currency_and_salary_metadata_are_validated():
    report = {"market_context": {"target_country": "Lithuania"}, "market_analysis": [{}], "income_forecasts": [_forecast()]}
    assert validate_market_strategy(report) == []
    report["income_forecasts"][0]["currency"] = "PLN"
    assert any("currency" in error for error in validate_market_strategy(report))


def test_poland_and_lithuania_are_not_mixed():
    report = {"market_context": {"target_country": "Poland"}, "market_analysis": [{"country": "Lithuania"}]}
    assert any("not the selected country" in error for error in validate_market_strategy(report))


def test_regulated_route_requires_licensing_and_one_vacancy_is_insufficient():
    report = {"market_analysis": [{"country": "Germany", "regulated_profession": True, "vacancy_sample_size": 1}]}
    errors = validate_market_strategy(report)
    assert any("licensing" in error for error in errors)
    assert any("one vacancy" in error for error in errors)


def test_three_complete_scenarios_and_evidence_based_insights():
    report = {
        "development_scenarios": [_scenario("safe"), _scenario("main"), _scenario("ambitious")],
        "personal_insights": [
            {"insight": str(i), "evidence_fact_ids": ["f1", "f2"], "route_impact": "Выбор гибрида", "practical_consequence": "Проверить модель"}
            for i in range(3)
        ],
    }
    assert validate_market_strategy(report) == []


def test_internal_enums_are_never_rendered_to_user():
    value = humanize_internal_values({"assessment_id": "secret", "entry": "direct_entry", "note": "bridge_project"})
    assert "assessment_id" not in value
    assert value["entry"] == "можно начинать проверять сейчас"
    assert value["note"] == "сначала нужен подтверждающий проект"


def test_self_employment_calculators_are_transparent():
    assert income_calculator("group", price_per_participant=200, participants=8)["gross_revenue"] == 1600
    product = income_calculator("product", price=20, paying_users=100, acquisition_costs=300, infrastructure=100, support=100)
    assert product["forecast_income"] == 1500


def test_html_has_responsive_market_table_and_new_sections():
    report = {
        "market_context": {"target_country": "Lithuania"},
        "income_forecasts": [_forecast()],
        "development_scenarios": [_scenario("safe"), _scenario("main"), _scenario("ambitious")],
        "personal_insights": [{"insight": "Связь двух фактов", "evidence_fact_ids": ["f1", "f2"], "route_impact": "Выбор", "practical_consequence": "Тест"}],
        "career_action_plan": {"48_hours": "Шаблон", "14_days": "10 откликов", "90_days": "2 интервью"},
    }
    html = render_report_html(report, build_meta(report))
    assert "Что здесь легко не заметить" in html
    assert "Рынок выбранной страны" in html
    assert "table-scroll" in html and "@media (max-width: 640px)" in html
    assert "direct_entry" not in html
