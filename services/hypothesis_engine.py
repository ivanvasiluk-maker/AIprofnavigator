"""
Hypothesis-based conversation engine (PATCH-26).

Instead of asking predefined questions, the system forms hypotheses
from the user's narrative and selects a conversation action that
tests the most uncertain but impactful hypothesis.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from services.evidence_profile import CareerEvidenceProfile

ConversationAction = Literal[
    "reflect",
    "clarify",
    "confirm_hypothesis",
    "resolve_contradiction",
    "check_boundary",
    "check_constraint",
    "offer_preliminary_result",
]


class CareerHypothesis(BaseModel):
    statement: str
    confidence: Literal["confirmed", "probable", "weak", "unknown"] = "unknown"
    supporting_evidence: list[str] = Field(default_factory=list)
    disconfirming_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    action: ConversationAction
    hypothesis: CareerHypothesis | None = None
    gap_key: str | None = None
    message_text: str = ""


def build_hypotheses_from_analysis(story_analysis: dict) -> list[CareerHypothesis]:
    """
    Build initial hypotheses from the v2 story analysis.
    Uses professional_core_hypotheses, functions_detected, and explicit_refusals.
    """
    if not isinstance(story_analysis, dict):
        return []

    hypotheses: list[CareerHypothesis] = []

    # From PATCH-23 v2 fields: professional_core_hypotheses
    for raw in (story_analysis.get("professional_core_hypotheses") or []):
        text = str(raw or "").strip()
        if not text:
            continue
        hypotheses.append(
            CareerHypothesis(
                statement=text,
                confidence="probable",
                supporting_evidence=[],
                disconfirming_evidence=[],
                missing_evidence=[],
            )
        )

    # Build from functions_detected
    for func in (story_analysis.get("functions_detected") or []):
        if not isinstance(func, dict):
            continue
        name = str(func.get("name") or "").strip()
        confidence_raw = str(func.get("confidence") or "unknown").strip()
        if confidence_raw not in {"confirmed", "probable", "weak", "unknown"}:
            confidence_raw = "unknown"
        if not name:
            continue
        evidence = [str(e).strip() for e in (func.get("evidence") or []) if str(e).strip()]
        results = [str(r).strip() for r in (func.get("results") or []) if str(r).strip()]
        missing: list[str] = []
        if func.get("autonomy") == "unknown":
            missing.append("уровень самостоятельности")
        if func.get("frequency") == "unknown":
            missing.append("регулярность функции")
        if func.get("scale") == "unknown":
            missing.append("масштаб ответственности")
        hypotheses.append(
            CareerHypothesis(
                statement=f"Пользователь регулярно выполнял функцию: {name}",
                confidence=confidence_raw,  # type: ignore[arg-type]
                supporting_evidence=evidence + results,
                disconfirming_evidence=[],
                missing_evidence=missing,
            )
        )

    # Deduplicate by statement prefix
    seen: set[str] = set()
    unique: list[CareerHypothesis] = []
    for h in hypotheses:
        key = h.statement[:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique


def _best_testable_hypothesis(hypotheses: list[CareerHypothesis]) -> CareerHypothesis | None:
    """Pick the hypothesis with highest priority for testing."""
    candidates = [h for h in hypotheses if h.confidence in {"probable", "weak"} and h.missing_evidence]
    if not candidates:
        candidates = [h for h in hypotheses if h.confidence in {"probable", "weak"}]
    if not candidates:
        return None
    # Prefer higher confidence
    candidates.sort(key=lambda h: {"probable": 0, "weak": 1, "unknown": 2, "confirmed": 3}[h.confidence])
    return candidates[0]


def select_conversation_action(
    profile: CareerEvidenceProfile,
    hypotheses: list[CareerHypothesis],
    *,
    qa_index: int = 0,
    readiness_status: str = "not_ready",
    user_mode: str = "calm_steps",
) -> ConversationTurn:
    """
    Select the single best conversation action given current profile and hypotheses.

    Priority:
    1. offer_preliminary_result — if data is sufficient
    2. resolve_contradiction  — if known contradictions exist
    3. check_boundary         — if explicit refusals need verification
    4. check_constraint       — if safety-level gap open
    5. confirm_hypothesis     — if testable hypothesis with missing evidence
    6. reflect                — if enough evidence to summarize (≥2 answers given)
    7. clarify                — default gap question
    """
    # 1. Ready for result
    if readiness_status in {"ready", "ready_with_uncertainty"} and qa_index >= 2:
        return ConversationTurn(action="offer_preliminary_result")

    # 2. Contradictions
    if profile.contradictions:
        contradiction = profile.contradictions[0]
        return ConversationTurn(
            action="resolve_contradiction",
            message_text=f"Хочу разобраться: {contradiction}\n\nКак на самом деле это было?",
        )

    # 3. Explicit refusals that may not have been checked yet
    if profile.explicit_refusals and qa_index == 0:
        refusal = profile.explicit_refusals[0].statement
        return ConversationTurn(
            action="check_boundary",
            message_text=(
                f"Уточню сразу: вы упомянули, что не хотите «{refusal}». "
                "Это абсолютное ограничение или есть исключения?"
            ),
        )

    # 4. Safety constraint (legal access unknown for potentially regulated profession)
    legal = profile.legal_access
    if legal.profession_is_regulated is True and not legal.current_permission:
        return ConversationTurn(
            action="check_constraint",
            gap_key="regulated_profession_access",
        )

    # 5. Confirm hypothesis — test the most uncertain hypothesis
    testable = _best_testable_hypothesis(hypotheses)
    if testable is not None and qa_index <= 3:
        return ConversationTurn(
            action="confirm_hypothesis",
            hypothesis=testable,
        )

    # 6. Reflect — concrete summary if enough info accumulated
    if qa_index >= 2 and (len(profile.work_history_facts) >= 2 or profile.functions):
        return ConversationTurn(
            action="reflect",
            message_text=_build_reflect_text(profile),
        )

    # 7. Default: clarify via interview_policy gap question
    return ConversationTurn(action="clarify")


def _build_reflect_text(profile: CareerEvidenceProfile) -> str:
    """Build a concrete (non-generic) reflection from the evidence profile."""
    parts: list[str] = []

    goals = [e.statement for e in profile.explicit_goal[:2] if e.statement.strip()]
    if goals:
        parts.append(f"Главный запрос — {goals[0].lower().rstrip('.')}.")

    refusals = [e.statement for e in profile.explicit_refusals[:1] if e.statement.strip()]
    if refusals:
        parts.append(f"Вы хотите уйти от: {refusals[0].lower().rstrip('.')}.")

    funcs = [f.function_name for f in profile.functions[:2] if f.function_name]
    if funcs:
        parts.append(f"Из опыта видно: {', '.join(funcs)}.")

    if not parts:
        facts = [e.statement for e in profile.work_history_facts[:2] if e.statement.strip()]
        parts = [f.lower().rstrip(".") + "." for f in facts]

    return " ".join(parts) if parts else ""


def format_conversation_turn(
    turn: ConversationTurn,
    next_question_text: str = "",
    lang: str = "ru",
) -> str:
    """
    Return the conversational message text for a given action.
    Returns empty string when the action should fall back to the bare question.

    Rules:
    - No generic "Я вас понимаю."
    - reflect must contain concrete facts
    - confirm_hypothesis must name the specific hypothesis
    """
    action = turn.action

    if action == "confirm_hypothesis" and turn.hypothesis:
        h = turn.hypothesis
        statement = h.statement.rstrip(".")
        question = next_question_text or "Это похоже на ваш случай?"
        return (
            f"Похоже, {statement.lower()}.\n\n"
            f"Это похоже на ваш случай, или ценность вашей работы была в другом?\n\n"
            f"{question}"
        )

    if action == "resolve_contradiction" and turn.message_text:
        base = turn.message_text.rstrip()
        if next_question_text:
            return f"{base}\n\n{next_question_text}"
        return base

    if action == "check_boundary" and turn.message_text:
        base = turn.message_text.rstrip()
        if next_question_text:
            return f"{base}\n\n{next_question_text}"
        return base

    if action == "reflect" and turn.message_text:
        # Reflection must be concrete — if text is empty skip
        text = turn.message_text.strip()
        if not text:
            return ""
        if next_question_text:
            return f"{text}\n\nПо этому хочу уточнить: {next_question_text}"
        return text

    # clarify, check_constraint, offer_preliminary_result: let handler decide
    return ""
