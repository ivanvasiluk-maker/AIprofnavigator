"""Hard assessment boundary, provenance ledger, and pre-publication checks."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class SourcedFact:
    fact_id: str
    assessment_id: str
    user_id: str
    source_message_id: str
    source_quote: str
    created_at: str


def build_fact_ledger(
    assessment_id: str, user_id: str, messages: Iterable[dict[str, Any]]
) -> list[dict[str, str]]:
    """Create facts exclusively from messages belonging to this assessment."""
    facts: list[dict[str, str]] = []
    for index, message in enumerate(messages, 1):
        if str(message.get("assessment_id") or "").strip() != assessment_id:
            continue
        message_id = str(message.get("message_id") or "").strip()
        quote = str(message.get("text") or "").strip()
        if not message_id or not quote:
            continue
        created_at = str(message.get("created_at") or "").strip() or datetime.now(timezone.utc).isoformat()
        facts.append(asdict(SourcedFact(
            fact_id=f"{assessment_id}:fact:{index}", assessment_id=assessment_id,
            user_id=user_id, source_message_id=message_id,
            source_quote=quote, created_at=created_at,
        )))
    return facts


def audit_facts(
    assessment_id: str, user_id: str, facts: Iterable[dict[str, Any]],
    messages: Iterable[dict[str, Any]], candidate_routes: Iterable[str] = (),
) -> dict[str, Any]:
    """Reject unscoped, synthetic, fixture, fallback, and non-verbatim facts."""
    message_map = {
        str(m.get("message_id")): str(m.get("text") or "")
        for m in messages
        if str(m.get("assessment_id") or "").strip() == assessment_id
    }
    accepted: list[str] = []
    rejected: list[str] = []
    source_ids: list[str] = []
    accepted_quotes: list[str] = []
    for fact in facts:
        fact_id = str(fact.get("fact_id") or "<missing-id>")
        source_id = str(fact.get("source_message_id") or "")
        quote = str(fact.get("source_quote") or "")
        origin = str(fact.get("origin") or "user").casefold()
        valid = (
            str(fact.get("assessment_id") or "") == assessment_id
            and str(fact.get("user_id") or "") == user_id
            and source_id in message_map and bool(quote)
            and quote in message_map[source_id]
            and origin not in {"fixture", "example", "previous_assessment", "fallback"}
        )
        (accepted if valid else rejected).append(fact_id)
        if valid:
            source_ids.append(source_id)
            accepted_quotes.append(quote)
    blob = " ".join(accepted_quotes)
    low = blob.casefold()
    return {
        "current_assessment_id": assessment_id,
        "current_user_id": user_id,
        "accepted_fact_ids": accepted,
        "rejected_fact_ids": rejected,
        "source_message_ids": list(dict.fromkeys(source_ids)),
        "detected_country": "Литва" if re.search(r"вильнюс|литв", low) else None,
        "detected_languages": re.findall(r"(?:русск\w*|белорусск\w*|английск\w*|литовск\w*)(?:\s+[A-CА-С]\d(?:[–-][A-CА-С]?\d)?)?", blob, re.I),
        "detected_income": (match.group(0) if (match := re.search(r"€\s?\d[\d\s]*(?:[–-]\s?\d[\d\s]*)?", blob)) else None),
        "candidate_routes": list(candidate_routes),
    }


def consistency_errors(report: dict[str, Any], audit: dict[str, Any]) -> list[str]:
    """Return contradictions which require a repair pass or safe short report."""
    text = " ".join(_strings(report)).casefold()
    errors: list[str] = []
    if audit.get("detected_country") and any(x in text for x in ("страна не указана", "страна неизвестна")):
        errors.append("COUNTRY_IGNORED")
    if audit.get("detected_languages") and any(x in text for x in ("языки не указаны", "языки неизвестны")):
        errors.append("LANGUAGES_IGNORED")
    if audit.get("detected_income") and any(x in text for x in ("доход неизвестен", "доход не указан")):
        errors.append("INCOME_IGNORED")
    market_low = str(report.get("market_confidence") or report.get("market_data_confidence") or "").casefold() == "low"
    has_unknowns = bool(report.get("unknown_fields") or report.get("unanswered_critical_questions"))
    if str(report.get("confidence") or "").casefold() == "high" and (market_low or has_unknowns):
        errors.append("OVERSTATED_CONFIDENCE")
    if has_unknowns and "критичных неизвестных нет" in text:
        errors.append("UNKNOWN_FIELDS_CONTRADICTION")
    analyzed = set(map(str, report.get("analyzed_route_ids") or []))
    compared = set(map(str, report.get("comparison_route_ids") or []))
    if not compared.issubset(analyzed):
        errors.append("UNANALYZED_ROUTE_IN_COMPARISON")
    return errors


def contamination_errors(
    report: dict[str, Any], profile_snapshot: dict[str, Any], assessment_id: str
) -> list[str]:
    """Detect foreign evidence and unsupported cross-domain route jumps."""
    errors: list[str] = []
    if str(report.get("assessment_id") or "").strip() != assessment_id:
        errors.append("FOREIGN_ASSESSMENT_ID")
        return errors

    canonical = profile_snapshot.get("canonical_profile") or {}
    facts = canonical.get("facts") if isinstance(canonical, dict) else []
    current_facts = [
        fact for fact in facts or []
        if isinstance(fact, dict) and str(fact.get("assessment_id") or "") == assessment_id
    ]
    if len(current_facts) != len(facts or []):
        errors.append("FOREIGN_CANONICAL_FACT")
    source_blob = " ".join(dict.fromkeys(
        text.casefold()
        for fact in current_facts
        for text in _strings([fact.get("normalized_value"), fact.get("source_quote")])
    ))
    evidence = report.get("evidence") or []
    evidence_ids = {str(item.get("evidence_id") or "") for item in evidence if isinstance(item, dict)}
    routes = _route_dicts(report)
    for route in routes:
        route_evidence = {str(item) for item in route.get("evidence_ids") or []}
        if len(route_evidence) < 2 or not route_evidence.issubset(evidence_ids):
            errors.append(f"UNSCOPED_ROUTE_EVIDENCE:{route.get('route_id') or '?'}")
        if (route.get("is_primary") or route.get("rank") == 1) and int(route.get("function_match_count") or 0) < 2 and not route.get("domain_match"):
            errors.append(f"SINGLE_FUNCTION_PRIMARY_ROUTE:{route.get('route_id') or '?'}")

    # Psychological claims and scenarios are allowed only when grounded in the
    # current assessment. This also prevents a generic fallback leaking in.
    report_text = " ".join(_strings(report)).casefold()
    for claim in ("хаос в голове", "откладываю", "потерял уверенность", "потеряла уверенность", "начинаю и бросаю"):
        if claim in report_text and claim not in source_blob:
            errors.append("UNSUPPORTED_PSYCHOLOGICAL_CLAIM")
            break
    reagent_allergy = any(token in source_blob for token in ("аллерги", "реактив"))
    if reagent_allergy:
        for scenario in report.get("scenarios") or []:
            if not isinstance(scenario, dict):
                continue
            scenario_text = " ".join(_strings(scenario)).casefold()
            if scenario.get("kind") in {"safe", "ambitious"} and any(token in scenario_text for token in ("реактив", "лаборатор")) and "предупреж" not in scenario_text:
                errors.append(f"CONSTRAINT_VIOLATING_SCENARIO:{scenario.get('kind')}")

    dental = any(token in source_blob for token in ("зуб", "dental", "стомат", "корон", "протез", "керамик"))
    industrial_source = any(token in source_blob for token in ("промышлен", "manufactur", "supplier", "поставщик", "производственн", "цех", "erp"))
    if dental and not industrial_source:
        for route in routes:
            title = str(route.get("title") or "").casefold()
            if any(token in title for token in ("industrial", "supplier quality", "manufacturing", "промышлен")):
                errors.append(f"UNSUPPORTED_CROSS_DOMAIN_ROUTE:{route.get('route_id') or '?'}")
    return list(dict.fromkeys(errors))


def _route_dicts(report: dict[str, Any]) -> list[dict[str, Any]]:
    routes = report.get("routes") or {}
    result: list[dict[str, Any]] = []
    for key in ("primary_routes", "transition_routes", "quick_income_routes", "emergency_routes"):
        result.extend(item for item in routes.get(key) or [] if isinstance(item, dict))
    return result


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _strings(child)]
    return []
