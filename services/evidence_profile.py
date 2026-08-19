from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["confirmed", "probable", "weak", "unknown"]
DataImportance = Literal["blocking", "useful", "optional"]
MAX_ADDITIONAL_QUESTIONS = 7
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
    current_income: EvidenceItem | None = None
    income_deadline: EvidenceItem | None = None
    acceptable_transition_level: EvidenceItem | None = None

    management_preference: EvidenceItem | None = None
    work_format_preferences: list[EvidenceItem] = Field(default_factory=list)

    function_seniority: list[SeniorityAssessment] = Field(default_factory=list)
    professional_maturity: EvidenceItem | None = None
    current_functional_readiness: EvidenceItem | None = None
    local_legal_access_status: EvidenceItem | None = None
    market_entry_level: EvidenceItem | None = None

    residence_country: EvidenceItem | None = None
    residence_city: EvidenceItem | None = None
    target_countries: list[EvidenceItem] = Field(default_factory=list)
    work_authorization: EvidenceItem | None = None
    work_languages: list[EvidenceItem] = Field(default_factory=list)
    target_market_format: EvidenceItem | None = None
    preferred_currency: EvidenceItem | None = None
    relocation_possible: EvidenceItem | None = None
    salary_target: EvidenceItem | None = None
    transition_timeline: EvidenceItem | None = None
    learning_capacity: EvidenceItem | None = None
    acceptable_income_drop: EvidenceItem | None = None
    desired_change_scale: EvidenceItem | None = None
    functions_to_preserve: list[EvidenceItem] = Field(default_factory=list)
    functions_to_avoid: list[EvidenceItem] = Field(default_factory=list)

    contradictions: list[str] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)


_GAP_DEFINITIONS: dict[str, dict[str, object]] = {
    "residence_country": {
        "priority": 112, "critical": True, "importance": "blocking",
        "goal": "Отделить страну проживания от целевого рынка.",
        "question_ru": "В какой стране вы сейчас живёте?",
        "question_be": "У якой краіне вы цяпер жывяце?",
        "block": "market_context",
    },
    "target_country": {
        "priority": 110, "critical": True, "importance": "blocking",
        "goal": "Определить рынок, который materially меняет валюту, вакансии и право на работу.",
        "question_ru": "Вы хотите искать работу или клиентов преимущественно в стране проживания, на международном удалённом рынке или рассматриваете оба варианта?",
        "question_be": "У якой краіне або краінах вы плануеце шукаць працу?",
        "block": "market_context",
    },
    "work_authorization": {
        "priority": 108, "critical": True, "importance": "blocking",
        "goal": "Проверить юридическую доступность целевого рынка.",
        "question_ru": "Есть ли у вас право на работу на выбранном рынке или ограничения, которые важно учесть?",
        "question_be": "Ці ёсць у вас права на працу на абраным рынку або абмежаванні, якія важна ўлічыць?",
        "block": "legal_access",
    },
    "work_languages": {
        "priority": 106, "critical": True, "importance": "blocking",
        "goal": "Определить языки, на которых доступна профессиональная работа.",
        "question_ru": "На каких языках и примерно на каком уровне вы можете работать с работодателями или клиентами?",
        "question_be": "На якіх мовах і прыкладна на якім узроўні вы можаце працаваць з працадаўцамі або кліентамі?",
        "block": "language_local_context",
    },
    "professional_core": {
        "priority": 100,
        "critical": True, "importance": "blocking",
        "goal": "Уточнить профессиональное ядро и реальные рабочие функции.",
        "question_ru": "Какие 2-3 рабочие функции у вас получаются сильнее всего и чем это подтверждается в опыте?",
        "question_be": "Якія 2-3 працоўныя функцыі ў вас атрымліваюцца найлепш і чым гэта пацвярджаецца ў досведзе?",
        "block": "professional_experience",
    },
    "minimum_income": {
        "priority": 95,
        "critical": False, "importance": "useful",
        "goal": "Зафиксировать минимальный доход для безопасного выбора маршрута.",
        "question_ru": "Какой минимальный доход в месяц вам нужен, чтобы стабилизировать ситуацию?",
        "question_be": "Які мінімальны даход у месяц вам патрэбны, каб стабілізаваць сітуацыю?",
        "block": "financial_pressure",
    },
    "income_deadline": {
        "priority": 92,
        "critical": False, "importance": "useful",
        "goal": "Понять допустимый срок до первого дохода.",
        "question_ru": "Как быстро нужен первый стабильный доход?",
        "question_be": "Наколькі хутка патрэбны першы стабільны даход?",
        "block": "financial_pressure",
        "options": ["⚡ 2-4 недели", "📆 1-3 месяца", "📚 3-6 месяцев", "🧭 Можно дольше"],
    },
    "legal_access": {
        "priority": 88,
        "critical": True, "importance": "blocking",
        "goal": "Проверить ограничения доступа к профессии и праву на работу.",
        "question_ru": "Что сейчас с документами, правом на работу и признанием квалификации?",
        "question_be": "Што цяпер з дакументамі, правам на працу і прызнаннем кваліфікацыі?",
        "block": "legal_access",
    },
    "location_language": {
        "priority": 84,
        "critical": True, "importance": "blocking",
        "goal": "Оценить локальный контекст языка и интеграции для входа на рынок.",
        "question_ru": "Какие языки вы знаете и на каком уровне сейчас можете использовать их в работе?",
        "question_be": "Якія мовы вы ведаеце і на якім узроўні цяпер можаце выкарыстоўваць іх у працы?",
        "block": "language_local_context",
    },
    "work_constraints": {
        "priority": 80,
        "critical": False, "importance": "useful",
        "goal": "Зафиксировать ограничения, влияющие на безопасность рекомендаций.",
        "question_ru": "Какие ограничения важно учесть сейчас: здоровье, график, дети, переезды, нагрузка?",
        "question_be": "Якія абмежаванні важна ўлічыць цяпер: здароўе, графік, дзеці, пераезды, нагрузка?",
        "block": "constraints",
    },
    "work_format": {
        "priority": 78, "critical": False, "importance": "useful",
        "goal": "Отфильтровать роли по доступному формату.",
        "question_ru": "Какой формат вам доступен: удалённо, офис или гибрид?",
        "question_be": "Які фармат вам даступны: аддалена, офіс або гібрыд?",
        "block": "market_context",
    },
    "relocation": {
        "priority": 76, "critical": False, "importance": "useful",
        "goal": "Понять географию доступного рынка.",
        "question_ru": "Готовы ли вы к релокации, если подходящей роли нет рядом?",
        "question_be": "Ці гатовы вы да рэлакацыі, калі падыходзячай ролі няма побач?",
        "block": "market_context",
    },
    "salary_target": {
        "priority": 70, "critical": False, "importance": "useful",
        "goal": "Отделить желаемый доход от безопасного минимума.",
        "question_ru": "Какой доход и в какой валюте вы считаете желаемым? Можно ответить «не знаю».",
        "question_be": "Які даход і ў якой валюце вы лічыце жаданым? Можна адказаць «не ведаю».",
        "block": "financial_pressure",
    },
    "learning_capacity": {
        "priority": 68, "critical": False, "importance": "useful",
        "goal": "Ограничить маршруты реальной возможностью учиться.",
        "question_ru": "Сколько времени в неделю вы реально можете учиться?",
        "question_be": "Колькі часу на тыдзень вы рэальна можаце вучыцца?",
        "block": "career_transition",
    },
    "income_stepdown": {
        "priority": 64, "critical": False, "importance": "useful",
        "goal": "Оценить финансовую безопасность переходного уровня.",
        "question_ru": "Допустимо ли временно снизить доход или должность, и если да — насколько?",
        "question_be": "Ці дапушчальна часова знізіць даход або пасаду, і калі так — наколькі?",
        "block": "career_transition",
    },
    "change_scale": {
        "priority": 62, "critical": False, "importance": "useful",
        "goal": "Различить смену роли, отрасли и полное переобучение.",
        "question_ru": "Какой масштаб смены вы хотите: новая роль рядом с текущей, новая отрасль или полный разворот?",
        "question_be": "Які маштаб змены вы хочаце: новая роля побач з цяперашняй, новая галіна або поўны паварот?",
        "block": "career_transition",
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

    route_context = data.get("route_context") if isinstance(data.get("route_context"), dict) else {}
    explicit_country = str(route_context.get("country") or data.get("country") or data.get("residence_country") or "").strip()
    explicit_city = str(route_context.get("city") or data.get("city") or "").strip()
    if not explicit_country and explicit_city:
        from services.market_strategy import resolve_city_country
        resolved = resolve_city_country(explicit_city)
        explicit_country = str(resolved.get("country_code") or "")
    if explicit_country:
        profile.residence_country = EvidenceItem(statement=explicit_country, source="user_story", confidence="confirmed")
    target_market = str(route_context.get("target_country") or data.get("target_country") or "").strip()
    if target_market:
        profile.target_countries.append(EvidenceItem(statement=target_market, source="user_story", confidence="confirmed"))

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
    if any(token in " ".join(missing) for token in ["стран", "рынок", "country", "market"]):
        gaps.extend(["residence_country", "target_country"])
    if any(token in " ".join(missing) for token in ["срок", "быстро", "urgency", "deadline"]):
        gaps.append("income_deadline")
    if any(token in " ".join(missing) for token in ["документ", "право", "license", "legal"]):
        gaps.append("legal_access")
    if any(token in " ".join(missing) for token in ["язык", "language", "интеграц", "local"]):
        gaps.append("location_language")
    if any(token in " ".join(missing) for token in ["огранич", "здоров", "дет", "график", "load"]):
        gaps.append("work_constraints")
    if any(token in " ".join(missing) for token in ["формат", "remote", "офис", "гибрид"]):
        gaps.append("work_format")
    if any(token in " ".join(missing) for token in ["релокац", "переезд", "relocation"]):
        gaps.append("relocation")
    if any(token in " ".join(missing) for token in ["желаем", "salary target", "валют"]):
        gaps.append("salary_target")
    if any(token in " ".join(missing) for token in ["учиться", "обучен", "learning"]):
        gaps.append("learning_capacity")
    if any(token in " ".join(missing) for token in ["сниж", "stepdown"]):
        gaps.append("income_stepdown")
    if any(token in " ".join(missing) for token in ["масштаб смен", "change scale"]):
        gaps.append("change_scale")
    if any(token in " ".join(missing) for token in ["поддерж", "support", "ресурс"]):
        gaps.append("support_and_load")
    if any(token in " ".join(missing) for token in ["уров", "level", "entry"]):
        gaps.append("transition_level")

    if not gaps:
        gaps = ["residence_country", "target_country", "work_authorization", "work_languages", "minimum_income", "income_deadline"]

    if profile.residence_country:
        gaps = [key for key in gaps if key != "residence_country"]
    if profile.target_countries:
        gaps = [key for key in gaps if key != "target_country"]

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
    if len(asked) >= MAX_ADDITIONAL_QUESTIONS:
        return None

    # Market questions have a fixed decision-impact order. They run after the
    # professional core is known and before generic route refinements.
    market_order = (
        "residence_country", "target_country", "work_authorization",
        "work_languages", "minimum_income", "income_deadline", "work_format", "change_scale",
    )
    for gap_key in market_order:
        if gap_key not in profile.unresolved_gaps or gap_key in asked:
            continue
        meta = _GAP_DEFINITIONS[gap_key]
        use_be = (language or "ru") == "be"
        options = meta.get("options") if isinstance(meta.get("options"), list) else []
        return {
            "id": 1,
            "question": str(meta["question_be"] if use_be else meta["question_ru"]).strip(),
            "block": str(meta.get("block") or "market_context"),
            "type": "single_choice" if options else "short_text",
            "options": options,
            "question_id": f"gap_{gap_key}",
            "gap_key": gap_key,
            "internal_goal": str(meta.get("goal") or ""),
            "critical_gap": bool(meta.get("critical", False)),
            "question_value": int(meta.get("priority", 0)),
            "source": "critical_market_gap",
            "validity_status": "needs_confirmation",
        }

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

    if text.casefold() in {"не знаю", "не хочу отвечать", "не уточнено", "пропустить", "unknown", "skip"}:
        text = "unknown"

    evidence = EvidenceItem(
        statement=text,
        source="user_clarification",
        confidence="probable",
    )
    if gap_key == "residence_country":
        low = text.casefold().replace("ё", "е")
        locations = (
            (("берлин", "berlin"), "Berlin", "Germany"),
            (("праг", "prague", "praha"), "Prague", "Czechia"),
            (("краков", "krakow", "kraków"), "Krakow", "Poland"),
        )
        country_aliases = (
            (("германи", "germany", "deutschland"), "Germany"),
            (("чехи", "czechia", "czech republic"), "Czechia"),
            (("польш", "poland", "polska"), "Poland"),
        )
        city_country = next(((city, country) for aliases, city, country in locations if any(alias in low for alias in aliases)), None)
        country = city_country[1] if city_country else next((name for aliases, name in country_aliases if any(alias in low for alias in aliases)), "")
        profile.residence_country = EvidenceItem(
            statement=country or text, source="user_clarification",
            confidence="confirmed" if country else "probable",
        )
        if city_country:
            profile.residence_city = EvidenceItem(statement=city_country[0], source="user_clarification", confidence="confirmed")
    elif gap_key == "target_country":
        low = text.casefold().replace("ё", "е")
        both = any(marker in low for marker in ("и так и так", "оба вариант", "both", "локальн", "международн"))
        residence = profile.residence_country.statement if profile.residence_country else ""
        if residence and (both or any(marker in low for marker in ("стране проживания", "локальн"))):
            if residence not in {item.statement for item in profile.target_countries}:
                profile.target_countries.append(EvidenceItem(statement=residence, source="user_clarification", confidence="confirmed"))
        if both or any(marker in low for marker in ("международн", "remote", "удален")):
            profile.target_market_format = EvidenceItem(statement="international_remote", source="user_clarification", confidence="confirmed")
        elif not profile.target_countries:
            profile.target_countries.append(evidence)
            profile.target_market_format = evidence
    elif gap_key == "work_authorization":
        profile.work_authorization = evidence
    elif gap_key == "work_languages":
        profile.work_languages.append(evidence)
    elif gap_key == "minimum_income":
        profile.minimum_income = evidence
    elif gap_key == "salary_target":
        profile.salary_target = evidence
    elif gap_key == "work_format":
        profile.work_format_preferences.append(evidence)
    elif gap_key == "relocation":
        profile.relocation_possible = evidence
    elif gap_key == "learning_capacity":
        profile.learning_capacity = evidence
    elif gap_key == "income_stepdown":
        profile.acceptable_income_drop = evidence
    elif gap_key == "change_scale":
        profile.desired_change_scale = evidence
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


def classify_profile_gaps(profile: CareerEvidenceProfile) -> dict[DataImportance, list[str]]:
    """Return one explicit completeness contract shared by interview and report code.

    Unknown/refused answers count as answered: they remain uncertainties in the
    report and must never start another questioning cycle.
    """
    result: dict[DataImportance, list[str]] = {"blocking": [], "useful": [], "optional": []}
    for gap_key in profile.unresolved_gaps:
        meta = _GAP_DEFINITIONS.get(gap_key, {})
        importance = str(meta.get("importance") or ("blocking" if meta.get("critical") else "useful"))
        if importance not in result:
            importance = "optional"
        result[importance].append(gap_key)  # type: ignore[index]
    return result
