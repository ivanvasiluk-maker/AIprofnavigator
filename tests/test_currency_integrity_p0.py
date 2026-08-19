import pytest

from handlers.career import (
    _income_options_for_currency,
    _route_context_question,
    _validate_currency_keyboard,
)
from services.canonical_profile import build_canonical_profile, select_clarifying_question


LITHUANIA_STORY = (
    "Живу в Kaunas, Lithuania и ищу работу в Lithuania. "
    "Текущий доход €1250 net в месяц. Мне необходимо минимум €1500 net в месяц. "
    "Цель €1800–2000 net в месяц. Бюджет на обучение €500 на шесть месяцев."
)


def test_lithuania_explicit_eur_is_structured_and_minimum_is_not_asked_again():
    profile = build_canonical_profile({"story_text": LITHUANIA_STORY}, assessment_id="lt-eur")
    normalized = profile.normalized_profile

    assert normalized.city == "Kaunas"
    assert normalized.country == "Lithuania"
    assert normalized.currency_context.display_currency == "EUR"
    assert normalized.current_income_fact.amount == 1250
    assert normalized.minimum_income_fact.amount == 1500
    assert (normalized.target_income_fact.min, normalized.target_income_fact.max) == (1800, 2000)
    assert normalized.minimum_income_fact.basis == "net"
    assert normalized.training_budget_fact.amount == 500
    assert normalized.training_budget_fact.currency == "EUR"
    assert "minimum_income" in profile.question_state.resolved_fact_types
    question = select_clarifying_question(profile)
    assert question is None or question.question_id != "clarify_minimum_income"


def test_lithuania_keyboard_is_eur_and_foreign_keyboard_fails_closed():
    question = _route_context_question(5, {"country": "Lithuania"})
    labels = " ".join(question["options"])
    assert "€" in labels
    assert "PLN" not in labels
    with pytest.raises(ValueError, match="currency_ui_mismatch"):
        _validate_currency_keyboard(["6000+ PLN/мес"], "EUR")


def test_poland_keyboard_is_generated_only_for_polish_context():
    question = _route_context_question(5, {"country": "Poland"})
    labels = " ".join(question["options"])
    assert "PLN" in labels
    assert "€" not in labels
    assert _income_options_for_currency("PLN") != _income_options_for_currency("EUR")


def test_wrong_pln_button_is_audited_and_does_not_replace_explicit_eur():
    profile = build_canonical_profile({
        "story_text": "Живу в Lithuania. Мне необходимо минимум €1500 net в месяц.",
        "qa_answers": [{
            "assessment_id": "button-conflict", "source_message_id": "button:minimum_income",
            "answer": "Минимум 6000 PLN net в месяц",
        }],
    }, assessment_id="button-conflict")

    assert profile.normalized_profile.minimum_income_fact.currency == "EUR"
    assert profile.normalized_profile.minimum_income_fact.amount == 1500
    conflict = profile.normalized_profile.income_conflicts[0]
    assert conflict.status == "unresolved"
    assert conflict.likely_ui_mismatch is True


def test_text_currency_change_remains_unresolved_without_silent_conversion():
    profile = build_canonical_profile({
        "story_text": "Живу в Lithuania. Мне необходимо минимум €1500 net в месяц.",
        "source_messages": [{
            "assessment_id": "text-conflict", "message_id": "user-correction",
            "text": "Исправляю: минимум 6000 PLN net в месяц",
        }],
    }, assessment_id="text-conflict")

    assert profile.normalized_profile.minimum_income_fact.currency == "EUR"
    assert profile.normalized_profile.income_conflicts[0].likely_ui_mismatch is False
    assert profile.contradictions
