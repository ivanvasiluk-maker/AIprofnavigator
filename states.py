from aiogram.fsm.state import State, StatesGroup
from pydantic import BaseModel, Field


class InterviewContext(BaseModel):
    evidence_profile: dict = Field(default_factory=dict)
    hypotheses: list[dict] = Field(default_factory=list)
    current_action: str | None = None
    current_question_id: str | None = None
    current_question_goal: str | None = None

    asked_question_signatures: list[str] = Field(default_factory=list)
    answered_gap_ids: list[str] = Field(default_factory=list)
    skipped_gap_ids: list[str] = Field(default_factory=list)
    resolved_fact_types: list[str] = Field(default_factory=list)
    unresolved_critical_gaps: list[str] = Field(default_factory=list)
    unresolved_noncritical_gaps: list[str] = Field(default_factory=list)

    report_readiness: str = "not_ready"
    questions_asked_count: int = 0
    consecutive_long_answers: int = 0
    user_fatigue_score: float = 0.0


class CareerFlow(StatesGroup):
    START = State()
    SELECTING_PACE = State()
    SELECTING_VOICE_PACE = State()
    WAITING_STORY = State()
    CONFIRMING_STORY = State()
    ASK_CV = State()
    WAITING_CV = State()
    RESUME_ANALYZING = State()
    INTERVIEW = State()
    SELECTING_BARRIERS = State()
    GENERATING_REPORT = State()
    ROUTE_CONTEXT = State()
    ROUTE_SELECTION = State()
    FINAL_READY = State()
    SHOWING_DETAILS = State()
    WAITING_ROUTE_CHANGES = State()
    REBUILDING_ROUTE = State()
    CV_REVIEW_WAITING_FILE = State()
    CV_REVIEW_READY = State()
    BARRIER_ANALYSIS_MENU = State()
    BARRIER_ANALYSIS_DETAIL = State()
    KEYWORDS_MODE = State()
    SUPPORT_OFFER = State()
    THINKING_REMINDER = State()
    STEP_TRACKING = State()
    STEP_BARRIER_INPUT = State()
    REPORT_CLARIFICATION = State()
    REPORT_READINESS_CHECK = State()
    REPORT_NEEDS_CLARIFICATION = State()
    REPORT_GENERATING = State()
    REPORT_READY = State()
    START_GUIDE = State()
    REPORT_GENERATION_FAILED = State()
    PDF_GENERATING = State()
    PDF_READY = State()
    CRISIS_SUPPORT = State()

    confirming_transcription = State()

    # Backward-compatible aliases used by existing handlers/tests.
    choosing_language = START
    choosing_pace = SELECTING_PACE
    choosing_voice_pace = SELECTING_VOICE_PACE
    waiting_for_story = WAITING_STORY
    confirming_story = CONFIRMING_STORY
    waiting_for_resume_decision = ASK_CV
    waiting_for_resume = WAITING_CV
    waiting_for_answers = INTERVIEW
    waiting_for_route_context = ROUTE_CONTEXT
    waiting_for_barriers = SELECTING_BARRIERS
    waiting_for_post_result_action = FINAL_READY
    waiting_for_skiller_reason = BARRIER_ANALYSIS_DETAIL
    waiting_for_fears = BARRIER_ANALYSIS_MENU
