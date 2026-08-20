import pytest

from services.assessment_integrity import contamination_errors
from services.canonical_profile import build_canonical_profile
from utils.reporting import ReportMeta, _safe_text, render_report_html


STORY = (
    "Живу в Тбилиси, Грузия. Текущий доход 2400 GEL net, минимум 3000 GEL, "
    "цель 4000–4500 GEL в месяц. Русский — native, грузинский B1, английский B2. "
    "Рассматриваю локальную и удалённую работу, релокация невозможна. "
    "Аллергия на реактивы, без ночных смен, нужна сниженная физическая нагрузка; "
    "не могу увольняться до оффера."
)


@pytest.fixture(scope="module")
def profile():
    return build_canonical_profile({"story_text": STORY}, assessment_id="ge-1")


def test_georgia_profile_preserves_location_income_languages_and_preferences(profile):
    value = profile.normalized_profile
    assert (value.city, value.country, value.country_code) == ("Тбилиси", "Georgia", "GE")
    assert (value.current_income, value.minimum_income) == (2400, 3000)
    assert (value.target_income_min, value.target_income_max) == (4000, 4500)
    assert value.languages == {"Russian": "native", "Georgian": "B1", "English": "B2"}
    assert value.target_market_formats == ["local", "remote"]
    assert value.remote_allowed is True and value.relocation_allowed is False
    assert value.night_shifts is False
    assert {"reagent_allergy", "no_night_shifts", "reduced_physical_load", "no_resignation_before_offer", "no_relocation"}.issubset(value.schedule_constraints)


def test_georgia_currency_is_gel_and_never_local_eur(profile):
    value = profile.normalized_profile
    assert value.currency_context.residence_currency == "GEL"
    assert value.local_currency == "GEL"
    assert value.currency_context.display_currency == "GEL"
    assert {value.current_income_fact.currency, value.minimum_income_fact.currency, value.target_income_fact.currency} == {"GEL"}


def test_unscoped_psychological_fallback_is_rejected(profile):
    report = {"assessment_id": "ge-1", "summary": "Хаос в голове", "evidence": [], "routes": {}}
    snapshot = {"canonical_profile": profile.model_dump()}
    assert "UNSUPPORTED_PSYCHOLOGICAL_CLAIM" in contamination_errors(report, snapshot, "ge-1")


def test_single_function_cross_domain_route_cannot_be_primary(profile):
    report = {"assessment_id": "ge-1", "evidence": [], "routes": {"primary_routes": [{
        "route_id": "technical-writer", "title": "Technical Writer", "rank": 1,
        "function_match_count": 1, "domain_match": False, "evidence_ids": [],
    }]}}
    errors = contamination_errors(report, {"canonical_profile": profile.model_dump()}, "ge-1")
    assert "SINGLE_FUNCTION_PRIMARY_ROUTE:technical-writer" in errors


def test_reagent_allergy_blocks_unwarned_safe_or_ambitious_lab_scenario(profile):
    report = {"assessment_id": "ge-1", "evidence": [], "routes": {}, "scenarios": [{
        "kind": "ambitious", "goal": "Лабораторная работа с реактивами",
    }]}
    snapshot = {"canonical_profile": profile.model_dump()}
    assert "CONSTRAINT_VIOLATING_SCENARIO:ambitious" in contamination_errors(report, snapshot, "ge-1")


def test_renderer_humanizes_technical_values_and_keeps_table_headers_separate():
    assert [_safe_text(value) for value in ("unknown", True, False)] == ["не указано", "есть", "нет"]
    html = render_report_html({}, ReportMeta("Ирина", "Georgia", "full", "2026-08-20"))
    assert not any(token in html for token in (">unknown<", ">True<", ">False<", "МаршрутСтранаВалюта"))
