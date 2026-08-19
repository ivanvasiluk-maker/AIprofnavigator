from concurrent.futures import ThreadPoolExecutor

from services.assessment_integrity import audit_facts, build_fact_ledger, consistency_errors


A = "Senior IT-маркетолог, 8 лет, B2B и позиционирование. Литва."
B = ("Больше 10 лет работаю психологом, 25 клиентов в неделю, €3000–3500. "
     "Живу в Вильнюсе. Русский и белорусский, английский B2, литовский A1–A2. "
     "Интересны психологические программы, HealthTech и EdTech.")


def ledger(aid, uid, text):
    messages = [{"assessment_id": aid, "message_id": f"m-{aid}", "text": text, "created_at": "2026-08-17T00:00:00+00:00"}]
    return messages, build_fact_ledger(aid, uid, messages)


def test_sequential_assessments_do_not_mix_facts():
    _, old = ledger("a", "user", A)
    messages, current = ledger("b", "user", B)
    audit = audit_facts("b", "user", old + current, messages)
    assert audit["accepted_fact_ids"] == ["b:fact:1"]
    assert "a:fact:1" in audit["rejected_fact_ids"]
    assert audit["detected_country"] == "Литва"
    assert audit["detected_income"] == "€3000–3500"


def test_parallel_users_are_isolated():
    def run(aid, uid, text):
        messages, facts = ledger(aid, uid, text)
        return audit_facts(aid, uid, facts, messages)
    with ThreadPoolExecutor() as pool:
        first, second = list(pool.map(lambda args: run(*args), [("a", "u1", A), ("b", "u2", B)]))
    assert first["current_user_id"] == "u1" and second["current_user_id"] == "u2"
    assert first["accepted_fact_ids"] == ["a:fact:1"]
    assert second["accepted_fact_ids"] == ["b:fact:1"]


def test_new_assessment_same_user_and_restart_reject_old_state():
    old_messages, old = ledger("old", "u", A)
    new_messages, new = ledger("new", "u", B)
    restarted = audit_facts("new", "u", old + new, new_messages)
    assert restarted["accepted_fact_ids"] == ["new:fact:1"]
    assert restarted["source_message_ids"] == ["m-new"]
    assert old_messages[0]["message_id"] not in restarted["source_message_ids"]


def test_examples_fixtures_and_missing_sources_are_rejected():
    messages, facts = ledger("b", "u", B)
    fixture = {**facts[0], "fact_id": "fixture", "origin": "fixture"}
    no_source = {**facts[0], "fact_id": "missing", "source_message_id": ""}
    wrong_quote = {**facts[0], "fact_id": "quote", "source_quote": "рост заявок на 35%"}
    audit = audit_facts("b", "u", facts + [fixture, no_source, wrong_quote], messages)
    assert audit["rejected_fact_ids"] == ["fixture", "missing", "quote"]


def test_consistency_validator_blocks_required_contradictions():
    messages, facts = ledger("b", "u", B)
    audit = audit_facts("b", "u", facts, messages)
    report = {"summary": "Страна не указана; языки не указаны; доход неизвестен; критичных неизвестных нет",
              "confidence": "high", "market_confidence": "low", "unknown_fields": ["legal"],
              "analyzed_route_ids": ["healthtech"], "comparison_route_ids": ["healthtech", "pmm"]}
    assert set(consistency_errors(report, audit)) == {
        "COUNTRY_IGNORED", "LANGUAGES_IGNORED", "INCOME_IGNORED",
        "OVERSTATED_CONFIDENCE", "UNKNOWN_FIELDS_CONTRADICTION", "UNANALYZED_ROUTE_IN_COMPARISON",
    }
