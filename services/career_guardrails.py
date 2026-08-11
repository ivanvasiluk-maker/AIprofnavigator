"""
Career report guardrails (PATCH-25).

Each validator returns a list of error strings.
Strings prefixed [CRITICAL] block the report and trigger re-generation.
Strings prefixed [WARNING] are logged but do not block.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.evidence_profile import CareerEvidenceProfile


# ── Regulated professions that require local access check ────────────────────
_REGULATED_KEYWORDS: frozenset[str] = frozenset({
    "врач", "doctor", "physician", "медик", "медицин",
    "психолог", "психотерапевт", "psychologist", "therapist",
    "юрист", "адвокат", "нотариус", "lawyer", "attorney", "notary",
    "фармацевт", "pharmacist",
    "электрик", "electrician",
    "аудитор", "auditor",
    "бухгалтер", "accountant",
    "архитектор", "architect",
    "инженер-проектировщик",
})

# ── Generic roles forbidden without evidence per section 3 ───────────────────
_FORBIDDEN_WITHOUT_EVIDENCE: frozenset[str] = frozenset({
    "project manager", "проджект менеджер",
    "hr manager", "hr-менеджер", "hr менеджер",
    "business consultant", "бизнес-консультант", "бизнес консультант",
    "coach", "коуч", "life coach",
    "career counsellor", "карьерный консультант", "карьерный советник",
    "преподаватель", "учитель", "тренер",
    "психолог",
    "предприниматель", "entrepreneur",
    "engineering manager",
})

# ── Seniority labels that require function evidence ──────────────────────────
_HIGH_SENIORITY_LABELS: frozenset[str] = frozenset({
    "senior", "lead", "principal", "expert", "staff",
    "head of", "director", "cto", "cfo", "ceo", "c-level",
    "старший", "ведущий", "руководитель", "директор", "эксперт",
})

# ── Management/leadership role signals ───────────────────────────────────────
_MANAGEMENT_ROLE_SIGNALS: frozenset[str] = frozenset({
    "manager", "менеджер", "руководитель", "lead", "head of",
    "team lead", "тимлид", "director", "директор",
    "people management", "управление командой",
})

_CEO_LABELS: frozenset[str] = frozenset({
    "ceo", "cto", "cfo", "coo", "c-level", "chief", "вице-президент",
})


def _text_blob(report: dict) -> str:
    """Flatten all string values in the report into one searchable text."""
    parts: list[str] = []

    def _walk(obj: object) -> None:
        if isinstance(obj, str):
            parts.append(obj.lower())
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(report)
    return " ".join(parts)


def _profile_text_blob(profile: CareerEvidenceProfile) -> str:
    parts: list[str] = []
    for item in profile.work_history_facts:
        parts.append(item.statement.lower())
    for func in profile.functions:
        parts.append(func.function_name.lower())
        for ev in func.evidence:
            parts.append(ev.statement.lower())
    for item in profile.explicit_goal:
        parts.append(item.statement.lower())
    for item in profile.explicit_refusals:
        parts.append(item.statement.lower())
    for item in profile.location_and_language:
        parts.append(item.statement.lower())
    if profile.management_preference:
        parts.append(profile.management_preference.statement.lower())
    return " ".join(parts)


def _recommended_roles(report: dict) -> list[str]:
    roles: list[str] = []
    decision = report.get("career_decision")
    if isinstance(decision, dict):
        path = str(decision.get("recommended_main_path") or "")
        if path:
            roles.append(path.lower())
    for item in (report.get("career_recommendations") or []):
        if isinstance(item, dict) and item.get("title"):
            roles.append(str(item["title"]).lower())
    for item in (report.get("real_solutions") or []):
        if isinstance(item, dict) and item.get("title"):
            roles.append(str(item["title"]).lower())
    return roles


def _report_skills(report: dict) -> list[str]:
    skills: list[str] = []
    dh = report.get("digital_human")
    if isinstance(dh, dict):
        sk = dh.get("skills")
        if isinstance(sk, dict):
            for bucket in ["professional", "transferable", "hidden"]:
                for item in (sk.get(bucket) or []):
                    if isinstance(item, str) and item.strip():
                        skills.append(item.strip().lower())
    for item in (report.get("competency_signals") or []):
        if isinstance(item, str) and item.strip():
            skills.append(item.strip().lower())
    return skills


# ── Individual validators ────────────────────────────────────────────────────

def validate_no_invented_skills(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """Error 13: skills/tools not mentioned in profile narrative."""
    errors: list[str] = []
    profile_blob = _profile_text_blob(profile)
    if not profile_blob.strip():
        return errors
    suspicious: list[str] = []
    for skill in _report_skills(report):
        # Short generic skills (communication, organisation) are always allowed
        if len(skill) <= 12:
            continue
        # Tools / technologies get stricter check
        is_tool = any(token in skill for token in ["excel", "1c", "sap", "crm", "erp", "python", "sql", "autocad"])
        if not is_tool:
            continue
        if skill not in profile_blob:
            suspicious.append(skill)
    if suspicious:
        errors.append(f"[WARNING] Skills/tools in report not mentioned in history: {', '.join(suspicious[:5])}")
    return errors


def validate_explicit_refusals(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """Error 4: recommended direction explicitly refused by user."""
    errors: list[str] = []
    if not profile.explicit_refusals:
        return errors
    roles = _recommended_roles(report)
    report_blob = " ".join(roles)
    for refusal in profile.explicit_refusals:
        token = refusal.statement.strip().lower()
        if not token or len(token) < 5:
            continue
        # Check first 30 chars of refusal against recommended roles
        fragment = token[:30]
        if fragment in report_blob:
            errors.append(f"[CRITICAL] Report recommends '{fragment}' which user explicitly refused.")
    return errors


def validate_seniority_transfer(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """Error 2: seniority auto-transferred to different function without evidence."""
    errors: list[str] = []
    report_blob = _text_blob(report)
    known_functions = {f.function_name.lower() for f in profile.functions if f.function_name}
    if not known_functions:
        return errors
    for label in _HIGH_SENIORITY_LABELS:
        if label not in report_blob:
            continue
        # Only flag if high-seniority role is in a completely different domain
        # Heuristic: if profile has zero confirmed functions but report claims senior → flag
        has_any_confirmed = any(
            f.inferred_seniority and f.inferred_seniority not in {"unknown", "trainee", "junior"}
            for f in profile.functions
        )
        if not has_any_confirmed and profile.functions:
            errors.append(f"[WARNING] Report uses high-seniority label '{label}' but no confirmed seniority in evidence profile.")
            break
    return errors


def validate_regulated_professions(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """Errors 5, 6, 14: regulated profession recommended without access check."""
    errors: list[str] = []
    roles = _recommended_roles(report)
    role_blob = " ".join(roles)
    for keyword in _REGULATED_KEYWORDS:
        if keyword not in role_blob:
            continue
        legal = profile.legal_access
        if legal.profession_is_regulated is False:
            continue
        if not legal.current_permission:
            errors.append(
                f"[CRITICAL] Regulated profession '{keyword}' recommended "
                "but legal access / current permission not confirmed in profile."
            )
    return errors


def validate_function_evidence(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """Error 3: single episode turned into career profession."""
    errors: list[str] = []
    single_episode_names = {
        f.function_name.lower()
        for f in profile.functions
        if f.frequency == "single_episode" and f.function_name
    }
    if not single_episode_names:
        return errors
    roles = _recommended_roles(report)
    for role in roles:
        for name in single_episode_names:
            if name in role:
                errors.append(
                    f"[CRITICAL] Function '{name}' was a single episode in profile "
                    "but appears as main career path in report."
                )
    return errors


def validate_route_randomness(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """Error 12: generic roles without function evidence; section 3 forbidden defaults."""
    errors: list[str] = []
    profile_blob = _profile_text_blob(profile)
    roles = _recommended_roles(report)
    for role in roles:
        for forbidden in _FORBIDDEN_WITHOUT_EVIDENCE:
            if forbidden not in role:
                continue
            # Check if there is any matching evidence in profile
            if forbidden not in profile_blob:
                errors.append(
                    f"[WARNING] Generic role '{forbidden}' recommended without "
                    "corresponding function evidence in profile."
                )
    return errors


def validate_management_assumption(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """Error 9, 10: management proposed without preference evidence; entrepreneur ≠ CEO."""
    errors: list[str] = []
    roles_blob = " ".join(_recommended_roles(report))

    _NO_MGMT_TOKENS: frozenset[str] = frozenset({
        "без управления", "не хочу руководить", "без команды",
        "without management", "не хочу управлять", "не хочу быть руководителем",
        "no management", "не управлять",
    })

    # Check management_preference field
    mgmt_pref = profile.management_preference
    if mgmt_pref is not None:
        pref_text = mgmt_pref.statement.lower()
        if any(token in pref_text for token in _NO_MGMT_TOKENS):
            for signal in _MANAGEMENT_ROLE_SIGNALS:
                if signal in roles_blob:
                    errors.append(
                        f"[CRITICAL] Management role ('{signal}') proposed but user stated preference against management."
                    )
                    break

    # Also check explicit_refusals for management-related refusals
    for refusal in profile.explicit_refusals:
        ref_text = refusal.statement.lower()
        if any(token in ref_text for token in _NO_MGMT_TOKENS):
            for signal in _MANAGEMENT_ROLE_SIGNALS:
                if signal in roles_blob:
                    errors.append(
                        f"[CRITICAL] Management role ('{signal}') in report conflicts with explicit refusal: '{refusal.statement[:50]}'."
                    )
                    break
            break

    # Entrepreneur ≠ C-level without evidence
    is_entrepreneur = any(
        "предпринимател" in f.function_name.lower() or "owner" in f.function_name.lower()
        for f in profile.functions
    )
    if is_entrepreneur:
        for label in _CEO_LABELS:
            if label in roles_blob:
                has_ceo_evidence = any(
                    label in ev.statement.lower()
                    for f in profile.functions
                    for ev in f.evidence
                )
                if not has_ceo_evidence:
                    errors.append(
                        f"[WARNING] Entrepreneur in profile but report recommends '{label}' "
                        "without explicit corporate leadership evidence."
                    )
                break

    return errors


def validate_career_break_logic(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """Errors 7, 8: career break should not fully nullify prior experience or auto-restore seniority."""
    errors: list[str] = []
    if not profile.career_breaks:
        return errors
    report_blob = _text_blob(report)
    experience_blob = " ".join(ev.statement.lower() for ev in profile.work_history_facts)
    if not experience_blob:
        return errors

    # If profile has prior functions but report shows zero related skills → possible nullification
    function_names = [f.function_name.lower() for f in profile.functions if f.function_name]
    if function_names:
        functions_in_report = sum(1 for fn in function_names if fn in report_blob)
        if functions_in_report == 0:
            errors.append(
                "[WARNING] Profile contains career break AND prior functions, "
                "but none of those functions appear in report — experience may have been nullified."
            )

    # If report restores senior seniority after break without noting readiness caveat
    has_break_mention = any(token in report_blob for token in ["перерыв", "break", "gap", "пауза"])
    for label in _HIGH_SENIORITY_LABELS:
        if label in report_blob and not has_break_mention:
            errors.append(
                "[WARNING] Report assigns high seniority after career break "
                "without explicitly noting current readiness caveat."
            )
            break

    return errors


# ── New validators PATCH-2026-08 ─────────────────────────────────────────────

_ADMIN_ROLES: frozenset[str] = frozenset({
    "administrative assistant",
    "back-office specialist",
    "document controller",
    "operations coordinator",
    "office administrator",
})

_ADMIN_FUNCTION_SIGNALS: frozenset[str] = frozenset({
    "документооборот", "делопроизводство", "1с документ", "секретар",
    "document management", "document control", "back-office", "office admin",
    "канцелярия", "канцеляр",
})

_SURVIVAL_SIGNALS: frozenset[str] = frozenset({
    "без дохода", "no income", "долг", "debt",
    "срочно нужна", "urgent", "потери жилья", "housing risk",
    "финансовый дедлайн", "financial deadline",
    "быстрый доход как приоритет", "income urgency",
})

_PSYCH_INVENTED: frozenset[str] = frozenset({
    "тревога из-за переезда",
    "тревога из-за миграции",
    "страх отказов",
    "страх отказа",
    "хаос в голове",
    "финансовое давление",
    "проблемы интеграции",
    "избегание откликов",
    "паника",
})


def validate_survival_mode_evidence(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """PATCH-2026-08 §4: Survival mode requires explicit confirmed financial urgency."""
    errors: list[str] = []
    dh = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
    mode = str((dh or {}).get("strategy_mode") or "").strip()
    if mode != "Survival":
        return errors

    profile_blob = _profile_text_blob(profile)
    explicit_facts_blob = " ".join(
        str(f) for f in (
            (report.get("facts_only") or {}).get("explicit_facts") or []
            if isinstance(report.get("facts_only"), dict) else []
        )
    ).lower()
    combined = profile_blob + " " + explicit_facts_blob

    if not any(signal in combined for signal in _SURVIVAL_SIGNALS):
        errors.append(
            "[CRITICAL] strategy_mode=Survival but no confirmed financial urgency found in "
            "explicit_facts or profile. Migration alone does not justify Survival mode."
        )
    return errors


def validate_seniority_protection(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """PATCH-2026-08 §5: Senior/lead professionals must not get entry-level as primary route."""
    errors: list[str] = []
    roles = _recommended_roles(report)
    if not roles:
        return errors

    has_senior = any(
        f.inferred_seniority in {"senior", "lead", "expert"}
        or f.responsibility_scale in {"team", "department", "organization"}
        for f in profile.functions
    )
    years_senior = any(
        f.years is not None and f.years >= 5
        for f in profile.functions
    )
    if not (has_senior or years_senior):
        return errors

    refusals_blob = " ".join(r.statement.lower() for r in profile.explicit_refusals)
    user_wants_entry = any(
        token in refusals_blob
        for token in ["entry", "junior", "начальный", "любую работу", "срочно"]
    )
    if user_wants_entry:
        return errors

    explicit_facts_blob = " ".join(
        str(f) for f in (
            (report.get("facts_only") or {}).get("explicit_facts") or []
            if isinstance(report.get("facts_only"), dict) else []
        )
    ).lower()
    if any(signal in explicit_facts_blob for signal in _SURVIVAL_SIGNALS):
        return errors

    primary = roles[0].lower() if roles else ""
    for admin_role in _ADMIN_ROLES:
        if admin_role in primary:
            errors.append(
                f"[CRITICAL] Seniority protection: primary route '{roles[0]}' is an entry-level "
                "admin role for a user with 5+ years or senior-level profile, and no survival "
                "urgency was confirmed. Recommend seniority-matching roles instead."
            )
            break
    return errors


def validate_admin_roles_require_evidence(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """PATCH-2026-08 §5: Admin/back-office roles only if admin functions confirmed in profile."""
    errors: list[str] = []
    roles = _recommended_roles(report)
    if not roles:
        return errors

    profile_blob = _profile_text_blob(profile)
    has_admin_evidence = any(signal in profile_blob for signal in _ADMIN_FUNCTION_SIGNALS)
    if has_admin_evidence:
        return errors

    for role in roles:
        for admin_role in _ADMIN_ROLES:
            if admin_role in role.lower():
                errors.append(
                    f"[CRITICAL] Role '{role}' requires administrative background "
                    "but no admin function evidence found in profile. "
                    "Do not recommend admin roles without confirmed admin experience."
                )
    return errors


def validate_country_market_consistency(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """PATCH-2026-08 §8: No national market analysis if country is unconfirmed."""
    errors: list[str] = []
    location_blob = " ".join(
        item.statement.lower() for item in profile.location_and_language
    )
    explicit_country_known = any(
        token in location_blob
        for token in [
            "польш", "poland", "литв", "lithuania", "германи", "germany",
            "чехи", "czech", "нидерланд", "netherlands",
            "эстони", "латви", "финлянд",
        ]
    )
    if explicit_country_known:
        return errors

    report_blob = _text_blob(report)
    country_market_signals = [
        "польский рынок", "литовский рынок", "рынок польши", "рынок литвы",
        "pln brutto", "eur brutto", "zl brutto",
    ]
    for signal in country_market_signals:
        if signal in report_blob:
            errors.append(
                f"[WARNING] Report references '{signal}' (specific national market) "
                "but user country is not confirmed in profile. "
                "Replace country-specific salary/market data with 'требует уточнения страны'."
            )
            break
    return errors


def validate_no_invented_psychological_facts(profile: CareerEvidenceProfile, report: dict) -> list[str]:
    """PATCH-2026-08 §6: Psychological states must not be asserted without user evidence."""
    errors: list[str] = []
    profile_blob = _profile_text_blob(profile)
    report_blob = _text_blob(report)

    for phrase in _PSYCH_INVENTED:
        if phrase not in report_blob:
            continue
        if phrase in profile_blob:
            continue
        idx = report_blob.find(phrase)
        context_start = max(0, idx - 60)
        context = report_blob[context_start: idx + len(phrase) + 40]
        hedges = ["возможно", "вероятно", "похоже", "может быть", "гипотез", "if ", "если"]
        if any(hedge in context for hedge in hedges):
            continue
        errors.append(
            f"[WARNING] Psychological assertion '{phrase}' appears in report as fact "
            "but was not confirmed by user. Must be framed as hypothesis or removed."
        )
    return errors


# ── Main entry point ─────────────────────────────────────────────────────────

def validate_career_report(
    profile: CareerEvidenceProfile,
    report: dict,
) -> list[str]:
    """
    Run all guardrail validators against the generated career report.

    Returns a list of error strings.
    [CRITICAL] prefix → block report and trigger re-generation.
    [WARNING]  prefix → log only, do not block.
    """
    errors: list[str] = []
    errors += validate_no_invented_skills(profile, report)
    errors += validate_explicit_refusals(profile, report)
    errors += validate_seniority_transfer(profile, report)
    errors += validate_regulated_professions(profile, report)
    errors += validate_function_evidence(profile, report)
    errors += validate_route_randomness(profile, report)
    errors += validate_management_assumption(profile, report)
    errors += validate_career_break_logic(profile, report)
    # PATCH-2026-08: new validators
    errors += validate_survival_mode_evidence(profile, report)
    errors += validate_seniority_protection(profile, report)
    errors += validate_admin_roles_require_evidence(profile, report)
    errors += validate_country_market_consistency(profile, report)
    errors += validate_no_invented_psychological_facts(profile, report)
    return errors


def has_critical_errors(errors: list[str]) -> bool:
    return any(e.startswith("[CRITICAL]") for e in errors)
