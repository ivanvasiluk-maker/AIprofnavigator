from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html import escape
import logging
import re
from typing import Any, Literal
from difflib import SequenceMatcher


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
ValidationSeverity = Literal["warning", "error", "critical"]
EntryPathType = Literal["direct_entry", "adjacent_transition", "bridge_project", "retraining_required", "not_recommended_now"]

CAREER_PIPELINE_VERSION = "career-assessment-v2"
CAREER_TELEGRAM_RENDERER_VERSION = "career-assessment-telegram-v1"
CAREER_HTML_RENDERER_VERSION = "career-assessment-html-v1"

logger = logging.getLogger(__name__)


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
        "entry_path": {"type": "string", "enum": ["direct_entry", "adjacent_transition", "bridge_project", "retraining_required", "not_recommended_now"]},
        "evidence_claims": {"type": "array", "items": _object_schema({"claim": _STRING, "evidence_fact_ids": _STRINGS, "confidence": _STRING, "uncertainties": _STRINGS})},
        "market_notes": _STRINGS,
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
                "residence_country": _nullable(_STRING),
                "target_countries": _STRINGS,
                "preferred_currency": _nullable(_STRING),
                "work_format": _nullable(_STRING),
                "relocation_possible": _nullable(_STRING),
                "market_data_date": _nullable(_STRING),
                "market_data_sources": _STRINGS,
                "market_data_confidence": _STRING,
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
    residence_country: str | None = None
    target_countries: list[str] = field(default_factory=list)
    preferred_currency: str | None = None
    work_format: str | None = None
    relocation_possible: str | None = None
    market_data_date: str | None = None
    market_data_sources: list[str] = field(default_factory=list)
    market_data_confidence: str = "low"


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
    entry_path: EntryPathType = "bridge_project"
    evidence_claims: list[dict[str, Any]] = field(default_factory=list)
    market_notes: list[str] = field(default_factory=list)


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
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def market_context(self) -> CareerContext:
        """Canonical country/market object; ``context`` remains the wire alias.

        Keeping the wire key avoids invalidating stored v2 assessments while all
        new code can use the unambiguous market_context name.
        """
        return self.context

    def select_first_step(self, step_id: str) -> FirstStep:
        step = next((item for item in self.first_steps if item.step_id == step_id), None)
        if step is None:
            raise ValueError(f"Unknown first step: {step_id}")
        self.selected_first_step_id = step_id
        return step


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    field_path: str
    message: str
    actual_value: Any
    severity: ValidationSeverity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AssessmentValidationResult:
    valid: bool
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return self.valid

    def require_valid(self) -> None:
        if self.errors:
            details = "; ".join(
                f"{issue.code} at {issue.field_path}: {issue.message}" for issue in self.errors
            )
            raise ValueError("Invalid CareerAssessment: " + details)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


AssessmentValidation = AssessmentValidationResult


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
    evidence_ids = _texts(item.get("evidence_ids"))
    claims = [dict(claim) for claim in item.get("evidence_claims") or [] if isinstance(claim, dict)]
    if not claims and str(item.get("why_it_fits") or "").strip() and evidence_ids:
        claims = [{"claim": str(item.get("why_it_fits")).strip(), "evidence_fact_ids": evidence_ids, "confidence": "medium", "uncertainties": _texts(item.get("missing"))}]
    return CareerRoute(
        route_id=str(item.get("route_id") or "").strip(),
        title=str(item.get("title") or "").strip(),
        category=category,
        why_it_fits=str(item.get("why_it_fits") or "").strip(),
        evidence_ids=evidence_ids,
        preserves=_texts(item.get("preserves")),
        risks=_texts(item.get("risks")),
        missing=_texts(item.get("missing")),
        entry_level=str(item.get("entry_level") or "").strip(),
        disconfirming_conditions=_texts(item.get("disconfirming_conditions")),
        market_test=str(item.get("market_test") or "").strip(),
        entry_path=str(item.get("entry_path") or "bridge_project").strip(),  # type: ignore[arg-type]
        evidence_claims=claims,
        market_notes=_texts(item.get("market_notes")),
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
            residence_country=_optional_text(context.get("residence_country")) or _optional_text(context.get("country_name")),
            target_countries=_texts(context.get("target_countries")),
            preferred_currency=_optional_text(context.get("preferred_currency")),
            work_format=_optional_text(context.get("work_format")),
            relocation_possible=_optional_text(context.get("relocation_possible")),
            market_data_date=_optional_text(context.get("market_data_date")),
            market_data_sources=_texts(context.get("market_data_sources")),
            market_data_confidence=str(context.get("market_data_confidence") or "low"),
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
        metadata=dict(payload.get("metadata") or {}) if isinstance(payload.get("metadata"), dict) else {},
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
    core = [
        title for title in (hypotheses or ([current_identity] if current_identity else []))
        if title and not title.casefold().startswith("пользователь") and len(title.split()) <= 8
    ] or ["Текущая профессиональная специализация"]
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
    route_title = core[0]
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
        entry_path="bridge_project",
        evidence_claims=[{
            "claim": "Маршрут сохраняет подтверждённое профессиональное ядро до повторной полной сборки.",
            "evidence_fact_ids": [evidence[0].evidence_id, evidence[1].evidence_id],
            "confidence": "low",
            "uncertainties": ["Подтверждённое сравнение конкретных целевых ролей"],
        }],
        market_notes=["Диапазон требует рыночной проверки"],
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
            residence_country=_optional_text(profile_snapshot.get("residence_country")) or _optional_text(profile_snapshot.get("country_name")),
            target_countries=_texts(profile_snapshot.get("target_countries")) or ([_optional_text(profile_snapshot.get("country_name"))] if _optional_text(profile_snapshot.get("country_name")) else []),
            preferred_currency=_optional_text(profile_snapshot.get("currency")),
            work_format=_optional_text(profile_snapshot.get("work_format")),
            relocation_possible=_optional_text(profile_snapshot.get("relocation_possible")),
            market_data_date=_optional_text(profile_snapshot.get("market_data_date")),
            market_data_sources=_texts(profile_snapshot.get("market_data_sources")),
            market_data_confidence=str(profile_snapshot.get("market_data_confidence") or "low"),
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
                action=f"Найдите пять вакансий {route_title} и отметьте повторяющиеся требования.",
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


def _flatten_source_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        return [text for item in value.values() for text in _flatten_source_strings(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _flatten_source_strings(item)]
    return []


def build_deterministic_assessment(
    profile_snapshot: dict[str, Any],
    story_analysis: dict[str, Any],
    resume_analysis: dict[str, Any],
    *,
    assessment_id: str,
    session_id: str,
    profile_version: str,
    fallback_reason: str = "career_assessment_validation_failed_after_repair",
) -> CareerAssessment:
    """Build and rank career hypotheses using facts from this assessment only."""
    logger.warning(
        "career_assessment_fallback assessment_id=%s session_id=%s reason=%s",
        assessment_id,
        session_id,
        fallback_reason,
    )

    def values(source: dict[str, Any], *keys: str) -> list[str]:
        return list(dict.fromkeys(
            text for key in keys for text in _flatten_source_strings(source.get(key))
        ))

    def concise(items: list[str], limit: int = 8) -> list[str]:
        forbidden = ("пользователь", "имеет опыт", "заинтересован")
        return list(dict.fromkeys(
            item.rstrip(". ") for item in items
            if 0 < len(item.split()) <= limit
            and not any(marker in item.casefold() for marker in forbidden)
        ))

    def normalized(value: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-zа-яё0-9]+", value.casefold())
            if len(token) > 2
        }

    def money_value(key: str) -> Money | None:
        raw = profile_snapshot.get(key)
        if isinstance(raw, (int, float)):
            amount = float(raw)
        else:
            match = re.search(r"\d+(?:[.,]\d+)?", str(raw or "").replace(" ", ""))
            amount = float(match.group().replace(",", ".")) if match else None
        if amount is None:
            return None
        return Money(
            amount=amount,
            currency=_optional_text(profile_snapshot.get("currency")),
            period="month",
        )

    # Current roles and target roles are deliberately separate. Target roles
    # must never be used as evidence of current identity or seniority.
    current_roles = concise(
        values(profile_snapshot, "current_role", "profession")
        + values(story_analysis, "current_role", "current_identity", "profession")
        + values(resume_analysis, "current_role")
    )
    if not current_roles:
        current_roles = concise(values(story_analysis, "professional_core_hypotheses"))[:1]
    historical_roles = concise(values(resume_analysis, "job_titles", "positions", "roles"))
    target_roles = concise(
        values(profile_snapshot, "target_roles")
        + values(story_analysis, "career_hypotheses", "target_roles", "role_hypotheses")
        + values(resume_analysis, "target_roles")
    )
    target_roles = [role for role in target_roles if role not in current_roles]

    confirmed_functions = concise(
        values(story_analysis, "confirmed_functions", "functions")
        + values(resume_analysis, "confirmed_functions", "functions", "tasks")
    )
    transferable_skills = concise(
        values(story_analysis, "skills", "transferable_skills")
        + values(resume_analysis, "skills", "transferable_skills")
    )
    interests = concise(values(story_analysis, "interests", "preferred_directions"))
    unwanted = concise(values(story_analysis, "tasks_to_avoid", "functions_to_avoid"))
    functions = list(dict.fromkeys(confirmed_functions + transferable_skills))
    current_role = current_roles[0] if current_roles else ""
    desired_change = _optional_text(profile_snapshot.get("career_goal"))
    change_text = (desired_change or "").casefold()
    substantial_change = any(
        marker in change_text
        for marker in ("полностью", "существен", "новая професс", "сменить сфер")
    )

    source_groups: list[tuple[dict[str, Any], str, str, tuple[str, ...]]] = [
        (story_analysis, "answer", "story_analysis", (
            "facts_extracted", "experience_snapshot", "professional_core_hypotheses",
            "current_identity", "current_role", "profession", "confirmed_functions",
            "functions", "skills", "transferable_skills", "industry_experience",
            "interests", "preferred_directions", "tasks_to_avoid", "functions_to_avoid",
            "seniority_hypotheses", "constraints", "career_hypotheses", "target_roles",
        )),
        (resume_analysis, "resume", "resume_analysis", (
            "current_role", "job_titles", "positions", "roles", "target_roles", "tasks",
            "functions", "achievements", "measurable_results", "education",
            "certifications", "licenses", "languages", "skills", "transferable_skills",
            "industry_experience", "experience",
        )),
        (profile_snapshot, "history", "profile_snapshot", (
            "story_text", "answers_text", "career_goal", "current_role", "profession",
            "target_roles", "country_name", "target_countries", "work_authorization_status",
            "qualification_status", "minimum_income", "target_income", "learning_hours_week",
            "learning_budget", "work_preferences", "care_constraints", "external_barriers",
        )),
    ]
    raw_facts: list[tuple[str, str, str]] = []
    evidence_by_fact: dict[str, str] = {}
    for source, source_type, prefix, keys in source_groups:
        for key in keys:
            for fact in _flatten_source_strings(source.get(key)):
                raw_facts.append((fact[:500], source_type, f"{prefix}:{key}"))

    unique_facts: list[tuple[str, str, str]] = []
    seen_facts: set[str] = set()
    for fact, source_type, reference in raw_facts:
        fact_key = fact.casefold()
        if fact_key and fact_key not in seen_facts:
            seen_facts.add(fact_key)
            unique_facts.append((fact, source_type, reference))
    if not unique_facts:
        unique_facts.append(("Запрошена карьерная оценка", "answer", "assessment:request"))
    evidence = [
        EvidenceItem(f"fallback-evidence-{index}", fact, source_type, reference)
        for index, (fact, source_type, reference) in enumerate(unique_facts, 1)
    ]
    for item in evidence:
        evidence_by_fact.setdefault(item.fact.casefold(), item.evidence_id)
    # The schema requires two independent IDs. When only one user fact exists,
    # keep the same verbatim fact and mark the second ID as a structural anchor;
    # never manufacture a second biographical claim.
    if len(evidence) == 1:
        item = evidence[0]
        evidence.append(EvidenceItem(
            "fallback-evidence-2", item.fact, item.source_type,
            f"{item.source_reference}:structural_anchor",
        ))
    default_evidence_ids = [item.evidence_id for item in evidence[:4]]

    def evidence_ids_for(facts: list[str]) -> list[str]:
        ids = [evidence_by_fact.get(fact.casefold(), "") for fact in facts]
        result = list(dict.fromkeys(item for item in ids if item))
        for evidence_id in default_evidence_ids:
            if len(result) >= 2:
                break
            if evidence_id not in result:
                result.append(evidence_id)
        return result

    constraint_facts = list(dict.fromkeys(
        values(story_analysis, "constraints")
        + values(profile_snapshot, "care_constraints", "work_preferences", "external_barriers")
    ))
    constraints = [
        Constraint(
            title=fact,
            impact="Проверяется только для формата, графика и задач конкретного маршрута.",
            evidence_ids=[evidence_by_fact[fact.casefold()]],
            confirmed=True,
        )
        for fact in constraint_facts
        if fact.casefold() in evidence_by_fact
    ]

    self_employment_text = " ".join(
        interests
        + values(profile_snapshot, "career_goal", "work_preferences")
    ).casefold()
    wants_self_employment = any(
        marker in self_employment_text
        for marker in ("самостоят", "частн", "консалт", "предприним", "фриланс")
    )

    candidates: list[dict[str, Any]] = []

    def add_candidate(
        title: str,
        kind: str,
        route_functions: list[str],
        source_facts: list[str],
        *,
        experimental: bool = False,
    ) -> None:
        clean_title = title.strip()
        if clean_title:
            candidates.append({
                "title": clean_title,
                "kind": kind,
                "functions": list(dict.fromkeys(route_functions)),
                "source_facts": list(dict.fromkeys(source_facts)),
                "experimental": experimental,
            })

    if current_role and functions:
        add_candidate(current_role, "continuation", functions[:3], [current_role, *functions[:3]])
    for function in confirmed_functions:
        title = (
            f"{current_role} — специализация «{function}»"
            if current_role else f"Функциональное направление «{function}»"
        )
        add_candidate(title, "specialization", [function], [function, *current_roles[:1]])
    for role in target_roles:
        add_candidate(
            role,
            "retraining" if substantial_change else "transition",
            functions[:3],
            [role, *functions[:3]],
        )
    if wants_self_employment and (current_role or functions):
        base = current_role or functions[0]
        add_candidate(
            f"Самостоятельная практика: {base}",
            "self_employment", functions[:3] or [base],
            [base, *functions[:3]], experimental=True,
        )
    # With one confirmed function and no profession, provide a second reversible
    # functional model rather than inventing another occupation.
    if not current_role and len(confirmed_functions) == 1:
        add_candidate(
            f"Проектная работа с функцией «{confirmed_functions[0]}»",
            "functional_test", [confirmed_functions[0]], [confirmed_functions[0]],
            experimental=True,
        )
    if not candidates:
        for interest in interests[:4]:
            add_candidate(
                f"Направление интереса «{interest}»",
                "interest_test", [], [interest], experimental=len(candidates) == 0,
            )

    deduped: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for candidate in candidates:
        key = candidate["title"].casefold()
        if key not in seen_titles:
            seen_titles.add(key)
            deduped.append(candidate)
    candidates = deduped

    country_known = bool(profile_snapshot.get("country_name") or profile_snapshot.get("target_countries"))
    market_sources = values(profile_snapshot, "market_data_sources")
    languages = list(dict.fromkeys(
        values(resume_analysis, "languages")
        + values(story_analysis, "languages")
        + values(profile_snapshot, "languages", "current_language_level")
    ))
    language_known = bool(languages)
    authorization = _optional_text(profile_snapshot.get("work_authorization_status"))
    income_minimum = money_value("minimum_income")
    learning_time = _optional_text(profile_snapshot.get("learning_hours_week"))
    qualifications = values(
        resume_analysis, "education", "certifications", "licenses"
    ) + values(profile_snapshot, "qualification_status")
    achievements = values(resume_analysis, "achievements", "measurable_results")
    capital = list(dict.fromkeys(
        historical_roles
        + values(resume_analysis, "industry_experience", "experience", "education", "certifications", "licenses", "achievements", "measurable_results")
    ))

    def evaluate(candidate: dict[str, Any]) -> dict[str, Any]:
        kind = str(candidate["kind"])
        route_functions = list(candidate["functions"])
        route_tokens = normalized(" ".join([candidate["title"], *route_functions]))
        confirmed_tokens = normalized(" ".join(confirmed_functions))
        unwanted_tokens = normalized(" ".join(unwanted))
        function_overlap = len(route_tokens & confirmed_tokens)
        unwanted_overlap = len(route_tokens & unwanted_tokens)

        if function_overlap and unwanted_overlap == 0:
            function_fit = "confirmed"
        elif unwanted_overlap:
            function_fit = "conflict"
        elif route_functions:
            function_fit = "partial"
        else:
            function_fit = "unknown"

        capital_fit = (
            "high" if kind in {"continuation", "specialization"} and (functions or capital)
            else "medium" if kind in {"transition", "self_employment", "functional_test"} and (functions or capital)
            else "low" if kind == "retraining"
            else "unknown"
        )
        entry_fit = (
            "current_level_supported" if kind == "continuation" and current_role
            else "qualification_check_required" if qualifications
            else "market_check_required"
        )
        country_fit = (
            "source_check_available" if country_known and market_sources
            else "market_check_required" if country_known
            else "unknown_country"
        )
        language_fit = "level_check_required" if language_known else "unknown_language"
        income_fit = (
            "market_comparison_required" if income_minimum and market_sources
            else "salary_data_required" if income_minimum
            else "unknown_income"
        )
        constraints_fit = (
            "conflict" if unwanted_overlap
            else "route_check_required" if constraints or unwanted
            else "unknown_constraints"
        )
        learning_fit = (
            "substantial_retraining" if kind == "retraining"
            else "time_check_required" if learning_time
            else "limited_for_continuation" if kind == "continuation"
            else "unknown_learning_capacity"
        )
        safe_test = (
            "fast_reversible" if kind in {"continuation", "functional_test", "interest_test"}
            else "reversible_pilot" if kind in {"specialization", "self_employment"}
            else "vacancy_and_interview_test"
        )
        loss_risk = (
            "high" if kind == "retraining"
            else "medium" if kind in {"transition", "self_employment"}
            else "low"
        )
        criteria = {
            "confirmed_function_fit": function_fit,
            "professional_capital_preserved": capital_fit,
            "entry_level_realistic": entry_fit,
            "target_country_access": country_fit,
            "language_fit": language_fit,
            "income_minimum_fit": income_fit,
            "life_constraints_fit": constraints_fit,
            "learning_volume": learning_fit,
            "safe_test_speed": safe_test,
            "income_status_loss_risk": loss_risk,
        }
        points = {
            "confirmed": 4, "partial": 1, "conflict": -5,
            "high": 3, "medium": 1, "low": 0,
            "current_level_supported": 3, "qualification_check_required": 1,
            "source_check_available": 2, "fast_reversible": 2,
            "reversible_pilot": 1, "vacancy_and_interview_test": 1,
            "limited_for_continuation": 1, "substantial_retraining": -2,
        }
        score = sum(points.get(value, 0) for value in criteria.values())
        return {"score": score, "kind": kind, "criteria": criteria}

    evaluated = [(candidate, evaluate(candidate), index) for index, candidate in enumerate(candidates)]
    evaluated.sort(key=lambda item: (
        bool(item[0]["experimental"]),
        -int(item[1]["score"]),
        item[2],
    ))

    non_experimental = [item for item in evaluated if not item[0]["experimental"]]
    experimental = [item for item in evaluated if item[0]["experimental"]]
    # An explicitly supported experiment receives one alternative slot, but it
    # can never become the primary recommendation or displace all conventional
    # routes. All candidates were evaluated before this output limit is applied.
    selected = non_experimental[:3 if experimental else 4]
    if experimental:
        selected.append(experimental[0])

    insufficient_data = not current_role and len(confirmed_functions) < 2
    if not selected:
        fallback_candidate = {
            "title": "Проверка выполняемых функций",
            "kind": "insufficient_data",
            "functions": confirmed_functions,
            "source_facts": confirmed_functions,
            "experimental": False,
        }
        selected = [(fallback_candidate, evaluate(fallback_candidate), 0)]
        insufficient_data = True

    route_evaluations: dict[str, dict[str, Any]] = {}
    routes: list[CareerRoute] = []
    for index, (candidate, evaluation, _) in enumerate(selected, 1):
        route_id = f"source-route-{index}"
        label = str(candidate["title"])
        kind = str(candidate["kind"])
        route_functions = list(candidate["functions"])
        source_facts = list(candidate["source_facts"])
        criteria = dict(evaluation["criteria"])
        evidence_ids = evidence_ids_for(source_facts)
        gap_prefixes = (
            "Нужно подтвердить обязательные функции и уровень ответственности",
            "Нужен рабочий пример, доказывающий выбранную специализацию",
            "Необходимо проверить перенос квалификации и профессионального капитала",
            "Требуется внешний сигнал спроса и оценка безопасного входа",
        )
        missing = [f"{gap_prefixes[(index - 1) % len(gap_prefixes)]}: «{label}»"]
        if not country_known:
            missing.append("Целевая страна")
        if not language_known:
            missing.append("Рабочие языки и их уровень")
        if not authorization:
            missing.append("Юридическая доступность требует проверки")
        if income_minimum and not market_sources:
            missing.append("Нет рыночных данных для сравнения с финансовым минимумом")
        elif not income_minimum:
            missing.append("Финансовый минимум не указан")
        if kind == "insufficient_data":
            missing.extend(["Текущая профессиональная область", "Минимум две подтверждённые функции"])

        if kind == "retraining":
            entry_path: EntryPathType = "retraining_required"
        elif kind == "continuation":
            entry_path = "direct_entry"
        elif kind in {"specialization", "transition"}:
            entry_path = "adjacent_transition"
        elif kind in {"functional_test", "interest_test"}:
            entry_path = "bridge_project"
        else:
            entry_path = "not_recommended_now"

        preserved = route_functions or confirmed_functions or interests[:1]
        if not preserved:
            preserved = ["Факты текущей оценки без добавления неподтверждённой профессии"]
        risk_prefixes = (
            "Текущий формат может сохранить прежние нежелательные задачи",
            "Узкая функция может встречаться в недостаточном числе вакансий",
            "Новый работодатель может не признать прежний уровень ответственности",
            "Проверка спроса может не подтвердить жизнеспособность модели",
        )
        risks = [
            f"{risk_prefixes[(index - 1) % len(risk_prefixes)]}: {label}",
            f"Потеря дохода/статуса={criteria['income_status_loss_risk']}; ограничения={criteria['life_constraints_fit']}",
        ]
        disconfirming = [
            "Гипотеза опровергается, если её основные задачи совпадут с нежелательными задачами",
            "Гипотеза опровергается, если обязательные требования нельзя закрыть в доступные сроки",
        ]
        market_test = (
            f"Без увольнения проверить «{label}»: сопоставить пять актуальных описаний работы "
            f"с подтверждёнными функциями {', '.join(preserved)} и получить один внешний сигнал."
        )
        why = (
            f"Гипотеза опирается на факты текущей оценки: {', '.join(source_facts[:4])}."
            if source_facts
            else "Конкретная профессия не названа: сначала нужно подтвердить выполнявшиеся функции."
        )
        route_evaluations[route_id] = evaluation
        routes.append(CareerRoute(
            route_id=route_id,
            title=label,
            category="primary" if index == 1 else "transition",
            why_it_fits=why,
            evidence_ids=evidence_ids,
            preserves=preserved,
            risks=risks,
            missing=list(dict.fromkeys(missing)),
            entry_level=(
                "Текущий уровень поддержан только для продолжения подтверждённой роли"
                if kind == "continuation"
                else "Уровень входа определяется после проверки требований, квалификаций и допусков"
            ),
            disconfirming_conditions=disconfirming,
            market_test=market_test,
            entry_path=entry_path,
            evidence_claims=[{
                "claim": why,
                "evidence_fact_ids": evidence_ids,
                "confidence": "low" if insufficient_data else "medium",
                "uncertainties": missing,
            }],
            market_notes=[
                "Оценка: " + "; ".join(f"{key}={value}" for key, value in criteria.items())
            ],
        ))

    answered_questions = values(
        story_analysis, "answered_critical_questions", "answered_questions"
    ) + values(profile_snapshot, "answered_critical_questions")
    answered_blob = " ".join(answered_questions).casefold()
    question_candidates: list[tuple[bool, tuple[str, ...], str]] = [
        (len(confirmed_functions) < 2, ("функц", "задач"), "Какие три конкретные рабочие функции вы выполняли чаще всего и хотите сохранить?"),
        (not country_known, ("стран", "рынок"), "В какой стране вы планируете искать работу?"),
        (not language_known, ("язык",), "На каких языках и на каком уровне вы можете работать?"),
        (not authorization, ("прав", "документ"), "Есть ли у вас право на работу в целевой стране?"),
        (income_minimum is None, ("доход", "миним"), "Какой минимальный ежемесячный доход для вас допустим?"),
        (not desired_change, ("масштаб", "смен"), "Вы хотите сохранить профессию, перейти в смежную роль или полностью сменить сферу?"),
    ]
    next_question = next((
        question for missing, markers, question in question_candidates
        if missing and not any(marker in answered_blob for marker in markers)
    ), "")

    primary = routes[:1]
    alternatives = routes[1:4]
    recommended_id = primary[0].route_id
    assessment = CareerAssessment(
        assessment_id=assessment_id,
        session_id=session_id,
        profile_version=profile_version,
        status="preliminary",
        context=CareerContext(
            country_code=_optional_text(profile_snapshot.get("country_code")),
            country_name=_optional_text(profile_snapshot.get("country_name")),
            city=_optional_text(profile_snapshot.get("city")),
            current_languages=[LanguageLevel(language=item) for item in languages],
            work_authorization=authorization,
            income_minimum=income_minimum,
            income_target=money_value("target_income"),
            income_urgency=_optional_text(profile_snapshot.get("income_urgency")),
            available_learning_time=learning_time,
            learning_budget=money_value("learning_budget"),
            residence_country=_optional_text(profile_snapshot.get("residence_country")),
            target_countries=values(profile_snapshot, "target_countries"),
            preferred_currency=_optional_text(profile_snapshot.get("currency")),
            work_format=_optional_text(profile_snapshot.get("work_format")),
            relocation_possible=_optional_text(profile_snapshot.get("relocation_possible")),
            market_data_date=_optional_text(profile_snapshot.get("market_data_date")),
            market_data_sources=market_sources,
            market_data_confidence=str(profile_snapshot.get("market_data_confidence") or "low"),
        ),
        identity=ProfessionalIdentity(
            professional_core=confirmed_functions[:3] or current_roles[:2] or ["Подтверждённые функции отсутствуют"],
            core_description="Ядро определено через подтверждённые функции; название роли используется только как дополнительный контекст.",
            secondary_functions=functions[3:7],
            seniority_current=(
                concise(values(story_analysis, "seniority_hypotheses"))[:1] or
                ["Уровень ответственности не подтверждён"]
            )[0],
            seniority_transition=None,
            seniority_notes="Уровень ответственности переносится только при совпадении функций, масштаба и обязательных допусков.",
            professional_capital=capital or confirmed_functions or current_roles,
            transferable_functions=functions,
        ),
        evidence=evidence,
        user_choice=UserChoice(
            desired_change=desired_change,
            preferred_directions=interests + target_roles,
            functions_to_preserve=values(story_analysis, "functions_to_preserve"),
            functions_to_avoid=unwanted,
            priorities=values(profile_snapshot, "selected_career_priorities"),
            acceptable_income_drop=_optional_text(profile_snapshot.get("acceptable_income_drop")),
        ),
        constraints=constraints,
        routes=CareerRoutes(
            primary_routes=primary,
            transition_routes=alternatives,
            recommended_route_id=recommended_id,
            alternative_route_ids=[route.route_id for route in alternatives],
        ),
        questions=QuestionAssessment(
            answered_critical_questions=answered_questions,
            unanswered_critical_questions=[next_question] if next_question else [],
        ),
        conclusions=ConclusionAssessment(
            mandatory_conclusions=[
                "Все маршруты выведены только из фактов текущей оценки",
                "Неизвестные поля ограничивают только связанные с ними выводы",
            ],
            main_conclusion=(
                f"Основной маршрут для безопасной проверки — {primary[0].title}; "
                f"уверенность {'низкая' if insufficient_data else 'средняя'}."
            ),
            what_may_change_conclusion=(
                [next_question] if next_question else ["Результаты проверки требований рынка"]
            ),
        ),
        first_steps=[
            FirstStep(
                "fallback-functions", "Карта подтверждённых функций",
                "Уточнить профессиональное ядро",
                "Для каждой подтверждённой функции запишите один реальный пример и измеримый результат; отдельно отметьте нежелательные задачи.",
                "Функции связаны с примерами, результатами и ограничениями.",
                20, recommended_id, "clarification",
            ),
            FirstStep(
                "fallback-market", "Проверка требований",
                "Проверить маршрут без необратимого перехода",
                f"Сравните пять актуальных описаний работы по маршруту {primary[0].title} и отметьте функции, язык, допуски, формат и требования к уровню.",
                "Таблица совпадений, конфликтов и неизвестных требований.",
                45, recommended_id, "market_research",
            ),
            FirstStep(
                "fallback-contact", "Проверочный разговор",
                "Проверить ежедневные задачи и уровень входа",
                f"Попросите одного специалиста по маршруту {primary[0].title} проверить список задач, обязательные допуски и реалистичный уровень входа.",
                "Один внешний сигнал, подтверждающий или опровергающий маршрут.",
                20, recommended_id, "networking",
            ),
        ],
        metadata={
            "fallback_source_policy": "current_assessment_only",
            "fallback_confidence": "low" if insufficient_data else "medium",
            "fallback_reason": fallback_reason,
            "fallback_mode": "insufficient_data" if insufficient_data else "ranked_hypotheses",
            "route_evaluations": route_evaluations,
            "candidate_count_before_selection": len(candidates),
            "measurable_results_count": len(achievements),
        },
    )
    validate_career_assessment(
        assessment,
        snapshot_country_code=_optional_text(profile_snapshot.get("country_code")),
        snapshot_currency=_optional_text(profile_snapshot.get("currency")),
    ).require_valid()
    return assessment


def validate_career_assessment(
    assessment: CareerAssessment,
    *,
    snapshot_country_code: str | None = None,
    snapshot_currency: str | None = None,
    forbidden_recommendations: list[str] | None = None,
) -> AssessmentValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    def add_error(
        code: str,
        field_path: str,
        message: str,
        actual_value: Any,
        severity: ValidationSeverity = "error",
    ) -> None:
        errors.append(ValidationIssue(code, field_path, message, actual_value, severity))

    def add_warning(code: str, field_path: str, message: str, actual_value: Any) -> None:
        warnings.append(ValidationIssue(code, field_path, message, actual_value, "warning"))

    if not assessment.assessment_id:
        add_error("MISSING_ASSESSMENT_ID", "assessment_id", "assessment_id is empty", assessment.assessment_id)
    if not assessment.identity.professional_core:
        add_error("EMPTY_PROFESSIONAL_CORE", "identity.professional_core", "professional_core is empty", [])
    forbidden_core_fragments = ("пользователь", "имеет опыт", "заинтересован", "смежные роли на основе")
    for index, title in enumerate(assessment.identity.professional_core):
        normalized = title.strip().casefold()
        if (
            normalized.startswith("пользователь")
            or any(fragment in normalized for fragment in forbidden_core_fragments[1:])
            or title.strip().endswith(".")
            or len(title.split()) > 8
        ):
            add_error(
                "RAW_USER_SUMMARY_AS_TITLE",
                f"identity.professional_core[{index}]",
                "professional_core must be a concise professional role or function, not a user summary",
                title,
            )
    if not assessment.identity.core_description:
        add_error("EMPTY_CORE_DESCRIPTION", "identity.core_description", "core_description is empty", "")
    if not assessment.identity.seniority_current:
        add_error("INVALID_SENIORITY", "identity.seniority_current", "seniority_current is empty", "")
    if not assessment.identity.seniority_notes:
        add_error("INVALID_SENIORITY", "identity.seniority_notes", "seniority reasoning is empty", "")
    evidence_text = " ".join(item.fact for item in assessment.evidence).casefold()
    seniority_markers = (
        ("years_experience_8", ("8 лет", "восемь лет")),
        ("team_leadership", ("руковод", "управлял", "команд")),
        ("strategy_ownership", ("стратег",)),
        ("budget_responsibility", ("бюджет",)),
        ("measurable_result_35_percent", ("35",)),
    )
    reason_codes = [
        code for code, markers in seniority_markers if any(marker in evidence_text for marker in markers)
    ]
    assessment.metadata["seniority_reason_codes"] = list(dict.fromkeys(reason_codes))
    current_seniority = assessment.identity.seniority_current.casefold()
    if assessment.status == "full" and len(reason_codes) >= 3 and (
        "средн" in current_seniority
        or "middle" in current_seniority
        or not any(level in current_seniority for level in ("senior", "lead", "руковод"))
    ):
        add_error(
            "INVALID_SENIORITY",
            "identity.seniority_current",
            "current seniority is below the level supported by experience and responsibility facts",
            {"value": assessment.identity.seniority_current, "reason_codes": reason_codes},
        )
    if len(assessment.evidence) < 2:
        add_error("MISSING_ROUTE_EVIDENCE", "evidence", "assessment must contain at least two evidence items", len(assessment.evidence))
    resume_facts = {item.fact.casefold() for item in assessment.evidence if item.source_type == "resume" and item.fact.strip()}
    assessment.metadata["resume_important_facts_count"] = len(resume_facts)
    if assessment.status == "full" and resume_facts and len(resume_facts) < 8:
        add_error(
            "INSUFFICIENT_RESUME_COVERAGE",
            "evidence",
            "assessment must use at least eight distinct relevant resume facts",
            len(resume_facts),
        )
    if not assessment.routes.primary_routes:
        add_error("GENERIC_ROUTE_TITLE", "routes.primary_routes", "primary_routes is empty", [])
    recommended = assessment.routes.by_id(assessment.routes.recommended_route_id)
    if recommended is None:
        add_error("GENERIC_ROUTE_TITLE", "routes.recommended_route_id", "recommended_route_id does not exist", assessment.routes.recommended_route_id)
    elif len(set(recommended.evidence_ids)) < 2:
        add_error("MISSING_ROUTE_EVIDENCE", f"routes.{recommended.route_id}.evidence_ids", "recommended route must reference at least two evidence items", recommended.evidence_ids)

    route_ids = {route.route_id for route in assessment.routes.all_routes() if route.route_id}
    evidence_ids = {item.evidence_id for item in assessment.evidence if item.evidence_id}
    generic_route_titles = {
        "смежные роли",
        "возможный маршрут",
        "направление на основе опыта",
        "другие профессии",
        "-",
    }
    for route_index, route in enumerate(assessment.routes.all_routes()):
        route_path = f"routes.all_routes[{route_index}]"
        if not route.route_id or not route.title:
            add_error("GENERIC_ROUTE_TITLE", route_path, "every route must have a concrete id and title", route.title)
        normalized_title = route.title.strip().casefold()
        if (
            normalized_title in generic_route_titles
            or normalized_title.startswith("смежные роли на основе")
            or "пользователь имеет" in normalized_title
        ):
            add_error("GENERIC_ROUTE_TITLE", f"{route_path}.title", "route title must name a concrete role", route.title)
        if len(set(route.evidence_ids)) < 2:
            add_error("MISSING_ROUTE_EVIDENCE", f"{route_path}.evidence_ids", "route must reference at least two evidence items", route.evidence_ids)
        if not route.why_it_fits or not route.entry_level:
            add_error("UNSUPPORTED_RECOMMENDATION", route_path, "route lacks rationale or entry level", route.to_dict() if hasattr(route, "to_dict") else asdict(route))
        if not route.market_test:
            add_error("MISSING_ROUTE_TEST", f"{route_path}.market_test", "route lacks a market test", route.market_test)
        if not route.missing or not route.risks:
            add_error("UNSUPPORTED_RECOMMENDATION", route_path, "route must state missing evidence and risks", asdict(route))
        if not route.disconfirming_conditions:
            add_error("UNSUPPORTED_RECOMMENDATION", f"{route_path}.disconfirming_conditions", "route lacks disconfirming conditions", [])
        missing_evidence = set(route.evidence_ids) - evidence_ids
        if missing_evidence:
            add_error("MISSING_ROUTE_EVIDENCE", f"{route_path}.evidence_ids", "route references unknown evidence", sorted(missing_evidence))
        for claim_index, claim in enumerate(route.evidence_claims):
            claim_ids = set(_texts(claim.get("evidence_fact_ids")))
            if not str(claim.get("claim") or "").strip() or not claim_ids or claim_ids - evidence_ids:
                add_error("UNLINKED_CLAIM", f"{route_path}.evidence_claims[{claim_index}]", "every claim must reference known fact ids", claim)
        if assessment.context.target_countries and not route.evidence_claims:
            add_error("UNLINKED_CLAIM", f"{route_path}.evidence_claims", "every route must contain at least one evidence-linked claim", [])
        senior_identity = any(level in assessment.identity.seniority_current.casefold() for level in ("senior", "lead", "руковод"))
        downgraded_entry = any(level in route.entry_level.casefold() for level in ("junior", "specialist", "ассистент"))
        downgrade_explained = any(token in f"{route.why_it_fits} {' '.join(route.risks)} {' '.join(route.missing)}".casefold() for token in ("переход", "временно", "новой функц", "не подтверж", "ниже"))
        if senior_identity and downgraded_entry and not downgrade_explained:
            add_error("UNEXPLAINED_SENIORITY_DOWNGRADE", f"{route_path}.entry_level", "senior/lead may not be downgraded without a route-specific explanation", route.entry_level)

    # New country-aware assessments opt into strict cross-route uniqueness.  Legacy
    # stored reports remain readable and are upgraded on their next generation.
    if assessment.context.target_countries:
        routes_for_compare = assessment.routes.all_routes()
        fields = ("why_it_fits", "missing", "risks", "market_test", "entry_path")
        for left_index, left in enumerate(routes_for_compare):
            for right in routes_for_compare[left_index + 1:]:
                duplicates = []
                for field_name in fields:
                    left_value = getattr(left, field_name)
                    right_value = getattr(right, field_name)
                    left_text = " ".join(left_value) if isinstance(left_value, list) else str(left_value)
                    right_text = " ".join(right_value) if isinstance(right_value, list) else str(right_value)
                    if left_text and right_text and SequenceMatcher(None, left_text.casefold(), right_text.casefold()).ratio() >= 0.86:
                        duplicates.append(field_name)
                if len(duplicates) >= 2:
                    add_error("DUPLICATE_ROUTE_ANALYSIS", "routes", "routes must have distinct rationale, gap, risk, test and entry path", {"routes": [left.route_id, right.route_id], "fields": duplicates})

    if not 3 <= len(assessment.first_steps) <= 5:
        add_error("MISSING_FIRST_STEPS", "first_steps", "first_steps must contain 3 to 5 items", len(assessment.first_steps))
    if len({step.type for step in assessment.first_steps}) != len(assessment.first_steps):
        add_error("DUPLICATE_FIRST_STEP_TYPE", "first_steps", "first_steps must have different types", [step.type for step in assessment.first_steps])
    for step in assessment.first_steps:
        if not step.step_id or not step.action or not step.expected_result or step.duration_minutes <= 0:
            add_error("INVALID_FIRST_STEP", f"first_steps.{step.step_id}", "each first step needs id, action, duration, and expected result", asdict(step))
        if not step.related_route_id or step.related_route_id not in route_ids:
            add_error("INVALID_FIRST_STEP", f"first_steps.{step.step_id}.related_route_id", "step must reference an existing route", step.related_route_id)
        related_route = assessment.routes.by_id(step.related_route_id)
        if step.type == "market_research" and related_route and related_route.title.casefold() not in step.action.casefold():
            add_error(
                "MISSING_ROUTE_TEST",
                f"first_steps.{step.step_id}.action",
                "market research action must use the related route title",
                step.action,
            )

    if assessment.conclusions.critical_errors_detected:
        add_error("FORBIDDEN_OUTPUT_PATTERN", "conclusions.critical_errors_detected", "critical errors detected in conclusion", assessment.conclusions.critical_errors_detected, "critical")
    if not assessment.conclusions.mandatory_conclusions or not assessment.conclusions.main_conclusion:
        add_error("MISSING_CONCLUSION", "conclusions", "conclusion is incomplete", asdict(assessment.conclusions))
    duplicate_questions = set(assessment.questions.answered_critical_questions) & set(
        assessment.questions.unanswered_critical_questions
    )
    if duplicate_questions:
        add_error("DUPLICATE_QUESTION", "questions", "answered critical questions must not be asked again", sorted(duplicate_questions))
    if snapshot_country_code and assessment.context.country_code != snapshot_country_code:
        add_error("COUNTRY_MISMATCH", "context.country_code", "country does not match ProfileSnapshot", assessment.context.country_code)
    currencies = {
        money.currency
        for money in (assessment.context.income_minimum, assessment.context.income_target, assessment.context.learning_budget)
        if money and money.currency
    }
    if snapshot_currency and currencies and currencies != {snapshot_currency}:
        add_error("COUNTRY_MISMATCH", "context.currency", "currency does not match ProfileSnapshot", sorted(currencies))
    expected_currency = {"литва": "EUR", "lithuania": "EUR", "польша": "PLN", "poland": "PLN"}
    target_currency = next((currency for country, currency in expected_currency.items() if any(country in target.casefold() for target in assessment.context.target_countries)), None)
    if target_currency and assessment.context.preferred_currency and assessment.context.preferred_currency != target_currency:
        add_error("COUNTRY_CURRENCY_MISMATCH", "context.preferred_currency", "currency must follow the target market", assessment.context.preferred_currency)
    market_blob = " ".join(note for route in assessment.routes.all_routes() for note in route.market_notes)
    if any(char.isdigit() for char in market_blob) and (not assessment.context.market_data_date or not assessment.context.market_data_sources):
        add_error("UNSOURCED_MARKET_FIGURES", "context.market_data_sources", "market figures require a source and date", market_blob)
    report_text = " ".join(_all_strings(assessment.to_dict())).casefold()
    for diagnosis in ("у вас синдром самозванца", "вам не хватает уверенности", "вы боитесь перемен"):
        if diagnosis in report_text:
            add_error("PSYCHOLOGICAL_DIAGNOSIS", "$", "unsupported psychological assertion is forbidden", diagnosis)

    desired_change = (assessment.user_choice.desired_change or "").casefold()
    preferred_directions = " ".join(assessment.user_choice.preferred_directions).casefold()
    if "остаться" in desired_change and any(term in preferred_directions for term in ("продукт", "образован", "психолог", "консалт")):
        add_warning(
            "CONTRADICTORY_USER_CHOICE",
            "user_choice",
            "Interpret as preserving professional capital while testing a different role or context; ask one clarifying question if needed",
            asdict(assessment.user_choice),
        )
        assessment.metadata["user_choice_hypothesis"] = "Остаться в широком профессиональном поле, но сменить роль или контекст"

    visible_assessment = assessment.to_dict()
    visible_assessment.pop("metadata", None)
    visible_values = _all_strings(visible_assessment)
    forbidden_placeholders = {"-", "\\-", "данных недостаточно", "возможный маршрут"}
    if any(value.strip().casefold() in forbidden_placeholders for value in visible_values):
        add_error("FORBIDDEN_OUTPUT_PATTERN", "$", "placeholder user-facing value detected", "placeholder")
    if any(value.strip().startswith("{") and value.strip().endswith("}") for value in visible_values):
        add_error("FORBIDDEN_OUTPUT_PATTERN", "$", "serialized object detected in user-facing string", "serialized object")
    for forbidden in forbidden_recommendations or []:
        if any(forbidden.casefold() in value.casefold() for value in visible_values):
            add_error("UNSUPPORTED_RECOMMENDATION", "$", "forbidden recommendation detected", forbidden, "critical")

    def deduplicate(issues: list[ValidationIssue]) -> tuple[ValidationIssue, ...]:
        unique: dict[tuple[str, str, str], ValidationIssue] = {}
        for issue in issues:
            unique[(issue.code, issue.field_path, issue.message)] = issue
        return tuple(unique.values())

    result = AssessmentValidationResult(valid=not errors, errors=deduplicate(errors), warnings=deduplicate(warnings))
    assessment.metadata["validation"] = result.to_dict()
    return result


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
        return f"<section><h2>{escape(title)}</h2><p>Маршрут пока не подтверждён; он появится после проверки фактов.</p></section>"
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
            + f"<p><strong>Путь входа:</strong> {escape(route.entry_path)}</p>"
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
    known = list(evidence.values())[:7]
    assumptions = ["Рыночные выводы предварительны: встроенного актуального поиска вакансий нет."] if not assessment.context.market_data_sources else []
    heard = list(dict.fromkeys([*assessment.user_choice.functions_to_preserve, *assessment.user_choice.functions_to_avoid, *assessment.user_choice.priorities, *known]))[:7]
    residence = assessment.context.residence_country or assessment.context.country_name or "не указана"
    targets = assessment.context.target_countries or ([assessment.context.country_name] if assessment.context.country_name else [])
    currency = assessment.context.preferred_currency or next((m.currency for m in (assessment.context.income_minimum, assessment.context.income_target) if m and m.currency), None) or "не определена"
    constraints = [f"{item.title}: {item.impact}" for item in assessment.constraints if item.confirmed]
    route_rows = "".join(
        f"<tr><td>{escape(route.title)}</td><td>{escape('высокое' if len(route.evidence_ids) >= 3 else 'среднее')}</td><td>{escape('требует проверки')}</td><td>{escape('сохраняется' if route.preserves else 'может снизиться')}</td><td>{escape('быстро' if route.entry_path == 'direct_entry' else 'поэтапно')}</td><td>{escape('минимальный' if route.entry_path == 'direct_entry' else 'точечный/существенный')}</td><td>{escape('предварительно')}</td><td>{escape('зависит от подтверждённых ограничений')}</td><td>{escape(', '.join(route.risks))}</td></tr>"
        for route in assessment.routes.all_routes()[:4]
    )
    language_text = ", ".join(f"{item.language} {item.level or ''}".strip() for item in assessment.context.current_languages) or "не указаны"
    steps = "".join(
        f"<article><h3>{escape(step.title)} · {step.duration_minutes} минут</h3>"
        f"<p><strong>Цель:</strong> {escape(step.purpose)}</p>"
        f"<p><strong>Действие:</strong> {escape(step.action)}</p>"
        f"<p><strong>Ожидаемый результат и критерий успеха:</strong> {escape(step.expected_result)}</p></article>"
        for step in assessment.first_steps
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Карьерное заключение</title>
<style>body{{font-family:Georgia,serif;max-width:900px;margin:32px auto;padding:0 20px;color:#17211d;line-height:1.55}}h1,h2{{font-family:Arial,sans-serif}}section{{border-top:1px solid #b8c2bc;padding:20px 0}}article{{margin:16px 0}}.meta{{color:#526159}}</style></head><body>
<h1>Карьерное заключение</h1>
<section><h2>1. Короткое человеческое резюме</h2><p>{escape(assessment.identity.core_description)}</p><p>{escape(assessment.conclusions.main_conclusion)}</p></section>
<section><h2>2. Профессиональная идентичность</h2>{_list_html(assessment.identity.professional_core)}<p><strong>Подтверждённый уровень:</strong> {escape(assessment.identity.seniority_current)}</p><p>{escape(assessment.identity.seniority_notes)}</p><h3>Капитал, который важно сохранить</h3>{_list_html(assessment.identity.professional_capital)}</section>
<section><h2>3. Что мы услышали</h2>{_list_html(heard or known[:5])}</section>
<section><h2>4. Контекст страны и рынка</h2><p><strong>Страна проживания:</strong> {escape(residence)}</p><p><strong>Целевой рынок:</strong> {escape(', '.join(targets) or 'не указан')}</p><p><strong>Валюта:</strong> {escape(currency)}</p><p><strong>Языки работы:</strong> {escape(language_text)}</p><p><strong>Право на работу:</strong> {escape(assessment.context.work_authorization or 'неизвестно')}</p><p><strong>Формат:</strong> {escape(assessment.context.work_format or 'неизвестно')}</p><p><strong>Уверенность рыночных данных:</strong> {escape(assessment.context.market_data_confidence)}</p>{_list_html(assessment.context.market_data_sources or ['Диапазон требует рыночной проверки'])}</section>
{_routes_html('5. Рекомендуемый маршрут', [recommended] if recommended else [], evidence)}
{_routes_html('6. Альтернативные маршруты', [route for route in assessment.routes.all_routes() if route and route.route_id in assessment.routes.alternative_route_ids][:3], evidence)}
<section><h2>7. Сравнение маршрутов</h2><table><thead><tr><th>Маршрут</th><th>Соответствие опыту</th><th>Сохранение дохода</th><th>Сохранение статуса</th><th>Скорость</th><th>Дообучение</th><th>Доступность на рынке</th><th>Психологическая устойчивость</th><th>Общий риск</th></tr></thead><tbody>{route_rows}</tbody></table></section>
<section><h2>8. Условия, при которых переход будет устойчивым</h2>{_list_html(constraints or ['Проверять переход без увольнения и крупных расходов.', 'Не трактовать неизвестные семейные, медицинские или миграционные обстоятельства как психологические факты.'])}</section>
<section><h2>9. Пробелы и неопределённость</h2><h3>Что известно</h3>{_list_html(known)}<h3>Что предполагается</h3>{_list_html(assumptions or ['Предположения отделены от подтверждённых фактов.'])}<h3>Чего пока не знаем</h3>{_list_html(unanswered or ['Критичных неизвестных не зафиксировано.'])}<h3>Что может изменить рекомендацию</h3>{_list_html(assessment.conclusions.what_may_change_conclusion)}</section>
<section><h2>10. Несколько первых шагов</h2>{steps}</section>
<section><h2>11. Итоговая рекомендация</h2><p><strong>Основной маршрут:</strong> {escape(recommended.title if recommended else '')}</p><p>{escape(assessment.conclusions.main_conclusion)}</p><p><strong>Уровень уверенности:</strong> {escape('средний' if unanswered else 'высокий')}</p>{f'<p><strong>Альтернатива:</strong> {escape(", ".join(alternatives))}</p>' if alternatives else ''}<h3>Условие изменения рекомендации</h3>{_list_html(assessment.conclusions.what_may_change_conclusion)}</section>
</body></html>"""
