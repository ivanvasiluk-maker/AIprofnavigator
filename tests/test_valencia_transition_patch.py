from services.canonical_profile import build_canonical_profile, select_clarifying_question


def _income(profile, kind):
    return [
        fact.normalized_value
        for fact in profile.facts_of_type("income_requirement")
        if fact.normalized_value.get("kind") == kind
    ]


def test_valencia_facts_routes_and_income_survive_full_history_rebuild():
    data = {
        "story_text": (
            "Живу в Валенсии, Испания. Переезжать не хочу. Сейчас получаю €1450 net. "
            "Минимум нужен €1700 net, цель €2100–2400. Хочу уменьшить ручной труд."
        ),
        "story_analysis": {
            "current_role": "Зубной техник",
            "confirmed_functions": ["контроль качества", "базовые операции CAD/CAM"],
            "target_change": ["уменьшить мелкую ручную работу"],
            "target_roles": ["CAD/CAM technician", "Quality control", "Technical support"],
        },
    }
    first = build_canonical_profile(data, assessment_id="valencia")
    data["canonical_profile"] = first.model_dump(mode="json")
    rebuilt = build_canonical_profile(data, assessment_id="valencia")

    location = rebuilt.latest_value("market_context")
    assert location["city"] == "Валенсия"
    assert location["country"] == "Spain"
    assert any(item["amount"] == "1700" for item in _income(rebuilt, "minimum"))
    assert any(item["amount"] == "2100–2400" for item in _income(rebuilt, "target"))
    assert rebuilt.current_role == "Зубной техник"
    assert len(rebuilt.candidate_routes) == 3
    assert rebuilt.target_change
    assert len(rebuilt.facts) == len(first.facts)


def test_currency_conflict_is_not_silently_overwritten_and_is_asked_first():
    profile = build_canonical_profile(
        {
            "story_text": "Минимум нужен €1700 net.",
            "qa_answers": [{
                "assessment_id": "conflict",
                "question_id": "minimum_income",
                "answer": "3000–4500 PLN",
            }],
        },
        assessment_id="conflict",
    )

    assert profile.contradictions
    assert all(f.needs_clarification for f in profile.facts_of_type("income_requirement"))
    question = select_clarifying_question(profile)
    assert question is not None
    assert "€1700" in question.text
    assert "3000–4500 PLN" in question.text

