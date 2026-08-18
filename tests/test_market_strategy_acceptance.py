from services.market_strategy import resolve_city_country, validate_market_strategy
from services.career_assessment import career_assessment_from_dict
from tests.test_career_assessment import profile_10_assessment_payload


def _source(country, suffix):
    return {"source_url": f"https://{suffix}.example/{suffix}", "source_name": suffix, "country": country, "publication_date": "2026-07-01", "data_type": "official_statistics", "confidence": "medium"}


def _vacancy():
    return {"title": "Role", "country": "Lithuania", "work_mode": "hybrid", "language": "Lithuanian", "level": "middle", "required_skills": ["skill"], "preferred_skills": [], "licenses": [], "contract_type": "employment", "source_url": "https://jobs.example/role"}


def _route(index):
    return {"route_id": f"r{index}", "title": f"Route {index}", "income_model": ["employment", "b2b", "product"][index - 1], "buyer_type": ["employer", "company", "consumer"][index - 1], "daily_tasks": [f"task {index}"], "risk_level": "medium", "entry_time": "3 months", "requirements": ["skill"], "income_ceiling": "source-dependent", "scalability": "medium", "psychological_load": "medium"}


def _scenario(kind):
    return {"kind": kind, "market": "Lithuania", "horizon": "1-3 months", "goal": "test", "employment_model": "hybrid", "preserves": ["income"], "adds": ["route"], "income_forecast": "see forecast", "investment": "100 EUR", "hours_per_week": "5", "actions": ["send offer"], "checkpoints": ["10 contacts"], "success_criterion": "2 replies", "stop_criterion": "0 replies", "risks": ["demand"], "fallback": "current work"}


def _action(label):
    return {"what": label, "where": "LinkedIn", "audience": "employers", "volume": "10", "duration": "2 hours", "success_criterion": "2 replies", "change_criterion": "0 replies"}


def complete_strategy():
    sources = [_source("Lithuania", "official"), _source("Lithuania", "jobs")]
    return {
        "market_strategy_required": True,
        "evidence_fact_ids": ["f1", "f2", "f3"],
        "market_context": {"residence_country": "Lithuania", "target_countries": ["Lithuania"], "remote_market": "EU"},
        "route_hypotheses": [{"title": f"H{i}"} for i in range(6)],
        "selected_routes": [_route(1), _route(2), _route(3)],
        "market_analysis": [{"route_id": "r1", "country": "Lithuania", "local_market": True, "language_analysis": "Lithuanian required locally; English varies", "market_claims": ["demand"], "sources": sources, "vacancy_sample_size": 10, "vacancies": [_vacancy() for _ in range(10)], "regulated_profession": False}],
        "income_forecasts": [{"route_id": "r1", "country": "Lithuania", "currency": "EUR", "amount_type": "gross", "period": "month", "contract_type": "employment", "data_date": "2026-08-18", "confidence": "medium", "sources": sources, "estimates": {"conservative": 1000, "base": 1500, "optimistic": 2000}, "conditions": ["role fit"]}],
        "development_scenarios": [_scenario("safe"), _scenario("main"), _scenario("ambitious")],
        "personal_insights": [{"insight": f"Insight {i}", "evidence_fact_ids": ["f1", "f2"], "route_impact": "hybrid", "practical_consequence": "test"} for i in range(3)],
        "psychological_social_conditions": [{"factor_type": "avoidance", "evidence_fact_ids": ["f3"], "career_impact": "fewer applications", "riskier_scenario": "main", "environment_change": "accountability", "behavioral_tool": "one application daily; evaluate after ten"}],
        "career_action_plan": {"48_hours": _action("prepare template"), "14_days": _action("run route test"), "90_days": _action("reach interviews")},
        "final_recommendation": {"recommended_route_id": "r1", "why": "best evidence", "why_not_competitors": ["higher risk"], "realistic_income": "see sourced forecast", "first_action": "prepare template", "pre_investment_check": "10 market signals", "review_date": "2026-09-18", "next_scenario_condition": "2 replies"},
    }


def test_complete_lithuania_strategy_passes_strict_contract():
    assert validate_market_strategy(complete_strategy(), strict=True) == []


def test_city_normalization_and_ambiguity():
    assert resolve_city_country("Vilnius") == {"country_code": "LT", "needs_clarification": False}
    assert resolve_city_country("Springfield")["needs_clarification"] is True


def test_two_countries_require_separate_analysis_and_switch_rule():
    report = complete_strategy()
    report["market_context"]["target_countries"] = ["Lithuania", "Poland"]
    errors = validate_market_strategy(report, strict=True)
    assert any("Every selected country" in error for error in errors)
    assert any("switch-condition" in error for error in errors)


def test_us_regulated_profession_requires_state():
    report = complete_strategy()
    report["market_context"]["target_countries"] = ["USA"]
    row = report["market_analysis"][0]
    row.update({"country": "USA", "regulated_profession": True, "licensing_check": "official board"})
    report["income_forecasts"][0].update({"country": "USA", "currency": "USD", "period": "year"})
    assert any("US state" in error for error in validate_market_strategy(report, strict=True))


def test_missing_local_language_analysis_is_blocked():
    report = complete_strategy()
    report["market_analysis"][0].pop("language_analysis")
    assert any("local-language" in error for error in validate_market_strategy(report, strict=True))


def test_unavailable_market_data_cannot_contain_estimates():
    report = complete_strategy()
    report["income_forecasts"] = [{"status": "data_unavailable", "estimates": {"base": 1000}}]
    assert any("must not invent" in error for error in validate_market_strategy(report, strict=True))


def test_strategy_is_part_of_central_career_assessment_contract():
    payload = profile_10_assessment_payload()
    payload["strategy"] = complete_strategy()
    assessment = career_assessment_from_dict(payload)
    assert assessment.strategy.market_context["target_countries"] == ["Lithuania"]
    assert len(assessment.strategy.selected_routes) == 3
