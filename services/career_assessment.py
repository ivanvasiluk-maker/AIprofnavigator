from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html import escape
from typing import Any, Literal


AssessmentStatus = Literal["preliminary", "full"]
RouteCategory = Literal["primary", "transition", "quick_income", "emergency"]
FirstStepType = Literal[
    "quick_action",
    "market_research",
    "portfolio",
    "networking",
    "learning",
    "clarification",
]


def _object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


_STRING = {"type": "string"}
_STRINGS = {"type": "array", "items": _STRING}
_MONEY_SCHEMA = _object_schema(
    {
        "amount": _nullable({"type": "number"}),
        "currency": _nullable(_STRING),
        "period": _nullable(_STRING),
    }
)
_LANGUAGE_SCHEMA = _object_schema({"language": _STRING, "level": _nullable(_STRING)})
_ROUTE_SCHEMA = _object_schema(
    {
        "route_id": _STRING,
        "title": _STRING,
        "category": {"type": "string", "enum": ["primary", "transition", "quick_income", "emergency"]},
        "why_it_fits": _STRING,
        "evidence_ids": _STRINGS,
        "preserves": _STRINGS,
        "risks": _STRINGS,
        "missing": _STRINGS,
        "entry_level": _STRING,
        "disconfirming_conditions": _STRINGS,
        "market_test": _STRING,
    }
)

CAREER_ASSESSMENT_SCHEMA = _object_schema(
    {
        "assessment_id": _STRING,
        "session_id": _STRING,
        "profile_version": _STRING,
        "status": {"type": "string", "enum": ["preliminary", "full"]},
        "context": _object_schema(
            {
                "country_code": _nullable(_STRING),
                "country_name": _nullable(_STRING),
                "city": _nullable(_STRING),
                "current_languages": {"type": "array", "items": _LANGUAGE_SCHEMA},
                "target_languages": {"type": "array", "items": _LANGUAGE_SCHEMA},
                "work_authorization": _nullable(_STRING),
                "income_minimum": _nullable(_MONEY_SCHEMA),
                "income_target": _nullable(_MONEY_SCHEMA),
                "income_urgency": _nullable(_STRING),
                "available_learning_time": _nullable(_STRING),
                "learning_budget": _nullable(_MONEY_SCHEMA),
            }
        ),
        "identity": _object_schema(
            {
                "professional_core": _STRINGS,
                "core_description": _STRING,
                "secondary_functions": _STRINGS,
                "seniority_current": _STRING,
                "seniority_transition": _nullable(_STRING),
                "seniority_notes": _STRING,
                "professional_capital": _STRINGS,
                "transferable_functions": _STRINGS,
            }
        ),
        "evidence": {
            "type": "array",
            "items": _object_schema(
                {
                    "evidence_id": _STRING,
                    "fact": _STRING,
                    "source_type": {"type": "string", "enum": ["history", "resume", "answer"]},
                    "source_reference": _STRING,
                }
            ),
        },
        "user_choice": _object_schema(
            {
                "desired_change": _nullable(_STRING),
                "preferred_directions": _STRINGS,
                "functions_to_preserve": _STRINGS,
                "functions_to_avoid": _STRINGS,
                "priorities": _STRINGS,
                "acceptable_income_drop": _nullable(_STRING),
            }
        ),
        "constraints": {
            "type": "array",
            "items": _object_schema(
                {"title": _STRING, "impact": _STRING, "evidence_ids": _STRINGS, "confirmed": {"type": "boolean"}}
            ),
        },
        "routes": _object_schema(
            {
                "primary_routes": {"type": "array", "items": _ROUTE_SCHEMA},
                "transition_routes": {"type": "array", "items": _ROUTE_SCHEMA},
                "quick_income_routes": {"type": "array", "items": _ROUTE_SCHEMA},
                "emergency_routes": {"type": "array", "items": _ROUTE_SCHEMA},
                "recommended_route_id": _STRING,
                "alternative_route_ids": _STRINGS,
            }
        ),
        "questions": _object_schema(
            {
                "answered_critical_questions": _STRINGS,
                "unanswered_critical_questions": _STRINGS,
                "optional_questions": _STRINGS,
            }
        ),
        "conclusions": _object_schema(
            {
                "mandatory_conclusions": _STRINGS,
                "main_conclusion": _STRING,
                "what_may_change_conclusion": _STRINGS,
                "forbidden_recommendations_checked": _STRINGS,
                "critical_errors_detected": _STRINGS,
            }
        ),
        "first_steps": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": _object_schema(
                {
                    "step_id": _STRING,
                    "title": _STRING,
                    "purpose": _STRING,
                    "action": _STRING,
                    "expected_result": _STRING,
                    "duration_minutes": {"type": "integer", "minimum": 1},
                    "related_route_id": _nullable(_STRING),
                    "type": {
                        "type": "string",
                        "enum": ["quick_action", "market_research", "portfolio", "networking", "learning", "clarification"],
                    },
                }
            ),
        },
        "selected_first_step_id": _nullable(_STRING),
    }
)


@dataclass(slots=True)
class Money:
    amount: float | None = None
    currency: str | None = None
    period: str | None = None


@dataclass(slots=True)
class LanguageLevel:
    language: str
    level: str | None = None


@dataclass(slots=True)
class CareerContext:
    country_code: str | None = None
    country_name: str | None = None
    city: str | None = None
    current_languages: list[LanguageLevel] = field(default_factory=list)
    target_languages: list[LanguageLevel] = field(default_factory=list)
    work_authorization: str | None = None
    income_minimum: Money | None = None
    income_target: Money | None = None
    income_urgency: str | None = None
    available_learning_time: str | None = None
    learning_budget: Money | None = None


@dataclass(slots=True)
class ProfessionalIdentity:
    professional_core: list[str]
    core_description: str
    secondary_functions: list[str]
    seniority_current: str
    seniority_transition: str | None
    seniority_notes: str
    professional_capital: list[str]
    transferable_functions: list[str]


@dataclass(slots=True)
class EvidenceItem:
    evidence_id: str
    fact: str
    source_type: Literal["history", "resume", "answer"]
    source_reference: str


@dataclass(slots=True)
class UserChoice:
    desired_change: str | None = None
    preferred_directions: list[str] = field(default_factory=list)
    functions_to_preserve: list[str] = field(default_factory=list)
    functions_to_avoid: list[str] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)
    acceptable_income_drop: str | None = None


@dataclass(slots=True)
class Constraint:
    title: str
    impact: str
    evidence_ids: list[str]
    confirmed: bool


@dataclass(slots=True)
class CareerRoute:
    route_id: str
    title: str
    category: RouteCategory
    why_it_fits: str
    evidence_ids: list[str]
    preserves: list[str]
    risks: list[str]
    missing: list[str]
    entry_level: str
    disconfirming_conditions: list[str]
    market_test: str


@dataclass(slots=True)
class CareerRoutes:
    primary_routes: list[CareerRoute]
    transition_routes: list[CareerRoute] = field(default_factory=list)
    quick_income_routes: list[CareerRoute] = field(default_factory=list)
    emergency_routes: list[CareerRoute] = field(default_factory=list)
    recommended_route_id: str = ""
    alternative_route_ids: list[str] = field(default_factory=list)

    def all_routes(self) -> list[CareerRoute]:
        return [
            *self.primary_routes,
            *self.transition_routes,
            *self.quick_income_routes,
            *self.emergency_routes,
        ]

    def by_id(self, route_id: str | None) -> CareerRoute | None:
        return next((route for route in self.all_routes() if route.route_id == route_id), None)


@dataclass(slots=True)
class QuestionAssessment:
    answered_critical_questions: list[str] = field(default_factory=list)
    unanswered_critical_questions: list[str] = field(default_factory=list)
    optional_questions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConclusionAssessment:
    mandatory_conclusions: list[str]
    main_conclusion: str
    what_may_change_conclusion: list[str] = field(default_factory=list)
    forbidden_recommendations_checked: list[str] = field(default_factory=list)
    critical_errors_detected: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FirstStep:
    step_id: str
    title: str
    purpose: str
    action: str
    expected_result: str
    duration_minutes: int
    related_route_id: str | None
    type: FirstStepType


@dataclass(slots=True)
class CareerAssessment:
    assessment_id: str
    session_id: str
    profile_version: str
    status: AssessmentStatus
    context: CareerContext
    identity: ProfessionalIdentity
    evidence: list[EvidenceItem]
    user_choice: UserChoice
    constraints: list[Constraint]
    routes: CareerRoutes
    questions: QuestionAssessment
    conclusions: ConclusionAssessment
    first_steps: list[FirstStep]
    selected_first_step_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def select_first_step(self, step_id: str) -> FirstStep:
        step = next((item for item in self.first_steps if item.step_id == step_id), None)
        if step is None:
            raise ValueError(f"Unknown first step: {step_id}")
        self.selected_first_step_id = step_id
        return step


@dataclass(frozen=True, slots=True)
class AssessmentValidation:
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def require_valid(self) -> None:
        if self.errors:
            raise ValueError("Invalid CareerAssessment: " + "; ".join(self.errors))


def _money(value: Any) -> Money | None:
    if not isinstance(value, dict):
        return None
    amount = value.get("amount")
    return Money(
        amount=float(amount) if isinstance(amount, (int, float)) else None,
        currency=_optional_text(value.get("currency")),
        period=_optional_text(value.get("period")),
    )


def _languages(value: Any) -> list[LanguageLevel]:
    return [
        LanguageLevel(language=str(item.get("language") or "").strip(), level=_optional_text(item.get("level")))
        for item in value or []
        if isinstance(item, dict) and str(item.get("language") or "").strip()
    ]


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _texts(value: Any) -> list[str]:
    return [str(item).strip() for item in value or [] if str(item).strip()]


def _route(item: dict[str, Any], category: RouteCategory) -> CareerRoute:
    return CareerRoute(
        route_id=str(item.get("route_id") or "").strip(),
        title=str(item.get("title") or "").strip(),
        category=category,
        why_it_fits=str(item.get("why_it_fits") or "").strip(),
        evidence_ids=_texts(item.get("evidence_ids")),
        preserves=_texts(item.get("preserves")),
        risks=_texts(item.get("risks")),
        missing=_texts(item.get("missing")),
        entry_level=str(item.get("entry_level") or "").strip(),
        disconfirming_conditions=_texts(item.get("disconfirming_conditions")),
        market_test=str(item.get("market_test") or "").strip(),
    )


def career_assessment_from_dict(payload: dict[str, Any]) -> CareerAssessment:
    context = payload.get("context") or {}
    identity = payload.get("identity") or {}
    routes = payload.get("routes") or {}
    questions = payload.get("questions") or {}
    conclusions = payload.get("conclusions") or {}
    user_choice = payload.get("user_choice") or {}
    return CareerAssessment(
        assessment_id=str(payload.get("assessment_id") or "").strip(),
        session_id=str(payload.get("session_id") or "").strip(),
        profile_version=str(payload.get("profile_version") or "").strip(),
        status=str(payload.get("status") or "preliminary").strip(),  # type: ignore[arg-type]
        context=CareerContext(
            country_code=_optional_text(context.get("country_code")),
            country_name=_optional_text(context.get("country_name")),
            city=_optional_text(context.get("city")),
            current_languages=_languages(context.get("current_languages")),
            target_languages=_languages(context.get("target_languages")),
            work_authorization=_optional_text(context.get("work_authorization")),
            income_minimum=_money(context.get("income_minimum")),
            income_target=_money(context.get("income_target")),
            income_urgency=_optional_text(context.get("income_urgency")),
            available_learning_time=_optional_text(context.get("available_learning_time")),
            learning_budget=_money(context.get("learning_budget")),
        ),
        identity=ProfessionalIdentity(
            professional_core=_texts(identity.get("professional_core")),
            core_description=str(identity.get("core_description") or "").strip(),
            secondary_functions=_texts(identity.get("secondary_functions")),
            seniority_current=str(identity.get("seniority_current") or "").strip(),
            seniority_transition=_optional_text(identity.get("seniority_transition")),
            seniority_notes=str(identity.get("seniority_notes") or "").strip(),
            professional_capital=_texts(identity.get("professional_capital")),
            transferable_functions=_texts(identity.get("transferable_functions")),
        ),
        evidence=[
            EvidenceItem(
                evidence_id=str(item.get("evidence_id") or "").strip(),
                fact=str(item.get("fact") or "").strip(),
                source_type=str(item.get("source_type") or "answer").strip(),  # type: ignore[arg-type]
                source_reference=str(item.get("source_reference") or "").strip(),
            )
            for item in payload.get("evidence") or []
            if isinstance(item, dict)
        ],
        user_choice=UserChoice(
            desired_change=_optional_text(user_choice.get("desired_change")),
            preferred_directions=_texts(user_choice.get("preferred_directions")),
            functions_to_preserve=_texts(user_choice.get("functions_to_preserve")),
            functions_to_avoid=_texts(user_choice.get("functions_to_avoid")),
            priorities=_texts(user_choice.get("priorities")),
            acceptable_income_drop=_optional_text(user_choice.get("acceptable_income_drop")),
        ),
        constraints=[
            Constraint(
                title=str(item.get("title") or "").strip(),
                impact=str(item.get("impact") or "").strip(),
                evidence_ids=_texts(item.get("evidence_ids")),
                confirmed=bool(item.get("confirmed")),
            )
            for item in payload.get("constraints") or []
            if isinstance(item, dict)
        ],
        routes=CareerRoutes(
            primary_routes=[_route(item, "primary") for item in routes.get("primary_routes") or [] if isinstance(item, dict)],
            transition_routes=[_route(item, "transition") for item in routes.get("transition_routes") or [] if isinstance(item, dict)],
            quick_income_routes=[_route(item, "quick_income") for item in routes.get("quick_income_routes") or [] if isinstance(item, dict)],
            emergency_routes=[_route(item, "emergency") for item in routes.get("emergency_routes") or [] if isinstance(item, dict)],
            recommended_route_id=str(routes.get("recommended_route_id") or "").strip(),
            alternative_route_ids=_texts(routes.get("alternative_route_ids")),
        ),
        questions=QuestionAssessment(
            answered_critical_questions=_texts(questions.get("answered_critical_questions")),
            unanswered_critical_questions=_texts(questions.get("unanswered_critical_questions")),
            optional_questions=_texts(questions.get("optional_questions")),
        ),
        conclusions=ConclusionAssessment(
            mandatory_conclusions=_texts(conclusions.get("mandatory_conclusions")),
            main_conclusion=str(conclusions.get("main_conclusion") or "").strip(),
            what_may_change_conclusion=_texts(conclusions.get("what_may_change_conclusion")),
            forbidden_recommendations_checked=_texts(conclusions.get("forbidden_recommendations_checked")),
            critical_errors_detected=_texts(conclusions.get("critical_errors_detected")),
        ),
        first_steps=[
            FirstStep(
                step_id=str(item.get("step_id") or "").strip(),
                title=str(item.get("title") or "").strip(),
                purpose=str(item.get("purpose") or "").strip(),
                action=str(item.get("action") or "").strip(),
                expected_result=str(item.get("expected_result") or "").strip(),
                duration_minutes=int(item.get("duration_minutes") or 0),
                related_route_id=_optional_text(item.get("related_route_id")),
                type=str(item.get("type") or "clarification").strip(),  # type: ignore[arg-type]
            )
            for item in payload.get("first_steps") or []
            if isinstance(item, dict)
        ],
        selected_first_step_id=_optional_text(payload.get("selected_first_step_id")),
    )


def build_preliminary_assessment(
    profile_snapshot: dict[str, Any],
    story_analysis: dict[str, Any],
    *,
    assessment_id: str,
    session_id: str,
    profile_version: str,
) -> CareerAssessment:
    hypotheses = _texts(story_analysis.get("professional_core_hypotheses"))
    current_identity = str(story_analysis.get("current_identity") or "").strip()
    core = hypotheses or ([current_identity] if current_identity else ["Профессиональный опыт пользователя"])
    facts = _texts(story_analysis.get("facts_extracted"))
    story_text = str(profile_snapshot.get("story_text") or "").strip()
    career_goal = str(profile_snapshot.get("career_goal") or "").strip()
    if story_text:
        facts.append(story_text[:500])
    if career_goal:
        facts.append(f"Карьерная цель: {career_goal}")
    facts = list(dict.fromkeys(facts))
    while len(facts) < 2:
        facts.append(
            "Профиль сохранён для повторной аналитической сборки"
            if facts
            else "Пользователь запросил карьерное заключение"
        )
    evidence = [
        EvidenceItem(
            evidence_id=f"preliminary-evidence-{index}",
            fact=fact,
            source_type="history" if index == 1 else "answer",
            source_reference=f"profile_snapshot:{index}",
        )
        for index, fact in enumerate(facts[:4], start=1)
    ]
    route_id = "preliminary-core-route"
    route_title = f"Смежные роли на основе: {core[0]}"
    route = CareerRoute(
        route_id=route_id,
        title=route_title,
        category="primary",
        why_it_fits="Маршрут сохраняет подтверждённое профессиональное ядро до повторной полной сборки.",
        evidence_ids=[evidence[0].evidence_id, evidence[1].evidence_id],
        preserves=core[:3],
        risks=["Полная рекомендация требует повторной проверенной сборки"],
        missing=["Подтверждённое сравнение конкретных целевых ролей"],
        entry_level="Уровень уточняется по подтверждённым функциям и масштабу ответственности",
        disconfirming_conditions=["Новые факты показывают другое профессиональное ядро"],
        market_test="После повторной сборки сравнить требования конкретных смежных ролей.",
    )
    assessment = CareerAssessment(
        assessment_id=assessment_id,
        session_id=session_id,
        profile_version=profile_version,
        status="preliminary",
        context=CareerContext(
            country_code=_optional_text(profile_snapshot.get("country_code")),
            country_name=_optional_text(profile_snapshot.get("country_name")),
            city=_optional_text(profile_snapshot.get("city")),
            work_authorization=_optional_text(profile_snapshot.get("work_authorization_status")),
            income_urgency=_optional_text(profile_snapshot.get("income_urgency")),
            available_learning_time=_optional_text(profile_snapshot.get("learning_hours_week")),
        ),
        identity=ProfessionalIdentity(
            professional_core=core,
            core_description="Это предварительная карта из сохранённых подтверждённых данных.",
            secondary_functions=_texts(story_analysis.get("skills")),
            seniority_current=str((story_analysis.get("seniority_hypotheses") or ["Требует повторной проверки"])[0]),
            seniority_transition=None,
            seniority_notes="Уровень не переносится в новую функцию автоматически.",
            professional_capital=_texts(story_analysis.get("experience_snapshot")) or core,
            transferable_functions=_texts(story_analysis.get("skills")),
        ),
        evidence=evidence,
        user_choice=UserChoice(
            desired_change=_optional_text(profile_snapshot.get("career_goal")),
            priorities=_texts(profile_snapshot.get("selected_career_priorities")),
        ),
        constraints=[],
        routes=CareerRoutes(primary_routes=[route], recommended_route_id=route_id),
        questions=QuestionAssessment(
            unanswered_critical_questions=["Какие конкретные смежные роли подтвердит повторная сборка?"]
        ),
        conclusions=ConclusionAssessment(
            mandatory_conclusions=["Профессиональный капитал нельзя обнулять без подтверждающих оснований"],
            main_conclusion="Показана предварительная карта; полную рекомендацию нужно собрать повторно из сохранённого профиля.",
            what_may_change_conclusion=["Успешная повторная аналитическая сборка"],
        ),
        first_steps=[
            FirstStep(
                step_id="clarify-functions",
                title="Быстрое прояснение",
                purpose="Зафиксировать функции для сохранения.",
                action="Запишите три функции, которые хотите сохранить, и три, от которых хотите отказаться.",
                expected_result="Два конкретных списка функций для повторной сборки.",
                duration_minutes=15,
                related_route_id=route_id,
                type="clarification",
            ),
            FirstStep(
                step_id="market-check",
                title="Проверка рынка",
                purpose="Получить данные о смежных ролях.",
                action=f"Найдите пять вакансий по направлению «{core[0]}» и отметьте повторяющиеся требования.",
                expected_result="Список повторяющихся требований из пяти вакансий.",
                duration_minutes=45,
                related_route_id=route_id,
                type="market_research",
            ),
            FirstStep(
                step_id="professional-contact",
                title="Профессиональный контакт",
                purpose="Проверить гипотезу у человека из сферы.",
                action="Попросите одного специалиста из смежной роли назвать главное требование для входа.",
                expected_result="Один проверяемый критерий входа в смежную роль.",
                duration_minutes=20,
                related_route_id=route_id,
                type="networking",
            ),
        ],
    )
    validate_career_assessment(
        assessment,
        snapshot_country_code=str(profile_snapshot.get("country_code") or "") or None,
        snapshot_currency=str(profile_snapshot.get("currency") or "") or None,
    ).require_valid()
    return assessment


def validate_career_assessment(
    assessment: CareerAssessment,
    *,
    snapshot_country_code: str | None = None,
    snapshot_currency: str | None = None,
    forbidden_recommendations: list[str] | None = None,
) -> AssessmentValidation:
    errors: list[str] = []
    if not assessment.assessment_id:
        errors.append("assessment_id is empty")
    if not assessment.identity.professional_core:
        errors.append("professional_core is empty")
    if not assessment.identity.core_description:
        errors.append("core_description is empty")
    if not assessment.identity.seniority_current:
        errors.append("seniority_current is empty")
    if not assessment.identity.seniority_notes:
        errors.append("seniority_notes is empty")
    if len(assessment.evidence) < 2:
        errors.append("assessment must contain at least two evidence items")
    if not assessment.routes.primary_routes:
        errors.append("primary_routes is empty")
    recommended = assessment.routes.by_id(assessment.routes.recommended_route_id)
    if recommended is None:
        errors.append("recommended_route_id does not exist")
    elif len(set(recommended.evidence_ids)) < 2:
        errors.append("recommended route must reference at least two evidence items")

    route_ids = {route.route_id for route in assessment.routes.all_routes() if route.route_id}
    evidence_ids = {item.evidence_id for item in assessment.evidence if item.evidence_id}
    for route in assessment.routes.all_routes():
        if not route.route_id or not route.title:
            errors.append("every route must have a concrete id and title")
        if route.title.casefold() == "возможный маршрут":
            errors.append("placeholder route title is forbidden")
        if not route.why_it_fits or not route.entry_level or not route.market_test:
            errors.append(f"route {route.route_id} lacks rationale, entry level, or market test")
        if not route.disconfirming_conditions:
            errors.append(f"route {route.route_id} lacks disconfirming conditions")
        missing_evidence = set(route.evidence_ids) - evidence_ids
        if missing_evidence:
            errors.append(f"route {route.route_id} references unknown evidence")

    if not 3 <= len(assessment.first_steps) <= 5:
        errors.append("first_steps must contain 3 to 5 items")
    if len({step.type for step in assessment.first_steps}) != len(assessment.first_steps):
        errors.append("first_steps must have different types")
    for step in assessment.first_steps:
        if not step.step_id or not step.action or not step.expected_result or step.duration_minutes <= 0:
            errors.append("each first step needs id, action, duration, and expected result")
        if step.related_route_id and step.related_route_id not in route_ids:
            errors.append(f"step {step.step_id} references unknown route")

    if assessment.conclusions.critical_errors_detected:
        errors.append("critical errors detected in conclusion")
    if not assessment.conclusions.mandatory_conclusions or not assessment.conclusions.main_conclusion:
        errors.append("conclusion is incomplete")
    duplicate_questions = set(assessment.questions.answered_critical_questions) & set(
        assessment.questions.unanswered_critical_questions
    )
    if duplicate_questions:
        errors.append("answered critical questions must not be asked again")
    if snapshot_country_code and assessment.context.country_code != snapshot_country_code:
        errors.append("country does not match ProfileSnapshot")
    currencies = {
        money.currency
        for money in (assessment.context.income_minimum, assessment.context.income_target, assessment.context.learning_budget)
        if money and money.currency
    }
    if snapshot_currency and currencies and currencies != {snapshot_currency}:
        errors.append("currency does not match ProfileSnapshot")

    visible_values = _all_strings(assessment.to_dict())
    forbidden_placeholders = {"-", "\\-", "данных недостаточно", "возможный маршрут"}
    if any(value.strip().casefold() in forbidden_placeholders for value in visible_values):
        errors.append("placeholder user-facing value detected")
    if any(value.strip().startswith("{") and value.strip().endswith("}") for value in visible_values):
        errors.append("serialized object detected in user-facing string")
    for forbidden in forbidden_recommendations or []:
        if any(forbidden.casefold() in value.casefold() for value in visible_values):
            errors.append(f"forbidden recommendation detected: {forbidden}")
    return AssessmentValidation(tuple(dict.fromkeys(errors)))


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _all_strings(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _all_strings(item)]
    return []


STEP_BUTTON_LABELS: dict[FirstStepType, str] = {
    "quick_action": "⚡ Быстро прояснить",
    "market_research": "🔎 Проверить рынок",
    "portfolio": "🧩 Собрать кейс",
    "networking": "💬 Поговорить с человеком из сферы",
    "learning": "📚 Закрыть пробел",
    "clarification": "⚡ Уточнить приоритеты",
}


def render_telegram_map(assessment: CareerAssessment) -> str:
    recommended = assessment.routes.by_id(assessment.routes.recommended_route_id)
    alternative = next(
        (assessment.routes.by_id(route_id) for route_id in assessment.routes.alternative_route_ids),
        None,
    )
    constraint = next((item for item in assessment.constraints if item.confirmed), None)
    lines = [
        "Профессиональное ядро",
        ", ".join(assessment.identity.professional_core),
        "",
        f"Текущий уровень: {assessment.identity.seniority_current}",
    ]
    if assessment.identity.seniority_transition:
        lines.append(f"Переходный уровень: {assessment.identity.seniority_transition}")
    lines.extend(["", f"Основной маршрут: {recommended.title if recommended else ''}"])
    if alternative:
        lines.append(f"Альтернатива: {alternative.title}")
    if constraint:
        lines.extend(["", f"Ключевое ограничение: {constraint.title}. {constraint.impact}"])
    lines.extend(["", "С какого шага хотите начать?"])
    lines.extend(f"{STEP_BUTTON_LABELS[step.type]} · {step.duration_minutes} мин" for step in assessment.first_steps)
    return "\n".join(lines)


def render_route_comparison(assessment: CareerAssessment) -> str:
    rows = []
    for route in assessment.routes.all_routes():
        rows.append(
            "\n".join(
                [
                    route.title,
                    f"Почему подходит: {route.why_it_fits}",
                    f"Уровень входа: {route.entry_level}",
                    f"Сохраняет: {', '.join(route.preserves)}",
                    f"Риски: {', '.join(route.risks)}" if route.risks else "Риски: требуют рыночной проверки",
                    f"Проверка: {route.market_test}",
                ]
            )
        )
    return "\n\n".join(rows)


def render_first_step_instruction(assessment: CareerAssessment, step_id: str) -> str:
    step = assessment.select_first_step(step_id)
    return "\n".join(
        [
            step.title,
            f"Цель: {step.purpose}",
            f"Действие: {step.action}",
            f"Время: {step.duration_minutes} минут",
            f"Результат: {step.expected_result}",
        ]
    )


def _list_html(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _routes_html(title: str, routes: list[CareerRoute], evidence: dict[str, str]) -> str:
    if not routes:
        return ""
    cards = []
    for route in routes:
        facts = [evidence[item] for item in route.evidence_ids if item in evidence]
        cards.append(
            f"<article><h3>{escape(route.title)}</h3>"
            f"<p><strong>Почему подходит:</strong> {escape(route.why_it_fits)}</p>"
            f"<p><strong>Доказательства:</strong></p>{_list_html(facts)}"
            f"<p><strong>Что сохраняет:</strong></p>{_list_html(route.preserves)}"
            + (f"<p><strong>Чего не хватает:</strong></p>{_list_html(route.missing)}" if route.missing else "")
            + f"<p><strong>Уровень входа:</strong> {escape(route.entry_level)}</p>"
            + (f"<p><strong>Риски:</strong></p>{_list_html(route.risks)}" if route.risks else "")
            + f"<p><strong>Что может опровергнуть:</strong></p>{_list_html(route.disconfirming_conditions)}"
            + f"<p><strong>Рыночная проверка:</strong> {escape(route.market_test)}</p></article>"
        )
    return f"<section><h2>{escape(title)}</h2>{''.join(cards)}</section>"


def render_assessment_html(assessment: CareerAssessment) -> str:
    evidence = {item.evidence_id: item.fact for item in assessment.evidence}
    recommended = assessment.routes.by_id(assessment.routes.recommended_route_id)
    alternatives = [
        route.title
        for route_id in assessment.routes.alternative_route_ids
        if (route := assessment.routes.by_id(route_id)) is not None
    ]
    unanswered = assessment.questions.unanswered_critical_questions
    steps = "".join(
        f"<article><h3>{escape(step.title)} · {step.duration_minutes} минут</h3>"
        f"<p><strong>Цель:</strong> {escape(step.purpose)}</p>"
        f"<p><strong>Действие:</strong> {escape(step.action)}</p>"
        f"<p><strong>Результат:</strong> {escape(step.expected_result)}</p></article>"
        for step in assessment.first_steps
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Карьерное заключение {escape(assessment.assessment_id)}</title>
<style>body{{font-family:Georgia,serif;max-width:900px;margin:32px auto;padding:0 20px;color:#17211d;line-height:1.55}}h1,h2{{font-family:Arial,sans-serif}}section{{border-top:1px solid #b8c2bc;padding:20px 0}}article{{margin:16px 0}}.meta{{color:#526159}}</style></head><body>
<h1>Карьерное заключение</h1><p class="meta">Assessment ID: {escape(assessment.assessment_id)} · версия {escape(assessment.profile_version)}</p>
<section><h2>1. Ваша профессиональная идентичность</h2>{_list_html(assessment.identity.professional_core)}<p>{escape(assessment.identity.core_description)}</p><h3>Вторичные функции</h3>{_list_html(assessment.identity.secondary_functions)}</section>
<section><h2>2. Ваш профессиональный уровень</h2><p><strong>Текущий:</strong> {escape(assessment.identity.seniority_current)}</p>{f'<p><strong>В переходной функции:</strong> {escape(assessment.identity.seniority_transition)}</p>' if assessment.identity.seniority_transition else ''}<p>{escape(assessment.identity.seniority_notes)}</p></section>
<section><h2>3. Что подтверждает этот вывод</h2>{_list_html(list(evidence.values()))}</section>
<section><h2>4. Что вы хотите сохранить и изменить</h2><h3>Сохранить</h3>{_list_html(assessment.user_choice.functions_to_preserve)}<h3>Изменить</h3>{_list_html(assessment.user_choice.functions_to_avoid)}<h3>Приоритеты</h3>{_list_html(assessment.user_choice.priorities)}</section>
{_routes_html('5. Основные маршруты', assessment.routes.primary_routes, evidence)}
{_routes_html('6. Переходные маршруты', assessment.routes.transition_routes, evidence)}
{_routes_html('7. Быстрый доход', assessment.routes.quick_income_routes, evidence)}
{_routes_html('8. Аварийный вариант', assessment.routes.emergency_routes, evidence)}
{f'<section><h2>9. Что пока нужно уточнить</h2>{_list_html(unanswered)}</section>' if unanswered else ''}
<section><h2>10. Несколько первых шагов</h2>{steps}</section>
<section><h2>11. Основное заключение</h2><p><strong>Рекомендуемый маршрут:</strong> {escape(recommended.title if recommended else '')}</p><p>{escape(assessment.conclusions.main_conclusion)}</p>{f'<p><strong>Альтернатива:</strong> {escape(", ".join(alternatives))}</p>' if alternatives else ''}<h3>Что может изменить рекомендацию</h3>{_list_html(assessment.conclusions.what_may_change_conclusion)}</section>
</body></html>"""