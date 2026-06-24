from aiogram.fsm.state import State, StatesGroup


class CareerFlow(StatesGroup):
    START = State()
    SELECTING_PACE = State()
    SELECTING_VOICE_PACE = State()
    WAITING_STORY = State()
    ASK_CV = State()
    WAITING_CV = State()
    RESUME_ANALYZING = State()
    INTERVIEW = State()
    SELECTING_BARRIERS = State()
    GENERATING_REPORT = State()
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
    PDF_GENERATING = State()
    PDF_READY = State()

    confirming_transcription = State()

    # Backward-compatible aliases used by existing handlers/tests.
    choosing_language = START
    choosing_pace = SELECTING_PACE
    choosing_voice_pace = SELECTING_VOICE_PACE
    waiting_for_story = WAITING_STORY
    waiting_for_resume_decision = ASK_CV
    waiting_for_resume = WAITING_CV
    waiting_for_answers = INTERVIEW
    waiting_for_barriers = SELECTING_BARRIERS
    waiting_for_post_result_action = FINAL_READY
    waiting_for_skiller_reason = BARRIER_ANALYSIS_DETAIL
    waiting_for_fears = BARRIER_ANALYSIS_MENU
