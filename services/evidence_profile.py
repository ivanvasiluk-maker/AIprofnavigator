from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["confirmed", "probable", "weak", "unknown"]
EvidenceSource = Literal[
    "user_story",
    "user_clarification",
    "resume",
    "button",
    "system_inference",
]


class EvidenceItem(BaseModel):
    statement: str
    source: EvidenceSource
    source_fragment: str | None = None
    confidence: Confidence
    contradicts: list[str] = Field(default_factory=list)


class FunctionEvidence(BaseModel):
    function_name: str
    evidence: list[EvidenceItem] = Field(default_factory=list)

    years: float | None = None
    frequency: Literal[
        "daily",
        "weekly",
        "periodic",
        "single_episode",
        "unknown",
    ] = "unknown"

    autonomy: Literal[
        "observed",
        "assisted",
        "followed_instructions",
        "performed_independently",
        "owned_full_process",
        "improved_process",
        "created_methodology",
        "unknown",
    ] = "unknown"

    responsibility_scale: Literal[
        "task",
        "client",
        "process",
        "project",
        "team",
        "department",
        "organization",
        "unknown",
    ] = "unknown"

    demonstrated_results: list[str] = Field(default_factory=list)
    inferred_seniority: str | None = None
    seniority_confidence: Confidence = "unknown"


class LegalAccess(BaseModel):
    profession_is_regulated: bool | None = None
    qualification_status: str | None = None
    current_permission: str | None = None
    missing_requirements: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class SeniorityAssessment(BaseModel):
    function_name: str
    level: Literal[
        "trainee",
        "junior",
        "strong_junior",
        "middle",
        "senior",
        "lead",
        "expert",
        "unknown",
    ]
    evidence_summary: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    confidence: Confidence


class CareerEvidenceProfile(BaseModel):
    explicit_goal: list[EvidenceItem] = Field(default_factory=list)
    explicit_refusals: list[EvidenceItem] = Field(default_factory=list)

    work_history_facts: list[EvidenceItem] = Field(default_factory=list)
    functions: list[FunctionEvidence] = Field(default_factory=list)

    preferred_tasks: list[EvidenceItem] = Field(default_factory=list)
    rejected_tasks: list[EvidenceItem] = Field(default_factory=list)

    education: list[EvidenceItem] = Field(default_factory=list)
    legal_access: LegalAccess = Field(default_factory=LegalAccess)

    career_breaks: list[EvidenceItem] = Field(default_factory=list)
    health_or_load_constraints: list[EvidenceItem] = Field(default_factory=list)
    location_and_language: list[EvidenceItem] = Field(default_factory=list)

    minimum_income: EvidenceItem | None = None
    income_deadline: EvidenceItem | None = None
    acceptable_transition_level: EvidenceItem | None = None

    management_preference: EvidenceItem | None = None
    work_format_preferences: list[EvidenceItem] = Field(default_factory=list)

    function_seniority: list[SeniorityAssessment] = Field(default_factory=list)
    professional_maturity: EvidenceItem | None = None
    current_functional_readiness: EvidenceItem | None = None
    local_legal_access_status: EvidenceItem | None = None
    market_entry_level: EvidenceItem | None = None

    contradictions: list[str] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)


_GAP_DEFINITIONS: dict[str, dict[str, object]] = {
    "professional_core": {
        "priority": 100,
        "critical": True,
        "goal": "Уточнить профессиональное ядро и реальные рабочие функции.",
        "question_ru": "Какие 2-3 рабочие функции у вас получаются сильнее всего и чем это подтверждается в опыте?",
        "question_be": "Якія 2-3 працоўныя функцыі ў вас атрымліваюцца найлепш і чым гэта пацвярджаецца ў досведзе?",
        "block": "professional_experience",
    },
    "minimum_income": {
        "priority": 95,
        "critical": True,
        "goal": "Зафиксировать минимальный доход для безопасного выбора маршрута.",
        "question_ru": "Какой минимальный доход в месяц вам нужен, чтобы стабилизировать ситуацию?",
        "question_be": "Які мінімальны даход у месяц вам патрэбны, каб стабілізаваць сітуацыю?",
        "block": "financial_pressure",
    },
    "income_deadline": {
        "priority": 92,
        "critical": True,
        "goal": "Понять допустимый срок до первого дохода.",
        "question_ru": "Как быстро нужен первый стабильный доход?",
        "question_be": "Наколькі хутка патрэбны першы стабільны даход?",
        "block": "financial_pressure",
        "options": ["⚡ 2-4 недели", "📆 1-3 месяца", "📚 3-6 месяцев", "🧭 Можно дольше"],
    },
    "legal_access": {
        "priority": 88,
        "critical": True,
        "goal": "Проверить ограничения доступа к профессии и праву на работу.",
        "question_ru": "Что сейчас с документами, правом на работу и признанием квалификации?",
        "question_be": "Што цяпер з дакументамі, правам на працу і прызнаннем кваліфікацыі?",
        "block": "legal_access",
    },
    "location_language": {
        "priority": 84,
        "critical": True,
        "goal": "Оценить локальный контекст языка и интеграции для входа на рынок.",
        "question_ru": "Какие языки вы знаете и на каком уровне сейчас можете использовать их в работе?",
        "question_be": "Якія мовы вы ведаеце і на якім узроўні цяпер можаце выкарыстоўваць іх у працы?",
        "block": "language_local_context",
    },
    "work_constraints": {
        "priority": 80,
        "critical": True,
        "goal": "Зафиксировать ограничения, влияющие на безопасность рекомендаций.",
        "question_ru": "Какие ограничения важно учесть сейчас: здоровье, график, дети, переезды, нагрузка?",
        "question_be": "Якія абмежаванні важна ўлічыць цяпер: здароўе, графік, дзеці, пераезды, нагрузка?",
        "block": "constraints",
    },
    "functional_readiness": {
        "priority": 72,
        "critical": False,
        "goal": "Понять актуальную готовность к входу в роль и стартовый уровень.",
        "question_ru": "С какой роли и уровня вы готовы начать сейчас, если это даст быстрый вход?",
        "question_be": "З якой ролі і ўзроўню вы гатовы пачаць цяпер, калі гэта дасць хуткі ўваход?",
        "block": "professional_experience",
    },
    "support_and_load": {
        "priority": 66,
        "critical": False,
        "goal": "Оценить поддерживающий контекст и устойчивость темпа.",
        "question_ru": "Есть ли у вас сейчас поддержка и сколько ресурса на действия в неделю?",
        "question_be": "Ці ёсць у вас цяпер падтрымка і колькі рэсурсу на дзеянні на тыдзень?",
        "block": "social_support",
    },
    "transition_level": {
        "priority": 60,
        "critical": False,
        "goal": "Определить приемлемый переходный уровень для входа в рынок.",
        "question_ru": "Готовы ли вы временно начать с переходной роли ниже прошлого статуса?",
        "question_be": "Ці гатовы вы часова пачаць з пераходнай ролі ніжэй за мінулы статус?",
        "block": "career_transition",
        "options": ["Да", "Да, но временно", "Не уверен(а)", "Нет"],
    },
}


def build_evidence_profile_from_analysis(analysis: dict | None) -> CareerEvidenceProfile:
    data = analysis if isinstance(analysis, dict) else {}
    profile = CareerEvidenceProfile()

    for goal in data.get("goals", []) if isinstance(data.get("goals"), list) else []:
        text = str(goal).strip()
        if not text:
            continue
        profile.explicit_goal.append(
            EvidenceItem(
                statement=text,
                source="user_story",
                confidence="probable",
            )
        )

    for row in data.get("experience_snapshot", []) if isinstance(data.get("experience_snapshot"), list) else []:
        text = str(row).strip()
        if not text:
            continue
        profile.work_history_facts.append(
            EvidenceItem(
                statement=text,
                source="user_story",
                confidence="probable",
            )
        )

    missing = [str(item).strip().lower() for item in data.get("missing_data", []) if str(item).strip()] if isinstance(data.get("missing_data"), list) else []
    gaps: list[str] = []

    if not profile.work_history_facts:
        gaps.append("professional_core")
    if not profile.explicit_goal:
        gaps.append("functional_readiness")

    if any(token in " ".join(missing) for token in ["доход", "income", "зарплат"]):
        gaps.append("minimum_income")
    if any(token in " ".join(missing) for token in ["срок", "быстро", "urgency", "deadline"]):
        gaps.append("income_deadline")
    if any(token in " ".join(missing) for token in ["документ", "право", "license", "legal"]):
        gaps.append("legal_access")
    if any(token in " ".join(missing) for token in ["язык", "language", "интеграц", "local"]):
        gaps.append("location_language")
    if any(token in " ".join(missing) for token in ["огранич", "здоров", "дет", "график", "load"]):
        gaps.append("work_constraints")
    if any(token in " ".join(missing) for token in ["поддерж", "support", "ресурс"]):
        gaps.append("support_and_load")
    if any(token in " ".join(missing) for token in ["уров", "level", "entry"]):
        gaps.append("transition_level")

    if not gaps:
        gaps = ["minimum_income", "income_deadline", "legal_access", "location_language"]

    # Preserve order by business priority and avoid duplicates.
    dedup = {key for key in gaps if key in _GAP_DEFINITIONS}
    ordered = sorted(dedup, key=lambda key: int(_GAP_DEFINITIONS[key]["priority"]))
    ordered.reverse()
    profile.unresolved_gaps = ordered
    return profile


def next_question_from_profile(
    profile: CareerEvidenceProfile,
    *,
    language: str = "ru",
    asked_gap_keys: set[str] | None = None,
    user_mode: str = "calm_steps",
) -> dict[str, object] | None:
    from services.interview_policy import select_next_gap

    asked = asked_gap_keys or set()

    # Policy-driven selection: scored, behavioural, prohibition-aware
    result = select_next_gap(profile, asked_gaps=asked, user_mode=user_mode, language=language)
    if result is not None:
        return result

    # Fallback: legacy gap definitions for profile gaps not covered by policy
    for gap_key in profile.unresolved_gaps:
        if gap_key in asked:
            continue
        meta = _GAP_DEFINITIONS.get(gap_key)
        if not meta:
            continue
        use_be = (language or "ru") == "be"
        question_text = str(meta["question_be"] if use_be else meta["question_ru"]).strip()
        if not question_text:
            continue
        options = meta.get("options") if isinstance(meta.get("options"), list) else []
        return {
            "id": 1,
            "question": question_text,
            "block": str(meta.get("block") or "professional_experience"),
            "type": "single_choice" if options else "short_text",
            "options": [str(item).strip() for item in options if str(item).strip()],
            "question_id": f"gap_{gap_key}",
            "gap_key": gap_key,
            "internal_goal": str(meta.get("goal") or "").strip(),
            "critical_gap": bool(meta.get("critical", False)),
            "question_value": int(meta.get("priority", 0)),
            "source": "evidence_gap",
            "validity_status": "needs_confirmation",
        }
    return None


def apply_answer_to_profile(profile: CareerEvidenceProfile, gap_key: str, answer_text: str) -> CareerEvidenceProfile:
    text = str(answer_text or "").strip()
    if not text:
        return profile

    evidence = EvidenceItem(
        statement=text,
        source="user_clarification",
        confidence="probable",
    )
    if gap_key == "minimum_income":
        profile.minimum_income = evidence
    elif gap_key == "income_deadline":
        profile.income_deadline = evidence
    elif gap_key == "work_constraints":
        profile.health_or_load_constraints.append(evidence)
    elif gap_key == "location_language":
        profile.location_and_language.append(evidence)
    elif gap_key == "legal_access":
        profile.legal_access.evidence.append(evidence)
    elif gap_key == "support_and_load":
        profile.work_format_preferences.append(evidence)
    elif gap_key == "functional_readiness":
        profile.acceptable_transition_level = evidence
    elif gap_key == "professional_core":
        profile.work_history_facts.append(evidence)
    elif gap_key == "transition_level":
        profile.current_functional_readiness = evidence

    profile.unresolved_gaps = [item for item in profile.unresolved_gaps if item != gap_key]
    return profile


def profile_ready_for_safe_conclusion(profile: CareerEvidenceProfile) -> bool:
    critical = [key for key in profile.unresolved_gaps if bool(_GAP_DEFINITIONS.get(key, {}).get("critical", False))]
    return len(critical) == 0
