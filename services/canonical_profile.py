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
    "work_authorization", "preferred_format",
]

CITY_COUNTRIES = {
    "porto": ("Portugal", "PT"), "порту": ("Portugal", "PT"),
    "vilnius": ("Lithuania", "LT"), "вильнюс": ("Lithuania", "LT"),
    "warsaw": ("Poland", "PL"), "варшава": ("Poland", "PL"),
    "riga": ("Latvia", "LV"), "рига": ("Latvia", "LV"),
    "tallinn": ("Estonia", "EE"), "таллин": ("Estonia", "EE"),
}


class CanonicalFact(BaseModel):
    fact_id: str
    assessment_id: str
    fact_type: FactType
    normalized_value: Any
    source_message_id: str
    source_quote: str
    confidence: float = Field(ge=0, le=1)
    created_at: str
    supersedes_fact_id: str | None = None


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

    def facts_of_type(self, fact_type: str) -> list[CanonicalFact]:
        return [fact for fact in self.facts if fact.fact_type == fact_type]

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
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
    )


def build_canonical_profile(data: dict[str, Any], *, assessment_id: str) -> CanonicalProfile:
    """Build the sole report input without truncating source messages.

    Structured answers are appended after the original story/resume and therefore win when
    ``latest_value`` is used. Conflicting evidence remains in ``facts`` for auditability.
    """
    profile = CanonicalProfile(assessment_id=assessment_id)
    sources: list[tuple[str, str, str]] = []
    for key in ("story_text", "answers_text"):
        text = str(data.get(key) or "")
        if text.strip():
            sources.append((key, text, ""))
    for row in data.get("source_messages") or []:
        if isinstance(row, dict) and str(row.get("text") or "").strip():
            sources.append((str(row.get("message_id") or "message"), str(row["text"]), str(row.get("created_at") or "")))
    for row in data.get("qa_answers") or []:
        if isinstance(row, dict) and str(row.get("answer") or "").strip():
            sources.append((str(row.get("source_message_id") or row.get("question_id") or "clarification"), str(row["answer"]), str(row.get("created_at") or "")))

    route = data.get("route_context") if isinstance(data.get("route_context"), dict) else {}
    structured = {
        "country": route.get("country") or data.get("country"), "city": route.get("city") or data.get("city"),
        "work_authorization": route.get("documents_and_work_rights") or data.get("work_authorization_status"),
        "minimum_income": route.get("minimum_monthly_income") or data.get("minimum_income"),
        "target_income": route.get("desired_monthly_income") or data.get("target_income"),
        "income_urgency": route.get("income_urgency") or data.get("income_urgency"),
        "language": route.get("current_language_level") or data.get("current_language_level"),
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
                profile.facts.append(_fact(assessment_id, "market_context", {"city": city.title(), "country": country, "country_code": code}, message_id, text, .98, created_at or None))
                break
        for match in re.finditer(r"(?:€|eur\s*)\s?(\d[\d\s]*(?:[–-]\d[\d\s]*)?)\s*(net|gross)?", text, re.I):
            context = text[max(0, match.start() - 35):match.end() + 35]
            kind = "minimum" if re.search(r"миним|minimum", context, re.I) else "target" if re.search(r"цел|жела|target", context, re.I) else "current"
            profile.facts.append(_fact(assessment_id, "income_requirement", {"kind": kind, "amount": match.group(1).replace(" ", ""), "currency": "EUR", "tax_basis": (match.group(2) or "unknown").lower(), "period": "month"}, message_id, context, .9, created_at or None))
        if re.search(r"прав[оа]\s+на\s+работ|work authori[sz]", low):
            authorized = not bool(re.search(r"нет|не име|without", low))
            profile.facts.append(_fact(assessment_id, "work_authorization", authorized, message_id, text, .9, created_at or None))
        for match in re.finditer(r"(русск\w*|португальск\w*|английск\w*|russian|portuguese|english)\s*[—:=-]?\s*(родн\w*|[abc][12]|native)", low, re.I):
            profile.facts.append(_fact(assessment_id, "language", {"language": match.group(1), "level": match.group(2).upper()}, message_id, match.group(0), .95, created_at or None))

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
    add_structured("work_authorization", structured["work_authorization"], str(structured["work_authorization"] or ""))
    for kind in ("minimum_income", "target_income"):
        add_structured("income_requirement", {"kind": "minimum" if kind == "minimum_income" else "target", "display": structured[kind]}, str(structured[kind] or ""))
    add_structured("income_requirement", {"kind": "urgency", "display": structured["income_urgency"]}, str(structured["income_urgency"] or ""))
    add_structured("language", {"display": structured["language"]}, str(structured["language"] or ""))
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
                        assessment_id, "interest", {"kind": "target_role", "title": text},
                        f"{analysis_name}:{key}", text, .8,
                    ))

    authorization_facts = profile.facts_of_type("work_authorization")
    normalized_auth = {str(item.normalized_value).casefold() for item in authorization_facts}
    if len(normalized_auth) > 1:
        profile.contradictions.append([item.fact_id for item in authorization_facts])

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
    profile.facts.append(_fact(profile.assessment_id, question.target_fact_type, answer.strip(), source_message_id, answer.strip(), .95))
    if question.target_fact_type not in state.resolved_fact_types:
        state.resolved_fact_types.append(question.target_fact_type)
    return profile
