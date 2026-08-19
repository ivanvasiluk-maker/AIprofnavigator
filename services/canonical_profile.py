from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


FactType = Literal[
    "profession", "professional_function", "skill", "responsibility", "achievement",
    "education", "certification", "work_condition", "constraint", "undesirable_task",
    "interest", "income_requirement", "market_context", "language",
    "work_authorization", "preferred_format", "experience", "industry",
    "health_related_limit", "family_constraint", "relocation", "business_trip",
    "learning_resource", "transition_urgency", "desired_change_scale",
    "target_change", "candidate_route", "recommended_route",
]

CITY_COUNTRIES = {
    "berlin": ("Germany", "DE"), "берлин": ("Germany", "DE"), "берлине": ("Germany", "DE"),
    "prague": ("Czechia", "CZ"), "praha": ("Czechia", "CZ"),
    "прага": ("Czechia", "CZ"), "праге": ("Czechia", "CZ"),
    "porto": ("Portugal", "PT"), "порту": ("Portugal", "PT"),
    "vilnius": ("Lithuania", "LT"), "вильнюс": ("Lithuania", "LT"),
    "warsaw": ("Poland", "PL"), "варшава": ("Poland", "PL"),
    "riga": ("Latvia", "LV"), "рига": ("Latvia", "LV"),
    "tallinn": ("Estonia", "EE"), "таллин": ("Estonia", "EE"),
    "valencia": ("Spain", "ES"), "валенсия": ("Spain", "ES"),
    "валенсии": ("Spain", "ES"),
    "krakow": ("Poland", "PL"), "kraków": ("Poland", "PL"),
    "краков": ("Poland", "PL"), "кракове": ("Poland", "PL"),
}

COUNTRY_ALIASES = {
    "poland": "Poland", "polska": "Poland", "польша": "Poland",
    "польше": "Poland", "польшу": "Poland", "польши": "Poland",
    "spain": "Spain", "испания": "Spain", "испании": "Spain",
    "portugal": "Portugal", "португалия": "Portugal", "португалии": "Portugal",
    "czechia": "Czechia", "czech republic": "Czechia", "чехия": "Czechia", "чехии": "Czechia", "чехию": "Czechia",
    "lithuania": "Lithuania", "литва": "Lithuania", "литве": "Lithuania", "литву": "Lithuania",
    "germany": "Germany", "германия": "Germany", "германии": "Germany", "германию": "Germany",
}

LANGUAGE_ALIASES = {
    "польск": "Polish", "polish": "Polish", "polski": "Polish",
    "английск": "English", "english": "English",
    "испанск": "Spanish", "spanish": "Spanish",
    "русск": "Russian", "russian": "Russian",
    "украинск": "Ukrainian", "українськ": "Ukrainian", "ukrainian": "Ukrainian",
    "чешск": "Czech", "czech": "Czech",
}


class NormalizedUserProfile(BaseModel):
    country: str | None = None
    city: str | None = None
    target_market: str | None = None
    target_market_primary: str | None = None
    target_market_secondary: str | None = None
    relocation_allowed: bool | None = None
    remote_allowed: bool | None = None
    hybrid_allowed: bool | None = None
    full_time: bool | None = None
    night_shifts: bool | None = None
    work_rights: bool | None = None
    current_role: str | None = None
    previous_roles: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    years_experience: float | None = None
    languages: dict[str, str] = Field(default_factory=dict)
    language_details: list[dict[str, Any]] = Field(default_factory=list)
    current_income: float | None = None
    minimum_income: float | None = None
    target_income: str | None = None
    target_income_min: float | None = None
    target_income_max: float | None = None
    currency: str | None = None
    income_currency: str | None = None
    income_period: str | None = None
    gross_net: str | None = None
    schedule_constraints: list[str] = Field(default_factory=list)
    training_hours_per_week: float | str | None = None
    training_budget: float | None = None
    training_budget_currency: str | None = None
    training_horizon: str | None = None
    transferable_skills: list[str] = Field(default_factory=list)
    psychological_barriers: list[str] = Field(default_factory=list)
    life_constraints: list[str] = Field(default_factory=list)
    financial_minimum_status: str = "confirmed"
    professional_functions: list[str] = Field(default_factory=list)
    management_experience: list[str] = Field(default_factory=list)
    digital_tools: list[str] = Field(default_factory=list)
    desired_changes: list[str] = Field(default_factory=list)
    undesired_tasks: list[str] = Field(default_factory=list)
    candidate_interests: list[str] = Field(default_factory=list)


class CanonicalFact(BaseModel):
    fact_id: str
    assessment_id: str
    fact_type: FactType
    normalized_value: Any
    source_message_id: str
    source_quote: str
    confidence: float = Field(ge=0, le=1)
    updated_at: str
    supersedes_fact_id: str | None = None
    status: Literal["active", "superseded"] = "active"
    needs_clarification: bool = False

    @property
    def created_at(self) -> str:
        """Compatibility alias for profiles persisted before the P0 contract."""
        return self.updated_at


class QuestionState(BaseModel):
    asked_question_ids: list[str] = Field(default_factory=list)
    answered_gap_ids: list[str] = Field(default_factory=list)
    skipped_gap_ids: list[str] = Field(default_factory=list)
    resolved_fact_types: list[str] = Field(default_factory=list)
    remaining_critical_gaps: list[str] = Field(default_factory=list)
    question_count: int = 0


class ClarifyingQuestion(BaseModel):
    question_id: str
    target_fact_type: str
    reason: str
    expected_impact: str
    source_check_completed: bool = True
    text: str


class CanonicalProfile(BaseModel):
    assessment_id: str
    facts: list[CanonicalFact] = Field(default_factory=list)
    contradictions: list[list[str]] = Field(default_factory=list)
    question_state: QuestionState = Field(default_factory=QuestionState)
    # Career identity and career decision are intentionally different entities.
    current_role: str | None = None
    professional_core: list[str] = Field(default_factory=list)
    target_change: list[str] = Field(default_factory=list)
    candidate_routes: list[str] = Field(default_factory=list)
    recommended_route: str | None = None
    normalized_profile: NormalizedUserProfile = Field(default_factory=NormalizedUserProfile)
    consistency_issues: list[str] = Field(default_factory=list)

    def grouped(self) -> dict[str, list[CanonicalFact]]:
        """Return the complete, stable contract consumed by every report section."""
        mapping = {
            "identity": ("profession",), "experience": ("experience",),
            "professional_functions": ("professional_function",), "skills": ("skill",),
            "responsibilities": ("responsibility",), "achievements": ("achievement",),
            "education": ("education",), "certifications": ("certification",),
            "industries": ("industry",), "languages": ("language",),
            "location": ("market_context",), "target_markets": ("market_context",),
            "work_authorization": ("work_authorization",),
            "current_income": ("income_requirement",), "minimum_income": ("income_requirement",),
            "target_income": ("income_requirement",), "preferred_formats": ("preferred_format",),
            "interests": ("interest",), "undesirable_tasks": ("undesirable_task",),
            "constraints": ("constraint",), "health_related_limits": ("health_related_limit",),
            "family_constraints": ("family_constraint",), "relocation": ("relocation",),
            "business_trips": ("business_trip",), "learning_resources": ("learning_resource",),
            "transition_urgency": ("transition_urgency",), "desired_change_scale": ("desired_change_scale",),
        }
        result: dict[str, list[CanonicalFact]] = {}
        for group, types in mapping.items():
            facts = [fact for fact in self.facts if fact.status == "active" and fact.fact_type in types]
            if group.endswith("income"):
                kind = group.removesuffix("_income")
                facts = [fact for fact in facts if isinstance(fact.normalized_value, dict) and fact.normalized_value.get("kind") == kind]
            result[group] = facts
        return result

    def facts_of_type(self, fact_type: str) -> list[CanonicalFact]:
        return [fact for fact in self.facts if fact.fact_type == fact_type and fact.status == "active"]

    def latest_value(self, fact_type: str, key: str | None = None) -> Any:
        matches = self.facts_of_type(fact_type)
        if key is None and matches and all(isinstance(fact.normalized_value, dict) for fact in matches):
            merged: dict[str, Any] = {}
            for fact in matches:
                merged.update({name: value for name, value in fact.normalized_value.items() if value not in (None, "", [])})
            return merged
        for fact in reversed(matches):
            value = fact.normalized_value
            if key is None:
                return value
            if isinstance(value, dict) and value.get(key) not in (None, "", []):
                return value[key]
        return None


def _fact(assessment_id: str, fact_type: FactType, value: Any, message_id: str, quote: str,
          confidence: float = 1.0, created_at: str | None = None) -> CanonicalFact:
    return CanonicalFact(
        fact_id=f"fact_{uuid4().hex}", assessment_id=assessment_id, fact_type=fact_type,
        normalized_value=value, source_message_id=message_id or "assessment_input",
        source_quote=quote, confidence=confidence,
        updated_at=created_at or datetime.now(timezone.utc).isoformat(),
    )


def build_canonical_profile(data: dict[str, Any], *, assessment_id: str) -> CanonicalProfile:
    """Build the sole report input without truncating source messages.

    Structured answers are appended after the original story/resume and therefore win when
    ``latest_value`` is used. Conflicting evidence remains in ``facts`` for auditability.
    """
    persisted = data.get("canonical_profile")
    if isinstance(persisted, dict) and str(persisted.get("assessment_id") or "") == assessment_id:
        profile = CanonicalProfile.model_validate(persisted)
        # Defensive isolation even if corrupted state contains a foreign fact.
        profile.facts = [fact for fact in profile.facts if fact.assessment_id == assessment_id]
    else:
        profile = CanonicalProfile(assessment_id=assessment_id)
    # Rebuilding the profile is idempotent. Facts are re-extracted from the full
    # history below, rather than appended to an old extraction on every turn.
    profile.facts = []
    profile.contradictions = []
    sources: list[tuple[str, str, str]] = []
    for key in ("story_text", "answers_text"):
        text = str(data.get(key) or "")
        if text.strip():
            sources.append((key, text, ""))
    for collection in ("source_messages", "uploaded_documents"):
        for row in data.get(collection) or []:
            if (isinstance(row, dict)
                    and str(row.get("assessment_id") or assessment_id) == assessment_id
                    and str(row.get("text") or row.get("content") or "").strip()):
                body = str(row.get("text") or row.get("content") or "")
                sources.append((str(row.get("message_id") or row.get("document_id") or "message"), body, str(row.get("created_at") or "")))
    for row in data.get("qa_answers") or []:
        if (isinstance(row, dict)
                and str(row.get("assessment_id") or assessment_id) == assessment_id
                and str(row.get("answer") or "").strip()):
            sources.append((str(row.get("source_message_id") or row.get("question_id") or "clarification"), str(row["answer"]), str(row.get("created_at") or "")))

    route = data.get("route_context") if isinstance(data.get("route_context"), dict) else {}
    evidence_profile = data.get("evidence_profile") if isinstance(data.get("evidence_profile"), dict) else {}
    residence_evidence = evidence_profile.get("residence_country") if isinstance(evidence_profile.get("residence_country"), dict) else {}
    residence_city_evidence = evidence_profile.get("residence_city") if isinstance(evidence_profile.get("residence_city"), dict) else {}
    target_evidence = evidence_profile.get("target_countries") if isinstance(evidence_profile.get("target_countries"), list) else []
    target_format_evidence = evidence_profile.get("target_market_format") if isinstance(evidence_profile.get("target_market_format"), dict) else {}
    structured = {
        "country": route.get("country") or data.get("country") or residence_evidence.get("statement"),
        "city": route.get("city") or data.get("city") or residence_city_evidence.get("statement"),
        "target_market_primary": next((item.get("statement") for item in target_evidence if isinstance(item, dict) and item.get("statement")), None),
        "target_market_secondary": target_format_evidence.get("statement"),
        "work_authorization": route.get("documents_and_work_rights") or data.get("work_authorization_status"),
        "minimum_income": route.get("minimum_monthly_income") or data.get("minimum_income"),
        "current_income": route.get("current_monthly_income") or data.get("current_income"),
        "target_income": route.get("desired_monthly_income") or data.get("target_income"),
        "income_urgency": route.get("income_urgency") or data.get("income_urgency"),
        # Keep the complete language collection.  ``current_language_level`` is
        # retained as a compatibility fallback for older persisted profiles.
        "language": route.get("languages") or data.get("languages") or route.get("current_language_level") or data.get("current_language_level"),
        "format": route.get("work_preferences") or data.get("work_preferences"),
        "constraints": route.get("health_or_schedule_limits") or data.get("care_constraints"),
        "relocation": route.get("relocation_and_travel") or route.get("relocation_possible") or data.get("relocation_possible"),
        "change_scale": route.get("career_goal_type") or data.get("career_goal"),
        "preserve": route.get("functions_to_preserve") or data.get("functions_to_preserve"),
        "avoid": route.get("tasks_to_avoid") or route.get("functions_to_avoid") or data.get("functions_to_avoid"),
        "learning": route.get("available_time_for_study") or data.get("learning_hours_week"),
    }

    for message_id, text, created_at in sources:
        low = text.casefold().replace("ё", "е")
        for city, (country, code) in CITY_COUNTRIES.items():
            if re.search(rf"\b{re.escape(city)}\b", low):
                display_city = (
                    "Валенсия" if city in {"валенсия", "валенсии"}
                    else "Краков" if city in {"краков", "кракове"}
                    else "Prague" if city in {"prague", "praha", "прага", "праге"}
                    else "Berlin" if city in {"berlin", "берлин", "берлине"}
                    else city.title()
                )
                profile.facts.append(_fact(assessment_id, "market_context", {"city": display_city, "country": country, "country_code": code}, message_id, text, .98, created_at or None))
                break
        if not any(f.source_message_id == message_id and f.fact_type == "market_context" for f in profile.facts):
            for alias, country in COUNTRY_ALIASES.items():
                if re.search(rf"\b{re.escape(alias)}\b", low):
                    profile.facts.append(_fact(assessment_id, "market_context", {"country": country}, message_id, alias, .94, created_at or None))
                    break
        for match in re.finditer(r"(?:(€|eur|pln|zł|czk|kč)\s*)?(\d[\d\s]*(?:[–-]\s*\d[\d\s]*)?)\s*(€|eur|pln|zł|czk|kč)?\s*(net|gross)?", text, re.I):
            currency_token = (match.group(1) or match.group(3) or "").casefold()
            if not currency_token:
                continue
            context = text[max(0, match.start() - 35):match.end() + 35]
            classifier = text[max(0, match.start() - 24):match.start()] + " " + message_id
            minimum_at = max((m.start() for m in re.finditer(r"миним|minimum", classifier, re.I)), default=-1)
            target_at = max((m.start() for m in re.finditer(r"цел|жела|target", classifier, re.I)), default=-1)
            kind = "target" if target_at > minimum_at else "minimum" if minimum_at >= 0 else "current"
            currency = "EUR" if currency_token in {"€", "eur"} else "CZK" if currency_token in {"czk", "kč"} else "PLN"
            # A learning budget is a separate monetary entity and must never
            # overwrite the salary currency.
            if re.search(r"обучен|курс|training|education", context, re.I):
                profile.facts.append(_fact(assessment_id, "learning_resource", {
                    "kind": "training_budget", "amount": match.group(2).replace(" ", ""),
                    "currency": currency,
                }, message_id, context, .95, created_at or None))
                continue
            profile.facts.append(_fact(assessment_id, "income_requirement", {"kind": kind, "amount": match.group(2).replace(" ", ""), "currency": currency, "tax_basis": (match.group(4) or "unknown").lower(), "period": "month"}, message_id, context, .9, created_at or None))
        if re.search(r"прав[оа]\s+на\s+работ|work authori[sz]", low):
            authorized = not bool(re.search(r"нет|не име|without", low))
            profile.facts.append(_fact(assessment_id, "work_authorization", authorized, message_id, text, .9, created_at or None))
        for match in re.finditer(
            r"(украинск\w*|українськ\w*|русск\w*|испанск\w*|іспанськ\w*|"
            r"португальск\w*|чешск\w*|английск\w*|украинский|ukrainian|russian|spanish|"
            r"portuguese|czech|english)\s*[—:=-]?\s*(свободн\w*|родн\w*|[abc][12]|native|fluent)",
            low,
            re.I,
        ):
            raw_language = match.group(1).casefold()
            language = next((name for marker, name in LANGUAGE_ALIASES.items() if marker in raw_language), match.group(1).title())
            profile.facts.append(_fact(assessment_id, "language", {"language": language, "level": match.group(2).upper()}, message_id, match.group(0), .95, created_at or None))
        for marker, language in LANGUAGE_ALIASES.items():
            match = re.search(rf"(?:{re.escape(marker)}\w*)\s*[—:=-]?\s*([abc][12]|native|fluent)", low, re.I)
            if match:
                profile.facts.append(_fact(assessment_id, "language", {"language": language, "level": match.group(1).upper()}, message_id, match.group(0), .97, created_at or None))

    def add_structured(fact_type: FactType, value: Any, quote: str) -> None:
        meaningful = value not in (None, "", [], {})
        if isinstance(value, dict):
            meaningful = any(item not in (None, "", [], {}) for item in value.values())
        if meaningful and quote.strip():
            profile.facts.append(_fact(assessment_id, fact_type, value, "structured_answer", quote))

    city = str(structured["city"] or "").strip()
    country = str(structured["country"] or "").strip()
    mapped = CITY_COUNTRIES.get(city.casefold().replace("ё", "е"))
    add_structured("market_context", {"city": city or None, "country": country or (mapped[0] if mapped else None), "country_code": mapped[1] if mapped else None}, f"{city}, {country}".strip(", "))
    add_structured("market_context", {
        "target_market_primary": structured["target_market_primary"],
        "target_market_secondary": structured["target_market_secondary"],
    }, f"{structured['target_market_primary'] or ''}, {structured['target_market_secondary'] or ''}".strip(", "))
    add_structured("work_authorization", structured["work_authorization"], str(structured["work_authorization"] or ""))
    for kind in ("current_income", "minimum_income", "target_income"):
        add_structured("income_requirement", {"kind": kind.removesuffix("_income"), "display": structured[kind]}, str(structured[kind] or ""))
    add_structured("income_requirement", {"kind": "urgency", "display": structured["income_urgency"]}, str(structured["income_urgency"] or ""))
    language_values = structured["language"] if isinstance(structured["language"], list) else [structured["language"]]
    for language_value in language_values:
        add_structured("language", {"display": language_value}, str(language_value or ""))
    add_structured("preferred_format", structured["format"], str(structured["format"] or ""))
    add_structured("constraint", structured["constraints"], str(structured["constraints"] or ""))
    add_structured("market_context", {"relocation": structured["relocation"]}, str(structured["relocation"] or ""))
    add_structured("interest", structured["change_scale"], str(structured["change_scale"] or ""))
    add_structured("professional_function", structured["preserve"], str(structured["preserve"] or ""))
    add_structured("undesirable_task", structured["avoid"], str(structured["avoid"] or ""))
    add_structured("constraint", {"learning_resources": structured["learning"]}, str(structured["learning"] or ""))

    classified_fields: dict[FactType, tuple[str, ...]] = {
        "profession": ("current_identity", "current_role", "profession", "job_titles", "positions", "roles"),
        "professional_function": ("confirmed_functions", "functions"),
        "skill": ("skills", "transferable_skills"),
        "responsibility": ("responsibilities", "tasks"),
        "achievement": ("achievements", "measurable_results"),
        "education": ("education",), "certification": ("certifications", "licenses"),
        "work_condition": ("work_conditions",), "constraint": ("constraints",),
        "undesirable_task": ("tasks_to_avoid", "functions_to_avoid", "rejected_tasks"),
        "interest": ("interests", "preferred_directions", "goals"),
        "target_change": ("target_change", "desired_changes", "what_to_change"),
    }
    for analysis_name in ("resume_analysis", "story_analysis"):
        analysis = data.get(analysis_name) if isinstance(data.get(analysis_name), dict) else {}
        for fact_type, keys in classified_fields.items():
            for key in keys:
                raw = analysis.get(key)
                values = raw if isinstance(raw, list) else [raw]
                for value in values:
                    text = str(value or "").strip()
                    if text:
                        profile.facts.append(_fact(assessment_id, fact_type, text, f"{analysis_name}:{key}", text, .85))
        for key in ("target_roles", "career_hypotheses", "role_hypotheses"):
            raw = analysis.get(key)
            values = raw if isinstance(raw, list) else [raw]
            for value in values:
                text = str(value or "").strip()
                if text:
                    profile.facts.append(_fact(
                        assessment_id, "candidate_route", text,
                        f"{analysis_name}:{key}", text, .8,
                    ))
                    profile.facts.append(_fact(
                        assessment_id, "interest", {"kind": "target_role", "title": text},
                        f"{analysis_name}:{key}", text, .8,
                    ))

    # Never resolve conflicting confirmed facts silently. Explicitly linked
    # corrections supersede their predecessor; all other conflicts remain open.
    for fact_type in ("work_authorization", "market_context", "income_requirement", "language"):
        facts = profile.facts_of_type(fact_type)
        def conflict_key(item: CanonicalFact) -> str:
            value = str(item.normalized_value).casefold().strip()
            if fact_type == "work_authorization":
                if value in {"true", "есть", "да", "authorized"}:
                    return "yes"
                if value in {"false", "нет", "не имею", "without"}:
                    return "no"
            return value
        conflict_groups: list[list[CanonicalFact]] = []
        if fact_type == "income_requirement":
            for kind in ("current", "minimum", "target"):
                group = [f for f in facts if isinstance(f.normalized_value, dict) and f.normalized_value.get("kind") == kind and f.confidence >= .8]
                def income_key(fact: CanonicalFact) -> tuple[str, str]:
                    value = fact.normalized_value
                    raw = str(value.get("amount") or value.get("display") or "")
                    amount = "-".join(re.findall(r"\d+", raw.replace(" ", "")))
                    currency = str(value.get("currency") or "").upper()
                    if not currency:
                        currency = "EUR" if "€" in raw or "EUR" in raw.upper() else "PLN" if "PLN" in raw.upper() or "ZŁ" in raw.upper() else ""
                    return amount, currency
                values = {income_key(f) for f in group}
                if len(values) > 1:
                    conflict_groups.append(group)
        elif fact_type == "market_context":
            # Relocation preferences may coexist with a location object.
            location = [f for f in facts if isinstance(f.normalized_value, dict) and (f.normalized_value.get("city") or f.normalized_value.get("country"))]
            values = {(str(f.normalized_value.get("city") or "").casefold(), str(f.normalized_value.get("country") or "").casefold()) for f in location}
            if len(values) > 1:
                conflict_groups.append(location)
        elif len({conflict_key(item) for item in facts if item.confidence >= .8}) > 1 and fact_type == "work_authorization":
            conflict_groups.append(facts)
        for group in conflict_groups:
            for item in group:
                item.needs_clarification = True
            profile.contradictions.append([item.fact_id for item in group])

    def strings(fact_type: str) -> list[str]:
        return list(dict.fromkeys(str(f.normalized_value).strip() for f in profile.facts_of_type(fact_type) if str(f.normalized_value).strip()))
    roles = strings("profession")
    profile.current_role = roles[-1] if roles else None
    profile.professional_core = strings("professional_function") + strings("skill")
    profile.target_change = strings("target_change") + strings("undesirable_task")
    profile.candidate_routes = strings("candidate_route")
    recommended = strings("recommended_route")
    profile.recommended_route = recommended[-1] if recommended else None

    # Materialize the normalized projection consumed by final checks and route
    # generation. It contains scalar values, never an unprocessed answer blob.
    all_text = "\n".join(text for _, text, _ in sources)
    low_all = all_text.casefold().replace("ё", "е")
    market: dict[str, Any] = {}
    for fact in profile.facts_of_type("market_context"):
        if isinstance(fact.normalized_value, dict):
            market.update({k: v for k, v in fact.normalized_value.items() if v not in (None, "")})
    language_map: dict[str, str] = {}
    language_details: dict[str, dict[str, Any]] = {}
    for fact in profile.facts_of_type("language"):
        value = fact.normalized_value
        if isinstance(value, dict):
            name = str(value.get("language") or "").strip()
            level = str(value.get("level") or "").strip()
            if name and level:
                level = "native" if level.casefold().startswith(("родн", "native")) else "fluent" if level.casefold().startswith(("свобод", "fluent")) else level.upper()
                language_map[name] = level
                language_details[name] = {"language": name, "level": level, "source": fact.source_message_id, "confidence": fact.confidence}
    income_by_kind: dict[str, dict[str, Any]] = {}
    for fact in profile.facts_of_type("income_requirement"):
        value = fact.normalized_value
        if isinstance(value, dict) and value.get("kind") in {"current", "minimum", "target"}:
            income_by_kind[str(value["kind"])] = value

    def income_number(kind: str) -> float | None:
        raw = str(income_by_kind.get(kind, {}).get("amount") or income_by_kind.get(kind, {}).get("display") or "")
        match = re.search(r"\d+(?:[.,]\d+)?", raw.replace(" ", ""))
        return float(match.group().replace(",", ".")) if match else None

    # Salary currency belongs to the income entity. Do not infer or replace it
    # from residence, target market, or a differently denominated study budget.
    latest_income = income_by_kind.get("current") or income_by_kind.get("minimum") or income_by_kind.get("target") or {}
    target_raw = str(income_by_kind.get("target", {}).get("amount") or income_by_kind.get("target", {}).get("display") or "").strip() or None
    country = str(market.get("country") or "").strip() or None
    city = str(market.get("city") or "").strip() or None
    # Keep the legacy display field for existing renderers; route generation
    # uses the normalized primary/secondary fields below.
    target_market = " / ".join(item for item in (city, country) if item) or None
    target_primary = str(market.get("target_market_primary") or country or "").strip() or None
    target_secondary = str(market.get("target_market_secondary") or "").strip() or (
        "international_remote" if re.search(r"международн\w*\s+(?:удален|remote)|international\s+remote", low_all) else None
    )
    relocation_allowed = None
    if re.search(r"(?:не\s+(?:хочу|готов|могу)\s+переезж|переезж\w*\s+не\s+(?:хочу|готов|могу)|переезд\w*\s+не)", low_all):
        relocation_allowed = False
    elif re.search(r"(?:готов\w*\s+к\s+переезд|могу\s+переех|relocat)", low_all):
        relocation_allowed = True
    work_rights_value = profile.latest_value("work_authorization")
    work_rights = work_rights_value if isinstance(work_rights_value, bool) else (
        True if str(work_rights_value).casefold() in {"да", "есть", "true", "authorized"}
        else False if str(work_rights_value).casefold() in {"нет", "false", "without"} else None
    )
    experience_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:лет|года|год|years?)\s+(?:опыт|стаж)", low_all)
    hours_match = re.search(r"(\d+(?:[.,]\d+)?(?:\s*[–-]\s*\d+(?:[.,]\d+)?)?)\s*(?:час\w*|hours?)\s+(?:в\s+)?недел", low_all)
    budget_match = re.search(r"(?:бюджет\w*|обучени\w*|курс\w*)[^\d€]*(?:(€|eur|pln|zł|czk|kč)\s*)?(\d[\d\s]*)(?:\s*(€|eur|pln|zł|czk|kč))?", low_all)
    horizon_match = re.search(r"(?:за|на|в течение)\s*(\d+)\s*(месяц\w*|months?)", low_all)
    target_numbers = re.findall(r"\d+(?:[.,]\d+)?", (target_raw or "").replace(" ", ""))
    learning_facts = [f.normalized_value for f in profile.facts_of_type("learning_resource") if isinstance(f.normalized_value, dict)]
    budget_currency_token = (budget_match.group(1) or budget_match.group(3) or "") if budget_match else ""
    budget_currency = ({"€": "EUR", "EUR": "EUR", "PLN": "PLN", "ZŁ": "PLN", "CZK": "CZK", "KČ": "CZK"}.get(budget_currency_token.upper()))
    if learning_facts:
        budget_currency = str(learning_facts[-1].get("currency") or budget_currency or "") or None
    analysis_values = [data.get("story_analysis"), data.get("resume_analysis")]
    management: list[str] = []
    tools_found = list(dict.fromkeys(re.findall(r"\b(?:Excel|ERP|Power\s*BI|SQL|SAP|CRM|CAD/?CAM)\b", all_text, re.I)))
    education: list[str] = []
    for analysis in analysis_values:
        if not isinstance(analysis, dict):
            continue
        for key, destination in (("management_experience", management), ("leadership_experience", management), ("education", education)):
            raw = analysis.get(key)
            for item in raw if isinstance(raw, list) else [raw]:
                if str(item or "").strip():
                    destination.append(str(item).strip())
    profile.normalized_profile = NormalizedUserProfile(
        country=country, city=city, target_market=target_market,
        target_market_primary=target_primary, target_market_secondary=target_secondary,
        relocation_allowed=relocation_allowed,
        remote_allowed=True if re.search(r"удален|remote", low_all) else None,
        hybrid_allowed=True if re.search(r"гибрид|hybrid", low_all) else None,
        full_time=True if re.search(r"полный\s+(?:день|рабоч)|full[ -]?time", low_all) else None,
        night_shifts=False if re.search(r"без\s+ночн|ночн\w*\s+смен\w*\s+не|no night", low_all) else None,
        work_rights=work_rights, current_role=profile.current_role,
        previous_roles=roles[:-1],
        education=list(dict.fromkeys(education)),
        years_experience=float(experience_match.group(1).replace(",", ".")) if experience_match else None,
        languages=language_map, language_details=list(language_details.values()), current_income=income_number("current"),
        minimum_income=income_number("minimum"), target_income=target_raw,
        target_income_min=float(target_numbers[0].replace(",", ".")) if target_numbers else None,
        target_income_max=float(target_numbers[-1].replace(",", ".")) if len(target_numbers) > 1 else None,
        currency=str(latest_income.get("currency") or "").upper() or None,
        income_currency=str(latest_income.get("currency") or "").upper() or None,
        income_period=str(latest_income.get("period") or "month"),
        gross_net=str(latest_income.get("tax_basis") or "").lower() or None,
        schedule_constraints=strings("constraint"),
        training_hours_per_week=(hours_match.group(1).replace(" ", "") if hours_match and re.search(r"[–-]", hours_match.group(1)) else float(hours_match.group(1).replace(",", ".")) if hours_match else None),
        training_budget=float(budget_match.group(2).replace(" ", "")) if budget_match else (float(str(learning_facts[-1].get("amount"))) if learning_facts else None),
        training_budget_currency=budget_currency,
        training_horizon=f"{horizon_match.group(1)} months" if horizon_match else None,
        professional_functions=strings("professional_function"),
        transferable_skills=strings("skill"),
        management_experience=list(dict.fromkeys(management)), digital_tools=tools_found,
        desired_changes=profile.target_change, undesired_tasks=strings("undesirable_task"),
        candidate_interests=profile.candidate_routes,
    )
    issues: list[str] = []
    # A different residence currency is not a contradiction: users may be paid
    # by international employers. Only contradictory user statements are.
    if any(len(group) > 1 for group in profile.contradictions):
        profile.normalized_profile.financial_minimum_status = "conflict"
    if profile.contradictions:
        issues.append("Есть противоречащие друг другу подтверждённые факты")
    if profile.normalized_profile.target_market and len(profile.normalized_profile.target_market) > 80:
        issues.append("Целевой рынок не нормализован")
    profile.consistency_issues = issues

    state_raw = data.get("question_state") if isinstance(data.get("question_state"), dict) else {}
    profile.question_state = QuestionState.model_validate(state_raw)
    resolved = {fact.fact_type for fact in profile.facts if fact.normalized_value not in (None, "", "unknown")}
    profile.question_state.resolved_fact_types = sorted(resolved)
    return profile


QUESTION_PRIORITY = [
    ("market_context", "target_market", "Вы хотите искать работу или клиентов преимущественно в стране проживания, на международном рынке или рассматриваете оба варианта?", "Изменит рынок, доступные роли и прогноз дохода."),
    ("work_authorization", "work_authorization", "Есть ли у вас право работать на выбранном рынке без дополнительного разрешения?", "Изменит юридическую доступность маршрутов."),
    ("language", "language_level", "Какими языками вы владеете и на каком уровне?", "Изменит доступность локального рынка и уровень входа."),
    ("income_requirement", "minimum_income", "Какой минимальный ежемесячный доход позволит вам перейти без финансового риска? Укажите валюту и сумму до или после налогов.", "Изменит безопасность перехода и сравнение маршрутов."),
    ("income_requirement", "income_urgency", "Когда новый маршрут должен начать приносить необходимый доход: в течение месяца, трёх месяцев, полугода или позже?", "Изменит допустимую скорость и риск перехода."),
    ("preferred_format", "work_format", "Что вы готовы рассматривать: работу по найму, самостоятельные услуги, собственный бизнес или сочетание вариантов?", "Изменит модель занятости и основной маршрут."),
    ("market_context", "relocation_travel", "Рассматриваете ли вы релокацию или командировки, и если да — как часто?", "Изменит географическую доступность маршрутов."),
    ("interest", "change_scale", "Вы хотите остаться в своей области в другом формате или готовы осваивать новую профессию?", "Изменит выбор между смежным переходом и переобучением."),
    ("professional_function", "functions_to_preserve", "Какие функции из нынешней работы вы хотите обязательно сохранить?", "Изменит профессиональное ядро целевых ролей."),
    ("undesirable_task", "tasks_to_avoid", "Какие задачи из нынешней работы вы больше не хотите выполнять даже за более высокую зарплату?", "Изменит рейтинг и безопасность маршрутов."),
    ("constraint", "load_constraints", "Есть ли ограничения по здоровью, нагрузке или графику, которые нужно учитывать?", "Изменит допустимые ежедневные задачи и формат работы."),
    ("constraint", "learning_resources", "Сколько времени и денег вы реально готовы вложить в обучение в ближайшие шесть месяцев?", "Изменит реалистичный уровень входа и объём обучения."),
]


def _gap_is_resolved(profile: CanonicalProfile, fact_type: str, gap_id: str) -> bool:
    facts = profile.facts_of_type(fact_type)
    if gap_id == "minimum_income":
        return any(isinstance(item.normalized_value, dict) and item.normalized_value.get("kind") == "minimum" for item in facts)
    if gap_id == "income_urgency":
        return any(isinstance(item.normalized_value, dict) and item.normalized_value.get("kind") == "urgency" for item in facts)
    if gap_id == "relocation_travel":
        return any(isinstance(item.normalized_value, dict) and any(key in item.normalized_value for key in ("relocation", "travel")) for item in facts)
    if gap_id == "change_scale":
        return any(any(marker in str(item.normalized_value).casefold() for marker in ("смен", "профес", "остаться", "формат")) for item in facts)
    if gap_id == "learning_resources":
        return any(isinstance(item.normalized_value, dict) and "learning_resources" in item.normalized_value for item in facts)
    return bool(facts)


def select_clarifying_question(profile: CanonicalProfile) -> ClarifyingQuestion | None:
    state = profile.question_state
    if state.question_count >= 5:
        return None
    excluded = set(state.answered_gap_ids) | set(state.skipped_gap_ids)
    if profile.contradictions:
        facts = [fact for fact in profile.facts if fact.fact_id in profile.contradictions[0]]
        question_id = "clarify_contradiction"
        if question_id not in state.asked_question_ids and "contradiction" not in excluded:
            values = " и ".join(f"«{fact.source_quote}»" for fact in facts[:2])
            return ClarifyingQuestion(
                question_id=question_id, target_fact_type=facts[0].fact_type,
                reason="Подтверждённые ответы противоречат друг другу.",
                expected_impact="Уточнение предотвращает неверную оценку доступности маршрутов.",
                text=f"В ваших ответах встречаются разные сведения: {values}. Какой вариант актуален сейчас?",
            )
    for fact_type, gap_id, text, impact in QUESTION_PRIORITY:
        question_id = f"clarify_{gap_id}"
        if _gap_is_resolved(profile, fact_type, gap_id) or gap_id in excluded or question_id in state.asked_question_ids:
            continue
        return ClarifyingQuestion(question_id=question_id, target_fact_type=fact_type,
            reason="Параметр не найден ни в резюме, ни в описании, ни в ответах текущего assessment.",
            expected_impact=impact, text=text)
    return None


def record_question_answer(profile: CanonicalProfile, question: ClarifyingQuestion, answer: str,
                           *, source_message_id: str = "clarification") -> CanonicalProfile:
    state = profile.question_state
    if question.question_id not in state.asked_question_ids:
        state.asked_question_ids.append(question.question_id)
        state.question_count += 1
    gap_id = question.question_id.removeprefix("clarify_")
    if answer.strip().casefold() in {"не знаю", "не хочу отвечать", "пропустить", "unknown", "skip"}:
        if gap_id not in state.skipped_gap_ids:
            state.skipped_gap_ids.append(gap_id)
        return profile
    if gap_id not in state.answered_gap_ids:
        state.answered_gap_ids.append(gap_id)
    uncertain = bool(re.search(r"\b(?:наверное|может быть|не уверен|скорее всего|вроде)\b", answer, re.I))
    profile.facts.append(_fact(profile.assessment_id, question.target_fact_type, answer.strip(), source_message_id, answer.strip(), .6 if uncertain else .95))
    profile.facts[-1].needs_clarification = uncertain
    if question.target_fact_type not in state.resolved_fact_types:
        state.resolved_fact_types.append(question.target_fact_type)
    return profile
