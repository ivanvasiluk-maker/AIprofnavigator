from __future__ import annotations

import re
from typing import Any


_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9_+-]+")


def normalize_text(value: object) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def tokenize(value: object) -> set[str]:
    text = normalize_text(value)
    short_domain_tokens = {"hr", "it", "ai", "qa", "ux", "ui"}
    return {
        token for token in _TOKEN_RE.findall(text)
        if len(token) >= 3 or token in short_domain_tokens
    }


def semantic_match_score(expected: object, actual: object) -> float:
    expected_tokens = tokenize(expected)
    actual_tokens = tokenize(actual)
    if not expected_tokens or not actual_tokens:
        return 0.0
    def related(left: str, right: str) -> bool:
        if left == right:
            return True
        # The fixtures are bilingual and Russian role nouns are commonly
        # compared with inflected function verbs (электромонтажник / электромонтаж).
        # A conservative five-character stem catches that relation without
        # turning generic short words into a match.
        return min(len(left), len(right)) >= 6 and left[:5] == right[:5]

    matched = sum(1 for token in expected_tokens if any(related(token, actual) for actual in actual_tokens))
    return matched / max(1, len(expected_tokens))


def semantic_signal(expected: object, actual: object, *, threshold: float = 0.45) -> bool:
    return semantic_match_score(expected, actual) >= threshold


def flatten_strings(value: object) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        if value.strip():
            items.append(value.strip())
        return items
    if isinstance(value, dict):
        for child in value.values():
            items.extend(flatten_strings(child))
        return items
    if isinstance(value, list):
        for child in value:
            items.extend(flatten_strings(child))
    return items


def report_blob(report: dict[str, Any]) -> str:
    return "\n".join(flatten_strings(report))


def route_blocks(report: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = report.get("route_evidence_blocks")
    if isinstance(blocks, list):
        return [item for item in blocks if isinstance(item, dict)]
    routes = report.get("routes") if isinstance(report.get("routes"), dict) else {}
    recommended_id = str(routes.get("recommended_route_id") or "").strip()
    active_blocks: list[dict[str, Any]] = []
    groups = (
        ("primary_routes", "primary"),
        ("transition_routes", "transition"),
        ("quick_income_routes", "quick"),
        ("emergency_routes", "emergency"),
    )
    for group_name, default_role in groups:
        values = routes.get(group_name) if isinstance(routes.get(group_name), list) else []
        for item in values:
            if not isinstance(item, dict):
                continue
            role = "primary" if str(item.get("route_id") or "") == recommended_id else default_role
            active_blocks.append({
                "route": str(item.get("title") or "").strip(),
                "route_id": str(item.get("route_id") or "").strip(),
                "income_role": role,
                "why_it_fits": [str(item.get("why_it_fits") or "").strip()],
                "evidence_from_user": [str(value).strip() for value in item.get("evidence_ids") or [] if str(value).strip()],
                "what_may_disprove_this_route": [
                    str(value).strip() for value in item.get("disconfirming_conditions") or [] if str(value).strip()
                ],
                "missing_competencies": [str(value).strip() for value in item.get("missing") or [] if str(value).strip()],
                "risks": [str(value).strip() for value in item.get("risks") or [] if str(value).strip()],
            })
    if active_blocks:
        return active_blocks
    return []


def extract_route_slots(report: dict[str, Any]) -> dict[str, list[str]]:
    slots: dict[str, list[str]] = {
        "main_route": [],
        "transition_route": [],
        "quick_route": [],
        "emergency_route": [],
        "examples_only": [],
        "all_titles": [],
    }
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    recommended_main_path = str(decision.get("recommended_main_path") or "").strip()
    backup_path = str(decision.get("backup_path") or "").strip()
    if recommended_main_path:
        slots["main_route"].append(recommended_main_path)
    if backup_path:
        slots["transition_route"].append(backup_path)

    for block in route_blocks(report):
        route = str(block.get("route") or "").strip()
        if not route:
            continue
        role = normalize_text(block.get("income_role"))
        if role == "primary":
            slots["main_route"].append(route)
        elif role == "transition":
            slots["transition_route"].append(route)
        elif role == "quick":
            slots["quick_route"].append(route)
        elif role == "emergency":
            slots["emergency_route"].append(route)
        else:
            slots["examples_only"].append(route)

    recommendations = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
    for item in recommendations:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if title:
            slots["examples_only"].append(title)

    seen: set[str] = set()
    all_titles: list[str] = []
    for group_name in ("main_route", "transition_route", "quick_route", "emergency_route", "examples_only"):
        normalized_group: list[str] = []
        for title in slots[group_name]:
            key = normalize_text(title)
            if not key:
                continue
            normalized_group.append(title)
            if key not in seen:
                seen.add(key)
                all_titles.append(title)
        slots[group_name] = normalized_group
    slots["all_titles"] = all_titles
    return slots


def contains_contextual_route(
    expected_route: str,
    actual_titles: list[str],
    *,
    threshold: float = 0.5,
) -> tuple[bool, list[str]]:
    fragments: list[str] = []
    for actual in actual_titles:
        if semantic_signal(expected_route, actual, threshold=threshold) or normalize_text(expected_route) in normalize_text(actual):
            fragments.append(actual)
    return bool(fragments), fragments


def make_score(
    *,
    score: int,
    max_score: int,
    reason_codes: list[str] | None = None,
    supporting_fragments: list[str] | None = None,
    missing_elements: list[str] | None = None,
    evaluator_comment: str = "",
    critical_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "score": score,
        "max_score": max_score,
        "reason_codes": reason_codes or [],
        "supporting_fragments": supporting_fragments or [],
        "missing_elements": missing_elements or [],
        "evaluator_comment": evaluator_comment,
        "critical_findings": critical_findings or [],
    }


def cautious_language_present(report: dict[str, Any]) -> bool:
    blob = report_blob(report)
    markers = [
        "возможный маршрут",
        "предварительная гипотеза",
        "потребуется проверить",
        "данных недостаточно",
        "неясно",
        "нужно проверить",
        "требует проверки",
        "не подтвержден",
        "не подтверждён",
        "не указан",
    ]
    return any(marker in normalize_text(blob) for marker in markers)


def evidence_fragments(report: dict[str, Any]) -> list[str]:
    fragments: list[str] = []
    for block in route_blocks(report):
        for key in ("evidence_from_user", "why_it_fits", "what_may_disprove_this_route"):
            value = block.get(key)
            if isinstance(value, list):
                fragments.extend(str(item).strip() for item in value if str(item).strip())
    facts_only = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
    for key in ("explicit_facts", "resume_facts", "inferences", "unknowns", "contradictions"):
        value = facts_only.get(key)
        if isinstance(value, list):
            fragments.extend(str(item).strip() for item in value if str(item).strip())
    evidence = report.get("evidence") if isinstance(report.get("evidence"), list) else []
    for item in evidence:
        if isinstance(item, dict):
            fact = str(item.get("fact") or "").strip()
            if fact:
                fragments.append(fact)
    identity = report.get("identity") if isinstance(report.get("identity"), dict) else {}
    fragments.extend(str(item).strip() for item in identity.get("professional_core") or [] if str(item).strip())
    fragments.extend(str(item).strip() for item in identity.get("transferable_functions") or [] if str(item).strip())
    return fragments
