from __future__ import annotations

import copy
import re
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.canonical_profile import CanonicalProfile, build_canonical_profile


class ReportSnapshot(BaseModel):
    """Immutable, assessment-scoped input shared by generator and renderer."""

    model_config = ConfigDict(frozen=True)

    assessment_id: str
    user_id: str
    profile_version: str
    mode: str
    person_name: str | None = None
    story: dict[str, Any] = Field(default_factory=dict)
    resume: dict[str, Any] = Field(default_factory=dict)
    facts: dict[str, Any] = Field(default_factory=dict)
    routes: dict[str, Any] = Field(default_factory=dict)
    constraints: tuple[str, ...] = ()
    market_context: dict[str, Any] = Field(default_factory=dict)
    source_status: dict[str, Any] = Field(default_factory=dict)


def _texts(value: object) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item or "").strip()]


FUNCTION_ALIASES = (
    "confirmed_functions", "functions", "professional_functions",
    "recurring_functions", "tasks", "responsibilities",
)


def normalize_functions(extraction: object, source: str = "unknown") -> list[dict[str, Any]]:
    """Convert every supported extractor alias to the sole function contract."""
    payload = extraction if isinstance(extraction, dict) else {"confirmed_functions": extraction}
    result: list[dict[str, Any]] = []
    for alias in FUNCTION_ALIASES:
        raw = payload.get(alias)
        for item in raw if isinstance(raw, list) else ([raw] if raw else []):
            row = item if isinstance(item, dict) else {"label": item}
            label = str(row.get("label") or row.get("name") or row.get("title") or "").strip()
            if not label:
                continue
            function_id = str(row.get("id") or re.sub(r"[^a-zа-яё0-9]+", "_", label.casefold()).strip("_")).strip()
            result.append({
                "id": function_id,
                "label": label,
                "category": "function",
                "evidence": _texts(row.get("evidence")),
                "sources": list(dict.fromkeys(_texts(row.get("sources")) + ([source] if source != "unknown" else []))),
                "frequency": row.get("frequency") if row.get("frequency") in {"regular", "occasional", "unknown"} else "unknown",
                "confidence": row.get("confidence") if row.get("confidence") in {"high", "medium", "low"} else "medium",
            })
    return result


def merge_functions(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Union function evidence; an empty incoming extraction never erases facts."""
    merged: list[dict[str, Any]] = []
    for row in (item for group in groups for item in group):
        match = next((old for old in merged if old["id"] == row["id"] or (
            old["category"] == row["category"] and
            SequenceMatcher(None, old["label"].casefold(), row["label"].casefold()).ratio() >= .82
        )), None)
        if match is None:
            merged.append(copy.deepcopy(row))
            continue
        match["evidence"] = list(dict.fromkeys(match["evidence"] + row["evidence"]))
        match["sources"] = list(dict.fromkeys(match["sources"] + row["sources"]))
        if row["confidence"] == "high" or match["confidence"] == "low":
            match["confidence"] = row["confidence"]
        if row["frequency"] == "regular":
            match["frequency"] = "regular"
    return merged


def _person_name(story_text: str, analysis: dict[str, Any]) -> str | None:
    explicit = str(analysis.get("person_name") or analysis.get("name") or "").strip()
    if explicit:
        return explicit.split()[0]
    match = re.search(r"меня\s+зовут\s+([А-ЯЁA-Z][а-яёa-z]+)", story_text, re.I)
    if not match:
        match = re.search(r"(?:^|[.!?]\s+)я[\s,—-]+([А-ЯЁA-Z][а-яёa-z]+)", story_text, re.I)
    return match.group(1).title() if match else None


def _selected_route(data: dict[str, Any]) -> str:
    report = data.get("final_report") if isinstance(data.get("final_report"), dict) else {}
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    return str(
        data.get("selected_preliminary_route")
        or data.get("route_specific_selected_route")
        or decision.get("recommended_main_path")
        or ""
    ).strip()


def _route_hypotheses(data: dict[str, Any], selected: str) -> list[dict[str, Any]]:
    rows = data.get("route_hypotheses") if isinstance(data.get("route_hypotheses"), list) else []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in ([{"title": selected}] if selected else []) + rows:
        payload = row if isinstance(row, dict) else {"title": row}
        title = str(payload.get("title") or payload.get("role") or payload.get("route") or "").strip()
        key = title.casefold()
        if title and key not in seen:
            seen.add(key)
            result.append({**copy.deepcopy(payload), "title": title})
    return result


def build_report_snapshot(data: dict[str, Any]) -> ReportSnapshot:
    assessment_id = str(data.get("assessment_id") or "").strip()
    if not assessment_id:
        raise ValueError("assessment_id is required for report snapshot")
    canonical: CanonicalProfile = build_canonical_profile(data, assessment_id=assessment_id)
    normalized = canonical.normalized_profile
    story_analysis = copy.deepcopy(data.get("story_analysis") if isinstance(data.get("story_analysis"), dict) else {})
    resume_analysis = copy.deepcopy(data.get("resume_analysis") if isinstance(data.get("resume_analysis"), dict) else {})
    confirmed_functions = merge_functions(
        normalize_functions({"confirmed_functions": normalized.professional_functions}, "persisted"),
        normalize_functions(story_analysis, "story"),
        normalize_functions(resume_analysis, "resume"),
    )
    functions = [row["label"] for row in confirmed_functions]
    evidence = [
        str(fact.normalized_value).strip()
        for fact in canonical.facts
        if fact.fact_type in {"professional_function", "responsibility", "achievement"}
        and str(fact.normalized_value).strip()
    ]
    selected = _selected_route(data)
    route_hypotheses = _route_hypotheses(data, selected)
    country = "Czech Republic" if normalized.country == "Czechia" else normalized.country
    city = "Brno" if str(normalized.city or "").casefold() == "брно" else normalized.city
    mode_raw = str(data.get("user_mode") or data.get("mode") or "").strip().casefold()
    mode = "quick" if mode_raw in {"fast", "quick"} else "deep"
    story_text = str(data.get("story_text") or "")
    experience_match = re.search(r"(\d+)\s*[-–]?\s*лет(?:ним|него|ний|\s+опыт)", story_text, re.I)
    source_rows = [
        row for key in ("source_messages", "uploaded_documents", "qa_answers")
        for row in (data.get(key) or []) if isinstance(row, dict)
    ]
    source_ids = sorted({str(row.get("assessment_id") or assessment_id) for row in source_rows})
    resume_loaded = bool(resume_analysis) and str(data.get("resume_parse_status") or "completed") == "completed"
    return ReportSnapshot(
        assessment_id=assessment_id,
        user_id=str(data.get("public_user_id") or ""),
        profile_version=str(data.get("profile_version") or assessment_id),
        mode=mode,
        person_name=_person_name(story_text, story_analysis),
        story={"analysis": story_analysis, "present": bool(story_text.strip())},
        resume={"analysis": resume_analysis, "loaded": resume_loaded},
        facts={
            **normalized.model_dump(mode="json"),
            "country": country,
            "city": city,
            "professional_functions": functions,
            "confirmed_functions": confirmed_functions,
            "years_experience": normalized.years_experience or (int(experience_match.group(1)) if experience_match else None),
            "team_size": int(re.search(r"(?:команд\w*|подчинени\w*)[^\d]{0,20}(\d+)", story_text, re.I).group(1)) if re.search(r"(?:команд\w*|подчинени\w*)[^\d]{0,20}(\d+)", story_text, re.I) else None,
        },
        routes={
            "selected": {
                "title": selected,
                "status": "user_selected_hypothesis",
                "evidence": list(dict.fromkeys(evidence)),
                "confirmed_functions": functions,
            } if selected else {},
            "hypotheses": route_hypotheses,
        },
        constraints=tuple(normalized.schedule_constraints),
        market_context={
            "country": country,
            "city": city,
            "target_market": normalized.target_market,
            "formats": normalized.target_market_formats,
        },
        source_status={
            "story_persisted": bool(story_text.strip()),
            "resume_parse_status": str(data.get("resume_parse_status") or ("completed" if resume_analysis else "not_provided")),
            "resume_loaded": resume_loaded,
            "source_assessment_ids": source_ids or [assessment_id],
            "resolved_fact_types": list(data.get("resolved_fact_types") or []),
        },
    )


def structured_identity_summary(snapshot: ReportSnapshot) -> str:
    facts = snapshot.facts
    name = snapshot.person_name or "Специалист"
    role = str(facts.get("current_role") or "специалист с подтверждённым профессиональным опытом")
    years = facts.get("years_experience")
    functions = _texts(facts.get("professional_functions"))[:5]
    capital = ", ".join(functions) if functions else "подтверждённые функции текущей оценки"
    first = f"{name} — {role.lower()}" + (f" с {int(years)}-летним опытом." if years else ".")
    second = f"Сильнейший профессиональный капитал: {capital}."
    selected = snapshot.routes.get("selected") if isinstance(snapshot.routes.get("selected"), dict) else {}
    third = (
        f"Маршрут {selected.get('title')} сохранён как выбранная пользователем гипотеза и проверяется по фактам текущей оценки."
        if selected else "Маршруты проверяются только по фактам текущей оценки."
    )
    return " ".join((first, second, third))


def validate_report_snapshot(snapshot: ReportSnapshot, raw_story: str = "") -> list[str]:
    errors: list[str] = []
    facts = snapshot.facts
    location_claim = re.search(
        r"(?:жив(?:у|ёт|ем)|нахожусь|переехал[аи]?|live|based|moved)\s+(?:сейчас\s+)?(?:в|in|to)\s+[^.!?\n]+",
        raw_story,
        re.I,
    )
    if location_claim and not facts.get("country"):
        errors.append("COUNTRY_LOST_FROM_STORY")
    if location_claim and not facts.get("city"):
        errors.append("CITY_LOST_FROM_STORY")
    if snapshot.source_status.get("resume_parse_status") == "completed" and not snapshot.resume.get("loaded"):
        errors.append("COMPLETED_RESUME_NOT_LOADED")
    functions = _texts(facts.get("professional_functions"))
    selected = snapshot.routes.get("selected") if isinstance(snapshot.routes.get("selected"), dict) else {}
    if selected and (len(functions) < 2 or len(_texts(selected.get("evidence"))) < 2):
        errors.append("SELECTED_ROUTE_WITHOUT_EVIDENCE")
    if re.search(r"\d[\d\s]*(?:–|-)\s*\d[\d\s]*\s*CZK|\d[\d\s]*\s*CZK", raw_story, re.I) and not any(facts.get(key) is not None for key in ("current_income", "minimum_income", "target_income")):
        errors.append("INCOME_LOST_FROM_STORY")
    if re.search(r"(?:русск|чешск|английск|russian|czech|english)", raw_story, re.I) and not facts.get("languages"):
        errors.append("LANGUAGES_LOST_FROM_STORY")
    if snapshot.mode not in {"quick", "deep"}:
        errors.append("INVALID_MODE")
    if any(source_id != snapshot.assessment_id for source_id in snapshot.source_status.get("source_assessment_ids", [])):
        errors.append("CROSS_ASSESSMENT_SOURCE")
    if snapshot.story.get("present") and len(functions) < 2:
        errors.append("PROFESSIONAL_FUNCTIONS_MISSING")
    return list(dict.fromkeys(errors))


def validate_report_consistency(snapshot: ReportSnapshot, assessment: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metadata = assessment.get("metadata") if isinstance(assessment.get("metadata"), dict) else {}
    if str(assessment.get("assessment_id") or "") != snapshot.assessment_id:
        errors.append("ASSESSMENT_ID_MISMATCH")
    if str(metadata.get("report_mode") or "") != snapshot.mode:
        errors.append("MODE_MISMATCH")
    if bool(metadata.get("resume_loaded")) != bool(snapshot.resume.get("loaded")):
        errors.append("RESUME_STATUS_MISMATCH")
    rendered_blob = str(assessment).casefold()
    if "критичных неизвестных нет" in rendered_blob and "данных недостаточно" in rendered_blob:
        errors.append("CONTRADICTORY_UNCERTAINTY")
    selected = snapshot.routes.get("selected") if isinstance(snapshot.routes.get("selected"), dict) else {}
    selected_title = str(selected.get("title") or "").strip()
    selected_supported = len(_texts(selected.get("evidence"))) >= 2 and len(_texts(selected.get("confirmed_functions"))) >= 2
    routes = assessment.get("routes") if isinstance(assessment.get("routes"), dict) else {}
    all_routes = [
        row for key in ("primary_routes", "transition_routes", "quick_income_routes", "emergency_routes")
        for row in (routes.get(key) or []) if isinstance(row, dict)
    ]
    route_titles = {str(row.get("title") or "").strip().casefold() for row in all_routes}
    if selected_title and selected_supported and selected_title.casefold() not in route_titles:
        errors.append("SUPPORTED_SELECTED_ROUTE_DROPPED")
    recommended_id = str(routes.get("recommended_route_id") or "")
    recommended = next((row for row in all_routes if str(row.get("route_id") or "") == recommended_id), {})
    if selected_title and selected_supported and str(recommended.get("title") or "").strip().casefold() != selected_title.casefold():
        errors.append("SUPPORTED_SELECTED_ROUTE_NOT_RECOMMENDED")
    return errors
