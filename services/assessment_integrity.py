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
    message_map = {str(m.get("message_id")): str(m.get("text") or "") for m in messages}
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


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _strings(child)]
    return []
