from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal
from pydantic import BaseModel, Field as PydanticField
if TYPE_CHECKING:
    from services.evidence_profile import CareerEvidenceProfile

CRITICAL_GAP_TYPES: list[str] = [
    "explicit_goal",
    "explicit_refusal",
    "personal_contribution",
    "repeated_function",
    "autonomy",
    "responsibility_scale",
    "demonstrated_result",
    "regulated_profession_access",
    "minimum_income",
    "income_deadline",
    "transition_level_acceptance",
    "management_preference",
    "health_or_load_constraint",
]

# Priority levels — lower number = higher priority
_SAFETY = 1
_IDENTITY = 2
_ROUTE = 3
_PRACTICAL = 4
_PERSONALIZATION = 5

_USER_TOLERANCE_BY_MODE: dict[str, float] = {
    "fast": 0.5,
    "calm_steps": 0.8,
    "deep_route": 1.0,
    "support": 0.6,
}


@dataclass(frozen=True)
class GapScore:
    gap_type: str
    decision_impact: float
    uncertainty: float
    safety_importance: float
    answerability: float
    user_tolerance: float
    priority_level: int

    @property
    def question_value(self) -> float:
        return (
            self.decision_impact
            * self.uncertainty
            * self.safety_importance
            * self.answerability
            * self.user_tolerance
        )


@dataclass
class _GapMeta:
    priority_level: int
    base_decision_impact: float
    base_safety_importance: float
    base_answerability: float
    question_ru: str
    question_be: str
    block: str
    options: list[str] = field(default_factory=list)


_GAP_REGISTRY: dict[str, _GapMeta] = {
    # ── Level 1: Safety & legality ──────────────────────────────────────────
    "regulated_profession_access": _GapMeta(
        priority_level=_SAFETY,
        base_decision_impact=1.0,
        base_safety_importance=1.0,
        base_answerability=0.85,
        question_ru=(
            "Ваша профессия требует лицензии или разрешения? "
            "Что у вас сейчас есть с точки зрения документов для работы?"
        ),
        question_be=(
            "Ваша прафесія патрабуе ліцэнзіі або дазволу? "
            "Што ў вас зараз ёсць з пункту гледжання дакументаў для працы?"
        ),
        block="legal_access",
    ),
    "health_or_load_constraint": _GapMeta(
        priority_level=_SAFETY,
        base_decision_impact=0.9,
        base_safety_importance=0.85,
        base_answerability=0.9,
        question_ru=(
            "Есть ли физические ограничения, режим или нагрузка, "
            "которые важно учесть при подборе вариантов?"
        ),
        question_be=(
            "Ці ёсць фізічныя абмежаванні, рэжым або нагрузка, "
            "якія важна ўлічыць пры падборы варыянтаў?"
        ),
        block="constraints",
    ),
    # ── Level 2: Professional identity accuracy ──────────────────────────────
    "personal_contribution": _GapMeta(
        priority_level=_IDENTITY,
        base_decision_impact=0.95,
        base_safety_importance=0.7,
        base_answerability=0.9,
        question_ru=(
            "Возьмите любую ключевую задачу из вашего опыта — "
            "что именно вы делали сами, без помощи коллег?"
        ),
        question_be=(
            "Вазьміце любое ключавое заданне з вашага досведу — "
            "што менавіта вы рабілі самі, без дапамогі калег?"
        ),
        block="professional_experience",
    ),
    "repeated_function": _GapMeta(
        priority_level=_IDENTITY,
        base_decision_impact=0.9,
        base_safety_importance=0.7,
        base_answerability=0.95,
        question_ru="Эта работа была регулярной частью вашей деятельности или разовым проектом?",
        question_be="Гэтая праца была рэгулярнай часткай вашай дзейнасці ці аднаразовым праектам?",
        block="professional_experience",
        options=["Регулярная функция", "Повторялась время от времени", "Разовый эпизод"],
    ),
    "autonomy": _GapMeta(
        priority_level=_IDENTITY,
        base_decision_impact=0.95,
        base_safety_importance=0.7,
        base_answerability=0.9,
        question_ru=(
            "Когда вы выполняли эту работу — действовали по инструкции "
            "или сами принимали решения о том, как это делать?"
        ),
        question_be=(
            "Калі вы выконвалі гэтую працу — дзейнічалі па інструкцыі "
            "ці самі прымалі рашэнні аб тым, як гэта рабіць?"
        ),
        block="professional_experience",
        options=[
            "По инструкции",
            "Частично самостоятельно",
            "Полностью самостоятельно",
            "Сам(а) создавал(а) методику",
        ],
    ),
    "responsibility_scale": _GapMeta(
        priority_level=_IDENTITY,
        base_decision_impact=0.9,
        base_safety_importance=0.65,
        base_answerability=0.9,
        question_ru=(
            "Чья работа зависела от ваших решений — "
            "только ваша, конкретных клиентов, команды или всего процесса?"
        ),
        question_be=(
            "Чыя праца залежала ад вашых рашэнняў — "
            "толькі вашая, канкрэтных кліентаў, каманды ці ўсяго працэсу?"
        ),
        block="professional_experience",
        options=["Только моя", "Отдельных клиентов", "Команды", "Всего проекта или процесса"],
    ),
    "demonstrated_result": _GapMeta(
        priority_level=_IDENTITY,
        base_decision_impact=0.85,
        base_safety_importance=0.6,
        base_answerability=0.8,
        question_ru=(
            "Есть ли результат из вашего опыта, который можно выразить "
            "конкретной цифрой или фактом — время, деньги, объём?"
        ),
        question_be=(
            "Ці ёсць вынік з вашага досведу, які можна выразіць "
            "канкрэтнай лічбай або фактам — час, грошы, аб'ём?"
        ),
        block="professional_experience",
    ),
    # ── Level 3: Route choice ────────────────────────────────────────────────
    "explicit_goal": _GapMeta(
        priority_level=_ROUTE,
        base_decision_impact=0.9,
        base_safety_importance=0.6,
        base_answerability=0.9,
        question_ru=(
            "Что для вас важнее всего сейчас: "
            "стабильный доход, смена направления или рост в своей области?"
        ),
        question_be=(
            "Што для вас важнейшае зараз: "
            "стабільны даход, змена кірунку ці рост у сваёй галіне?"
        ),
        block="career_goals",
        options=["Стабильный доход", "Сменить направление", "Расти в своей области", "Пока не знаю"],
    ),
    "explicit_refusal": _GapMeta(
        priority_level=_ROUTE,
        base_decision_impact=0.8,
        base_safety_importance=0.6,
        base_answerability=0.95,
        question_ru=(
            "Есть что-то, чем вы точно не хотите заниматься — "
            "роль, функция или формат работы?"
        ),
        question_be=(
            "Ці ёсць нешта, чым вы дакладна не хочаце займацца — "
            "роля, функцыя або фармат працы?"
        ),
        block="career_goals",
    ),
    "transition_level_acceptance": _GapMeta(
        priority_level=_ROUTE,
        base_decision_impact=0.85,
        base_safety_importance=0.55,
        base_answerability=0.95,
        question_ru=(
            "Готовы ли вы временно начать с позиции ниже прошлого уровня, "
            "если это даст быстрый вход в нужную сферу?"
        ),
        question_be=(
            "Ці гатовы вы часова пачаць з пасады ніжэй за мінулы ўзровень, "
            "калі гэта дасць хуткі ўваход у патрэбную сферу?"
        ),
        block="career_transition",
        options=["Да", "Да, но временно", "Не уверен(а)", "Нет"],
    ),
    "management_preference": _GapMeta(
        priority_level=_ROUTE,
        base_decision_impact=0.8,
        base_safety_importance=0.55,
        base_answerability=0.95,
        question_ru=(
            "Вам важно работать с людьми и руководить, "
            "или предпочитаете роль без управленческой ответственности?"
        ),
        question_be=(
            "Вам важна працаваць з людзьмі і кіраваць, "
            "ці аддаяце перавагу ролі без кіраўнічай адказнасці?"
        ),
        block="work_preferences",
        options=["Хочу руководить", "Не против, но не главное", "Без управления", "Не знаю"],
    ),
    # ── Level 4: Practical realism ───────────────────────────────────────────
    "minimum_income": _GapMeta(
        priority_level=_PRACTICAL,
        base_decision_impact=0.85,
        base_safety_importance=0.5,
        base_answerability=0.95,
        question_ru="Какой минимальный доход в месяц вам нужен, чтобы стабилизировать ситуацию?",
        question_be="Які мінімальны даход у месяц вам патрэбны, каб стабілізаваць сітуацыю?",
        block="financial_pressure",
    ),
    "income_deadline": _GapMeta(
        priority_level=_PRACTICAL,
        base_decision_impact=0.85,
        base_safety_importance=0.5,
        base_answerability=0.95,
        question_ru="Как быстро нужен первый стабильный доход?",
        question_be="Наколькі хутка патрэбны першы стабільны даход?",
        block="financial_pressure",
        options=["⚡ 2-4 недели", "📆 1-3 месяца", "📚 3-6 месяцев", "🧭 Можно дольше"],
    ),
}


def _uncertainty_from_profile(gap_type: str, profile: CareerEvidenceProfile) -> float:
    """Returns 0.0 (fully known) → 1.0 (completely unknown)."""
    if gap_type == "explicit_goal":
        if not profile.explicit_goal:
            return 1.0
        return 0.0 if any(e.confidence == "confirmed" for e in profile.explicit_goal) else 0.4

    if gap_type == "explicit_refusal":
        return 0.0 if profile.explicit_refusals else 0.7

    if gap_type == "personal_contribution":
        funcs = profile.functions
        if not funcs:
            return 1.0
        return sum(1 for f in funcs if f.autonomy == "unknown") / len(funcs)

    if gap_type == "repeated_function":
        funcs = profile.functions
        if not funcs:
            return 1.0
        return sum(1 for f in funcs if f.frequency == "unknown") / len(funcs)

    if gap_type == "autonomy":
        funcs = profile.functions
        if not funcs:
            return 1.0
        return sum(1 for f in funcs if f.autonomy in {"unknown", "observed"}) / len(funcs)

    if gap_type == "responsibility_scale":
        funcs = profile.functions
        if not funcs:
            return 1.0
        return sum(1 for f in funcs if f.responsibility_scale == "unknown") / len(funcs)

    if gap_type == "demonstrated_result":
        funcs = profile.functions
        if not funcs:
            return 0.8
        return sum(1 for f in funcs if not f.demonstrated_results) / len(funcs)

    if gap_type == "regulated_profession_access":
        if profile.legal_access.profession_is_regulated is False:
            return 0.0
        if profile.legal_access.profession_is_regulated is True:
            return 0.1 if profile.legal_access.current_permission else 0.9
        return 0.5  # unknown whether regulated

    if gap_type == "minimum_income":
        return 0.0 if profile.minimum_income is not None else 1.0

    if gap_type == "income_deadline":
        return 0.0 if profile.income_deadline is not None else 1.0

    if gap_type == "transition_level_acceptance":
        return 0.0 if profile.acceptable_transition_level is not None else 0.8

    if gap_type == "management_preference":
        return 0.0 if profile.management_preference is not None else 0.6

    if gap_type == "health_or_load_constraint":
        return 0.0 if profile.health_or_load_constraints else 0.5

    return 0.5


def _is_skippable(gap_type: str, profile: CareerEvidenceProfile, asked_gaps: set[str]) -> bool:
    """
    Prohibition rules — returns True when the question must NOT be asked:
      • already asked this session
      • answer already in profile (uncertainty == 0)
      • user expressed explicit refusal (don't re-probe rejections)
      • profession confirmed non-regulated (skip legal-access question)
      • full legal docs already on record
    """
    if gap_type in asked_gaps:
        return True

    if _uncertainty_from_profile(gap_type, profile) == 0.0:
        return True

    if gap_type == "explicit_refusal" and profile.explicit_refusals:
        return True

    if gap_type == "regulated_profession_access":
        if profile.legal_access.profession_is_regulated is False:
            return True
        if profile.legal_access.qualification_status and profile.legal_access.current_permission:
            return True

    return False


def _compute_gap_score(
    gap_type: str,
    profile: CareerEvidenceProfile,
    user_mode: str,
) -> GapScore:
    meta = _GAP_REGISTRY[gap_type]
    uncertainty = _uncertainty_from_profile(gap_type, profile)
    user_tolerance = _USER_TOLERANCE_BY_MODE.get(str(user_mode or "calm_steps"), 0.8)
    return GapScore(
        gap_type=gap_type,
        decision_impact=meta.base_decision_impact,
        uncertainty=uncertainty,
        safety_importance=meta.base_safety_importance,
        answerability=meta.base_answerability,
        user_tolerance=user_tolerance,
        priority_level=meta.priority_level,
    )


def select_next_gap(
    profile: CareerEvidenceProfile,
    *,
    asked_gaps: set[str] | None = None,
    user_mode: str = "calm_steps",
    language: str = "ru",
) -> dict[str, object] | None:
    """
    Pick the single highest-value gap question from CRITICAL_GAP_TYPES.

    Scoring: question_value = decision_impact × uncertainty
             × safety_importance × answerability × user_tolerance

    Tiebreaker: lower priority_level wins (safety > identity > route > practical).
    Returns None when no gap warrants a question.
    """
    asked = asked_gaps or set()
    best: GapScore | None = None

    for gap_type in CRITICAL_GAP_TYPES:
        if gap_type not in _GAP_REGISTRY:
            continue
        if _is_skippable(gap_type, profile, asked):
            continue
        score = _compute_gap_score(gap_type, profile, user_mode)
        if score.question_value <= 0.0:
            continue
        if best is None or (score.question_value, -score.priority_level) > (
            best.question_value,
            -best.priority_level,
        ):
            best = score

    if best is None:
        return None

    meta = _GAP_REGISTRY[best.gap_type]
    use_be = (language or "ru") == "be"
    question_text = (meta.question_be if use_be else meta.question_ru).strip()
    options = list(meta.options)

    return {
        "id": 1,
        "question": question_text,
        "block": meta.block,
        "type": "single_choice" if options else "short_text",
        "options": options,
        "question_id": f"gap_{best.gap_type}",
        "gap_key": best.gap_type,
        "internal_goal": f"Закрыть пробел: {best.gap_type}",
        "critical_gap": best.priority_level <= _IDENTITY,
        "question_value": round(best.question_value, 4),
        "decision_impact": best.decision_impact,
        "uncertainty": best.uncertainty,
        "safety_importance": best.safety_importance,
        "priority_level": best.priority_level,
        "source": "interview_policy",
        "validity_status": "needs_confirmation",
    }


def is_ready_for_conclusion(
    profile: CareerEvidenceProfile,
    *,
    user_mode: str = "calm_steps",
    min_value_threshold: float = 0.15,
) -> bool:
    """
    True when no remaining gap has sufficient value to justify another question.
    Safety-level gaps with meaningful uncertainty always block the conclusion.
    """
    # PATCH-32: when readiness already supports a safe preliminary map,
    # do not keep asking low-value follow-ups just because they exist.
    readiness = evaluate_report_readiness(profile)
    if readiness.status in {"ready", "ready_with_uncertainty"} and not readiness.blocking_gaps:
        return True

    result = select_next_gap(profile, user_mode=user_mode)
    if result is None:
        return True
    priority = int(result.get("priority_level") or _PRACTICAL)
    value = float(result.get("question_value") or 0.0)
    # Safety gaps override the threshold — never skip them
    if priority == _SAFETY and float(result.get("uncertainty") or 0.0) > 0.3:
        return False
    return value < min_value_threshold


class ReportReadiness(BaseModel):
    status: Literal["not_ready", "ready_with_uncertainty", "ready"]
    blocking_gaps: list[str] = PydanticField(default_factory=list)
    non_blocking_gaps: list[str] = PydanticField(default_factory=list)
    warnings: list[str] = PydanticField(default_factory=list)


class RouteSpecificGap(BaseModel):
    gap_key: str
    prompt: str
    internal_goal: str
    options: list[str] = PydanticField(default_factory=list)
    critical: bool = False


def evaluate_report_readiness(
    profile: CareerEvidenceProfile,
    route_hypotheses: list | None = None,
) -> ReportReadiness:
    """
    Evaluate whether the profile is ready for a preliminary career result.

    Returns ReportReadiness with:
      - not_ready: critical blockers prevent safe output
      - ready_with_uncertainty: useful result possible, mark open areas
      - ready: main conclusions are confirmed
    """
    blocking: list[str] = []
    non_blocking: list[str] = []
    warnings: list[str] = []

    has_work_history = bool(profile.work_history_facts)
    has_functions = bool(profile.functions)
    has_goal = bool(profile.explicit_goal)
    has_refusals = bool(profile.explicit_refusals)
    legal = profile.legal_access

    # ── Blocking conditions ──────────────────────────────────────────────────
    if not has_work_history and not has_functions:
        blocking.append("no_professional_core")

    if legal.profession_is_regulated is True and not legal.current_permission:
        blocking.append("unknown_regulated_access")

    # Goal directly contradicts explicit refusal (naive keyword overlap)
    if has_goal and has_refusals:
        goal_blob = " ".join(e.statement.lower() for e in profile.explicit_goal)
        for refusal in profile.explicit_refusals:
            token = refusal.statement.strip().lower()[:25]
            if token and token in goal_blob:
                blocking.append("goal_refusal_conflict")
                break

    # ── Non-blocking gaps ────────────────────────────────────────────────────
    if not has_goal:
        non_blocking.append("explicit_goal_unknown")
    if profile.minimum_income is None:
        non_blocking.append("minimum_income_unknown")
    if profile.income_deadline is None:
        non_blocking.append("income_deadline_unknown")
    if legal.profession_is_regulated is None:
        non_blocking.append("legal_access_unclear")
    if not profile.location_and_language:
        non_blocking.append("language_context_unknown")
    if profile.acceptable_transition_level is None:
        non_blocking.append("transition_level_unknown")

    # ── Warnings ─────────────────────────────────────────────────────────────
    if profile.functions and all(f.frequency == "single_episode" for f in profile.functions):
        warnings.append("all_functions_single_episode_risk")
    if profile.contradictions:
        warnings.append(f"contradictions_present:{len(profile.contradictions)}")

    route_count = len(route_hypotheses) if route_hypotheses else 0

    # ── Status decision ───────────────────────────────────────────────────────
    if blocking:
        status: Literal["not_ready", "ready_with_uncertainty", "ready"] = "not_ready"
    elif (has_work_history or has_functions or route_count > 0) and len(non_blocking) <= 1:
        status = "ready"
    elif has_work_history or has_functions or route_count > 0:
        status = "ready_with_uncertainty"
    else:
        status = "not_ready"
        if "no_professional_core" not in blocking:
            blocking.append("insufficient_data_for_any_route")

    return ReportReadiness(
        status=status,
        blocking_gaps=blocking,
        non_blocking_gaps=non_blocking,
        warnings=warnings,
    )


def get_route_specific_gaps(
    selected_route: str,
    profile: CareerEvidenceProfile,
) -> list[RouteSpecificGap]:
    """
    Return narrow, route-specific clarifications.

    General questions should be asked before route choice.
    Narrow questions are only asked after the selected route is known.
    """
    route = str(selected_route or "").lower().replace("ё", "е")
    gaps: list[RouteSpecificGap] = []

    def _append_unique(item: RouteSpecificGap) -> None:
        if any(existing.gap_key == item.gap_key for existing in gaps):
            return
        gaps.append(item)

    # Accountant -> ERP / Business analysis transition
    if any(token in route for token in ["erp", "business analyst", "analyst", "1c", "sap"]):
        _append_unique(
            RouteSpecificGap(
                gap_key="erp_personal_tasks",
                prompt="Чтобы проверить переход в ERP, что именно вы делали лично: настройка процессов, отчеты, обучение пользователей или только ввод данных?",
                internal_goal="Уточнить личный вклад в ERP-функции.",
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="erp_requirements",
                prompt="Вы работали с требованиями к системе: собирали, уточняли, согласовывали?",
                internal_goal="Проверить опыт с requirements.",
                options=["Да, самостоятельно", "Да, с поддержкой", "Нет", "Частично"],
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="erp_testing",
                prompt="Участвовали ли вы в тестировании изменений ERP и фиксации дефектов?",
                internal_goal="Проверить BA/ERP readiness по тестированию.",
                options=["Да, регулярно", "Иногда", "Нет"],
            )
        )
        if profile.acceptable_transition_level is None:
            _append_unique(
                RouteSpecificGap(
                    gap_key="erp_level_income_stepdown",
                    prompt="Если вход в ERP потребует стартовать с уровня ниже текущего и временно ниже дохода, это допустимо?",
                    internal_goal="Проверить допустимость переходного уровня и дохода.",
                    options=["Да", "Да, временно", "Нет", "Не уверен(а)"],
                )
            )

    # Doctor return path
    if any(token in route for token in ["doctor", "врач", "physician", "medical", "медицин"]):
        _append_unique(
            RouteSpecificGap(
                gap_key="doctor_diploma_recognition_stage",
                prompt="На какой стадии признание диплома сейчас: документы не поданы, поданы, экзамены, частичный допуск, полный допуск?",
                internal_goal="Уточнить стадию признания диплома.",
                critical=True,
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="doctor_allowed_activities",
                prompt="Какие виды медицинской деятельности вам уже разрешены официально прямо сейчас?",
                internal_goal="Проверить разрешенный объем практики.",
                critical=True,
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="doctor_access_timeline",
                prompt="Какой реалистичный срок до следующего уровня допуска?",
                internal_goal="Уточнить временную рамку legal access.",
                options=["< 3 месяцев", "3-6 месяцев", "6-12 месяцев", "> 12 месяцев", "Неясно"],
                critical=True,
            )
        )

    # Senior developer path
    if any(token in route for token in ["developer", "разработ", "engineering", "software", "backend", "frontend"]):
        if profile.management_preference is None:
            _append_unique(
                RouteSpecificGap(
                    gap_key="dev_people_management_boundary",
                    prompt="Для этого маршрута важно: вы хотите полный отказ от people management или частичную роль управления?",
                    internal_goal="Понять границу по people management.",
                    options=["Полный отказ", "Частично ок", "Готов(а) управлять"],
                )
            )
        _append_unique(
            RouteSpecificGap(
                gap_key="dev_oncall_tolerance",
                prompt="On-call для вас допустим полностью, частично или лучше исключить?",
                internal_goal="Уточнить допустимость on-call.",
                options=["Исключить", "Только редкий", "Допустим"],
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="dev_startup_risk",
                prompt="Какой риск стартапа для вас приемлем сейчас?",
                internal_goal="Проверить риск-толерантность по типу компании.",
                options=["Низкий риск", "Средний", "Готов(а) к высокому риску"],
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="dev_product_work_share",
                prompt="Какую долю продуктовой работы вы хотите: минимум, 50/50 или в основном продукт?",
                internal_goal="Настроить формат целевой роли.",
                options=["Минимум", "50/50", "В основном продукт"],
            )
        )

    # Beginner psychologist
    if any(token in route for token in ["психолог", "psycholog", "counsell", "therap"]):
        _append_unique(
            RouteSpecificGap(
                gap_key="psych_legal_status",
                prompt="Какой у вас сейчас правовой статус для практики: нет допуска, ограниченный, полный?",
                internal_goal="Проверить legal status психологической практики.",
                options=["Нет допуска", "Ограниченный", "Полный", "Неясно"],
                critical=True,
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="psych_scope_boundaries",
                prompt="С какими запросами вы готовы работать, а какие сразу направляете дальше?",
                internal_goal="Зафиксировать границы практики.",
                critical=True,
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="psych_supervision",
                prompt="Есть ли у вас регулярная супервизия или план ее организации?",
                internal_goal="Проверить устойчивость и безопасность практики.",
                options=["Да, регулярная", "Периодическая", "Пока нет"],
                critical=True,
            )
        )
        _append_unique(
            RouteSpecificGap(
                gap_key="psych_referral",
                prompt="Как вы будете перенаправлять сложные случаи (кризис, медицинские риски)?",
                internal_goal="Проверить логику перенаправления сложных случаев.",
                critical=True,
            )
        )

    return gaps
