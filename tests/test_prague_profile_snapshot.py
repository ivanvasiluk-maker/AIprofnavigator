from services.canonical_profile import build_canonical_profile


def test_prague_profile_keeps_each_money_entity_and_normalizes_facts():
    data = {
        "assessment_id": "prague-case",
        "story_text": (
            "Живу в Праге. Ищу прежде всего в Чехии, но рассматриваю международную "
            "удалённую работу. Есть право на работу. Переезжать не хочу. Готов работать "
            "удалённо или гибридно. Полный день. Без ночных смен. Получаю 48 000 CZK net. "
            "Минимум 45 000 CZK net, цель 65 000–80 000 CZK net. Украинский родной, "
            "русский свободный, чешский B1, английский B2. На обучение могу потратить "
            "€1500 за 8 месяцев, 5–6 часов в неделю."
        ),
    }
    profile = build_canonical_profile(data, assessment_id="prague-case").normalized_profile

    assert (profile.country, profile.city) == ("Czechia", "Prague")
    assert (profile.target_market_primary, profile.target_market_secondary) == (
        "Czechia", "international_remote"
    )
    assert (profile.relocation_allowed, profile.remote_allowed, profile.hybrid_allowed) == (False, True, True)
    assert (profile.full_time, profile.night_shifts, profile.work_rights) == (True, False, True)
    assert profile.languages == {"Ukrainian": "native", "Russian": "fluent", "Czech": "B1", "English": "B2"}
    assert (profile.current_income, profile.minimum_income) == (48000, 45000)
    assert (profile.target_income_min, profile.target_income_max) == (65000, 80000)
    assert (profile.income_currency, profile.gross_net, profile.income_period) == ("CZK", "net", "month")
    assert (profile.training_budget, profile.training_budget_currency) == (1500, "EUR")
    assert (profile.training_hours_per_week, profile.training_horizon) == ("5–6", "8 months")


def test_profile_rebuild_does_not_load_foreign_assessment():
    data = {
        "assessment_id": "new",
        "story_text": "Живу в Праге.",
        "canonical_profile": {"assessment_id": "old", "facts": []},
    }
    profile = build_canonical_profile(data, assessment_id="new")
    assert profile.assessment_id == "new"
    assert all(fact.assessment_id == "new" for fact in profile.facts)
