from __future__ import annotations

import copy
import re

from services.career_assessment import (
    CAREER_ASSESSMENT_SCHEMA,
    career_assessment_from_dict,
    render_assessment_html,
    validate_career_assessment,
)
from tests.test_career_assessment import profile_10_assessment_payload


def _assessment(*, residence: str, target: str, currency: str):
    payload = copy.deepcopy(profile_10_assessment_payload())
    payload["context"].update({
        "residence_country": residence,
        "target_countries": [target],
        "preferred_currency": currency,
        "market_data_date": None,
        "market_data_sources": [],
        "market_data_confidence": "low",
    })
    # This fixture predates strict uniqueness; make each route intentionally distinct.
    for index, route in enumerate(
        payload["routes"][group][item]
        for group in ("primary_routes", "transition_routes", "quick_income_routes")
        for item in range(len(payload["routes"][group]))
    ):
        route["why_it_fits"] += f" Уникальная функция маршрута {index}."
        route["risks"] = [["конкуренция за запуск", "узкая исследовательская специализация", "delivery ответственность", "образовательные метрики", "нестабильность продаж"][index]]
        route["missing"] = [["launch-кейс", "исследовательская методология", "управление backlog", "retention кейс", "платящий клиент"][index]]
        route["market_test"] = f"Уникальная проверка роли {route['title']} номер {index}."
        route["entry_path"] = ["direct_entry", "adjacent_transition", "bridge_project", "retraining_required", "not_recommended_now"][index]
        route["market_notes"] = ["Диапазон требует рыночной проверки"]
        route["evidence_claims"] = [{"claim": route["why_it_fits"], "evidence_fact_ids": route["evidence_ids"], "confidence": "medium", "uncertainties": route["missing"]}]
    return career_assessment_from_dict(payload)


def test_lithuania_market_uses_eur_and_never_pln() -> None:
    html = render_assessment_html(_assessment(residence="Литва", target="Литва", currency="EUR"))
    assert "EUR" in html
    assert "PLN" not in html


def test_lithuania_resident_poland_target_is_explicitly_pln() -> None:
    assessment = _assessment(residence="Литва", target="Польша", currency="PLN")
    html = render_assessment_html(assessment)
    assert "Страна проживания:</strong> Литва" in html
    assert "Целевой рынок:</strong> Польша" in html
    assert "Валюта:</strong> PLN" in html
    assert validate_career_assessment(assessment).valid


def test_missing_salary_is_uncertainty_without_invented_numbers() -> None:
    assessment = _assessment(residence="Литва", target="Литва", currency="EUR")
    assessment.context.income_minimum = None
    assessment.context.income_target = None
    html = render_assessment_html(assessment)
    assert "Актуальный датированный источник не получен" in html
    assert "не заявлен без сопоставимого источника" in html
    assert not re.search(r"\b\d{3,6}\s*(?:EUR|PLN)", html)


def test_html_has_sequential_strategy_sections_and_no_technical_ids() -> None:
    assessment = _assessment(residence="Литва", target="Литва", currency="EUR")
    html = render_assessment_html(assessment)
    assert re.findall(r"<h2>(\d+)\.", html) == [str(number) for number in range(1, 15)]
    assert assessment.assessment_id not in html
    assert "renderer" not in html.casefold()
    assert "career-assessment-html" not in html
    assert "Безопасный сценарий" in html
    assert "Основной сценарий" in html
    assert "Амбициозный сценарий" in html
    assert "Что здесь легко не заметить" in html
    assert "overflow-x:auto" in html
    assert "direct_entry" not in html


def test_strategy_contract_requires_market_income_scenarios_and_insights() -> None:
    required = set(CAREER_ASSESSMENT_SCHEMA["required"])
    assert {"market_analysis", "income_forecasts", "scenarios", "personal_insights", "psychology_factors"} <= required
    assessment = _assessment(residence="Литва", target="Литва", currency="EUR")
    validation = validate_career_assessment(assessment)
    assert validation.valid, validation.errors
    assert {item.scenario_type for item in assessment.scenarios} == {"safe", "main", "ambitious"}
    assert len(assessment.personal_insights) >= 3
    assert all(len(set(item.evidence_fact_ids)) >= 2 for item in assessment.personal_insights)
    assert {item.route_id for item in assessment.market_analysis} == {route.route_id for route in assessment.routes.all_routes()}
    assert {item.route_id for item in assessment.income_forecasts} == {route.route_id for route in assessment.routes.all_routes()}


def test_duplicate_route_analysis_and_unlinked_claim_are_rejected() -> None:
    assessment = _assessment(residence="Литва", target="Литва", currency="EUR")
    left, right = assessment.routes.all_routes()[:2]
    right.why_it_fits = left.why_it_fits
    right.risks = left.risks
    right.missing = left.missing
    right.market_test = left.market_test
    right.evidence_claims[0]["evidence_fact_ids"] = []
    codes = {issue.code for issue in validate_career_assessment(assessment).errors}
    assert "DUPLICATE_ROUTE_ANALYSIS" in codes
    assert "UNLINKED_CLAIM" in codes


def test_psychological_diagnosis_is_rejected() -> None:
    assessment = _assessment(residence="Литва", target="Литва", currency="EUR")
    assessment.constraints[0].impact = "У вас синдром самозванца"
    assert "PSYCHOLOGICAL_DIAGNOSIS" in {issue.code for issue in validate_career_assessment(assessment).errors}


def test_market_context_alias_and_comparison_contract() -> None:
    assessment = _assessment(residence="Литва", target="Литва", currency="EUR")
    assert assessment.market_context is assessment.context
    html = render_assessment_html(assessment)
    for heading in (
        "Соответствие опыту", "Сохранение дохода", "Сохранение статуса", "Скорость",
        "Дообучение", "Доступность на рынке", "Психологическая устойчивость", "Общий риск",
    ):
        assert heading in html


def test_every_country_aware_route_requires_claim_linkage() -> None:
    assessment = _assessment(residence="Литва", target="Литва", currency="EUR")
    assessment.routes.all_routes()[0].evidence_claims = []
    assert "UNLINKED_CLAIM" in {issue.code for issue in validate_career_assessment(assessment).errors}
