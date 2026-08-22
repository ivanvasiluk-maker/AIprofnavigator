from __future__ import annotations

import asyncio
import copy
import io
import json
import os
import re
import tempfile
import uuid
import zipfile
from functools import wraps
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Document, FSInputFile, Message, ReplyKeyboardRemove
from pypdf import PdfReader

from config import settings
from keyboards import (
    ALL_INPUT_DONT_KNOW,
    ALL_SHORT_STORY_OPTIONS,
    ALL_STORY_CONFIRM_ACTIONS,
    ALL_SELF_EXPLORE_ACTIONS,
    ALL_STEP_TRACKING_ACTIONS,
    ALL_SUPPORT_OPTIONS,
    ALL_INPUT_TEXT,
    ALL_INPUT_VOICE,
    ALL_PSYCH_BARRIER_DONE,
    ALL_PSYCH_GROUP_OPTIONS,
    ALL_PSYCH_BARRIER_OPTIONS,
    PSYCH_BARRIER_OPTIONS,
    ALL_RESTART,
    ALL_RESUME_SKIP,
    ALL_RESUME_UPLOAD,
    ALL_SUPPORT_MODE_ACTIONS,
    ALL_ROUTE_SELECTION_ACTIONS,
    ALL_ROUTE_CHOICE_ACTIONS,
    ALL_CAREER_SWITCH_REASON_OPTIONS,
    ALL_ANSWER_REVIEW_ACTIONS,
    ALL_BARRIER_DETAIL_ACTIONS,
    ALL_CV_REVIEW_ACTIONS,
    ALL_CAREER_STRATEGY_ACTIONS,
    ALL_PRACTICAL_BARRIER_ACTIONS,
    ALL_SPECIALIST_ROUTING_ACTIONS,
    ALL_CRISIS_SUPPORT_ACTIONS,
    SUPPORT_DONE,
    ALL_RESULT_ACTIONS,
    RESULT_ANALYZE_FEARS,
    RESULT_BACK_TO_MENU,
    RESULT_START_FIRST_STEP,
    RESULT_FIX_FACT_OR_PRIORITY,
    RESULT_UPLOAD_OR_EDIT_RESUME,
    RESULT_ANALYZE_MARKET,
    RESULT_SPECIALIST_EXPLICIT,
    RESULT_GROUP_EXPLICIT,
    CTA_CAREER_CHAT,
    CTA_CAREER_CONSULTANT,
    CTA_JOB_SEARCH_SUPPORT,
    RESULT_CLARIFY,
    RESULT_DETAILS,
    RESULT_DO_STEPS,
    RESULT_DOWNLOAD_PDF,
    RESULT_DOWNLOAD_DOCX,
    QUESTION_ADD_TEXT,
    EXTENDED_DIAG_YES,
    EXTENDED_DIAG_SKIP,
    RESULT_FIX_CV,
    RESULT_KEYWORDS,
    RESULT_OPEN_FULL_REPORT,
    MAP_CHECK_TRUE,
    SHOW_MAP_NOW,
    CLARIFY_MORE,
    PRELIM_LOOKS_LIKE_ME,
    PRELIM_HAS_ERROR,
    PRELIM_ADD_DETAIL,
    preliminary_result_offer_keyboard,
    preliminary_map_keyboard,
    MAP_CHECK_FIX_FACT,
    MAP_CHECK_CHANGE_PRIORITY,
    MAP_CHECK_DISAGREE_ROUTE,
    RESULT_REBUILD,
    RESULT_SELF_EXPLORE,
    RESULT_SPECIALIST,
    RESULT_SUPPORT_GROUP,
    RESULT_MY_MAP,
    RESULT_SUPPORT,
    RESULT_THINK,
    RESULT_TODAY_STEP,
    SUPPORT_BACK_TO_MAP,
    PDF_FALLBACK_STEPS,
    PDF_FALLBACK_CLARIFY,
    PDF_FALLBACK_SPECIALIST,
    CAREER_STRATEGY_FAST_INCOME,
    CAREER_STRATEGY_UPSKILL,
    CAREER_STRATEGY_LONG,
    CAREER_STRATEGY_HELP,
    ROUTE_CHOICE_STABLE,
    ROUTE_CHOICE_PRIVATE,
    ROUTE_CHOICE_RETRAIN,
    ROUTE_CHOICE_HELP,
    ROUTE_CHOICE_CLOSE,
    ROUTE_CHOICE_OTHER,
    ROUTE_CHOICE_NO_LOGIC,
    SPECIALIST_ROUTE_CAREER,
    SPECIALIST_ROUTE_PSYCH,
    SPECIALIST_ROUTE_BOTH,
    SPECIALIST_ROUTE_SELF,
    CRISIS_HELP_HOTLINE,
    CRISIS_CONTINUE_LATER,
    CRISIS_SPECIALIST,
    CRISIS_TRUSTED_PERSON,
    STEP_BARRIERS,
    STEP_DONE,
    STEP_DONE_USER,
    STEP_TOO_HARD,
    STEP_MAKE_EASIER,
    STEP_OTHER_STEP,
    STEP_NEXT_DAY,
    STEP_NOT_DONE,
    STEP_OPEN_TODAY,
    STORY_CONFIRM_FIX,
    STORY_CONFIRM_OK,
    PSYCH_SKIP,
    BARRIER_GROUP_BEHAVIOR,
    BARRIER_GROUP_INTERNAL,
    BARRIER_GROUP_LIFE,
    ANSWER_KEEP,
    ANSWER_SKIP,
    ANSWER_RETRY,
    ANSWER_CONTEXT_YES,
    ANSWER_CONTEXT_NO,
    BARRIER_DETAIL_BACK,
    BARRIER_DETAIL_CHAOS,
    BARRIER_DETAIL_FEAR_REJECTION,
    BARRIER_DETAIL_FIRST_STEP,
    BARRIER_DETAIL_MONEY,
    CV_REVIEW_BACK,
    CV_REVIEW_BULLETS,
    CV_REVIEW_LETTER,
    PRACTICAL_BACK,
    PRACTICAL_DEEP,
    PRACTICAL_STEP,
    answer_review_keyboard,
    barrier_analysis_keyboard,
    cv_review_actions_keyboard,
    barriers_group_keyboard,
    barriers_keyboard,
    interview_support_keyboard,
    interview_work_format_keyboard,
    input_method_keyboard,
    extended_diagnostics_keyboard,
    question_options_keyboard,
    result_actions_keyboard,
    next_step_cta_keyboard,
    self_exploration_keyboard,
    short_story_keyboard,
    practical_barrier_keyboard,
    pdf_fallback_keyboard,
    map_validation_keyboard,
    pace_keyboard,
    career_strategy_keyboard,
    specialist_routing_keyboard,
    crisis_support_keyboard,
    resume_choice_keyboard,
    resume_wait_keyboard,
    step_tracking_keyboard,
    support_mode_keyboard,
    route_choice_keyboard,
    report_readiness_keyboard,
    career_switch_reason_keyboard,
    # route-context intake uses plain text prompts and the existing input method keyboard
    story_confirmation_keyboard,
    telegram_link_keyboard,
    think_reminder_keyboard,
    first_step_selection_keyboard,
    assessment_actions_keyboard,
    start_guide_keyboard,
    guide_followup_keyboard,
    income_urgency_keyboard,
    selected_step_actions_keyboard,
    assessment_recovery_keyboard,
)
from localization import t
from openai_client import ai_client
from services.evidence_profile import (
    CareerEvidenceProfile,
    apply_answer_to_profile,
    build_evidence_profile_from_analysis,
    next_question_from_profile,
    profile_ready_for_safe_conclusion,
)
from services.canonical_profile import (
    CanonicalProfile,
    ClarifyingQuestion,
    build_canonical_profile,
    record_question_answer,
    select_clarifying_question,
)
from services.career_assessment import (
    CAREER_HTML_RENDERER_VERSION,
    CAREER_PIPELINE_VERSION,
    CAREER_TELEGRAM_RENDERER_VERSION,
    CareerAssessment,
    build_deterministic_assessment,
    career_assessment_from_dict,
    render_first_step_instruction,
    render_route_comparison,
    render_telegram_map,
    render_short_conclusion,
    start_guide_response,
    validated_assessment_result,
    build_income_bridge,
    validate_career_assessment,
)
from services.assessment_integrity import audit_facts, build_fact_ledger, consistency_errors, contamination_errors
from states import CareerFlow, InterviewContext
from utils.analytics import behavior_insights, behavior_offer_snapshot, days_since_first_seen, ensure_public_user_id, log_behavior_event
from utils.persistence import get_report_by_generation_id, save_profile_version, save_report_version, touch_session, update_report_files
from utils.reporting import build_telegram_summary, ensure_next_step_guidance, generate_docx_report_file, generate_pdf_report
from utils.reporting import generate_assessment_html_file, generate_html_report_file, generate_pdf_from_html_file_with_error

router = Router()
_REMINDER_TASKS: dict[int, asyncio.Task] = {}
_PDF_TASKS: dict[int, asyncio.Task] = {}
_PDF_READY_BY_CHAT: dict[int, str] = {}
_INTERVIEW_UPDATE_LOCKS: dict[int, asyncio.Lock] = {}


def _runtime_build_metadata() -> dict[str, str]:
    commit = str(os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA") or "").strip()
    if not commit:
        try:
            git_dir = Path(__file__).resolve().parents[1] / ".git"
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
            commit = (git_dir / head.removeprefix("ref: ")).read_text(encoding="utf-8").strip() if head.startswith("ref: ") else head
        except (OSError, ValueError):
            commit = "unknown"
    build_time = str(os.getenv("BUILD_TIME") or "").strip()
    if not build_time:
        try:
            build_time = (Path(__file__).resolve().parents[1] / ".build_time").read_text(encoding="utf-8").strip()
        except OSError:
            build_time = datetime.fromtimestamp(Path(__file__).stat().st_mtime, timezone.utc).isoformat()
    return {"build_commit": commit, "build_time": build_time, "environment": str(settings.environment)}


def _runtime_debug_log(event: str, **payload: object) -> None:
    print(json.dumps({"event": event, **_runtime_build_metadata(), **payload}, ensure_ascii=False, default=str), flush=True)


def _serialize_interview_update(handler):
    """Serialize rapid reply-keyboard updates for one Telegram chat.

    Aiogram can execute adjacent updates concurrently. Both handlers below
    perform read-modify-write operations on the same FSM lists and indexes, so
    processing them without a chat lock can reorder Done and the preceding
    option or advance two questions at once.
    """
    @wraps(handler)
    async def wrapped(message: Message, state: FSMContext, *args, **kwargs):
        chat = getattr(message, "chat", None)
        key = int(getattr(chat, "id", 0) or getattr(getattr(message, "from_user", None), "id", 0) or id(state))
        lock = _INTERVIEW_UPDATE_LOCKS.setdefault(key, asyncio.Lock())
        async with lock:
            return await handler(message, state, *args, **kwargs)
    return wrapped

_BARRIER_DONE_ALIASES = {
    "все",
    "всё",
    "готово",
    "дальше",
    "continue",
    "done",
}

_BARRIER_OPTION_BY_LOWER = {item.strip().lower(): item for item in ALL_PSYCH_BARRIER_OPTIONS}
_BARRIER_DONE_BY_LOWER = {item.strip().lower() for item in ALL_PSYCH_BARRIER_DONE}
_INTERVIEW_PSYCH_DONE = "✅ Психология: готово"
_INTERVIEW_SOCIAL_DONE = "✅ Соцблок: готово"
_INTERVIEW_ENERGY_DONE = "✅ Энергия: готово"
_INTERVIEW_PRIORITIES_DONE = "✅ Приоритеты: готово"
_INTERVIEW_INTEGRATION_DONE = "✅ Интеграция: готово"
_BARRIER_GROUP_MAX_SELECT = 3
_HARD_REQUIRED_MULTI_KEYS = {"psych", "integration", "energy", "priorities"}

_NEED_DECISION_QUESTIONS = [
    "1/3. Как долго вы можете прожить без стабильного дохода?",
    "2/3. Насколько для вас важно сохранить профессиональный статус?",
    "3/3. Готовы ли вы учиться регулярно ближайшие 3–6 месяцев?",
]

LANGUAGE_DOCUMENTS_BUTTONS = [
    "Польский A1-A2, право работать есть",
    "Польский B1+, право работать есть",
    "Язык слабый, документы в порядке",
    "Не уверен по документам",
    "Нужно уточнить право на работу",
    "Отвечу текстом",
]

_CONSTRUCTION_BRIDGE_ROLES = [
    "Assistant Cost Estimator",
    "Junior Quantity Surveyor",
    "Construction Documentation Specialist",
    "Technical Assistant Construction",
    "Construction Project Assistant",
]

# All fields that must be wiped when a new story begins; prevents stale conclusions
# from a previous run contaminating a new analysis.  Preserve: public_user_id, language,
# user_mode, session_id, source_tag, memory_context, interaction_profile (overwritten below).
SESSION_FSM_CACHE: dict[tuple[str, str], FSMContext] = {}
SESSION_MESSAGE_CACHE: dict[tuple[str, str], Message] = {}


async def _register_session_context(state: FSMContext, message: Message | None = None, *, user_id: str | None = None, session_id: str | None = None) -> None:
    public_user_id = str(user_id or "").strip()
    session_id_value = str(session_id or "").strip()
    if not public_user_id or not session_id_value:
        data = state.get_data() if hasattr(state, "get_data") else {}
        if asyncio.iscoroutine(data):
            data = await data
        if hasattr(data, "__call__"):
            data = {}
        public_user_id = str((data or {}).get("public_user_id") or "").strip()
        session_id_value = str((data or {}).get("session_id") or "").strip()
    if not public_user_id or not session_id_value:
        return
    SESSION_FSM_CACHE[(public_user_id, session_id_value)] = state
    if message is not None:
        SESSION_MESSAGE_CACHE[(public_user_id, session_id_value)] = message


async def _maybe_trigger_career_finalization(message: Message, state: FSMContext, *, trigger: str = "last_required_answer") -> None:
    data = await state.get_data()
    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message) or "").strip()
    session_id = str(data.get("session_id") or "").strip()
    if not public_user_id or not session_id:
        return
    await _register_session_context(state, message, user_id=public_user_id, session_id=session_id)

    required_questions_completed = bool(data.get("required_questions_completed")) or bool((data.get("profile_snapshot") or {}).get("ready_for_report"))
    clarification_limit_reached = bool(data.get("clarification_limit_reached")) or (
        int(data.get("readiness_clarification_count") or 0) >= 6
    )
    report_already_generated = bool(data.get("report_already_generated"))
    report_generation_in_progress = bool(data.get("report_generation_in_progress"))
    await state.update_data(
        required_questions_completed=required_questions_completed,
        clarification_limit_reached=clarification_limit_reached,
        report_already_generated=report_already_generated,
        report_generation_in_progress=report_generation_in_progress,
    )
    if report_generation_in_progress:
        return
    if required_questions_completed and not report_already_generated:
        await finalize_career_flow(public_user_id, session_id, trigger)
        return
    if clarification_limit_reached and not report_already_generated:
        await finalize_career_flow(public_user_id, session_id, "clarification_limit_reached")


async def finalize_career_flow(user_id: str, session_id: str, trigger: str) -> None:
    state = SESSION_FSM_CACHE.get((user_id, session_id))
    if state is None:
        return
    message = SESSION_MESSAGE_CACHE.get((user_id, session_id))
    data = await state.get_data()
    lang = _user_language(data)
    profile_version = str(data.get("profile_version") or data.get("report_generation_id") or "v1").strip() or "v1"
    idempotency_key = f"career_report:{user_id}:{session_id}:{profile_version}"
    if bool(data.get("report_generation_in_progress")):
        if message is not None:
            await message.answer("Уже собираю заключение, подождите немного.")
        return
    if bool(data.get("short_report_sent")) and not bool(data.get("html_report_generated")):
        if message is not None:
            await message.answer("Краткое заключение уже отправлено. Формирую подробный документ.")
    await state.update_data(
        report_generation_in_progress=True,
        report_already_generated=False,
        report_generation_status="REPORT_GENERATING",
        generation_started_at=datetime.now(timezone.utc).isoformat(),
        last_finalization_trigger=trigger,
        finalization_idempotency_key=idempotency_key,
    )
    if message is not None:
        await message.answer("Собираю заключение", reply_markup=ReplyKeyboardRemove())

    try:
        report = data.get("final_report") if isinstance(data.get("final_report"), dict) else {}
        if not report:
            await _build_and_send_report(message, state, lang) if message else None
            fresh_data = await state.get_data()
            report = fresh_data.get("final_report") if isinstance(fresh_data.get("final_report"), dict) else {}
            # The report builder owns delivery of both the Telegram map and the
            # downloadable document.  Once it has produced a report, do not send
            # a second legacy summary from this wrapper; only close the
            # finalization/idempotency flags.  Keeping REPORT_GENERATION_FAILED
            # allows the user to retry a document whose short map was delivered.
            if report and bool(fresh_data.get("final_report_generated")):
                generation_status = str(fresh_data.get("report_generation_status") or "REPORT_READY")
                await state.update_data(
                    short_report_sent=True,
                    report_already_generated=True,
                    report_generation_in_progress=False,
                    report_generation_status=generation_status,
                )
                return
        if not report:
            payload = _ensure_preliminary_report({}, data)
            decision = payload.get("career_decision") or {}
            route = str(decision.get("recommended_main_path") or "Маршрут на основе подтверждённых функций")
            fallback_text = (
                "Предварительное карьерное заключение\n\n"
                f"Основной маршрут: {route}.\n"
                "Уверенность: низкая — критичные неизвестные явно сохранены.\n\n"
                "Первые шаги:\n"
                f"1. Найти пять вакансий «{route}» на выбранном рынке.\n"
                "2. Упаковать один подтверждённый кейс из прошлого опыта.\n"
                "3. Обсудить требования входа с одним специалистом этой роли.\n\n"
                "Диапазон требует рыночной проверки."
            )
            if message is not None:
                await message.answer(fallback_text)
            await state.update_data(
                final_report=payload, final_report_generated=True, short_report_sent=True,
                report_already_generated=True, report_generation_status="REPORT_READY",
                html_report_generated=False, report_generation_in_progress=False,
                final_report_validated_after_rebuild=True,
            )
            await state.set_state(CareerFlow.REPORT_READY)
            return

        short_summary = build_telegram_summary(report)
        if message is not None:
            await message.answer(short_summary)
        await state.update_data(
            final_report=report,
            short_report_sent=True,
            report_generation_status="SHORT_REPORT_SENT",
            report_already_generated=True,
            final_report_generated=True,
        )

        try:
            user_name = ""
            if message is not None and message.from_user is not None:
                user_name = " ".join(part for part in [message.from_user.first_name, message.from_user.last_name] if part).strip()
            html_path = generate_html_report_file(
                report,
                output_dir=settings.report_output_dir,
                user_name=user_name,
                profile_version=str(data.get("report_generation_id") or profile_version),
            )
            await state.update_data(
                html_report_path=_normalize_report_path(str(html_path)),
                html_report_generated=True,
                report_generation_status="REPORT_READY",
                report_generation_in_progress=False,
                report_already_generated=True,
            )
            await state.set_state(CareerFlow.REPORT_READY)
        except Exception as html_exc:
            print(f"[finalize] html_error={type(html_exc).__name__}: {html_exc}", flush=True)
            if message is not None:
                await message.answer("Краткий вывод готов. Подробный документ не удалось сформировать из-за технической ошибки. Повторить создание документа?")
            await state.update_data(
                html_report_generated=False,
                report_generation_status="SHORT_REPORT_SENT",
                report_generation_in_progress=False,
                report_already_generated=True,
            )
            await state.set_state(CareerFlow.REPORT_READY)
    except Exception as exc:
        print(f"[finalize] failed: {type(exc).__name__}: {exc}", flush=True)
        payload = _ensure_preliminary_report({}, data)
        route = str((payload.get("career_decision") or {}).get("recommended_main_path") or "Маршрут на основе подтверждённых функций")
        fallback_text = (f"Предварительное карьерное заключение\n\nОсновной маршрут: {route}.\n"
                         "Уверенность: низкая. Диапазон требует рыночной проверки.\n\n"
                         "Первые шаги: 1) пять вакансий; 2) один кейс; 3) один разговор со специалистом.")
        if message is not None:
            await message.answer(fallback_text)
        await state.update_data(
            final_report=payload, short_report_sent=True, final_report_generated=True,
            report_already_generated=True, report_generation_status="REPORT_READY",
            report_generation_in_progress=False, html_report_generated=False,
        )
        await state.set_state(CareerFlow.REPORT_READY)


_STORY_RESET_FIELDS: dict[str, object] = {
    # assessment boundary: none of these objects may survive a new case
    "assessment_id": "",
    "profile_version": "",
    "source_messages": [],
    "uploaded_documents": [],
    "canonical_profile": {},
    "profile_snapshot": {},
    "career_assessment": {},
    "route_comparison": {},
    # previous conclusion
    "final_report": {},
    "report_chunks": {},
    "final_report_generated": False,
    "final_report_validated_after_rebuild": False,
    "report_generation_id": "",
    "html_report_path": "",
    "pdf_report_path": "",
    "docx_report_path": "",
    "post_result_stage": "",
    # interview / evidence
    "story_analysis": {},
    "qa_answers": [],
    "qa_index": 0,
    "answers_text": "",
    "interview_context": {},
    "asked_question_signatures": [],
    "evidence_profile": {},
    "conversation_hypotheses": [],
    "preliminary_offer_shown": False,
    "preliminary_map_route1": "",
    "preliminary_map_route2": "",
    "preliminary_route_selected": False,
    "selected_preliminary_route": "",
    "pending_answer_review": {},
    "answer_review_snapshot": {},
    "pending_question_append": {},
    "pending_choice_reason": {},
    "awaiting_extended_diagnostics_choice": False,
    "extended_diagnostics_done": False,
    "mandatory_diagnostics_in_progress": False,
    "mandatory_diagnostics_done": False,
    "promised_question_count": 0,
    # route context
    "route_context": {},
    "route_context_index": 0,
    "route_context_text_mode_for": "",
    "route_context_question_id": "",
    "awaiting_route_context": False,
    "country_config": {},
    "fsm_generation": 0,  # incremented each time a new question batch starts
    # route selection / strategy
    "career_strategy": "",
    "awaiting_route_specific_questions": False,
    "route_specific_gaps": [],
    "route_specific_index": 0,
    "route_specific_answers": [],
    "route_specific_selected_route": "",
    "route_specific_done": False,
    # selected markers / multi-select choices
    "selected_barriers": [],
    "selected_fears": [],
    "selected_psych_markers": [],
    "selected_energy_sources": [],
    "selected_career_priorities": [],
    "selected_psych_state": [],
    "selected_coping": [],
    "selected_social_state": [],
    "selected_integration_state": [],
    "selected_choice_reasons": {},
    # misc interview flags
    "guardrail_retry_done": False,
    "awaiting_story_correction": False,
    "career_planning_paused": False,
    "crisis_detected": False,
    "resume_analysis": {},
    "cv_uploaded": False,
}

_CAREER_STRATEGY_BY_ACTION = {
    CAREER_STRATEGY_FAST_INCOME: ("fast_income", CAREER_STRATEGY_FAST_INCOME),
    CAREER_STRATEGY_UPSKILL: ("upskill_for_profile", CAREER_STRATEGY_UPSKILL),
    CAREER_STRATEGY_LONG: ("long_transition", CAREER_STRATEGY_LONG),
    CAREER_STRATEGY_HELP: ("need_decision", CAREER_STRATEGY_HELP),
}

_ROUTE_CONTEXT_LANGUAGE_CURRENT_OPTIONS = [
    "Английский: A1-A2",
    "Английский: B1",
    "Английский: B2",
    "Английский: C1-C2",
    "Локальный язык: A1-A2",
]

_ROUTE_CONTEXT_LANGUAGE_TARGET_OPTIONS = [
    "Цель: английский B2",
    "Цель: английский C1+",
    "Цель: локальный язык A2",
    "Цель: локальный язык B1",
    "Пока без языковой цели",
]

# ── Country-aware helpers ──────────────────────────────────────────
_COUNTRY_CONFIGS: dict[str, dict[str, str]] = {
    "lt": {"country_code": "LT", "country_name": "Литва", "currency": "EUR", "currency_symbol": "€", "local_language": "Литовский", "market_locale": "lt-LT"},
    "pl": {"country_code": "PL", "country_name": "Польша", "currency": "PLN", "currency_symbol": "zł", "local_language": "Польский", "market_locale": "pl-PL"},
    "de": {"country_code": "DE", "country_name": "Германия", "currency": "EUR", "currency_symbol": "€", "local_language": "Немецкий", "market_locale": "de-DE"},
    "cz": {"country_code": "CZ", "country_name": "Чехия", "currency": "CZK", "currency_symbol": "Kč", "local_language": "Чешский", "market_locale": "cs-CZ"},
    "ee": {"country_code": "EE", "country_name": "Эстония", "currency": "EUR", "currency_symbol": "€", "local_language": "Эстонский", "market_locale": "et-EE"},
    "lv": {"country_code": "LV", "country_name": "Латвия", "currency": "EUR", "currency_symbol": "€", "local_language": "Латышский", "market_locale": "lv-LV"},
    "nl": {"country_code": "NL", "country_name": "Нидерланды", "currency": "EUR", "currency_symbol": "€", "local_language": "Нидерландский", "market_locale": "nl-NL"},
    "fi": {"country_code": "FI", "country_name": "Финляндия", "currency": "EUR", "currency_symbol": "€", "local_language": "Финский", "market_locale": "fi-FI"},
    "gb": {"country_code": "GB", "country_name": "Великобритания", "currency": "GBP", "currency_symbol": "£", "local_language": "Английский", "market_locale": "en-GB"},
    "us": {"country_code": "US", "country_name": "США", "currency": "USD", "currency_symbol": "$", "local_language": "Английский", "market_locale": "en-US"},
    "remote": {"country_code": "REMOTE", "country_name": "Удалённо", "currency": "USD", "currency_symbol": "$", "local_language": "Английский", "market_locale": "remote"},
}


def _resolve_country_config(country_text: str) -> dict[str, str]:
    """Map user's free-text country answer to a structured country config."""
    text = (country_text or "").lower().strip().replace("ё", "е")
    if any(t in text for t in ["литв", "вильн", "lithuani", "lt-"]):
        return _COUNTRY_CONFIGS["lt"]
    if any(t in text for t in ["польш", "варшав", "краков", "poland", "polish", "pl-"]):
        return _COUNTRY_CONFIGS["pl"]
    if any(t in text for t in ["герман", "берлин", "мюнхен", "франкфурт", "german", "deutsch", "de-"]):
        return _COUNTRY_CONFIGS["de"]
    if any(t in text for t in ["чехи", "праг", "czech", "cz-"]):
        return _COUNTRY_CONFIGS["cz"]
    if any(t in text for t in ["эстон", "таллин", "estonia", "ee-"]):
        return _COUNTRY_CONFIGS["ee"]
    if any(t in text for t in ["латв", "рига", "latvia", "lv-"]):
        return _COUNTRY_CONFIGS["lv"]
    if any(t in text for t in ["нидерланд", "голланд", "амстердам", "netherland", "nl-"]):
        return _COUNTRY_CONFIGS["nl"]
    if any(t in text for t in ["финлянд", "хельсинк", "finland", "suomi", "fi-"]):
        return _COUNTRY_CONFIGS["fi"]
    if any(t in text for t in ["великобритан", "лондон", "britain", "england", "uk "]):
        return _COUNTRY_CONFIGS["gb"]
    if any(t in text for t in ["сша", "нью-йорк", "usa", "united states", "america"]):
        return _COUNTRY_CONFIGS["us"]
    if any(t in text for t in ["удал", "удален", "remote", "online", "global", "онлайн"]):
        return _COUNTRY_CONFIGS["remote"]
    return {"country_code": "UNKNOWN", "country_name": country_text.strip(), "currency": "EUR", "currency_symbol": "€", "local_language": "-", "market_locale": "unknown"}


def _income_options_for_currency(currency: str) -> tuple[list[str], list[str], list[str]]:
    """Build one-currency controls; amounts are market configuration, not labels."""
    currency = str(currency or "").upper()
    scales = {
        "EUR": ((1200, 1500, 1800, 2200), (1500, 1800, 2200, 3000), (0, 200, 500, 1000)),
        "PLN": ((3000, 4500, 6000, 8000), (4500, 6000, 8000, 11000), (0, 500, 2000, 4000)),
        "GBP": ((1500, 2500, 3500, 4500), (2500, 3500, 5000, 6500), (0, 200, 800, 1500)),
        "USD": ((2000, 3500, 5000, 7000), (3500, 5000, 8000, 11000), (0, 300, 1000, 2000)),
    }
    if currency not in scales:
        raise ValueError(f"unsupported display currency: {currency or 'Unknown'}")
    symbol = "€" if currency == "EUR" else currency
    unit = f"{symbol}" if currency != "EUR" else "€"
    def income(prefix: str, points: tuple[int, int, int, int]) -> list[str]:
        a, b, c, d = points
        suffix = " EUR" if currency == "EUR" else ""
        return [f"{prefix}до {unit}{a}{suffix} net/мес", f"{prefix}{unit}{a}–{b}{suffix} net/мес",
                f"{prefix}{unit}{b}–{c}{suffix} net/мес", f"{prefix}{unit}{c}–{d}{suffix} net/мес",
                f"{prefix}{unit}{d}+{suffix} net/мес", f"Ввести свою сумму ({currency})", f"Не знаю ({currency})"]
    minimum, desired, budget = scales[currency]
    budget_suffix = " EUR" if currency == "EUR" else ""
    return income("Минимум: ", minimum), income("Цель: ", desired), [
        f"Бюджет на обучение: {symbol}{budget[0]}{budget_suffix}", f"Бюджет на обучение: до {symbol}{budget[2]}{budget_suffix}",
        f"Бюджет на обучение: {symbol}{budget[1]}–{budget[2]}{budget_suffix}", f"Бюджет на обучение: {symbol}{budget[3]}+{budget_suffix}",
    ]


def _validate_currency_keyboard(options: list[str], display_currency: str) -> None:
    """Fail closed before Telegram can send controls from another market."""
    currencies = set(re.findall(r"\b(?:EUR|PLN|GBP|USD|CZK)\b", " ".join(options), re.I))
    if "€" in " ".join(options):
        currencies.add("EUR")
    if currencies and {item.upper() for item in currencies} != {display_currency.upper()}:
        raise ValueError("currency_ui_mismatch")


def _language_options_for_country(country_code: str) -> tuple[list[str], list[str]]:
    """Returns (current_level_options, target_options) for the given country."""
    if country_code == "PL":
        return (
            ["Польский: нет / ниже A1", "Польский: A1-A2", "Польский: B1", "Польский: B2+", "Английский: A2 и выше"],
            ["Цель: польский A2", "Цель: польский B1", "Цель: польский B2+", "Цель: английский B1+", "Пока без языковой цели"],
        )
    if country_code == "DE":
        return (
            ["Немецкий: нет / ниже A1", "Немецкий: A1-A2", "Немецкий: B1", "Немецкий: B2+", "Английский: B1 и выше"],
            ["Цель: немецкий A2", "Цель: немецкий B1", "Цель: немецкий B2+", "Цель: английский B1+", "Пока без языковой цели"],
        )
    if country_code in ("GB", "US", "REMOTE"):
        return (
            ["Английский: A1-A2", "Английский: B1", "Английский: B2", "Английский: C1-C2"],
            ["Цель: английский B2", "Цель: английский C1+", "Пока без языковой цели"],
        )
    if not country_code or country_code == "UNKNOWN":
        local_lang = "Местный язык"
        return (
            [f"{local_lang}: нет / ниже A1", f"{local_lang}: A1-A2", f"{local_lang}: B1+", "Английский: B1 и выше", "Пока учу английский"],
            [f"Цель: {local_lang.lower()} A2", f"Цель: {local_lang.lower()} B1", "Цель: английский B1+", "Пока без языковой цели"],
        )
    lang_map = {"LT": "Литовский", "LV": "Латышский", "EE": "Эстонский", "NL": "Нидерландский", "FI": "Финский", "CZ": "Чешский"}
    local_lang = lang_map.get(country_code, "Местный язык")
    return (
        [f"{local_lang}: нет / ниже A1", f"{local_lang}: A1-A2", f"{local_lang}: B1+", "Английский: B1 и выше", "Пока учу английский"],
        [f"Цель: {local_lang.lower()} A2", f"Цель: {local_lang.lower()} B1", "Цель: английский B1+", "Пока без языковой цели"],
    )

_ROUTE_CONTEXT_INCOME_URGENCY_OPTIONS = [
    "Доход нужен срочно: в течение 2-4 недель",
    "Доход нужен в течение 1-2 месяцев",
    "Могу ждать 3+ месяца",
]

_ROUTE_CONTEXT_MIN_INCOME_OPTIONS = [
    "Минимум: до 1000 EUR/мес",
    "Минимум: 1000-1500 EUR/мес",
    "Минимум: 1500-2500 EUR/мес",
    "Минимум: 2500+ EUR/мес",
]

_ROUTE_CONTEXT_DESIRED_INCOME_OPTIONS = [
    "Цель: до 1500 EUR/мес",
    "Цель: 1500-2500 EUR/мес",
    "Цель: 2500-4000 EUR/мес",
    "Цель: 4000+ EUR/мес",
]

_ROUTE_CONTEXT_TRAINING_BUDGET_OPTIONS = [
    "Бюджет на обучение: 0 EUR",
    "Бюджет на обучение: до 200 EUR",
    "Бюджет на обучение: 200-800 EUR",
    "Бюджет на обучение: 800+ EUR",
]

# Keep every consumer (including older interview templates) on the same
# generated currency labels instead of maintaining a second hardcoded set.
(_ROUTE_CONTEXT_MIN_INCOME_OPTIONS,
 _ROUTE_CONTEXT_DESIRED_INCOME_OPTIONS,
 _ROUTE_CONTEXT_TRAINING_BUDGET_OPTIONS) = _income_options_for_currency("EUR")

_ROUTE_CONTEXT_STUDY_TIME_OPTIONS = [
    "Учёба: 0-2 часа в неделю",
    "Учёба: 3-5 часов в неделю",
    "Учёба: 6-10 часов в неделю",
    "Учёба: 10+ часов в неделю",
]

_ROUTE_CONTEXT_GOAL_OPTIONS = [
    "Остаться в текущей профессии",
    "Перейти в близкую сферу",
    "Полностью сменить сферу",
    "Пока не знаю",
]

_ROUTE_CONTEXT_WORK_FORMAT_OPTIONS = [
    "📄 Больше с документами",
    "👥 Больше с людьми",
    "⚖️ 50/50",
    "🚫 Лучше без активных продаж",
    "✅ Могу общаться, если есть понятные правила",
]
WORK_FORMAT_OPTIONS = _ROUTE_CONTEXT_WORK_FORMAT_OPTIONS

_ROUTE_CONTEXT_HEALTH_LIMIT_OPTIONS = [
    "Ограничений нет",
    "Есть ограничения по графику",
    "Есть ограничения по здоровью",
    "Есть ограничения по детям/уходу",
    "Есть несколько ограничений одновременно",
]

_ROUTE_CONTEXT_DOCS_OPTIONS = [
    "Документы в порядке, право на работу есть",
    "Право на работу есть, но документы частично",
    "Право на работу нужно уточнить",
    "Есть риски по легализации/документам",
]

_ROUTE_CONTEXT_DIPLOMA_OPTIONS = [
    "Диплом/квалификация подтверждены",
    "Диплом есть, но не подтверждён(а)",
    "Диплома нет / не по профилю",
    "Не знаю, что с признанием",
]

_ROUTE_CONTEXT_PORTFOLIO_OPTIONS = [
    "Есть портфолио и рекомендации",
    "Есть только портфолио",
    "Есть только рекомендации",
    "Пока нет портфолио/рекомендаций",
]

_INTERVIEW_INCOME_INTERVAL_OPTIONS, _, _ = _income_options_for_currency("EUR")

_INTERVIEW_INCOME_SPEED_OPTIONS = [
    "⚡ 2-4 недели",
    "📆 1-2 месяца",
    "📚 3-6 месяцев",
    "🧭 Могу дольше при сильном маршруте",
]

_INTERVIEW_TIME_INTERVAL_OPTIONS = [
    "0-2 часа в неделю",
    "3-5 часов в неделю",
    "6-10 часов в неделю",
    "10+ часов в неделю",
]

_ROUTE_CONTEXT_FIELDS = [
    {
        "id": "country",
        "prompt": "1/15. В какой стране вы сейчас ищете работу?",
        "keys": ["country"],
    },
    {
        "id": "city",
        "prompt": "2/15. В каком городе (или регионе) вы хотите работать?",
        "keys": ["city"],
    },
    {
        "id": "current_language_level",
        "prompt": "3/15. Какие языки вы знаете сейчас и на каком уровне? Можно выбрать несколько вариантов.",
        "keys": ["current_language_level"],
        "options": _ROUTE_CONTEXT_LANGUAGE_CURRENT_OPTIONS,
    },
    {
        "id": "target_language",
        "prompt": "4/15. Какие языки и уровни для вас цель на ближайшие месяцы? Можно выбрать несколько вариантов.",
        "keys": ["target_language"],
        "options": _ROUTE_CONTEXT_LANGUAGE_TARGET_OPTIONS,
    },
    {
        "id": "income_urgency",
        "prompt": "5/15. Насколько срочно нужен стабильный доход?",
        "keys": ["income_urgency"],
        "options": _ROUTE_CONTEXT_INCOME_URGENCY_OPTIONS,
    },
    {
        "id": "minimum_monthly_income",
        "prompt": "6/15. Какой минимальный месячный доход нужен, чтобы закрыть базовые расходы?",
        "keys": ["minimum_monthly_income"],
        "options": _ROUTE_CONTEXT_MIN_INCOME_OPTIONS,
    },
    {
        "id": "desired_monthly_income",
        "prompt": "7/15. Какой доход вы считаете желаемым на этом этапе?",
        "keys": ["desired_monthly_income"],
        "options": _ROUTE_CONTEXT_DESIRED_INCOME_OPTIONS,
    },
    {
        "id": "training_budget",
        "prompt": "8/15. Выберите бюджет на обучение в ближайшие 1-3 месяца.",
        "keys": ["training_budget"],
        "options": _ROUTE_CONTEXT_TRAINING_BUDGET_OPTIONS,
    },
    {
        "id": "available_time_for_study",
        "prompt": "9/15. Сколько времени в неделю реально готовы учиться?",
        "keys": ["available_time_for_study"],
        "options": _ROUTE_CONTEXT_STUDY_TIME_OPTIONS,
    },
    {
        "id": "goal",
        "prompt": "10/15. Какая карьерная цель сейчас ближе?",
        "keys": ["career_goal_type"],
        "options": _ROUTE_CONTEXT_GOAL_OPTIONS,
    },
    {
        "id": "work",
        "prompt": "11/15. Какой формат работы вам подходит?",
        "keys": ["work_preferences"],
        "options": _ROUTE_CONTEXT_WORK_FORMAT_OPTIONS,
    },
    {
        "id": "health_or_schedule_limits",
        "prompt": "12/15. Есть ли ограничения по здоровью/графику/детям? Можно выбрать несколько вариантов.",
        "keys": ["health_or_schedule_limits"],
        "options": _ROUTE_CONTEXT_HEALTH_LIMIT_OPTIONS,
    },
    {
        "id": "documents",
        "prompt": "13/15. Какой у вас статус документов и права на работу?",
        "keys": ["documents_and_work_rights"],
        "options": _ROUTE_CONTEXT_DOCS_OPTIONS,
    },
    {
        "id": "diploma_status",
        "prompt": "14/15. Какой статус диплома/признания квалификации?",
        "keys": ["diploma_status"],
        "options": _ROUTE_CONTEXT_DIPLOMA_OPTIONS,
    },
    {
        "id": "proof",
        "prompt": "15/15. Есть ли портфолио, рекомендации или реальные примеры работ?",
        "keys": ["portfolio_or_references"],
        "options": _ROUTE_CONTEXT_PORTFOLIO_OPTIONS,
    },
]


def _resume_debug_log(message: Message, step: str, **fields: object) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    suffix = f" {details}" if details else ""
    print(f"[resume-flow] user_id={user_id} step={step}{suffix}", flush=True)


def _safe_default(value: object, default: str = "данных недостаточно") -> str:
    text = str(value or "").strip()
    return text if text else default


CRISIS_RISK_MARKERS = [
    "суицид",
    "суицидальные мысли",
    "убить себя",
    "покончить с собой",
    "самоповреждение",
    "нет смысла жить",
    "хочу умереть",
    "не хочу жить",
    "удариться",
    "покончить",
    "не могу есть",
    "не могу нормально есть",
    "не могу спать",
    "не сплю",
    "не могу встать",
    "не могу вставать",
    "не могу подняться с кровати",
    "не могу работать",
    "не могу выйти на работу",
    "не могу функционировать",
    "не встаю",
    "лежу в постели",
    "ничего не вижу",
    "полная безнадежность",
    "совсем сломался",
    "нет будущего",
    "не видно выхода",
]

_RESTART_INTENT_MARKERS = [
    "пройти заново",
    "начать заново",
    "начать сначала",
    "с начала",
    "пройти сначала",
    "хочу пройти сначала",
    "хочу начать сначала",
    "restart",
    "start over",
    "new start",
    "новый старт",
]

_PRELIMINARY_RESULT_MARKERS = [
    "предварительный результат",
    "показать результат",
    "перейти к результату",
    "достаточно",
    "хватит вопросов",
    "остановить интервью",
    "show result",
    "показать карту",
]


def _detect_crisis_risk(text: str) -> bool:
    """Check for crisis/safety signals in user input."""
    blob = str(text or "").lower().replace("ё", "е")
    return any(marker in blob for marker in CRISIS_RISK_MARKERS)


def _is_restart_intent(text: str) -> bool:
    low = str(text or "").strip().lower().replace("ё", "е")
    if not low:
        return False
    if low in {"/start", "restart", "start over"}:
        return True
    restart_labels = {item.lower() for item in ALL_RESTART}
    if low in restart_labels:
        return True
    return any(
        low == marker
        or low.startswith(f"{marker} ")
        or low.endswith(f" {marker}")
        for marker in _RESTART_INTENT_MARKERS
    )


def _is_preliminary_result_intent(text: str) -> bool:
    low = str(text or "").strip().lower().replace("ё", "е")
    if not low:
        return False
    return any(marker in low for marker in _PRELIMINARY_RESULT_MARKERS)


async def _maybe_switch_to_crisis_support(
    message: Message,
    state: FSMContext,
    lang: str,
    text: str,
    *,
    source: str,
) -> bool:
    if not _detect_crisis_risk(text):
        return False
    await state.update_data(career_planning_paused=True, crisis_detected=True, crisis_detected_source=source)
    await _handle_crisis_detected(message, state, lang)
    return True


def _route_field_value(route: dict[str, object], field: str) -> str:
    if not isinstance(route, dict):
        return ""

    if field == "target_roles":
        payload = route.get("target_roles_6_months") or route.get("realistic_entry_roles") or route.get("new_career_options") or []
        if isinstance(payload, list):
            return "|".join(str(item).strip().lower() for item in payload if str(item).strip())
        return str(payload or "").strip().lower()

    if field == "timeline":
        timeline = route.get("time_to_entry") or route.get("training_plan_12_weeks") or route.get("decision_checkpoint") or route.get("goal_30_days")
        if isinstance(timeline, dict):
            return "|".join(f"{k}:{timeline[k]}" for k in sorted(timeline.keys()))
        return str(timeline or "").strip().lower()

    if field == "skills":
        skills = route.get("required_tools_and_skills") or route.get("gap_analysis") or []
        if isinstance(skills, list):
            return "|".join(str(item).strip().lower() for item in skills if str(item).strip())
        return str(skills or "").strip().lower()

    if field == "education":
        education = route.get("recommended_certificates") or route.get("diploma_or_license_check") or route.get("training_cost") or ""
        if isinstance(education, list):
            return "|".join(str(item).strip().lower() for item in education if str(item).strip())
        if isinstance(education, dict):
            return "|".join(f"{k}:{education[k]}" for k in sorted(education.keys()))
        return str(education or "").strip().lower()

    if field == "income_path":
        income = route.get("income_at_start") or route.get("income_growth_potential") or route.get("goal_30_days") or ""
        if isinstance(income, dict):
            return "|".join(f"{k}:{income[k]}" for k in sorted(income.keys()))
        return str(income or "").strip().lower()

    if field == "today_action":
        today = route.get("today_action")
        if isinstance(today, dict):
            return str(today.get("action") or "").strip().lower()
        return str(today or "").strip().lower()

    return ""


def _validate_route_divergence(route_a: dict[str, object], route_b: dict[str, object]) -> tuple[bool, int, dict[str, bool]]:
    compare = {
        "target_roles": _route_field_value(route_a, "target_roles") != _route_field_value(route_b, "target_roles"),
        "timeline": _route_field_value(route_a, "timeline") != _route_field_value(route_b, "timeline"),
        "skills": _route_field_value(route_a, "skills") != _route_field_value(route_b, "skills"),
        "education": _route_field_value(route_a, "education") != _route_field_value(route_b, "education"),
        "income_path": _route_field_value(route_a, "income_path") != _route_field_value(route_b, "income_path"),
        "today_action": _route_field_value(route_a, "today_action") != _route_field_value(route_b, "today_action"),
    }
    divergence_score = sum(1 for is_different in compare.values() if is_different)
    return divergence_score >= 4, divergence_score, compare


def _normalize_choice_text(value: object) -> str:
    text = str(value or "")
    for replacement in ("\u00a0", "\u200b", "\u200c", "\u200d", "\u202f"):
        text = text.replace(replacement, " ")
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _match_choice_action(action: str, allowed_actions: set[str]) -> str | None:
    if not action:
        return None
    normalized_input = _normalize_choice_text(action)
    if normalized_input in {_normalize_choice_text(item) for item in allowed_actions}:
        for item in allowed_actions:
            if _normalize_choice_text(item) == normalized_input:
                return item
    return None


def _career_strategy_from_action(action: str) -> tuple[str, str]:
    return _CAREER_STRATEGY_BY_ACTION.get(action, ("need_decision", CAREER_STRATEGY_HELP))


def _career_strategy_action_from_code(strategy_code: str) -> str:
    for action, mapped in _CAREER_STRATEGY_BY_ACTION.items():
        if mapped[0] == strategy_code:
            return action
    return CAREER_STRATEGY_UPSKILL


def _need_decision_comparison_text(bundle: dict[str, object]) -> str:
    rows = bundle.get("comparison_table") if isinstance(bundle.get("comparison_table"), list) else []
    if not rows:
        return ""
    lines = ["Мини-сравнение путей:"]
    for row in rows[:3]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "- {path}: плюс — {gain}; риск/цена — {tradeoff}; первый результат — {first_result}.".format(
                path=_safe_default(row.get("path"), "Маршрут"),
                gain=_safe_default(row.get("gain"), "данных недостаточно"),
                tradeoff=_safe_default(row.get("tradeoff"), "данных недостаточно"),
                first_result=_safe_default(row.get("first_result"), "данных недостаточно"),
            )
        )
    return "\n".join(lines)


def _resolve_country_config_for_context(route_context: dict[str, object] | None) -> dict[str, str]:
    """Resolve a stable country config from the current route context, without relying on stale globals."""
    if not isinstance(route_context, dict):
        return {}

    explicit_cfg = route_context.get("country_config")
    if isinstance(explicit_cfg, dict):
        cfg = {str(k): str(v).strip() for k, v in explicit_cfg.items() if str(k).strip()}
        if cfg:
            return cfg

    explicit_code = str(route_context.get("country_code") or "").strip()
    if explicit_code:
        by_code = _COUNTRY_CONFIGS.get(str(explicit_code).lower())
        if isinstance(by_code, dict):
            return {str(k): str(v).strip() for k, v in by_code.items() if str(k).strip()}

    for candidate_key in ("country", "city"):
        candidate = str(route_context.get(candidate_key) or "").strip()
        if candidate:
            resolved = _resolve_country_config(candidate)
            if str(resolved.get("country_code") or "").strip():
                return {str(k): str(v).strip() for k, v in resolved.items() if str(k).strip()}
    return {}


def _normalize_route_context(route_context: dict[str, object] | None) -> dict[str, str]:
    """Normalize legacy/alias keys so the final readiness gate matches the canonical field names."""
    if not isinstance(route_context, dict):
        return {}

    normalized: dict[str, str] = {}
    alias_map = {
        "goal": "career_goal_type",
        "work": "work_preferences",
        "documents": "documents_and_work_rights",
        "proof": "portfolio_or_references",
    }

    for key, value in route_context.items():
        if not str(key).strip():
            continue
        canonical_key = alias_map.get(str(key), str(key))
        if value is None:
            normalized[canonical_key] = ""
        else:
            normalized[canonical_key] = str(value).strip()

    resolved_country_config = _resolve_country_config_for_context(route_context)
    if resolved_country_config:
        normalized["country_config"] = resolved_country_config
    elif str(normalized.get("country") or "").strip():
        country_config = _resolve_country_config(str(normalized["country"]))
        normalized["country_config"] = country_config

    return normalized


def _clean_profile_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, list):
        cleaned = []
        for item in value:
            text = str(item).strip()
            if not text or text in {"-", "—", "None", "null"}:
                continue
            cleaned.append(text)
        return cleaned
    if isinstance(value, tuple):
        return _clean_profile_value(list(value))
    text = str(value).strip()
    if not text or text in {"-", "—", "None", "null"}:
        return ""
    return text


def _build_profile_snapshot(data: dict[str, object]) -> dict[str, object]:
    """Create the immutable report view from the assessment's canonical profile."""
    assessment_id = str(data.get("assessment_id") or data.get("report_generation_id") or "pending-assessment")
    canonical_profile = build_canonical_profile(data, assessment_id=assessment_id)
    route_context = _normalize_route_context(data.get("route_context") if isinstance(data.get("route_context"), dict) else {})
    country_config = _resolve_country_config_for_context(route_context)
    if not country_config and isinstance(route_context.get("country_config"), dict):
        country_config = route_context["country_config"]
    if not country_config and str(route_context.get("country") or data.get("country") or "").strip():
        country_config = _resolve_country_config(str(route_context.get("country") or data.get("country") or ""))

    evidence_profile = data.get("evidence_profile") if isinstance(data.get("evidence_profile"), dict) else {}
    residence_evidence = evidence_profile.get("residence_country") if isinstance(evidence_profile.get("residence_country"), dict) else {}
    residence_city_evidence = evidence_profile.get("residence_city") if isinstance(evidence_profile.get("residence_city"), dict) else {}
    target_evidence = evidence_profile.get("target_countries") if isinstance(evidence_profile.get("target_countries"), list) else []
    residence_country = str(residence_evidence.get("statement") or route_context.get("residence_country") or data.get("residence_country") or "").strip()
    target_countries = [str(item.get("statement") or "").strip() for item in target_evidence if isinstance(item, dict) and str(item.get("statement") or "").strip()]
    if not target_countries and str(route_context.get("country") or "").strip():
        target_countries = [str(route_context.get("country") or "").strip()]
    snapshot: dict[str, object] = {
        "country_code": str((country_config or {}).get("country_code") or "UNKNOWN").upper(),
        "country_name": str((country_config or {}).get("country_name") or str(route_context.get("country") or "").strip() or "").strip(),
        "residence_country": residence_country,
        "target_countries": target_countries,
        "city": str(residence_city_evidence.get("statement") or route_context.get("city") or "").strip(),
        "currency": str((country_config or {}).get("currency") or "EUR").upper(),
        "local_language": str((country_config or {}).get("local_language") or "-").strip(),
        "market_locale": str((country_config or {}).get("market_locale") or "unknown").strip(),
        "market_data_date": None,
        "market_data_sources": [],
        "market_data_confidence": "low",
        "answers_text": str(data.get("answers_text") or "").strip(),
        "story_text": str(data.get("story_text") or "").strip(),
        "story_analysis": dict(data.get("story_analysis") or {}) if isinstance(data.get("story_analysis"), dict) else {},
        "resume_analysis": dict(data.get("resume_analysis") or {}) if isinstance(data.get("resume_analysis"), dict) else {},
        "route_context": {str(key): str(value) for key, value in route_context.items() if str(key).strip() and key != "country_config"},
        "ready_for_report": False,
        "canonical_profile": {
            **canonical_profile.model_dump(mode="json"),
            "groups": {
                name: [fact.model_dump(mode="json") for fact in facts]
                for name, facts in canonical_profile.grouped().items()
            },
        },
        "normalized_profile": canonical_profile.normalized_profile.model_dump(mode="json"),
        "consistency_issues": list(canonical_profile.consistency_issues),
    }

    # Promote normalized scalars/lists for existing assessment consumers. Empty
    # extraction results never overwrite a stronger structured answer.
    for key, value in canonical_profile.normalized_profile.model_dump(mode="json").items():
        if value not in (None, "", [], {}):
            snapshot[key] = value

    normalized_answers = {
        "income_urgency": _clean_profile_value(route_context.get("income_urgency") or data.get("income_urgency")),
        "minimum_income": _clean_profile_value(route_context.get("minimum_monthly_income") or data.get("minimum_income") or route_context.get("minimum_income")),
        "target_income": _clean_profile_value(route_context.get("desired_monthly_income") or data.get("target_income") or route_context.get("target_income")),
        "currency": str(
            canonical_profile.normalized_profile.currency
            or (country_config or {}).get("currency")
            or data.get("currency")
            or "EUR"
        ).upper(),
        "learning_budget": _clean_profile_value(route_context.get("training_budget") or data.get("learning_budget")),
        "learning_hours_week": _clean_profile_value(route_context.get("available_time_for_study") or data.get("learning_hours_week")),
        "career_goal": _clean_profile_value(route_context.get("career_goal_type") or data.get("career_goal")),
        "work_preferences": _clean_profile_value(route_context.get("work_preferences") or data.get("work_preferences") or []),
        "care_constraints": bool(str(route_context.get("health_or_schedule_limits") or data.get("care_constraints") or "").strip() and str(route_context.get("health_or_schedule_limits") or data.get("care_constraints") or "").strip() not in {"-", "—", "Нет", "нет"}),
        "work_authorization_status": _clean_profile_value(route_context.get("documents_and_work_rights") or data.get("work_authorization_status")),
        "qualification_status": _clean_profile_value(route_context.get("diploma_status") or data.get("qualification_status")),
        "portfolio_status": _clean_profile_value(route_context.get("portfolio_or_references") or data.get("portfolio_status")),
        "psychological_barriers": _clean_profile_value(data.get("selected_psych_markers") or route_context.get("psychological_barriers") or []),
        "behavioral_barriers": _clean_profile_value(data.get("selected_barriers") or route_context.get("behavioral_barriers") or []),
        "external_barriers": _clean_profile_value(data.get("selected_fears") or route_context.get("external_barriers") or []),
    }

    for key, value in normalized_answers.items():
        if value == "" or value == [] or value == () or value is None:
            continue
        snapshot[key] = value

    market: dict[str, object] = {}
    for fact in canonical_profile.facts_of_type("market_context"):
        if isinstance(fact.normalized_value, dict):
            market.update({key: value for key, value in fact.normalized_value.items() if value not in (None, "")})
    if market:
        snapshot["city"] = market.get("city") or snapshot["city"]
        snapshot["country_name"] = market.get("country") or snapshot["country_name"]
        snapshot["country_code"] = market.get("country_code") or snapshot["country_code"]
        if not snapshot["residence_country"]:
            snapshot["residence_country"] = snapshot["country_name"]
        if not snapshot["target_countries"] and snapshot["country_name"]:
            snapshot["target_countries"] = [snapshot["country_name"]]
    authorization = canonical_profile.latest_value("work_authorization")
    if authorization not in (None, ""):
        snapshot["work_authorization_status"] = authorization
    languages = [fact.normalized_value for fact in canonical_profile.facts_of_type("language")]
    if languages:
        snapshot["languages"] = languages
    incomes = [fact.normalized_value for fact in canonical_profile.facts_of_type("income_requirement")]
    for income in incomes:
        if not isinstance(income, dict):
            continue
        kind = income.get("kind")
        value = income.get("display") or income.get("amount")
        if kind == "minimum" and value not in (None, ""):
            snapshot["minimum_income"] = value
        elif kind == "target" and value not in (None, ""):
            snapshot["target_income"] = value
        elif kind == "urgency" and value not in (None, ""):
            snapshot["income_urgency"] = value
    snapshot["ready_for_report"] = _snapshot_is_ready_for_report(snapshot)
    return snapshot


def _snapshot_is_ready_for_report(snapshot: dict[str, object]) -> bool:
    if not isinstance(snapshot, dict):
        return False
    route_context = snapshot.get("route_context") if isinstance(snapshot.get("route_context"), dict) else {}
    if not route_context:
        return False
    if not str(snapshot.get("country_code") or "").strip() or str(snapshot.get("country_code") or "").upper() == "UNKNOWN":
        return False
    required_fields = (
        "country",
        "city",
        "current_language_level",
        "target_language",
        "income_urgency",
        "minimum_monthly_income",
        "desired_monthly_income",
        "training_budget",
        "available_time_for_study",
        "career_goal_type",
        "work_preferences",
        "health_or_schedule_limits",
        "documents_and_work_rights",
        "diploma_status",
        "portfolio_or_references",
    )
    for field in required_fields:
        if not str(route_context.get(field) or "").strip():
            return False
    return True


def _route_context_missing(data: dict[str, object]) -> list[str]:
    missing: list[str] = []
    route_context = _normalize_route_context(data.get("route_context") if isinstance(data.get("route_context"), dict) else {})
    for field in (
        "country",
        "city",
        "current_language_level",
        "target_language",
        "income_urgency",
        "minimum_monthly_income",
        "desired_monthly_income",
        "training_budget",
        "available_time_for_study",
        "career_goal_type",
        "work_preferences",
        "health_or_schedule_limits",
        "documents_and_work_rights",
        "diploma_status",
        "portfolio_or_references",
    ):
        if not str(route_context.get(field) or data.get(field) or "").strip():
            missing.append(field)
    return missing


_ROUTE_CONTEXT_FIELD_LABELS: dict[str, str] = {
    "country": "страна",
    "city": "город",
    "current_language_level": "текущий уровень языка",
    "target_language": "целевой язык",
    "income_urgency": "срочность дохода",
    "minimum_monthly_income": "минимальный доход",
    "desired_monthly_income": "желаемый доход",
    "training_budget": "бюджет обучения",
    "available_time_for_study": "время на обучение",
    "career_goal_type": "карьерная цель",
    "work_preferences": "предпочтения по работе",
    "health_or_schedule_limits": "ограничения по нагрузке или графику",
    "documents_and_work_rights": "документы и право на работу",
    "diploma_status": "статус диплома",
    "portfolio_or_references": "портфолио или рекомендации",
}


def _route_context_question(index: int, route_context: dict | None = None) -> dict[str, object]:
    if index < 0 or index >= len(_ROUTE_CONTEXT_FIELDS):
        return {}
    q = dict(_ROUTE_CONTEXT_FIELDS[index])
    if not route_context:
        if q.get("id") == "current_language_level":
            q["options"], _ = _language_options_for_country("PL")
        elif q.get("id") == "target_language":
            _, q["options"] = _language_options_for_country("PL")
        elif q.get("id") == "minimum_monthly_income":
            q["options"], _, _ = _income_options_for_currency("EUR")
        elif q.get("id") == "desired_monthly_income":
            _, q["options"], _ = _income_options_for_currency("EUR")
        elif q.get("id") == "training_budget":
            _, _, q["options"] = _income_options_for_currency("EUR")
        return q
    country_config = _resolve_country_config_for_context(route_context)
    if not country_config and isinstance(route_context.get("country_config"), dict):
        country_config = route_context["country_config"]
    country_code = str((country_config or {}).get("country_code") or "").upper()
    currency = str((country_config or {}).get("currency") or "EUR")
    q_id = str(q.get("id") or "")
    if q_id == "current_language_level":
        q["options"], _ = _language_options_for_country(country_code)
    elif q_id == "target_language":
        _, q["options"] = _language_options_for_country(country_code)
    elif q_id == "minimum_monthly_income":
        q["options"], _, _ = _income_options_for_currency(currency)
    elif q_id == "desired_monthly_income":
        _, q["options"], _ = _income_options_for_currency(currency)
    elif q_id == "training_budget":
        _, _, q["options"] = _income_options_for_currency(currency)
    if q_id in {"minimum_monthly_income", "desired_monthly_income", "training_budget"}:
        _validate_currency_keyboard(list(q.get("options") or []), currency)
    return q


def _route_context_accepts_multiple_values(question_id: str) -> bool:
    return question_id in {"current_language_level", "target_language", "health_or_schedule_limits"}


def _route_context_answer_is_valid(raw: str, options: list[str], question_id: str) -> bool:
    if not raw or not options:
        return False
    normalized_raw = raw.strip()
    if not normalized_raw:
        return False
    if normalized_raw in {str(opt).strip() for opt in options}:
        return True

    if not _route_context_accepts_multiple_values(question_id):
        return False

    parts = [part.strip() for part in re.split(r"[;,]", normalized_raw) if part.strip()]
    if not parts:
        return False
    option_lookup = {str(opt).strip().lower(): str(opt).strip() for opt in options}
    for part in parts:
        if part.lower() not in option_lookup and not any(part.lower() in str(opt).strip().lower() for opt in options):
            return False
    return True


def _route_context_options(question: dict[str, object]) -> list[str]:
    options = question.get("options") if isinstance(question, dict) else []
    if not isinstance(options, list):
        return []
    return [str(item).strip() for item in options if str(item).strip()]


def _is_route_context_stale_input(raw: str) -> bool:
    """Reject old UI texts from previous screens that must never be treated as route answers."""
    if not raw:
        return False
    normalized = raw.strip()
    if not normalized:
        return False
    low = normalized.lower()
    stale_markers = {
        "✍️ написать историю",
        "✍️ другое / расскажу своими словами",
        "📄 загрузить резюме",
        "📄 пришлю резюме",
        "➡️ продолжить без резюме",
        "✅ да, вы поняли верно",
        "✅ отметил(а), что мешает",
        "нормальный разбор",
        "хорошо, делаем нормальный разбор",
        "принято",
    }
    if low in stale_markers:
        return True
    return (
        low.startswith("✍️")
        or low.startswith("📄")
        or low.startswith("➡️")
        or low.startswith("✅")
        or "напишите историю" in low
        or "загрузить резюме" in low
        or "продолжить без резюме" in low
        or "отметил" in low and "мешает" in low
        or "поняли верно" in low
    )


def _route_context_reply_markup(question: dict[str, object]):
    options = _route_context_options(question)
    if options:
        keyboard = question_options_keyboard(options)
        if keyboard:
            return keyboard
    return input_method_keyboard()


def _route_context_section_text(route_context: dict[str, str]) -> str:
    ordered = [
        ("Страна", route_context.get("country", "")),
        ("Город", route_context.get("city", "")),
        ("Текущий уровень языка", route_context.get("current_language_level", "")),
        ("Целевой язык", route_context.get("target_language", "")),
        ("Срочность дохода", route_context.get("income_urgency", "")),
        ("Минимальный доход", route_context.get("minimum_monthly_income", "")),
        ("Желаемый доход", route_context.get("desired_monthly_income", "")),
        ("Бюджет на обучение", route_context.get("training_budget", "")),
        ("Время на обучение", route_context.get("available_time_for_study", "")),
        ("Карьерная цель", route_context.get("career_goal_type", "")),
        ("Предпочтения по работе", route_context.get("work_preferences", "")),
        ("Ограничения", route_context.get("health_or_schedule_limits", "")),
        ("Документы и право на работу", route_context.get("documents_and_work_rights", "")),
        ("Статус диплома", route_context.get("diploma_status", "")),
        ("Портфолио / рекомендации", route_context.get("portfolio_or_references", "")),
    ]
    lines = [f"- {label}: {value}" for label, value in ordered if str(value).strip()]
    return "\n".join(lines)


def _split_route_context_answer(answer: str, expected_parts: int) -> list[str]:
    parts = [part.strip() for part in re.split(r"[;\n,]+", answer or "") if part.strip()]
    if len(parts) >= expected_parts:
        return parts[:expected_parts]
    if len(parts) == 1 and expected_parts > 1:
        return [parts[0]] + [""] * (expected_parts - 1)
    return parts


async def _start_route_context_intake(message: Message, state: FSMContext, lang: str, *, remaining_count: int | None = None) -> None:
    data = await state.get_data()
    route_context = dict(data.get("route_context") or {})
    question_index = int(data.get("route_context_index") or 0)
    if question_index <= 0 and not route_context:
        await message.answer(t(lang, "route_context_intro"), reply_markup=input_method_keyboard())
    question = _route_context_question(question_index, route_context)
    if not question:
        return
    await state.set_state(CareerFlow.ROUTE_CONTEXT)
    await state.update_data(route_context=route_context, route_context_index=question_index, route_context_question_id=str(question.get("id") or question_index))
    await message.answer(str(question.get("prompt") or ""), reply_markup=_route_context_reply_markup(question))


def _route_context_next_index(current_index: int, answer: str, keys: list[str]) -> tuple[dict[str, str], int]:
    route_context: dict[str, str] = {}
    parts = _split_route_context_answer(answer, max(1, len(keys)))
    if len(keys) == 1:
        route_context[keys[0]] = answer.strip()
    else:
        for idx, key in enumerate(keys):
            value = parts[idx] if idx < len(parts) else ""
            route_context[key] = value.strip() or answer.strip()

    # Allow multi-touch answers for language and health questions: keep a comma-separated value list as a single field.
    if len(keys) == 1 and keys[0] in {"current_language_level", "target_language", "health_or_schedule_limits"}:
        route_context[keys[0]] = answer.strip()

    return route_context, current_index + 1


def _route_specific_reply_markup(gap_row: dict[str, object]):
    options = gap_row.get("options", []) if isinstance(gap_row.get("options"), list) else []
    if options:
        return question_options_keyboard([str(item).strip() for item in options if str(item).strip()])
    return input_method_keyboard()


async def _maybe_start_route_specific_clarification(
    message: Message,
    state: FSMContext,
    lang: str,
    selected_route: str,
) -> bool:
    data = await state.get_data()
    if bool(data.get("awaiting_route_specific_questions")):
        return True

    from services.interview_policy import get_route_specific_gaps  # noqa: PLC0415

    raw_ep = data.get("evidence_profile")
    if isinstance(raw_ep, dict):
        try:
            profile = CareerEvidenceProfile.model_validate(raw_ep)
        except Exception:
            profile = build_evidence_profile_from_analysis(data.get("story_analysis") or {})
    else:
        profile = build_evidence_profile_from_analysis(data.get("story_analysis") or {})

    gaps = get_route_specific_gaps(selected_route, profile)
    if not gaps:
        return False

    gap_rows = [gap.model_dump() for gap in gaps]
    first = gap_rows[0]
    await state.update_data(
        awaiting_route_specific_questions=True,
        route_specific_gaps=gap_rows,
        route_specific_index=0,
        route_specific_answers=[],
        route_specific_selected_route=selected_route,
    )
    await _track_event(
        message,
        state,
        "route_specific_clarification_started",
        meta={"route": selected_route, "count": len(gap_rows)},
    )
    await message.answer(
        "Хорошо, выбрали маршрут. Уточню только важные детали именно для него.",
        reply_markup=_route_specific_reply_markup(first),
    )
    await message.answer(str(first.get("prompt") or ""), reply_markup=_route_specific_reply_markup(first))
    return True


def _cancel_reminder(chat_id: int) -> None:
    task = _REMINDER_TASKS.pop(chat_id, None)
    if task and not task.done():
        task.cancel()


async def _run_reminder(bot, chat_id: int, language: str, delay_seconds: int) -> None:
    try:
        await asyncio.sleep(delay_seconds)
        await bot.send_message(chat_id, t(language, "thinking_reminder_fire"), reply_markup=result_actions_keyboard())
    finally:
        _REMINDER_TASKS.pop(chat_id, None)


def _schedule_reminder(bot, chat_id: int, language: str, delay_seconds: int = 172800) -> str:
    _cancel_reminder(chat_id)
    _REMINDER_TASKS[chat_id] = asyncio.create_task(_run_reminder(bot, chat_id, language, delay_seconds))
    due_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    return due_at.isoformat()


def _cancel_pdf_task(chat_id: int) -> None:
    task = _PDF_TASKS.pop(chat_id, None)
    if task and not task.done():
        task.cancel()


def _report_public_url(path: Path) -> str:
    base = str(settings.report_base_url or "").strip().rstrip("/")
    if not base:
        return ""
    lowered = base.lower()
    if "localhost" in lowered or "127.0.0.1" in lowered or "[::1]" in lowered:
        return ""
    try:
        host = (urlparse(base).hostname or "").lower()
    except Exception:
        host = ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return ""
    return f"{base}/{path.name}"


def _normalize_report_path(raw_path: str) -> str:
    value = str(raw_path or "").strip()
    if not value:
        return ""
    path_obj = Path(value).expanduser()
    if not path_obj.is_absolute():
        path_obj = Path.cwd() / path_obj
    return str(path_obj.resolve())


def _resolve_pdf_report_path(data: dict) -> str:
    direct = _normalize_report_path(str(data.get("pdf_report_path") or ""))
    if direct and Path(direct).exists():
        return direct

    report_generation_id = str(data.get("report_generation_id") or "").strip()
    if report_generation_id:
        persisted = get_report_by_generation_id(report_generation_id) or {}
        persisted_path = _normalize_report_path(str(persisted.get("pdf_report_path") or ""))
        if persisted_path and Path(persisted_path).exists():
            return persisted_path

    try:
        chat_id = int(data.get("chat_id") or 0)
    except Exception:
        chat_id = 0
    return _PDF_READY_BY_CHAT.get(chat_id, "")


def _resolve_html_report_path(data: dict) -> str:
    direct = _normalize_report_path(str(data.get("html_report_path") or ""))
    if direct and Path(direct).exists():
        return direct

    report_generation_id = str(data.get("report_generation_id") or "").strip()
    if report_generation_id:
        persisted = get_report_by_generation_id(report_generation_id) or {}
        persisted_path = _normalize_report_path(str(persisted.get("html_report_path") or ""))
        if persisted_path and Path(persisted_path).exists():
            return persisted_path

    return ""


def _resolve_docx_report_path(data: dict) -> str:
    direct = _normalize_report_path(str(data.get("docx_report_path") or ""))
    if direct and Path(direct).exists():
        return direct

    report_generation_id = str(data.get("report_generation_id") or "").strip()
    if report_generation_id:
        persisted = get_report_by_generation_id(report_generation_id) or {}
        persisted_path = _normalize_report_path(str(persisted.get("docx_report_path") or ""))
        if persisted_path and Path(persisted_path).exists():
            return persisted_path

    return ""


async def _send_text_report_fallback_document(message: Message, lang: str, report: dict) -> None:
    await message.answer(
        "Полный текстовый разбор отключен. Основной формат отчёта — web-версия (HTML). "
        "Попробуйте открыть отчёт по кнопке или повторите запрос.",
        reply_markup=result_actions_keyboard(),
    )


def _specialist_notify_target_chat_id() -> int | None:
    raw = str(settings.specialist_notify_chat_id or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


async def _notify_specialist_request_owner(message: Message, state: FSMContext, action: str) -> None:
    target_chat_id = _specialist_notify_target_chat_id()
    if not target_chat_id:
        return

    data = await state.get_data()
    public_user_id = _ensure_public_id(data, message)
    username = ("@" + message.from_user.username) if message.from_user and message.from_user.username else "-"
    full_name = " ".join(
        [
            part
            for part in [
                message.from_user.first_name if message.from_user else "",
                message.from_user.last_name if message.from_user else "",
            ]
            if part
        ]
    ).strip() or "-"
    now_iso = datetime.now(timezone.utc).isoformat()
    text = "\n".join(
        [
            "Уведомление: новая заявка на разбор со специалистом.",
            f"Пользователь: {full_name} {username}".strip(),
            f"ID заявки: {public_user_id}",
            f"Время: {now_iso}",
        ]
    )

    try:
        await message.bot.send_message(target_chat_id, text)
        await _track_event(
            message,
            state,
            "specialist_notify_sent",
            action=action,
            meta={"target_chat_id": target_chat_id},
        )
    except Exception as exc:
        await _track_event(
            message,
            state,
            "specialist_notify_failed",
            action=action,
            meta={"error": type(exc).__name__},
        )


async def _run_pdf_generation_background(
    *,
    bot,
    chat_id: int,
    lang: str,
    html_path: Path,
    report_generation_id: str,
) -> None:
    try:
        try:
            pdf_path, pdf_error = await asyncio.to_thread(generate_pdf_from_html_file_with_error, html_path)
        except Exception as exc:
            pdf_path, pdf_error = None, str(exc)

        if pdf_path is not None and pdf_path.exists():
            pdf_path_str = _normalize_report_path(str(pdf_path))
            _PDF_READY_BY_CHAT[chat_id] = pdf_path_str
            if report_generation_id:
                update_report_files(report_generation_id, pdf_report_path=pdf_path_str)
            return

        if report_generation_id:
            update_report_files(report_generation_id, pdf_report_path="")
        if pdf_error:
            print(f"[pdf-bg] chat_id={chat_id} error={pdf_error}", flush=True)
    finally:
        _PDF_TASKS.pop(chat_id, None)


def _user_language(data: dict) -> str:
    return data.get("language") or data.get("lang", "ru")


def _ensure_public_id(data: dict, message: Message) -> str:
    existing = str(data.get("public_user_id") or "").strip()
    if existing:
        return existing
    source_id = message.from_user.id if message.from_user else message.chat.id
    return ensure_public_user_id(source_id)


def _canonical_event_aliases(event: str, action: str, meta: dict | None = None) -> list[str]:
    normalized_event = str(event or "").strip()
    normalized_action = str(action or "").strip()
    meta_payload = meta if isinstance(meta, dict) else {}
    aliases: list[str] = []

    if normalized_event == "story_submitted":
        aliases.append("story_evidence_extracted")
    if normalized_event == "question_shown":
        aliases.append("clarifying_question_asked")
    if normalized_event == "conflict_detected":
        aliases.append("clarifying_question_skipped_existing_answer")
    if normalized_event == "prelim_map_error_flagged":
        aliases.append("profile_correction_received")
    if normalized_event == "guardrail_violations":
        aliases.append("report_guardrail_failed")
    if normalized_event == "guardrail_regen_triggered":
        aliases.append("report_regenerated")
    if normalized_event == "interview_ready_early":
        readiness_status = str(meta_payload.get("status") or "").strip().lower()
        aliases.append("interview_ready" if readiness_status == "ready" else "interview_ready_with_uncertainty")

    if normalized_event == "answer_submitted":
        aliases.append("question_answered")
    if normalized_event in {"pdf_generation_error", "pdf_fallback_html"}:
        aliases.append("pdf_failed")
    if normalized_event == "route_selected":
        aliases.append("route_changed")
    if normalized_event == "result_action_clicked" and normalized_action == MAP_CHECK_DISAGREE_ROUTE:
        aliases.append("user_disagreed")
    if normalized_event == "result_action_clicked" and normalized_action in {RESULT_SPECIALIST, PDF_FALLBACK_SPECIALIST}:
        aliases.append("specialist_clicked")
    if normalized_event == "step_action" and normalized_action == STEP_OPEN_TODAY:
        aliases.append("first_step_started")
    if normalized_event == "step_action" and normalized_action == STEP_DONE:
        aliases.append("first_step_completed")
    if normalized_event == "step_action" and normalized_action == STEP_NOT_DONE:
        aliases.append("first_step_too_hard")

    return aliases


async def _track_event(
    message: Message,
    state: FSMContext,
    event: str,
    *,
    action: str = "",
    meta: dict | None = None,
) -> None:
    data = await state.get_data()
    public_user_id = _ensure_public_id(data, message)
    user_mode = str(data.get("user_mode") or "")
    lang = _user_language(data)
    state_name = (await state.get_state()) or ""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    previous_state_name = str(data.get("state_name") or "")
    previous_event_dt = None
    previous_state_entered_dt = None
    previous_event_raw = str(data.get("last_event_at") or "")
    previous_state_entered_raw = str(data.get("state_entered_at") or "")

    try:
        previous_event_dt = datetime.fromisoformat(previous_event_raw) if previous_event_raw else None
        if previous_event_dt and previous_event_dt.tzinfo is None:
            previous_event_dt = previous_event_dt.replace(tzinfo=timezone.utc)
    except Exception:
        previous_event_dt = None

    try:
        previous_state_entered_dt = datetime.fromisoformat(previous_state_entered_raw) if previous_state_entered_raw else None
        if previous_state_entered_dt and previous_state_entered_dt.tzinfo is None:
            previous_state_entered_dt = previous_state_entered_dt.replace(tzinfo=timezone.utc)
    except Exception:
        previous_state_entered_dt = None

    state_changed = previous_state_name != state_name and previous_state_name != ""
    if state_changed or not previous_state_entered_dt:
        state_entered_at_iso = now_iso
        state_entered_dt = now
    else:
        state_entered_at_iso = previous_state_entered_dt.isoformat()
        state_entered_dt = previous_state_entered_dt

    event_meta = dict(meta or {})
    if previous_event_dt is not None:
        event_meta["seconds_from_prev_event"] = round(max(0.0, (now - previous_event_dt).total_seconds()), 2)
    if state_entered_dt is not None:
        event_meta["seconds_in_current_state"] = round(max(0.0, (now - state_entered_dt).total_seconds()), 2)
    if state_changed and previous_state_entered_dt is not None:
        event_meta["previous_state"] = previous_state_name
        event_meta["previous_state_duration_seconds"] = round(max(0.0, (now - previous_state_entered_dt).total_seconds()), 2)

    if not data.get("public_user_id"):
        await state.update_data(public_user_id=public_user_id)
    await log_behavior_event(
        public_user_id=public_user_id,
        event=event,
        state_name=state_name,
        action=action,
        user_mode=user_mode,
        language=lang,
        meta=event_meta,
        session_id=str(data.get("session_id") or "").strip(),
    )
    for alias in _canonical_event_aliases(event, action, event_meta):
        alias_meta = dict(event_meta)
        alias_meta["source_event"] = event
        await log_behavior_event(
            public_user_id=public_user_id,
            event=alias,
            state_name=state_name,
            action=action,
            user_mode=user_mode,
            language=lang,
            meta=alias_meta,
            session_id=str(data.get("session_id") or "").strip(),
        )
    await state.update_data(
        public_user_id=public_user_id,
        state_name=state_name,
        state_entered_at=state_entered_at_iso,
        last_event_at=now_iso,
    )
    session_id = str(data.get("session_id") or "").strip()
    if session_id:
        touch_session(
            session_id,
            state_name=state_name,
            user_mode=user_mode,
            language=lang,
        )
    if state_changed:
        snapshot = {
            "state_name": state_name,
            "language": lang,
            "user_mode": user_mode,
            "story_text": str(data.get("story_text") or "")[:4000],
            "qa_index": int(data.get("qa_index") or 0),
            "final_report_generated": bool(data.get("final_report_generated")),
            "report_generation_id": str(data.get("report_generation_id") or ""),
        }
        save_profile_version(
            public_user_id,
            "state_sync",
            snapshot,
            session_id=session_id,
        )


def _build_system_offer_text(data: dict) -> str:
    public_user_id = str(data.get("public_user_id") or "").strip()
    snapshot = behavior_offer_snapshot(public_user_id) if public_user_id else {"insights": [], "top_actions": [], "stats": {}}
    insights = list(snapshot.get("insights", []))
    if not insights:
        insights = [
            "Вы стабильно проходите шаги по карте и возвращаетесь к действиям.",
            "Выбираете прикладные действия, а не абстрактные советы.",
        ]
    top_actions = snapshot.get("top_actions", []) if isinstance(snapshot, dict) else []
    praise_lines: list[str] = []
    for action, count in top_actions[:2]:
        praise_lines.append(f"- действие «{action}» у вас сработало {count} раз;")

    stats = snapshot.get("stats", {}) if isinstance(snapshot, dict) else {}
    if int(stats.get("today_step_opened", 0)) > 0:
        praise_lines.append("- вы возвращались к первому шагу, то есть умеете запускать движение в реальности;")
    if int(stats.get("report_generated", 0)) > 0:
        praise_lines.append("- вы дошли до готовой карты, это редкий показатель дисциплины на старте;")
    if not praise_lines:
        praise_lines.append("- вы не теряете контакт с процессом и умеете делать короткие рабочие шаги;")

    days_live = days_since_first_seen(public_user_id) if public_user_id else 0
    day_prefix = ""
    if days_live >= 3:
        day_prefix = (
            "Сегодня уже 3+ день теста. Это важная точка: обычно люди теряют темп именно сейчас, "
            "поэтому оффер ниже про удержание темпа и рост результата.\n\n"
        )

    insights_block = "\n".join(f"- {item}" for item in insights[:3])
    praise_block = "\n".join(praise_lines[:3])
    return (
        f"{day_prefix}Что уже видно по вашему поведению:\n"
        f"{insights_block}\n\n"
        "Что у вас уже получается хорошо:\n"
        f"{praise_block}\n\n"
        "Что это значит:\n"
        "- вы уже умеете делать конкретные действия, не только читать советы;\n"
        "- у вас есть ресурс на системный прогресс, если есть внешняя структура и обратная связь.\n\n"
        "Бесплатная версия:\n"
        "- 1-2 запуска в кризис;\n"
        "- упражнения без глубокой обратной связи и без регулярной аналитики;\n"
        "- помогает стартовать, но не гарантирует удержание ритма.\n\n"
        "Платная версия NextYou:\n"
        "- мы анализируем ваши действия каждую неделю и показываем, где вы застреваете;\n"
        "- адаптивно перестраиваем карту под ваш реальный прогресс;\n"
        "- выдаем новый стек навыков и новый рабочий фокус под текущий этап;\n"
        "- держим дисциплину и доводим до результата через систему сопровождения.\n\n"
        "Мы продаем не набор навыков, а систему, которая изучает именно вас и дает то, что нужно вам сейчас."
    )


def _classify_answer_length(text: str) -> str:
    words = len((text or "").split())
    if words >= 90:
        return "long"
    if words <= 12:
        return "short"
    return "medium"


def _detect_emotional_tone(text: str) -> str:
    low = (text or "").lower()
    if any(token in low for token in ["никому не", "страш", "стыд", "не вывожу", "хаос", "устал", "не знаю"]):
        if "устал" in low or "нет сил" in low:
            return "tired"
        if "стыд" in low:
            return "ashamed"
        if "хаос" in low:
            return "confused"
        return "anxious"
    if any(token in low for token in ["быстр", "по делу", "срок", "доход", "kpi", "цифр"]):
        return "calm"
    if any(token in low for token in ["злю", "бесит", "сколько можно"]):
        return "angry"
    if any(token in low for token in ["готов", "делаю", "начинаю"]):
        return "motivated"
    return "unknown"


def _detect_structure_level(text: str) -> str:
    low = (text or "").lower()
    separators = sum(1 for token in [";", ",", "\n", "1.", "2.", "3."] if token in text)
    if any(token in low for token in ["не знаю", "ничего", "ав", "ячз"]) and len(low.split()) <= 5:
        return "fragmented"
    if separators >= 4:
        return "structured"
    if any(token in low for token in ["хаос", "то так", "не понимаю", "путаюсь"]):
        return "chaotic"
    return "structured"


def _detect_agency_level(text: str) -> str:
    low = (text or "").lower()
    if any(token in low for token in ["не знаю", "не могу", "нет сил", "боюсь"]):
        return "low"
    if any(token in low for token in ["готов", "сделаю", "давайте", "по делу"]):
        return "high"
    return "medium"


def _build_interaction_profile(story_text: str, data: dict) -> dict:
    existing = data.get("interaction_profile") or {}
    pace = existing.get("pace") or data.get("pace") or "normal"
    preferred_input = existing.get("preferred_input") or data.get("preferred_input") or "unknown"
    answer_length = _classify_answer_length(story_text)
    emotional_tone = _detect_emotional_tone(story_text)
    structure_level = _detect_structure_level(story_text)
    agency_level = _detect_agency_level(story_text)

    support_need = "medium"
    detail_preference = "balanced"
    if emotional_tone in {"anxious", "ashamed", "tired", "confused"}:
        support_need = "high"
        if pace == "normal":
            pace = "slow"
    elif emotional_tone == "calm":
        support_need = "low"
    if answer_length == "short":
        detail_preference = "brief"
        if preferred_input == "unknown":
            preferred_input = "buttons"
    elif answer_length == "long":
        detail_preference = "detailed"

    return {
        "answer_length": answer_length,
        "emotional_tone": emotional_tone,
        "structure_level": structure_level,
        "support_need": support_need,
        "pace": pace,
        "preferred_input": preferred_input,
        "detail_preference": detail_preference,
        "agency_level": agency_level,
    }


def _adaptive_question_count(story_text: str, profile: dict, analysis: dict) -> int:
    if profile.get("pace") == "fast" and profile.get("answer_length") in {"medium", "long"}:
        return 4
    if profile.get("emotional_tone") in {"tired", "angry"}:
        return 0
    if profile.get("answer_length") == "long":
        return 5
    # Basic data sufficiency score from extracted fields.
    enough_data = 0
    for key in ["skills", "constraints", "goals", "current_identity"]:
        value = analysis.get(key)
        if isinstance(value, list) and value:
            enough_data += 1
        if isinstance(value, str) and value.strip():
            enough_data += 1
    if enough_data >= 5:
        return 5
    if enough_data <= 2:
        return 8
    return 6


def _question_count_for_mode(mode: str, configured_value: object = None) -> int:
    mode_key = str(mode or "calm_steps")

    # Hard boundaries from MVP TZ.
    bounds = {
        "fast": (5, 5),
        "calm_steps": (8, 10),
        "deep_route": (12, 15),
        "support": (12, 15),
    }
    min_q, max_q = bounds.get(mode_key, (8, 10))

    try:
        configured = int(configured_value or 0)
    except Exception:
        configured = 0

    # If state/config provides a value, clamp it into allowed mode range.
    if configured > 0:
        return max(min_q, min(max_q, configured))

    # Defaults stay inside mode boundaries.
    defaults = {
        "fast": 5,
        "calm_steps": 8,
        "deep_route": 15,
        "support": 15,
    }
    default_value = defaults.get(mode_key, 10)
    return max(min_q, min(max_q, default_value))


def _join_items(items: list[str], limit: int = 6) -> str:
    cleaned = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    return ", ".join(cleaned[:limit]) if cleaned else "-"


def _clip(text: str, limit: int = 3800) -> str:
    raw = text or ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.replace("\r\n", "\n").split("\n")]
    normalized_lines: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        normalized_lines.append(line)
        previous_blank = is_blank
    clean = "\n".join(normalized_lines).strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


def _split_for_telegram(text: str, limit: int = 3800) -> list[str]:
    clean = str(text or "").replace("\r\n", "\n").strip()
    if not clean:
        return ["-"]
    if len(clean) <= limit:
        return [clean]

    chunks: list[str] = []
    current = ""
    paragraphs = clean.split("\n\n")

    for paragraph in paragraphs:
        part = paragraph.strip()
        if not part:
            continue

        candidate = f"{current}\n\n{part}" if current else part
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(part) <= limit:
            current = part
            continue

        # Split oversized paragraph by lines first.
        line_acc = ""
        for line in part.split("\n"):
            line = line.strip()
            if not line:
                continue
            line_candidate = f"{line_acc}\n{line}" if line_acc else line
            if len(line_candidate) <= limit:
                line_acc = line_candidate
                continue

            if line_acc:
                chunks.append(line_acc)
                line_acc = ""

            if len(line) <= limit:
                line_acc = line
                continue

            # Hard split long single line.
            start = 0
            while start < len(line):
                end = min(start + limit, len(line))
                chunks.append(line[start:end])
                start = end

        if line_acc:
            current = line_acc

    if current:
        chunks.append(current)

    return chunks or ["-"]


async def _answer_safe(message: Message, text: str, reply_markup=None) -> None:
    chunks = _split_for_telegram(text)
    for idx, chunk in enumerate(chunks):
        if idx == 0 and reply_markup is not None:
            await message.answer(chunk, reply_markup=reply_markup)
        else:
            await message.answer(chunk)


def _list_block(items: list[str], bullet: str = "- ") -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return "-"
    return "\n".join(f"{bullet}{item}" for item in cleaned)


def _selection_to_text(items: list[str]) -> str:
    cleaned = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    if not cleaned:
        return "-"
    return "\n".join(f"- {item}" for item in cleaned)


def _slugify(value: str) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", "_", text, flags=re.IGNORECASE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "option"


def _merge_answers_text(qa_answers: list[dict]) -> str:
    return "\n".join(
        f"{idx + 1}. {row.get('question', '-')}: {row.get('answer', '-')}"
        for idx, row in enumerate(qa_answers)
        if isinstance(row, dict)
    )


def _load_evidence_profile(data: dict, analysis: dict | None = None) -> CareerEvidenceProfile:
    raw = data.get("evidence_profile")
    if isinstance(raw, dict):
        try:
            return CareerEvidenceProfile.model_validate(raw)
        except Exception:
            pass
    return build_evidence_profile_from_analysis(analysis)


def _question_signature(question_row: dict[str, object], data: dict) -> str:
    primary = str(question_row.get("gap_key") or question_row.get("semantic_intent") or question_row.get("question_id") or "").strip()
    if not primary:
        primary = _slugify(str(question_row.get("question") or "general_clarification"))
    route_domain = str(
        data.get("route_specific_selected_route")
        or data.get("selected_preliminary_route")
        or question_row.get("source")
        or question_row.get("block")
        or "general"
    ).strip()
    return f"{_slugify(primary)}:{_slugify(route_domain)}"


def _split_unresolved_gaps(profile: CareerEvidenceProfile) -> tuple[list[str], list[str]]:
    unresolved = [str(item).strip() for item in list(profile.unresolved_gaps or []) if str(item).strip()]
    if not unresolved:
        return [], []
    critical_keys: set[str] = set()
    try:
        from services.interview_policy import CRITICAL_GAP_TYPES  # noqa: PLC0415

        critical_keys = {str(item).strip() for item in CRITICAL_GAP_TYPES if str(item).strip()}
    except Exception:
        critical_keys = {
            "legal_access",
            "minimum_income",
            "income_deadline",
            "professional_core",
            "goal",
        }

    critical: list[str] = []
    noncritical: list[str] = []
    for gap in unresolved:
        if gap in critical_keys:
            critical.append(gap)
            continue
        gap_low = gap.lower()
        if any(token in gap_low for token in ["legal", "income", "deadline", "permission", "goal"]):
            critical.append(gap)
        else:
            noncritical.append(gap)
    return critical, noncritical


def _build_interview_context(data: dict, analysis: dict | None = None) -> InterviewContext:
    existing_raw = data.get("interview_context")
    existing = existing_raw if isinstance(existing_raw, dict) else {}
    profile = _load_evidence_profile(data, analysis)

    hypotheses = data.get("conversation_hypotheses") if isinstance(data.get("conversation_hypotheses"), list) else []
    asked_signatures = existing.get("asked_question_signatures") if isinstance(existing.get("asked_question_signatures"), list) else data.get("asked_question_signatures")
    asked_signatures = [str(item).strip() for item in (asked_signatures or []) if str(item).strip()]

    readiness_status = str(existing.get("report_readiness") or "not_ready")
    try:
        from services.interview_policy import evaluate_report_readiness  # noqa: PLC0415

        readiness = evaluate_report_readiness(profile=profile, route_hypotheses=hypotheses)
        readiness_status = str(readiness.status)
    except Exception:
        pass

    critical_gaps, noncritical_gaps = _split_unresolved_gaps(profile)

    return InterviewContext(
        evidence_profile=profile.model_dump(),
        hypotheses=[row for row in hypotheses if isinstance(row, dict)],
        current_action=str(existing.get("current_action") or "") or None,
        current_question_id=str(existing.get("current_question_id") or "") or None,
        current_question_goal=str(existing.get("current_question_goal") or "") or None,
        asked_question_signatures=asked_signatures,
        answered_gap_ids=[str(item) for item in existing.get("answered_gap_ids", [])],
        skipped_gap_ids=[str(item) for item in existing.get("skipped_gap_ids", [])],
        resolved_fact_types=[str(item) for item in existing.get("resolved_fact_types", [])],
        unresolved_critical_gaps=critical_gaps,
        unresolved_noncritical_gaps=noncritical_gaps,
        report_readiness=readiness_status,
        questions_asked_count=int(existing.get("questions_asked_count") or 0),
        consecutive_long_answers=int(existing.get("consecutive_long_answers") or 0),
        user_fatigue_score=float(existing.get("user_fatigue_score") or 0.0),
    )


async def _save_interview_context(state: FSMContext, context: InterviewContext) -> None:
    await state.update_data(
        interview_context=context.model_dump(),
        evidence_profile=context.evidence_profile,
        conversation_hypotheses=context.hypotheses,
        asked_question_signatures=context.asked_question_signatures,
    )


def _apply_answer_to_interview_context(context: InterviewContext, answer_text: str) -> InterviewContext:
    answer_length = _classify_answer_length(answer_text)
    if answer_length == "long":
        context.consecutive_long_answers += 1
        context.user_fatigue_score = min(1.0, context.user_fatigue_score + 0.2)
    elif answer_length == "short":
        context.consecutive_long_answers = 0
        context.user_fatigue_score = max(0.0, context.user_fatigue_score - 0.05)
    else:
        context.consecutive_long_answers = 0
        context.user_fatigue_score = max(0.0, context.user_fatigue_score - 0.02)

    context.current_action = None
    context.current_question_id = None
    context.current_question_goal = None
    return context


async def _sync_interview_context_after_answer(
    state: FSMContext,
    data: dict,
    evidence_payload: dict[str, object],
    answer_text: str,
) -> InterviewContext:
    merged = dict(data)
    merged["evidence_profile"] = evidence_payload
    context = _build_interview_context(merged, merged.get("story_analysis") if isinstance(merged.get("story_analysis"), dict) else None)
    context = _apply_answer_to_interview_context(context, answer_text)
    await _save_interview_context(state, context)
    return context


def _find_next_unasked_question(
    analysis: dict,
    data: dict,
    start_index: int,
    asked_signatures: set[str],
) -> tuple[int, dict[str, object], str] | tuple[None, None, None]:
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    idx = max(0, int(start_index or 0))
    while idx < len(questions):
        row = questions[idx]
        if not isinstance(row, dict):
            idx += 1
            continue
        signature = _question_signature(row, data)
        if signature in asked_signatures:
            idx += 1
            continue
        return idx, row, signature
    return None, None, None


async def _ask_next_interview_question(
    message: Message,
    state: FSMContext,
    data: dict,
    analysis: dict,
    context: InterviewContext,
    qa_index: int,
    lang: str,
    user_mode: str,
) -> bool:
    if context.questions_asked_count >= 5:
        context.current_action = "show_preliminary_map"
        await _save_interview_context(state, context)
        return False
    asked = {str(item).strip() for item in context.asked_question_signatures if str(item).strip()}
    search_index = qa_index
    next_index, row, signature = _find_next_unasked_question(analysis, data, search_index, asked)
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    while next_index is not None and row is not None and signature is not None:
        decision_change = _decision_that_may_change(row)
        if decision_change:
            break
        if signature not in context.asked_question_signatures:
            context.asked_question_signatures.append(signature)
            asked.add(signature)
        await _track_event(
            message,
            state,
            "question_skipped_no_decision_impact",
            meta={
                "question_index": next_index + 1,
                "question_id": _question_id(row, next_index),
                "signature": signature,
            },
        )
        search_index = next_index + 1
        next_index, row, signature = _find_next_unasked_question(analysis, data, search_index, asked)

    if next_index is None or row is None or signature is None:
        await state.update_data(qa_index=len(questions))
        context.current_action = "show_preliminary_map"
        await _save_interview_context(state, context)
        return False

    text = _question_prompt(analysis, next_index, lang)
    evidence_payload = data.get("evidence_profile") if isinstance(data.get("evidence_profile"), dict) else context.evidence_profile
    hypothesis_text, turn_meta = _apply_hypothesis_action(data, evidence_payload, next_index, text, lang, user_mode)
    decision_change = _decision_that_may_change(row)
    await state.update_data(qa_index=next_index)
    await message.answer(hypothesis_text or text, reply_markup=_question_reply_markup(analysis, next_index))

    turn_action = str(turn_meta.get("action") or "").strip()
    if turn_action == "confirm_hypothesis":
        await _track_event(
            message,
            state,
            "career_hypothesis_created",
            meta={
                "question_index": next_index + 1,
                "question_id": _question_id(row, next_index),
                "hypothesis_statement": str(turn_meta.get("hypothesis_statement") or "")[:240],
                "hypothesis_confidence": str(turn_meta.get("hypothesis_confidence") or ""),
            },
        )

    if bool(row.get("critical_gap")):
        await _track_event(
            message,
            state,
            "critical_gap_detected",
            meta={
                "question_index": next_index + 1,
                "question_id": _question_id(row, next_index),
                "gap_key": str(row.get("gap_key") or ""),
                "decision_that_may_change": decision_change,
            },
        )

    if signature not in context.asked_question_signatures:
        context.asked_question_signatures.append(signature)
    context.current_action = "ask_question"
    context.current_question_id = str(_question_id(row, next_index))
    context.current_question_goal = str(row.get("internal_goal") or row.get("semantic_intent") or row.get("gap_key") or "")
    context.questions_asked_count += 1
    await _save_interview_context(state, context)
    await _track_event(
        message,
        state,
        "question_shown",
        meta={
            "question_index": next_index + 1,
            "question_id": _question_id(row, next_index),
            "signature": signature,
            "decision_that_may_change": decision_change,
        },
    )
    return True


def _build_evidence_questions(profile: CareerEvidenceProfile, lang: str, user_mode: str) -> list[dict[str, object]]:
    mode_key = str(user_mode or "calm_steps")
    soft_cap = {"fast": 3, "calm_steps": 5, "deep_route": 5, "support": 5}.get(mode_key, 5)

    questions: list[dict[str, object]] = []
    asked_gap_keys: set[str] = set()
    for _ in range(soft_cap):
        question = next_question_from_profile(
            profile,
            language=lang,
            asked_gap_keys=asked_gap_keys,
            user_mode=mode_key,
        )
        if not question:
            break
        gap_key = str(question.get("gap_key") or "").strip()
        if gap_key:
            asked_gap_keys.add(gap_key)
        question["id"] = len(questions) + 1
        questions.append(question)
    return questions


def _update_evidence_after_answer(data: dict, question_row: dict | object, answer_text: str) -> tuple[dict[str, object], bool]:
    analysis = data.get("story_analysis") if isinstance(data.get("story_analysis"), dict) else {}
    profile = _load_evidence_profile(data, analysis)
    gap_key = str(question_row.get("gap_key") or "").strip() if isinstance(question_row, dict) else ""
    if gap_key:
        profile = apply_answer_to_profile(profile, gap_key, answer_text)
    assessment_id = str(data.get("assessment_id") or data.get("report_generation_id") or "pending-assessment")
    canonical_before = build_canonical_profile(data, assessment_id=assessment_id)
    diagnostic_data = copy.deepcopy(data)
    diagnostic_data["qa_answers"] = [
        *(diagnostic_data.get("qa_answers") or []),
        {
            "assessment_id": assessment_id,
            "question_id": str(question_row.get("id") or "") if isinstance(question_row, dict) else "",
            "answer": answer_text,
            "source_message_id": "runtime-diagnostic",
        },
    ]
    canonical_after = build_canonical_profile(diagnostic_data, assessment_id=assessment_id)
    _runtime_debug_log(
        "assessment_answer_routed",
        assessment_id=assessment_id,
        question_id=str(question_row.get("id") or "") if isinstance(question_row, dict) else "",
        target_fact_type=gap_key,
        target_schema_path=f"evidence_profile.{gap_key}" if gap_key else "qa_answers",
        raw_answer=answer_text,
        extracted_facts=profile.model_dump(mode="json"),
        canonical_profile_before=canonical_before.model_dump(mode="json"),
        canonical_profile_after=canonical_after.model_dump(mode="json"),
        generator_version=CAREER_PIPELINE_VERSION,
        renderer_version=CAREER_TELEGRAM_RENDERER_VERSION,
        fallback_reason=None,
        validation_errors=[],
    )
    from services.interview_policy import is_ready_for_conclusion
    mode = str(data.get("user_mode") or "calm_steps")
    ready = profile_ready_for_safe_conclusion(profile) and is_ready_for_conclusion(profile, user_mode=mode)
    return profile.model_dump(), ready


def _readiness_status_from_payload(evidence_payload: dict[str, object]) -> str:
    try:
        from services.evidence_profile import CareerEvidenceProfile as _CEP_READY  # noqa: PLC0415
        from services.interview_policy import evaluate_report_readiness  # noqa: PLC0415

        profile = _CEP_READY.model_validate(evidence_payload)
        readiness = evaluate_report_readiness(profile)
        return str(readiness.status or "not_ready")
    except Exception:
        return "ready_with_uncertainty"


async def _track_interview_ready_event(
    message: Message,
    state: FSMContext,
    *,
    question_index: int,
    evidence_payload: dict[str, object],
) -> None:
    readiness_status = _readiness_status_from_payload(evidence_payload)
    await _track_event(
        message,
        state,
        "interview_ready_early",
        meta={"question_index": question_index, "status": readiness_status},
    )


def _apply_hypothesis_action(
    data: dict,
    evidence_payload: dict,
    qa_index: int,
    next_question_text: str,
    lang: str,
    user_mode: str,
) -> tuple[str, dict[str, str]]:
    """Return hypothesis-framed message text, or '' to fall back to bare question."""
    try:
        from services.hypothesis_engine import CareerHypothesis, select_conversation_action, format_conversation_turn  # noqa: PLC0415
        from services.evidence_profile import CareerEvidenceProfile as _CEP3  # noqa: PLC0415
        from services.interview_policy import evaluate_report_readiness  # noqa: PLC0415
        _profile = _CEP3.model_validate(evidence_payload)
        _readiness = evaluate_report_readiness(_profile)
        _hyp_dicts = data.get("conversation_hypotheses")
        _hypotheses = [CareerHypothesis.model_validate(h) for h in (_hyp_dicts or [])] if isinstance(_hyp_dicts, list) else []
        _turn = select_conversation_action(
            _profile,
            _hypotheses,
            qa_index=qa_index,
            readiness_status=_readiness.status,
            user_mode=user_mode,
        )
        turn_meta: dict[str, str] = {
            "action": str(_turn.action),
            "readiness_status": str(_readiness.status),
        }
        if _turn.hypothesis:
            turn_meta["hypothesis_statement"] = str(_turn.hypothesis.statement or "").strip()
            turn_meta["hypothesis_confidence"] = str(_turn.hypothesis.confidence or "").strip()
        if _turn.gap_key:
            turn_meta["gap_key"] = str(_turn.gap_key or "").strip()
        return format_conversation_turn(_turn, next_question_text=next_question_text, lang=lang), turn_meta
    except Exception:
        return "", {}
    analysis = data.get("story_analysis") if isinstance(data.get("story_analysis"), dict) else {}
    profile = _load_evidence_profile(data, analysis)
    gap_key = str(question_row.get("gap_key") or "").strip() if isinstance(question_row, dict) else ""
    if gap_key:
        profile = apply_answer_to_profile(profile, gap_key, answer_text)
    from services.interview_policy import is_ready_for_conclusion
    mode = str(data.get("user_mode") or "calm_steps")
    ready = profile_ready_for_safe_conclusion(profile) and is_ready_for_conclusion(profile, user_mode=mode)
    return profile.model_dump(), ready


def _generate_preliminary_map(
    profile: object,  # CareerEvidenceProfile
    story_analysis: dict,
    lang: str,
) -> tuple[str, str, str]:
    """
    Build preliminary map text and extract the two route labels.
    Returns (map_text, route1_label, route2_label).
    """
    lines: list[str] = ["Вот что уже видно.\n"]

    # Professional core
    core_parts: list[str] = []
    funcs = getattr(profile, "functions", [])
    for f in funcs[:2]:
        name = str(getattr(f, "function_name", "") or "").strip()
        if name:
            core_parts.append(name)
    if not core_parts:
        for h in (story_analysis.get("professional_core_hypotheses") or [])[:1]:
            text = str(h or "").strip()
            if text:
                core_parts.append(text)
    if not core_parts:
        facts = getattr(profile, "work_history_facts", [])
        for item in facts[:1]:
            stmt = str(getattr(item, "statement", "") or "").strip()
            if stmt:
                core_parts.append(stmt)
    lines.append(f"Ваше профессиональное ядро:\n{', '.join(core_parts) if core_parts else 'уточняется'}")

    # Confirmed seniority level
    seniority_parts: list[str] = []
    for f in funcs[:2]:
        inferred = str(getattr(f, "inferred_seniority", "") or "").strip()
        fname = str(getattr(f, "function_name", "") or "").strip()
        if inferred and inferred not in {"unknown", ""}:
            seniority_parts.append(f"{inferred} в {fname}" if fname else inferred)
    if not seniority_parts:
        for h in (story_analysis.get("seniority_hypotheses") or [])[:1]:
            text = str(h or "").strip()
            if text:
                seniority_parts.append(text)
    lines.append(f"\nВаш подтверждённый уровень:\n{', '.join(seniority_parts) if seniority_parts else 'не определён — нужно уточнить'}")

    # What user wants to change
    change_parts: list[str] = []
    for item in (getattr(profile, "explicit_goal", []) or [])[:1]:
        stmt = str(getattr(item, "statement", "") or "").strip()
        if stmt:
            change_parts.append(stmt)
    for item in (getattr(profile, "explicit_refusals", []) or [])[:1]:
        stmt = str(getattr(item, "statement", "") or "").strip()
        if stmt:
            change_parts.append(f"уйти от: {stmt}")
    lines.append(f"\nЧто вы, вероятно, хотите изменить:\n{'; '.join(change_parts) if change_parts else 'уточняется'}")

    # Two realistic directions — derive from hypotheses or functions
    hypotheses = (story_analysis.get("professional_core_hypotheses") or [])
    directions: list[str] = []
    for h in hypotheses[:2]:
        text = str(h or "").strip()
        if text:
            directions.append(text)
    if len(directions) < 2 and funcs:
        for f in funcs:
            name = str(getattr(f, "function_name", "") or "").strip()
            if name and name not in " ".join(directions):
                directions.append(f"Роли в направлении: {name}")
            if len(directions) >= 2:
                break
    route1 = directions[0] if directions else "Маршрут 1"
    route2 = directions[1] if len(directions) > 1 else "Маршрут 2"
    lines.append(f"\nДва реалистичных направления:\n1. {route1}\n2. {route2}")

    # What's unclear
    unresolved = list(getattr(profile, "unresolved_gaps", []) or [])[:3]
    if unresolved:
        gaps_text = "; ".join(unresolved)
    else:
        critical_gaps = (story_analysis.get("critical_gaps") or [])[:2]
        gaps_text = "; ".join(str(g.get("gap_type") or "") for g in critical_gaps if isinstance(g, dict))
    if not gaps_text:
        gaps_text = "дополнительные данные прояснят точность маршрута"
    lines.append(f"\nЧто пока неясно:\n{gaps_text}")

    lines.append("\nКакой вариант разберём глубже?\n\nЭто не окончательный отчёт.")
    return "\n".join(lines), route1, route2


def _question_semantic_intent(question_text: str) -> str:
    q = str(question_text or "").lower()
    if "цель" in q:
        return "main_goal"
    if "барьер" in q or "мешает" in q:
        return "main_barrier"
    if "язык" in q or "документ" in q or "прав" in q:
        return "language_documents_work_right"
    if "сколько времени" in q and "стране" in q:
        return "time_in_country"
    if "ресур" in q or "времени" in q:
        return "resource_and_time"
    if "стресс" in q or "справля" in q:
        return "what_helps_under_stress"
    return "general_clarification"


def _expected_answer_type(row: dict[str, object]) -> str:
    if row.get("multi_key"):
        return "multi_select"
    opts = row.get("options", [])
    if isinstance(opts, list) and any(str(item).strip() for item in opts):
        return "single_select"
    return "free_text"


def _question_source(row: dict[str, object], mode: str, index: int) -> str:
    raw = str(row.get("source") or "").strip()
    if raw:
        return raw
    if row.get("multi_key") == "psych":
        return "state_and_resource"
    if row.get("multi_key") in {"social", "integration"}:
        return "integration"
    if row.get("multi_key") == "energy":
        return "resource"
    if row.get("multi_key") == "priorities":
        return "priorities"

    mode_key = str(mode or "calm_steps")
    if mode_key == "fast":
        return "story_screening"
    if mode_key == "deep_route":
        if index in {0, 3}:
            return "professional_profile"
        if index == 2:
            return "constraints"
        if index == 4:
            return "action_capacity"
        return "route_branch"

    if index == 0:
        return "professional_profile"
    if index in {1, 5}:
        return "priorities"
    if index in {2, 4}:
        return "constraints"
    if index in {3, 6}:
        return "integration"
    return "route_branch"


def _decision_that_may_change(row: dict[str, object]) -> str:
    decision = str(row.get("decision_impact") or "").strip()
    if decision:
        return decision

    gap_key = str(row.get("gap_key") or "").strip()
    if gap_key:
        return f"resolve_gap:{gap_key}"

    internal_goal = str(row.get("internal_goal") or row.get("semantic_intent") or "").strip()
    if internal_goal:
        return internal_goal

    question_text = str(row.get("question") or "").strip()
    if question_text:
        semantic = _question_semantic_intent(question_text)
        if semantic and semantic != "general_clarification":
            return semantic
        return "clarify_profile"

    return ""


def _question_validity_status(row: dict[str, object]) -> str:
    raw = str(row.get("validity_status") or row.get("status") or "").strip().lower()
    if raw in {"confirmed", "needs_confirmation", "needs_review", "provisional"}:
        return raw
    if row.get("multi_key") or _expected_answer_type(row) in {"single_select", "multi_select"}:
        return "needs_confirmation"
    return "confirmed"


def _extract_docx_text(raw_bytes: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
            tmp_file.write(raw_bytes)
            tmp_path = tmp_file.name
        with zipfile.ZipFile(tmp_path, "r") as archive:
            xml_data = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        text = re.sub(r"<[^>]+>", " ", xml_data)
        return " ".join(text.split())
    except Exception:
        return ""
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _extract_pdf_text(raw_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return " ".join(" ".join(pages).split())
    except Exception:
        return ""


def _extract_utf16le_ascii_runs(raw_bytes: bytes) -> list[str]:
    runs: list[str] = []
    current = bytearray()
    idx = 0
    while idx < len(raw_bytes) - 1:
        first = raw_bytes[idx]
        second = raw_bytes[idx + 1]
        if second == 0 and 32 <= first <= 126:
            current.append(first)
            idx += 2
            continue
        if len(current) >= 4:
            runs.append(current.decode("latin-1", errors="ignore"))
        current.clear()
        idx += 1
    if len(current) >= 4:
        runs.append(current.decode("latin-1", errors="ignore"))
    return runs


def _extract_legacy_doc_text(raw_bytes: bytes) -> str:
    candidates: list[str] = _extract_utf16le_ascii_runs(raw_bytes)
    for encoding in ("utf-16le", "cp1251", "latin-1"):
        try:
            decoded = raw_bytes.decode(encoding, errors="ignore")
        except Exception:
            continue
        decoded = decoded.replace("\x00", " ")
        parts = re.findall(r"[A-Za-zА-Яа-яЁёІіЎў0-9][A-Za-zА-Яа-яЁёІіЎў0-9 ,.;:()/%+\-]{8,}", decoded)
        cleaned_parts = [" ".join(part.split()) for part in parts]
        meaningful = [part for part in cleaned_parts if sum(ch.isalpha() for ch in part) >= 6]
        if meaningful:
            candidates.extend(meaningful[:40])

    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)

    text = " ".join(unique)
    return " ".join(text.split())


def _decode_resume_bytes(raw_bytes: bytes, file_name: str) -> str:
    name = (file_name or "").lower()
    if name.endswith(".pdf") or raw_bytes.startswith(b"%PDF"):
        extracted = _extract_pdf_text(raw_bytes)
        if extracted:
            return extracted
    if name.endswith(".doc"):
        extracted = _extract_legacy_doc_text(raw_bytes)
        if extracted:
            return extracted
    if name.endswith(".docx"):
        extracted = _extract_docx_text(raw_bytes)
        if extracted:
            return extracted
    for encoding in ("utf-8", "cp1251", "latin-1"):
        try:
            decoded = raw_bytes.decode(encoding)
            clean = " ".join(decoded.split())
            if clean:
                return clean
        except Exception:
            continue
    return ""


def format_story_snapshot(analysis: dict, lang: str) -> str:
    return _clip(
        "\n\n".join(
            [
                "=== Профиль ситуации ===",
                f"{t(lang, 'story_summary_label')}:\n{analysis.get('current_identity') or analysis.get('story_summary') or '-'}",
                f"{t(lang, 'skills_label')}:\n{_list_block(analysis.get('skills', []))}",
                f"{t(lang, 'constraints_label')}:\n{_list_block(analysis.get('constraints', []))}",
                f"{t(lang, 'goals_label')}:\n{_list_block(analysis.get('goals', []))}",
            ]
        )
    )


def _story_confirmation_text(analysis: dict, question_count: int) -> str:
    lines = ["Вот что я понял из вашей истории.", ""]

    facts: list[str] = []
    for source in [analysis.get("experience_snapshot", []), analysis.get("skills", []), analysis.get("goals", [])]:
        if not isinstance(source, list):
            continue
        for item in source:
            text = str(item or "").strip()
            if text and text not in facts:
                facts.append(text)
            if len(facts) >= 4:
                break
        if len(facts) >= 4:
            break

    if not facts:
        current_identity = str(analysis.get("current_identity") or analysis.get("story_summary") or "").strip()
        if current_identity:
            facts.append(current_identity)

    goals = analysis.get("goals", []) if isinstance(analysis.get("goals"), list) else []
    constraints = analysis.get("constraints", []) if isinstance(analysis.get("constraints"), list) else []
    skills = analysis.get("skills", []) if isinstance(analysis.get("skills"), list) else []

    main_request = str(goals[0]).strip() if goals else "Пока недостаточно данных, чтобы точно выделить главный запрос."
    main_constraint = str(constraints[0]).strip() if constraints else "Пока недостаточно данных, чтобы точно выделить ограничение."
    main_resource = str(skills[0]).strip() if skills else "Пока недостаточно данных, чтобы точно выделить ресурс."

    lines.append("Коротко по фактам:")
    lines.extend(f"- {item}" for item in facts[:4])
    lines.append("")
    lines.append(f"Главный запрос: {main_request}")
    lines.append(f"Ресурс: {main_resource}")
    lines.append(f"Ограничение: {main_constraint}")
    lines.append("")
    if question_count <= 0:
        lines.append("Данных уже достаточно для предварительной карты. Можно перейти к результату сразу или уточнить один критичный пункт позже.")
    elif question_count == 1:
        lines.append("Дальше задам 1 уточняющий вопрос и затем покажу маршруты.")
    else:
        lines.append(f"Дальше задам по одному уточняющему вопросу по критичным пробелам (сейчас вижу до {question_count} приоритетных пунктов).")
    return _clip("\n".join(lines), 1600)


def format_follow_up_questions(analysis: dict, lang: str) -> str:
    questions = analysis.get("follow_up_questions", [])
    numbered: list[str] = []
    for idx, row in enumerate(questions, start=1):
        if not isinstance(row, dict):
            numbered.append(f"{idx}. {row}")
            continue
        q_num = row.get("id", idx)
        try:
            q_num = int(q_num)
        except Exception:
            q_num = idx
        question_text = row.get("question", "-")
        options = row.get("options", [])
        numbered.append(f"{q_num}. {question_text}")
        if isinstance(options, list) and options:
            numbered.append("   варианты: " + " | ".join(str(item) for item in options[:10]))
    return _clip("\n".join(["=== Уточняющее интервью ===", "Ответьте коротко и по пунктам:", ""] + numbered + ["", t(lang, "questions_cta")]))


def _question_prompt(analysis: dict, index: int, lang: str) -> str:
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    total = len(questions)
    if total == 0:
        return t(lang, "questions_empty")
    safe_index = max(0, min(index, total - 1))
    row = questions[safe_index]
    if not isinstance(row, dict):
        return _clip(str(row))
    return _clip(str(row.get("question") or "-"))


def _questions_fast() -> list[dict[str, object]]:
    return [
        {
            "id": 1,
            "question": "Какая у вас сейчас главная цель на ближайшие 1-3 месяца?",
            "options": ["Быстро выйти на доход", "Найти стабильную работу", "Сменить сферу", "Перепаковать опыт"],
        },
        {
            "id": 2,
            "question": "Что сейчас главный барьер, который мешает двигаться?",
            "options": ["Язык", "Документы/право работать", "Страх отказов", "Нестабильный доход", "Неясный маршрут"],
        },
        {
            "id": 3,
            "question": "Что у вас сейчас с языком, документами и правом работать?",
            "options": list(LANGUAGE_DOCUMENTS_BUTTONS),
        },
        {
            "id": 4,
            "question": "Сколько времени вы уже живете в этой стране?",
            "options": ["Меньше 6 месяцев", "6-12 месяцев", "1-2 года", "Больше 2 лет"],
        },
        {
            "id": 5,
            "question": "Сколько ресурса и времени у вас сейчас на поиск и действия?",
            "options": ["Низкий ресурс, до 15 минут в день", "Средний ресурс, 30-60 минут", "Хороший ресурс, 1-2 часа"],
        },
    ]


def _questions_calm() -> list[dict[str, object]]:
    return [
        {"id": 1, "question": "Кем вы работали раньше и что в вашем опыте получается лучше всего?", "options": []},
        {"id": 2, "question": "Какой минимальный доход нужен в месяц, чтобы выдохнуть?", "options": list(_INTERVIEW_INCOME_INTERVAL_OPTIONS)},
        {
            "id": 3,
            "question": "Как быстро нужен первый стабильный доход?",
            "options": list(_INTERVIEW_INCOME_SPEED_OPTIONS),
        },
        {"id": 4, "question": "Какие языки вы знаете и на каком они сейчас уровне?", "options": []},
        {"id": 5, "question": "Какие ограничения важно учитывать: дети, документы, здоровье, график, переезды?", "options": []},
        {"id": 6, "question": "Какие направления вам сейчас кажутся хотя бы немного возможными?", "options": []},
        {
            "id": 7,
            "question": "Какая поддержка у вас есть сейчас?",
            "options": ["семья", "друзья", "профконтакты", "сообщество", "пока почти нет поддержки"],
        },
        {"id": 8, "question": "Что сейчас мешает сильнее всего: страх, усталость, хаос, язык или неясность маршрута?", "options": ["страх", "усталость", "хаос", "язык", "неясность маршрута"]},
    ]


def _questions_support() -> list[dict[str, object]]:
    return [
        {
            "id": 1,
            "question": "Что сейчас больше всего тревожит: деньги, работа, язык, страх отказов, усталость, дети, документы или одиночество?",
            "options": ["деньги", "работа", "язык", "страх отказов", "усталость", "дети", "документы", "одиночество"],
        },
        {"id": 2, "question": "Какой минимальный доход нужен в месяц?", "options": list(_INTERVIEW_INCOME_INTERVAL_OPTIONS)},
        {
            "id": 3,
            "question": "Как быстро нужен доход?",
            "options": list(_INTERVIEW_INCOME_SPEED_OPTIONS),
        },
        {"id": 4, "question": "Какие языки и уровень?", "options": []},
        {"id": 5, "question": "Чего точно не хотите делать?", "options": []},
        {"id": 6, "question": "Какие варианты работы вам кажутся хоть немного возможными?", "options": []},
        {"id": 7, "question": "Сколько часов в неделю реально готовы уделять поиску или обучению?", "options": list(_INTERVIEW_TIME_INTERVAL_OPTIONS)},
        {
            "id": 8,
            "question": "Как вы живёте и адаптируетесь в новой стране: кто рядом, какие барьеры, есть ли сообщество?",
            "options": ["семья", "друзья", "профконтакты", "сообщество", "пока никто"],
        },
    ]


def _questions_deep_route() -> list[dict[str, object]]:
    return [
        {"id": 1, "question": "Какая цель на ближайшие 3 месяца и как вы поймете, что цель достигнута?", "options": []},
        {"id": 2, "question": "Какие 2-3 роли на рынке кажутся вам реалистичными прямо сейчас?", "options": []},
        {"id": 3, "question": "Какие барьеры критичны: язык, документы, график, здоровье, дети, финансы?", "options": []},
        {"id": 4, "question": "Какие результаты и цифры из опыта вы уже можете показать в CV/профиле?", "options": []},
        {"id": 5, "question": "Какие навыки нужно усилить в первую очередь, чтобы повысить шанс интервью?", "options": []},
    ]


SEGMENT_WORKER = "worker_production"
SEGMENT_SERVICE = "service_care"
SEGMENT_LOGISTICS = "logistics_transport"
SEGMENT_OFFICE = "office_staff"
SEGMENT_SPECIALIST = "specialist_expert"
SEGMENT_LEADER = "leader"
SEGMENT_ENTREPRENEUR = "entrepreneur"


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().replace("ё", "е").split())


def _detect_user_segment(story_text: str, analysis: dict | None = None) -> str:
    raw = [story_text]
    if isinstance(analysis, dict):
        raw.append(str(analysis.get("story_summary", "")))
        raw.append(str(analysis.get("current_identity", "")))
        raw.extend(str(item) for item in analysis.get("experience_snapshot", []) if isinstance(item, str))
    text = _normalize_text("\n".join(raw))

    entrepreneur_markers = (
        "предприним", "собственн", "свой бизнес", "ип", "фоп", "founder", "startup", "бизнес"
    )
    leader_markers = (
        "руковод", "началь", "директор", "team lead", "head of", "управлял команд", "менеджер отдела"
    )
    worker_markers = (
        "свар", "монтаж", "слесар", "токар", "электрик", "строит", "производств", "цех", "завод", "шве", "станок"
    )
    service_markers = (
        "сидел", "уход", "няня", "caregiver", "медсестр", "санитар", "официант", "бариста", "повар", "салон", "beauty"
    )
    logistics_markers = (
        "водител", "курьер", "доставка", "логист", "склад", "warehouse", "погрузчик", "forklift", "экспедитор", "транспорт"
    )
    office_markers = (
        "офис", "документооборот", "секретар", "администратор", "ассистент", "бухгалтер", "back-office", "operations coordinator"
    )
    specialist_markers = (
        "аналит", "разработ", "инженер", "маркетолог", "юрист", "дизайнер", "архитектор", "эксперт", "специалист"
    )

    if any(marker in text for marker in entrepreneur_markers):
        return SEGMENT_ENTREPRENEUR
    if any(marker in text for marker in leader_markers):
        return SEGMENT_LEADER
    if any(marker in text for marker in worker_markers):
        return SEGMENT_WORKER
    if any(marker in text for marker in logistics_markers):
        return SEGMENT_LOGISTICS
    if any(marker in text for marker in service_markers):
        return SEGMENT_SERVICE
    if any(marker in text for marker in office_markers):
        return SEGMENT_OFFICE
    if any(marker in text for marker in specialist_markers):
        return SEGMENT_SPECIALIST
    return SEGMENT_SPECIALIST


def _segment_label(segment: str) -> str:
    labels = {
        SEGMENT_WORKER: "Рабочие профессии и производство",
        SEGMENT_SERVICE: "Сервис и уход за людьми",
        SEGMENT_LOGISTICS: "Логистика и транспорт",
        SEGMENT_OFFICE: "Офисные сотрудники",
        SEGMENT_SPECIALIST: "Специалисты и эксперты",
        SEGMENT_LEADER: "Руководители",
        SEGMENT_ENTREPRENEUR: "Предприниматели",
    }
    return labels.get(segment, labels[SEGMENT_SPECIALIST])


def _segment_common_questions() -> list[dict[str, object]]:
    return [
        {"id": 1, "question": "Какой минимальный доход вам нужен в месяц?", "options": list(_INTERVIEW_INCOME_INTERVAL_OPTIONS)},
        {
            "id": 2,
            "question": "Как быстро нужен первый стабильный доход?",
            "options": list(_INTERVIEW_INCOME_SPEED_OPTIONS),
        },
        {"id": 3, "question": "Какие языки вы знаете и на каком уровне?", "options": []},
        {"id": 4, "question": "Сколько часов в неделю вы реально готовы выделять на поиск работы или обучение?", "options": list(_INTERVIEW_TIME_INTERVAL_OPTIONS)},
    ]


def _interval_options_for_question(question_text: str) -> list[str]:
    q_text = str(question_text or "").lower().replace("ё", "е")
    if "как быстро" in q_text and "доход" in q_text:
        return list(_INTERVIEW_INCOME_SPEED_OPTIONS)

    income_markers = ["доход", "минимальный доход", "минимум", "нужен доход", "нужен минимальный доход", "доход в месяц", "доход нужен"]
    if any(marker in q_text for marker in income_markers) and any(token in q_text for token in ["миним", "нуж", "месяц", "доход"]):
        return list(_INTERVIEW_INCOME_INTERVAL_OPTIONS)

    time_markers = ["сколько часов", "часов в неделю", "времени в неделю", "график", "обучению", "обучение", "поиск работы", "учиться"]
    if any(marker in q_text for marker in time_markers) and any(token in q_text for token in ["час", "врем", "учит", "обуч", "поиск", "работ"]):
        return list(_INTERVIEW_TIME_INTERVAL_OPTIONS)
    return []


def _normalize_question_options(question_text: str, options: list[object] | None) -> list[str]:
    raw = options if isinstance(options, list) else []
    cleaned = [str(item).strip() for item in raw if str(item).strip()]
    if cleaned:
        return cleaned
    return _interval_options_for_question(question_text)


def _segment_questions(segment: str) -> list[dict[str, object]]:
    if segment == SEGMENT_WORKER:
        return [
            {"id": 1, "question": "Что у вас лучше всего получается руками или в производственной работе?", "options": []},
            {"id": 2, "question": "С каким оборудованием, инструментами или техникой вы уже работали?", "options": []},
            {"id": 3, "question": "Есть ли у вас права, сертификаты, допуски или лицензии?", "options": []},
            {"id": 4, "question": "Готовы ли вы к сменной работе? Какой график вам подходит?", "options": ["готов(а) к сменам", "только дневной", "гибкий график"]},
            {"id": 5, "question": "Готовы ли вы к переезду или к работе в соседнем городе?", "options": ["да", "нет", "только в пределах региона"]},
            {"id": 6, "question": "Был ли у вас опыт обучения новичков, старшинства или управления бригадой?", "options": []},
        ]
    if segment == SEGMENT_SERVICE:
        return [
            {"id": 1, "question": "В какой сфере сервиса, ухода или помощи людям у вас больше всего опыта?", "options": []},
            {"id": 2, "question": "С какими людьми вам комфортнее работать?", "options": ["дети", "взрослые", "пожилые", "клиенты в сервисе"]},
            {"id": 3, "question": "Какие задачи у вас получаются лучше всего: уход, сервис, организация или общение?", "options": []},
            {"id": 4, "question": "Есть ли у вас профильные курсы, сертификаты или медкнижка?", "options": []},
            {"id": 5, "question": "Готовы ли вы к сменному графику и работе в выходные?", "options": ["да", "нет", "частично"]},
            {"id": 6, "question": "Что вы готовы изучить в ближайшие 1-2 месяца, чтобы вырасти в доходе или роли?", "options": []},
        ]
    if segment == SEGMENT_LOGISTICS:
        return [
            {"id": 1, "question": "Какой у вас опыт в логистике, транспорте, доставке или на складе?", "options": []},
            {"id": 2, "question": "Какие категории прав и допуски у вас есть?", "options": []},
            {"id": 3, "question": "С какими системами, маршрутами или форматами работы вы уже сталкивались?", "options": []},
            {"id": 4, "question": "Готовы ли вы к ночным сменам, рейсам или плавающему графику?", "options": ["да", "нет", "частично"]},
            {"id": 5, "question": "Был ли у вас опыт координации перевозок, смены или склада?", "options": []},
            {"id": 6, "question": "В какую роль вы хотели бы вырасти дальше?", "options": []},
        ]
    if segment == SEGMENT_OFFICE:
        return [
            {"id": 1, "question": "Какие офисные процессы вы вели: документы, отчёты, координация, поддержка клиентов?", "options": []},
            {"id": 2, "question": "Какими инструментами вы уверенно пользуетесь?", "options": []},
            {"id": 3, "question": "Какой формат вам ближе: back-office, ассистент, администрирование или координатор?", "options": []},
            {"id": 4, "question": "Какие задачи хотите исключить из новой роли?", "options": []},
            {"id": 5, "question": "Какой формат работы вам подходит: офис, гибрид или удалённо?", "options": ["офис", "гибрид", "удаленно"]},
            {"id": 6, "question": "Был ли у вас опыт обучения коллег или координации небольшой команды?", "options": []},
        ]
    if segment == SEGMENT_LEADER:
        return [
            {"id": 1, "question": "Расскажите о рабочей ситуации, которой вы особенно гордитесь (по возможности в логике STAR).", "options": []},
            {"id": 2, "question": "Какую сложную проблему вы решили как руководитель? Что именно сделали?", "options": []},
            {"id": 3, "question": "Когда вам приходилось организовывать людей или процессы в сложной ситуации?", "options": []},
            {"id": 4, "question": "Какой масштаб команды/бюджета/зоны ответственности у вас был?", "options": []},
            {"id": 5, "question": "Когда вы обучали или наставляли других? Какой был результат?", "options": []},
            {"id": 6, "question": "Какую управленческую роль вы хотите рассматривать сейчас как основную?", "options": []},
        ]
    if segment == SEGMENT_ENTREPRENEUR:
        return [
            {"id": 1, "question": "Расскажите о бизнес-ситуации, где вы получили заметный результат (по возможности в логике STAR).", "options": []},
            {"id": 2, "question": "Какую самую сложную проблему в бизнесе вам удалось решить?", "options": []},
            {"id": 3, "question": "Как вы выстраивали людей, процессы или продажи?", "options": []},
            {"id": 4, "question": "Какие свои сильные компетенции вы хотите монетизировать в новой стране в первую очередь?", "options": []},
            {"id": 5, "question": "Готовы ли вы параллельно рассматривать найм для стабилизации дохода?", "options": ["да", "нет", "только временно"]},
            {"id": 6, "question": "В какой модели вам сейчас ближе двигаться: услуги, микро-бизнес, партнёрство или консультации?", "options": []},
        ]
    return [
        {"id": 1, "question": "Расскажите о рабочей ситуации, которой вы особенно гордитесь (по возможности в логике STAR).", "options": []},
        {"id": 2, "question": "Какую сложную проблему вы решали и за счет чего получилось?", "options": []},
        {"id": 3, "question": "Когда вам приходилось организовывать людей или процессы?", "options": []},
        {"id": 4, "question": "Когда вы обучали или наставляли других?", "options": []},
        {"id": 5, "question": "В какой тип задач сейчас хотите вложить максимум усилий?", "options": []},
        {"id": 6, "question": "Какие ограничения нужно учесть, чтобы выйти на доход без срыва?", "options": []},
    ]


def _mandatory_psych_social_questions() -> list[dict[str, object]]:
    return [
        # 1. Psychological barriers — multi-select, expanded
        {
            "question": "Что сейчас сильнее всего мешает начать? Выберите до 3 пунктов.",
            "options": [
                "😰 Страх отказа",
                "😶 Паралич — понимаю что надо, но не делаю",
                "🧩 Нет ясности, с чего начать",
                "⏳ Откладываю",
                "🪫 Мало сил",
                _INTERVIEW_PSYCH_DONE,
            ],
            "multi_key": "psych",
            "done_text": _INTERVIEW_PSYCH_DONE,
            "max_select": 3,
            "force_options_keyboard": True,
        },
        # 2. Emotional state right now — multi-select (NEW)
        {
            "question": "Как вы сейчас чувствуете себя в карьерной ситуации? Выберите всё, что подходит.",
            "options": [
                "✅ Есть план",
                "↕️ Бывают просадки",
                "🐢 Нужен щадящий темп",
                "🌀 Много неопределенности",
                "😔 Тревожно",
                "✅ Готово",
            ],
            "multi_key": "psych_state",
            "done_text": "✅ Готово",
            "max_select": 3,
            "force_options_keyboard": True,
        },
        # 3. Social support & context — multi-select, expanded
        {
            "question": "Что из этого сейчас про вас? Можно выбрать несколько пунктов.",
            "options": [
                "👨‍👩‍👧 Есть близкие рядом",
                "👥 Есть друзья/коллеги",
                "💼 Есть профессиональные контакты",
                "🌫 Почти без поддержки",
                "🗣 Мешает язык",
                "😔 Есть изоляция",
                _INTERVIEW_SOCIAL_DONE,
            ],
            "multi_key": "social",
            "done_text": _INTERVIEW_SOCIAL_DONE,
            "max_select": 4,
            "force_options_keyboard": True,
        },
        # 4. Coping strategies — multi-select (NEW)
        {
            "question": "Что помогает справляться со стрессом? Выберите до 3 вариантов.",
            "options": [
                "📋 Чёткий список задач",
                "👤 Поддержка рядом",
                "🏃 Физическая активность",
                "🔎 Понятен следующий шаг",
                "⏱ Задачи 5-15 минут",
                "🧘 Отдых и восстановление",
                "✅ Готово",
            ],
            "multi_key": "coping",
            "done_text": "✅ Готово",
            "max_select": 3,
            "force_options_keyboard": True,
        },
        # 5. Energy sources — multi-select, expanded
        {
            "question": "Что даёт вам больше всего энергии в работе? Можно выбрать до 5 вариантов.",
            "options": [
                "Работа с людьми",
                "Помощь людям",
                "Обучение",
                "Организация процессов",
                "Управление",
                "Творчество",
                "Анализ",
                "Техника / работа руками",
                "Исследования",
                "Продажи",
                "Проведение мероприятий",
                "Системная работа за компьютером",
                _INTERVIEW_ENERGY_DONE,
            ],
            "multi_key": "energy",
            "done_text": _INTERVIEW_ENERGY_DONE,
            "max_select": 5,
            "force_options_keyboard": True,
        },
        # 6. Time in country — single factual choice
        {
            "question": "Сколько времени вы уже живёте в этой стране?",
            "options": [
                "Меньше 6 месяцев",
                "6–12 месяцев",
                "1–2 года",
                "Больше 2 лет",
            ],
        },
        # 7. Integration — multi-select, expanded
        {
            "question": "Что из этого уже есть у вас в новой стране? Можно выбрать до 5 пунктов.",
            "options": [
                "Использую местный язык в быту",
                "Использую язык на работе или в поиске работы",
                "Есть местные знакомые или друзья",
                "Есть профессиональные контакты",
                "Участвую в сообществах или группах",
                "Понимаю, как устроен рынок труда",
                "Открыл(а) счёт / наладил(а) базовый быт",
                "Знаком(а) с правами работника в этой стране",
                _INTERVIEW_INTEGRATION_DONE,
            ],
            "multi_key": "integration",
            "done_text": _INTERVIEW_INTEGRATION_DONE,
            "max_select": 5,
            "force_options_keyboard": True,
        },
        # 8. Career priorities — multi-select (existing, unchanged)
        {
            "question": "Что для вас сейчас важнее всего в карьере? Можно выбрать до 4 пунктов.",
            "options": [
                "Быстро выйти на доход",
                "Сохранить профессиональный статус",
                "Сменить профессию",
                "Открыть собственное дело",
                "Работать удаленно",
                "Работать по специальности",
                "Повысить доход",
                "Найти устойчивость и баланс",
                _INTERVIEW_PRIORITIES_DONE,
            ],
            "multi_key": "priorities",
            "done_text": _INTERVIEW_PRIORITIES_DONE,
            "max_select": 4,
            "force_options_keyboard": True,
        },
    ]


def _required_diagnostic_questions() -> list[dict[str, object]]:
    required: list[dict[str, object]] = []
    for row in _mandatory_psych_social_questions():
        if not isinstance(row, dict):
            continue
        key = str(row.get("multi_key") or "").strip()
        if key in _HARD_REQUIRED_MULTI_KEYS:
            required.append(dict(row))
    return required


def _ensure_required_blocks(normalized: list[dict[str, object]], mode_key: str) -> list[dict[str, object]]:
    if mode_key == "fast":
        return normalized
    required_rows = _required_diagnostic_questions()
    if not required_rows:
        return normalized

    required_by_key = {
        str(row.get("multi_key") or "").strip(): row
        for row in required_rows
        if isinstance(row, dict) and str(row.get("multi_key") or "").strip()
    }

    existing_by_key = {
        str(row.get("multi_key") or "").strip(): idx
        for idx, row in enumerate(normalized)
        if isinstance(row, dict) and str(row.get("multi_key") or "").strip()
    }

    for key in _HARD_REQUIRED_MULTI_KEYS:
        if key in existing_by_key:
            continue

        replacement = required_by_key.get(key)
        if not replacement:
            continue
        replacement_row = dict(replacement)
        q_text = str(replacement_row.get("question") or "").strip() or f"Вопрос {len(normalized) + 1}"
        opts = replacement_row.get("options", []) if isinstance(replacement_row.get("options", []), list) else []
        replacement_row.setdefault("question", q_text)
        replacement_row.setdefault("options", [str(item).strip() for item in opts if str(item).strip()])
        replacement_row.setdefault("question_id", _slugify(q_text))
        replacement_row.setdefault("allowed_button_ids", [])
        replacement_row.setdefault("allowed_button_map", {})
        replacement_row.setdefault("expected_answer_type", _expected_answer_type(replacement_row))
        replacement_row.setdefault("semantic_intent", _question_semantic_intent(q_text))
        replacement_row.setdefault("source", "hard_required")
        replacement_row.setdefault("validity_status", "needs_confirmation")

        inserted = False
        for idx in range(len(normalized) - 1, -1, -1):
            row = normalized[idx]
            row_key = str(row.get("multi_key") or "").strip()
            if row_key not in _HARD_REQUIRED_MULTI_KEYS:
                normalized[idx] = replacement_row
                inserted = True
                break
        if not inserted:
            normalized.append(replacement_row)

    deduped: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    for row in normalized:
        row_key = str(row.get("multi_key") or "").strip()
        if row_key in _HARD_REQUIRED_MULTI_KEYS:
            if row_key in seen_keys:
                continue
            seen_keys.add(row_key)
        deduped.append(row)
    return deduped


def _extract_int_values(text: str) -> list[int]:
    compact = re.sub(r"[^0-9]", " ", text or "")
    values: list[int] = []
    for token in compact.split():
        try:
            values.append(int(token))
        except Exception:
            continue
    return values


def _looks_like_money_answer(text: str) -> bool:
    low = (text or "").lower()
    numbers = _extract_int_values(low)
    if not numbers:
        return False
    if any(token in low for token in ["евро", "euro", "eur", "usd", "$", "pln", "zl", "зл", "руб", "грн", "byn"]):
        return True
    # Values in this range are typically salary answers rather than time windows.
    return max(numbers) >= 200


def _looks_like_duration_answer(text: str) -> bool:
    low = (text or "").lower().strip()
    if not low:
        return False
    if any(token in low for token in ["нед", "меся", "дн", "день", "дня", "срочно", "как можно скорее", "год"]):
        return True
    if re.search(r"\b\d+\s*[-–]\s*\d+\b", low):
        return True
    nums = _extract_int_values(low)
    if nums and max(nums) <= 12:
        # Allow concise answers like "3" for months when user answers briefly.
        return True
    return False



def _known_story_fields(story_text: str) -> set[str]:
    low = (story_text or "").lower()
    known: set[str] = set()
    if any(token in low for token in ["доход", "зарплат", "евро", "pln", "zl", "зл"]) and _extract_int_values(low):
        known.add("income")
    if any(token in low for token in ["2-4", "2–4", "недел", "месяц", "срочно"]):
        known.add("speed")
    if any(token in low for token in ["язык", "english", "polish", "русск", "украин", "b1", "a2", "c1"]):
        known.add("languages")
    if any(token in low for token in ["документ", "график", "ребен", "дет", "здоров", "физич", "огранич"]):
        known.add("constraints")
    if any(token in low for token in ["офис", "hr", "back-office", "поддержк", "сфера", "направлен"]):
        known.add("directions")
    if any(token in low for token in ["поддерж", "семья", "друз", "контакт"]):
        known.add("support")
    if any(token in low for token in ["сообще", "интеграц", "адаптац", "местн", "клуб", "группа", "community"]):
        known.add("integration")
    return known


def _country_duration_category(text: str) -> str:
    low = _normalize_text(text)
    if not low:
        return ""
    if "полтора" in low or "1.5" in low:
        return "1_2_years"
    if any(token in low for token in ["меньше 6 месяцев", "менее 6 месяцев", "до 6 месяцев"]):
        return "lt_6_months"
    if any(token in low for token in ["6-12 месяцев", "6–12 месяцев", "6 12 месяцев", "6-12 мес", "6–12 мес"]):
        return "6_12_months"
    if any(token in low for token in ["1-2 года", "1–2 года", "1 2 года"]):
        return "1_2_years"
    if any(token in low for token in ["больше 2 лет", "более 2 лет", "свыше 2 лет"]):
        return "gt_2_years"

    years_match = re.search(r"(\d{1,2})\s*(?:лет|года|год)", low)
    if years_match:
        try:
            years = int(years_match.group(1))
            if years < 1:
                return "lt_6_months"
            if years <= 2:
                return "1_2_years"
            return "gt_2_years"
        except Exception:
            return ""
    return ""


def _country_duration_label(category: str) -> str:
    mapping = {
        "lt_6_months": "меньше 6 месяцев",
        "6_12_months": "6–12 месяцев",
        "1_2_years": "1–2 года",
        "gt_2_years": "больше 2 лет",
    }
    return mapping.get(category, "")


def _extract_story_country_duration(story_text: str) -> str:
    return _country_duration_category(str(story_text or ""))


def _extract_selected_country_duration(data: dict, answers_text: str) -> str:
    qa_answers = data.get("qa_answers") if isinstance(data.get("qa_answers"), list) else []
    for row in qa_answers:
        if not isinstance(row, dict):
            continue
        q = _normalize_text(str(row.get("question") or ""))
        a = str(row.get("answer") or "")
        if "сколько времени" in q and "стране" in q:
            category = _country_duration_category(a)
            if category:
                return category
    return _country_duration_category(str(answers_text or ""))


def _reconcile_country_duration(story_text: str, data: dict, answers_text: str) -> tuple[str, str, str]:
    story_category = _extract_story_country_duration(story_text)
    selected_category = _extract_selected_country_duration(data, answers_text)
    if not story_category:
        return answers_text, "", ""

    story_label = _country_duration_label(story_category)
    if selected_category and selected_category != story_category:
        note = (
            "Вижу расхождение: в истории указано полтора года, а в ответах выбран другой срок.\n\n"
            "Для маршрута беру полтора года. Если это ошибка — поправьте."
        )
        merged = (
            str(answers_text or "").strip()
            + f"\n\n[ПРИОРИТЕТ ФАКТА]\nСрок проживания в стране (основной): {story_label}."
        ).strip()
        return merged, note, story_label

    return answers_text, "", story_label


def _filter_known_questions(questions: list[dict[str, object]], story_text: str) -> list[dict[str, object]]:
    known = _known_story_fields(story_text)
    if not known:
        return questions
    filtered: list[dict[str, object]] = []
    for row in questions:
        q_low = str(row.get("question", "")).lower()
        if "доход" in q_low and "income" in known:
            continue
        if "быстро" in q_low and "speed" in known:
            continue
        if "язык" in q_low and "languages" in known:
            continue
        if any(token in q_low for token in ["огранич", "дет", "здоров", "документ"]) and "constraints" in known:
            continue
        if any(token in q_low for token in ["направлен", "сферы"]) and "directions" in known:
            continue
        if "поддерж" in q_low and "support" in known:
            continue
        if any(token in q_low for token in ["интеграц", "сообще", "адаптац", "барьер"]) and "integration" in known:
            continue
        filtered.append(row)
    return filtered


def _question_id(question_row: dict | object, default_index: int) -> int:
    if isinstance(question_row, dict):
        try:
            return int(question_row.get("id", default_index + 1))
        except Exception:
            return default_index + 1
    return default_index + 1


def _build_decision_layers(data: dict, story_analysis: dict | None, answers_text: str) -> dict[str, list[str]]:
    analysis = story_analysis if isinstance(story_analysis, dict) else {}
    qa_answers = data.get("qa_answers") if isinstance(data.get("qa_answers"), list) else []
    profile = data.get("interaction_profile") if isinstance(data.get("interaction_profile"), dict) else {}
    route_context = data.get("route_context") if isinstance(data.get("route_context"), dict) else {}

    def _append_unique(target: list[str], value: str) -> None:
        text = str(value or "").strip()
        if text and text not in target:
            target.append(text)

    career_profile: list[str] = []
    constraints: list[str] = []
    psychological_state: list[str] = []
    action_capacity: list[str] = []
    route_preferences: list[str] = []

    _append_unique(career_profile, f"Текущая идентичность: {str(analysis.get('current_identity', '')).strip() or 'данных недостаточно'}")
    for item in analysis.get("experience_snapshot", []) if isinstance(analysis.get("experience_snapshot"), list) else []:
        _append_unique(career_profile, f"Опыт: {item}")

    for row in qa_answers:
        if not isinstance(row, dict):
            continue
        question = str(row.get("question", "")).lower()
        answer = str(row.get("answer", "")).strip()
        signal = str(row.get("signal", "")).strip().lower()
        if signal:
            _append_unique(psychological_state, f"Сигнал: {signal}")
        if "язык" in question:
            _append_unique(career_profile, f"Язык: {answer}")
        if any(token in question for token in ["документ", "право работать", "разрешен", "лиценз", "допуск"]):
            _append_unique(career_profile, f"Документы/право работать: {answer}")
        if any(token in question for token in ["цель", "роль", "направлен", "варианты работы"]):
            _append_unique(career_profile, f"Реальная цель пользователя: {answer}")
        if "доход" in question:
            _append_unique(constraints, f"Доходная цель/финансовая необходимость: {answer}")
        if any(token in question for token in ["сколько часов", "времени", "график"]):
            _append_unique(constraints, f"Доступное время: {answer}")
        if any(token in question for token in ["рынок", "ваканс", "конкурен", "спрос"]):
            _append_unique(constraints, f"Рынок: {answer}")
        if any(token in question for token in ["риск", "страх"]):
            _append_unique(constraints, f"Готовность к риску: {answer}")
        if any(token in question for token in ["тревож", "устал", "сомне", "не знаю, с чего начать", "перегруз", "стресс"]):
            _append_unique(psychological_state, answer)

    for marker in data.get("selected_psych_markers", []) if isinstance(data.get("selected_psych_markers"), list) else []:
        _append_unique(psychological_state, str(marker))

    for state_item in data.get("selected_psych_state", []) if isinstance(data.get("selected_psych_state"), list) else []:
        _append_unique(psychological_state, f"Эмоциональное состояние: {state_item}")

    for coping_item in data.get("selected_coping", []) if isinstance(data.get("selected_coping"), list) else []:
        _append_unique(action_capacity, f"Стратегия совладания: {coping_item}")

    for social_item in data.get("selected_social_state", []) if isinstance(data.get("selected_social_state"), list) else []:
        _append_unique(psychological_state, f"Соцконтекст: {social_item}")

    choice_reasons = data.get("selected_choice_reasons") if isinstance(data.get("selected_choice_reasons"), dict) else {}
    for choice, reason in choice_reasons.items():
        c = str(choice or "").strip()
        r = str(reason or "").strip()
        if c and r:
            _append_unique(career_profile, f"Причина выбора «{c}»: {r}")

    if route_context:
        country = str(route_context.get("country") or "").strip()
        city = str(route_context.get("city") or "").strip()
        if country or city:
            _append_unique(career_profile, f"География: {', '.join(item for item in [country, city] if item)}")
        if str(route_context.get("current_language_level") or "").strip():
            _append_unique(constraints, f"Текущий уровень языка: {route_context.get('current_language_level')}")
        if str(route_context.get("target_language") or "").strip():
            _append_unique(route_preferences, f"Целевой язык: {route_context.get('target_language')}")
        if str(route_context.get("income_urgency") or "").strip():
            _append_unique(constraints, f"Срочность дохода: {route_context.get('income_urgency')}")
        if str(route_context.get("minimum_monthly_income") or "").strip():
            _append_unique(constraints, f"Минимальный доход: {route_context.get('minimum_monthly_income')}")
        if str(route_context.get("desired_monthly_income") or "").strip():
            _append_unique(route_preferences, f"Желаемый доход: {route_context.get('desired_monthly_income')}")
        if str(route_context.get("training_budget") or "").strip():
            _append_unique(constraints, f"Бюджет на обучение: {route_context.get('training_budget')}")
        if str(route_context.get("available_time_for_study") or "").strip():
            _append_unique(action_capacity, f"Время на обучение: {route_context.get('available_time_for_study')}")
        if str(route_context.get("career_goal_type") or "").strip():
            _append_unique(career_profile, f"Карьерная цель: {route_context.get('career_goal_type')}")
        if str(route_context.get("work_preferences") or "").strip():
            _append_unique(route_preferences, f"Формат работы: {route_context.get('work_preferences')}")
        if str(route_context.get("health_or_schedule_limits") or "").strip():
            _append_unique(constraints, f"Ограничения по графику/здоровью: {route_context.get('health_or_schedule_limits')}")
        if str(route_context.get("documents_and_work_rights") or "").strip():
            _append_unique(constraints, f"Документы и право на работу: {route_context.get('documents_and_work_rights')}")
        if str(route_context.get("diploma_status") or "").strip():
            _append_unique(career_profile, f"Статус диплома: {route_context.get('diploma_status')}")
        if str(route_context.get("portfolio_or_references") or "").strip():
            _append_unique(career_profile, f"Портфолио / рекомендации: {route_context.get('portfolio_or_references')}")

    answers_low = str(answers_text or "").lower().replace("ё", "е")
    if any(token in answers_low for token in ["не знаю, с чего начать", "не знаю с чего начать", "слишком сложно", "устал", "тревог", "сомне"]):
        _append_unique(psychological_state, "Эмоциональный перегруз/неопределенность")

    pace = str(profile.get("pace") or data.get("pace") or "normal")
    support_need = str(profile.get("support_need") or data.get("support_need") or "medium")
    detail_pref = str(profile.get("detail_preference") or data.get("detail_preference") or "balanced")
    _append_unique(action_capacity, f"Темп: {pace}")
    _append_unique(action_capacity, f"Потребность в поддержке: {support_need}")
    _append_unique(action_capacity, f"Размер шага: {detail_pref}")

    if not constraints:
        _append_unique(constraints, "Данных о изменении ограничений пока недостаточно")
    if not psychological_state:
        _append_unique(psychological_state, "Стабильное состояние без явного перегруза")

    return {
        "career_profile": career_profile[:10],
        "constraints": constraints[:10],
        "psychological_state": psychological_state[:10],
        "action_capacity": action_capacity[:8],
        "route_preferences": route_preferences[:8],
    }


def _top_strategy_roles(report: dict[str, object], limit: int = 4) -> list[str]:
    roles: list[str] = []
    market = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
    recommendations = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}

    def _add(value: object) -> None:
        text = str(value or "").strip()
        if text and text not in roles:
            roles.append(text)

    for item in market:
        if isinstance(item, dict):
            _add(item.get("profession"))
        if len(roles) >= limit:
            return roles[:limit]

    for item in recommendations:
        if isinstance(item, dict):
            _add(item.get("title"))
        if len(roles) >= limit:
            return roles[:limit]

    _add(decision.get("recommended_main_path"))
    _add(decision.get("backup_path"))
    # No fallback: empty roles means the report has no confirmed routes yet.
    return roles[:limit]


def _extract_years_in_profession(report: dict[str, object], route_context: dict[str, str]) -> int:
    candidates: list[str] = []
    for key in ("years_in_profession", "profile_years", "experience_years"):
        value = route_context.get(key)
        if value:
            candidates.append(str(value))

    facts_only = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
    for bucket in ("explicit_facts", "resume_facts"):
        items = facts_only.get(bucket) if isinstance(facts_only.get(bucket), list) else []
        for item in items:
            candidates.append(str(item or ""))

    story_blob = " ".join(
        [
            str(((report.get("digital_human") or {}) if isinstance(report.get("digital_human"), dict) else {}).get("current_state") or ""),
            str(((report.get("digital_human") or {}) if isinstance(report.get("digital_human"), dict) else {}).get("previous_identity") or ""),
        ]
    )
    if story_blob:
        candidates.append(story_blob)

    max_years = 0
    pattern = re.compile(r"(\d{1,2})\s*\+?\s*(?:лет|года|год|years?)", re.IGNORECASE)
    for text in candidates:
        for match in pattern.finditer(str(text or "")):
            try:
                max_years = max(max_years, int(match.group(1)))
            except Exception:
                continue
    return max_years


def _wants_return_to_profession(report: dict[str, object], route_context: dict[str, str]) -> bool:
    chunks = [
        str(route_context.get("career_goal_type") or ""),
        str(route_context.get("work_preferences") or ""),
        str((report.get("career_decision") or {}).get("why_this_path") if isinstance(report.get("career_decision"), dict) else ""),
        str((report.get("career_decision") or {}).get("decision_summary") if isinstance(report.get("career_decision"), dict) else ""),
    ]

    facts_only = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
    for bucket in ("explicit_facts", "inferences"):
        items = facts_only.get(bucket) if isinstance(facts_only.get(bucket), list) else []
        chunks.extend(str(item or "") for item in items)

    blob = " ".join(chunks).lower().replace("ё", "е")
    markers = [
        "вернуться в профес",
        "вернуться по профес",
        "по специальност",
        "сохранить профессиональный статус",
        "ближе к моему опыту",
        "вернуться в строительную сфер",
        "работать по профилю",
    ]
    return any(marker in blob for marker in markers)


def _is_generic_assistant_role(role: str) -> bool:
    text = str(role or "").strip().lower().replace("ё", "е")
    if not text:
        return True
    parts = [part.strip() for part in text.split("/") if part.strip()]
    if len(parts) > 1:
        # If every slash-separated fragment is generic assistant/back-office, treat whole role as generic.
        if all(_is_generic_assistant_role(part) for part in parts):
            return True
    if "administrative assistant" in text and "construction" not in text and "engineering" not in text:
        return True
    if "generic back-office specialist" in text:
        return True
    if text == "back-office specialist":
        return True
    return False


def _professional_bridge_goal_pack(profile_domain: str) -> tuple[str, str]:
    if profile_domain == "construction_engineering_cost_estimation":
        return (
            "сохранить доход и начать возвращение в строительную сферу",
            "выйти на assistant / junior роль рядом со сметами, строительной документацией или project coordination",
        )
    return (
        "сохранить доход и начать возвращение в профессиональную сферу",
        "выйти на assistant / junior роль рядом с профильными задачами, документацией или project coordination",
    )


def _build_fast_income_bundle(report: dict[str, object], route_context: dict[str, str]) -> dict[str, object]:
    roles = _top_strategy_roles(report, 4)
    market = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    profile_domain = str(report.get("profile_domain") or "").strip()
    years_in_profession = _extract_years_in_profession(report, route_context)
    wants_return = _wants_return_to_profession(report, route_context)
    is_professional_bridge = years_in_profession >= 5 and wants_return

    if is_professional_bridge:
        filtered_roles = [role for role in roles if not _is_generic_assistant_role(role)]
        if profile_domain == "construction_engineering_cost_estimation":
            for role in _CONSTRUCTION_BRIDGE_ROLES:
                if role not in filtered_roles:
                    filtered_roles.append(role)
        roles = (filtered_roles or roles)[:5]

    country = str(route_context.get("country") or "").strip()
    city = str(route_context.get("city") or "").strip()
    target_place = ", ".join(part for part in [city, country] if part) or "вашем городе"

    minimum_requirements: list[str] = []
    for item in market[:3]:
        if not isinstance(item, dict):
            continue
        for requirement in item.get("requirements", []) if isinstance(item.get("requirements", []), list) else []:
            text = str(requirement or "").strip()
            if text and text not in minimum_requirements:
                minimum_requirements.append(text)
            if len(minimum_requirements) >= 6:
                break
        if len(minimum_requirements) >= 6:
            break
    for extra in [
        f"Текущий язык: {route_context.get('current_language_level') or 'данных недостаточно'}",
        f"Целевой язык: {route_context.get('target_language') or 'данных недостаточно'}",
        f"Документы и право на работу: {route_context.get('documents_and_work_rights') or 'данных недостаточно'}",
        f"Формат работы: {route_context.get('work_preferences') or 'данных недостаточно'}",
    ]:
        if extra not in minimum_requirements:
            minimum_requirements.append(extra)

    role_line = ", ".join(roles[:3])
    bundle = {
        "goal_30_days": f"Закрепиться на одной из быстрых входных ролей в {target_place}, не уходя в тупиковую временную занятость.",
        "realistic_entry_roles": roles,
        "minimum_requirements": minimum_requirements,
        "cv_version_for_fast_entry": f"1-страничное CV под {role_line or _safe_default(decision.get('recommended_main_path'))} с акцентом на документы, сроки, координацию и готовность к старту.",
        "application_plan_7_days": [
            f"День 1: собрать 10 вакансий {role_line or 'по целевым ролям'} и выписать повторяющиеся требования.",
            "День 2: сделать 1-страничную версию CV под быстрый вход.",
            "День 3: подготовить 2 коротких самопрезентации под отклик и звонок.",
            "День 4: отправить 5 тестовых откликов.",
            "День 5: проверить 3 ответы рынка и скорректировать заголовок CV.",
            "День 6: собрать список из 5 компаний с внутренним ростом в operations/compliance/project coordination.",
            "День 7: отправить ещё 5 откликов и зафиксировать, где нужен донастрой CV.",
        ],
        "application_plan_30_days": [
            "Неделя 1: 10-15 откликов и 1 адаптированная версия CV.",
            "Неделя 2: 2-3 коротких скрининга или ответы от рынка.",
            "Неделя 3: исправить CV по факту откликов и сузить список до 2-3 ролей.",
            "Неделя 4: повторить цикл откликов и выбрать ближайший внутренний ростовой трек.",
        ],
        "bridge_to_next_role": "Через 3-6 месяцев цель — перейти из стартовой роли в operations, project coordination или compliance внутри той же компании или рядом с ней.",
        "risk_of_dead_end_roles": [
            "Временные позиции без обучения и без понятного внутреннего роста.",
            "Разовые подработки, которые не дают локального опыта и рекомендаций.",
            "Работа, где нельзя показать документы, сроки, координацию и результат.",
        ],
        "today_action": {
            "action": "Соберите 10 вакансий по выбранным быстрым ролям и выпишите 3 повторяющихся требования.",
            "timebox": "15 минут",
            "result": "Есть короткий список рынка и видны первые требования для версии CV.",
        },
    }

    if is_professional_bridge:
        short_term_goal, main_goal_3_6_months = _professional_bridge_goal_pack(profile_domain)
        bundle["route_type"] = "professional_bridge_with_income"
        bundle["short_term_goal"] = short_term_goal
        bundle["main_goal_3_6_months"] = main_goal_3_6_months
        bundle["bridge_to_next_role"] = (
            "Через 3-6 месяцев закрепиться в assistant/junior роли по профилю и двигаться к более полной роли в домене."
        )
        bundle["goal_30_days"] = (
            f"Сохранить доход в {target_place} и запустить возвращение в профильную профессию без ухода в generic assistant."
        )

    return bundle


def _build_upskill_bundle(report: dict[str, object], route_context: dict[str, str]) -> dict[str, object]:
    roles = _top_strategy_roles(report, 3)
    market = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
    digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
    what_not_reset = report.get("what_not_reset") if isinstance(report.get("what_not_reset"), list) else []
    current_language = str(route_context.get("current_language_level") or "данных недостаточно").strip()
    target_language = str(route_context.get("target_language") or "данных недостаточно").strip()
    diploma_status = str(route_context.get("diploma_status") or "данных недостаточно").strip()

    existing = [str(item).strip() for item in what_not_reset[:4] if str(item).strip() and str(item).strip() != "-"]
    if not existing:
        existing = ["Документы и формальные процедуры", "Контроль сроков", "Координация людей и задач"]

    rows = [
        {
            "already_have": existing[0] if len(existing) > 0 else "Данные из истории и резюме",
            "need_to_add": f"Локальный язык для {target_language if target_language != 'данных недостаточно' else 'работы'}",
            "how_to_confirm": "10-минутный mock interview и 10 рабочих фраз на целевом языке",
        },
        {
            "already_have": existing[1] if len(existing) > 1 else "Контроль сроков и задач",
            "need_to_add": "Excel / Google Sheets и локальный рабочий словарь",
            "how_to_confirm": "1 практическое задание и 2 примера из CV",
        },
        {
            "already_have": existing[2] if len(existing) > 2 else "Документооборот",
            "need_to_add": "Локальные процессы, нормы и правила обработки документов",
            "how_to_confirm": "Мини-кейс по вакансии и чек-лист из 5 пунктов",
        },
        {
            "already_have": existing[3] if len(existing) > 3 else "Координация людей и задач",
            "need_to_add": "Подтверждение роли в целевой компании через отклики и собеседования",
            "how_to_confirm": "2 скрининга или 5 тестовых откликов",
        },
    ]

    market_requirements: list[str] = []
    for item in market[:3]:
        if not isinstance(item, dict):
            continue
        for requirement in item.get("requirements", []) if isinstance(item.get("requirements", []), list) else []:
            text = str(requirement or "").strip()
            if text and text not in market_requirements:
                market_requirements.append(text)
            if len(market_requirements) >= 6:
                break
        if len(market_requirements) >= 6:
            break
    for extra in [
        f"Текущий язык: {current_language}",
        f"Целевой язык: {target_language}",
        f"Статус диплома: {diploma_status}",
    ]:
        if extra not in market_requirements:
            market_requirements.append(extra)

    return {
        "target_roles_6_months": roles,
        "gap_analysis": rows,
        "language_target": f"Перейти от {current_language} к рабочему уровню {target_language} для собеседований и переписки.",
        "required_tools_and_skills": market_requirements,
        "recommended_certificates": ["данных недостаточно: сначала проверить реальные вакансии и требования рынка"],
        "diploma_or_license_check": f"Проверить признание диплома и лицензий для целевых ролей; текущий статус: {diploma_status}.",
        "training_plan_12_weeks": {
            "0_4_weeks": [
                "Собрать 10 вакансий по целевым ролям и выписать общие требования.",
                "Обновить CV под 1-2 близкие роли и сделать короткий профиль на целевом языке.",
            ],
            "5_8_weeks": [
                "Добрать 1 практический навык, который чаще всего встречается в вакансиях.",
                "Сделать 1 мини-кейс или рабочий пример для портфолио.",
            ],
            "9_12_weeks": [
                "Проверить отклики, исправить CV и расширить список до 2-3 целевых ролей.",
                "Провести 2-3 собеседования или mock interview и зафиксировать пробелы.",
            ],
            "3_6_months": [
                "Собрать устойчивую языковую и профессиональную базу для перехода в target role.",
                "Перейти в смежную роль через внутренний рост или более точный рынок вакансий.",
            ],
        },
        "parallel_income_options": [
            "Временная administrative support / back-office роль в компании с внутренним ростом.",
            "Document control / operations support как мост к целевой роли.",
            "Частичная занятость, если она не ломает план обучения и даёт локальный опыт.",
        ],
        "portfolio_or_case_plan": [
            "Сделать 1 страницу с 2-3 кейсами по документообороту, срокам и координации.",
            "Подготовить 1 пример рабочей переписки на целевом языке.",
            "Собрать 1 чек-лист из реального задания вакансии и показать, как вы его решали.",
        ],
        "checkpoints": [
            "Через 2 недели: есть список из 10 вакансий и обновлённое CV.",
            "Через 4 недели: есть 3-5 откликов и 1-2 ответа от рынка.",
            "Через 8 недель: есть 1 мини-кейс или портфолио-образец.",
            "Через 12 недель: понятно, какие 2-3 роли реалистичны для перехода.",
        ],
        "today_action": {
            "action": "Выберите 3 целевые роли и сравните их по требованиям из 10 вакансий.",
            "timebox": "15 минут",
            "result": "Есть короткий список ролей и видны пробелы для добора навыков.",
        },
    }


def _build_long_transition_bundle(report: dict[str, object], route_context: dict[str, str]) -> dict[str, object]:
    roles = _top_strategy_roles(report, 3)
    market = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
    country = str(route_context.get("country") or "").strip()
    city = str(route_context.get("city") or "").strip()
    current_lang = str(route_context.get("current_language_level") or "данных недостаточно").strip()
    target_lang = str(route_context.get("target_language") or "данных недостаточно").strip()
    has_market_check = bool(country and city and len(market) >= 3)

    options = [
        "Project coordination",
        "Compliance / GDPR",
        "HR operations",
    ]

    comparison_table = [
        {
            "direction": "Project coordination",
            "time_to_entry": "4–8 месяцев",
            "language": "зависит от рынка",
            "cost": "средняя",
            "income_at_start": "средний",
            "income_growth_potential": "высокий",
            "risk": "нужен опыт",
        },
        {
            "direction": "Compliance / GDPR",
            "time_to_entry": "6–12 месяцев",
            "language": "выше среднего",
            "cost": "средняя",
            "income_at_start": "средний",
            "income_growth_potential": "высокий",
            "risk": "нужны локальные знания",
        },
        {
            "direction": "HR operations",
            "time_to_entry": "4–9 месяцев",
            "language": "средний–высокий",
            "cost": "средняя",
            "income_at_start": "средний",
            "income_growth_potential": "средний–высокий",
            "risk": "много конкуренции",
        },
    ]

    if has_market_check and market:
        by_role = {str(item.get("profession") or "").lower(): item for item in market if isinstance(item, dict)}
        mapping = {
            "project coordination": ["project coordinator", "operations coordinator"],
            "compliance / gdpr": ["compliance", "document control"],
            "hr operations": ["hr", "operations"],
        }
        for row in comparison_table:
            key = str(row.get("direction") or "").lower()
            candidates = mapping.get(key, [])
            picked = None
            for role_name, item in by_role.items():
                if any(token in role_name for token in candidates):
                    picked = item
                    break
            if picked:
                row["income_at_start"] = _safe_default(picked.get("salary_range"), str(row.get("income_at_start") or "средний"))
                row["risk"] = _safe_default(picked.get("competition"), str(row.get("risk") or "средний"))

    documents = [
        _safe_default(route_context.get("documents_and_work_rights"), "данных недостаточно"),
        _safe_default(route_context.get("diploma_status"), "данных недостаточно"),
    ]
    test_tasks = {
        "Project coordination": "Соберите 1 мини-план проекта на 2 недели с задачами, сроками и рисками.",
        "Compliance / GDPR": "Разберите 1 вакансию и составьте чек-лист из 10 требований комплаенса/документов.",
        "HR operations": "Сделайте 1 процесс-карту onboarding/recruitment на 1 страницу.",
    }

    checkpoint = (
        "Это предварительная гипотеза. Перед вложением денег мы проверим 15–20 актуальных вакансий и уточним требования работодателей."
        if not has_market_check
        else "Перед вложением денег всё равно проверьте 15–20 вакансий по городу и уточните реальные требования по языку и документам."
    )

    return {
        "new_career_options": options,
        "comparison_table": comparison_table,
        "time_to_entry": {row["direction"]: row["time_to_entry"] for row in comparison_table},
        "training_cost": {row["direction"]: row["cost"] for row in comparison_table},
        "language_requirement": {
            "current": current_lang,
            "target": target_lang,
            "by_path": {row["direction"]: row["language"] for row in comparison_table},
        },
        "income_at_start": {row["direction"]: row["income_at_start"] for row in comparison_table},
        "income_growth_potential": {row["direction"]: row["income_growth_potential"] for row in comparison_table},
        "required_documents": documents,
        "test_task_for_each_path": test_tasks,
        "decision_checkpoint": checkpoint,
        "today_action": {
            "action": "Выберите 2 направления из таблицы и сравните их по 15–20 вакансиям в вашем городе.",
            "timebox": "15 минут",
            "result": "Есть короткий shortlist и факты рынка перед затратами на обучение.",
        },
    }


def _build_need_decision_bundle(report: dict[str, object], route_context: dict[str, str]) -> dict[str, object]:
    missing = [field for field in _route_context_missing({"route_context": route_context}) if field]
    preliminary_route = _safe_default((report.get("career_decision") or {}).get("recommended_main_path"))
    return {
        "message": "Сейчас у вас не одна проблема «где найти работу», а выбор между скоростью, стабильностью и карьерным ростом.",
        "comparison_table": [
            {
                "path": "Быстрый доход",
                "gain": "Деньги и местный опыт",
                "tradeoff": "Может быть ниже статус и зарплата",
                "first_result": "2–6 недель",
            },
            {
                "path": "Добрать навыки",
                "gain": "Работа ближе к опыту",
                "tradeoff": "Понадобится дисциплина и время",
                "first_result": "3–6 месяцев",
            },
            {
                "path": "Переучиться",
                "gain": "Новая карьерная траектория",
                "tradeoff": "Дольше и дороже",
                "first_result": "6–18 месяцев",
            },
        ],
        "decision_questions": list(_NEED_DECISION_QUESTIONS),
        "missing_fields": missing,
        "preliminary_route": preliminary_route,
        "today_action": {
            "action": "Ответьте на 3 коротких вопроса выбора стратегии. После этого зафиксируем путь и только потом выберем конкретный маршрут.",
            "timebox": "10 минут",
            "result": "Появится осознанная стратегия: быстрый доход, добор навыков или долгий переход.",
        },
    }


def _recommend_strategy_from_need_decision_answers(answers: list[str]) -> str:
    blob = " ".join(str(item or "").lower().replace("ё", "е") for item in answers)
    if not blob:
        return "upskill_for_profile"

    short_runway = any(token in blob for token in ["1 месяц", "2 месяц", "2 недели", "срочно", "немед", "нет запаса", "без доход"])
    status_important = any(token in blob for token in ["важно сохранить", "статус важ", "важно статус", "проф статус"])
    ready_to_study = any(token in blob for token in ["готов", "да,", "учиться", "регулярно", "3-6 месяцев", "дисциплина"])
    no_study = any(token in blob for token in ["не готов", "не могу учиться", "нет времени", "сложно учиться"])

    if short_runway or no_study:
        return "fast_income"
    if ready_to_study and status_important:
        return "upskill_for_profile"
    if ready_to_study and not status_important:
        return "long_transition"
    return "upskill_for_profile"


def _collect_specialist_signals(report: dict[str, object], data: dict[str, object]) -> tuple[list[str], list[str]]:
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    answers_blob = " ".join(
        [
            str(data.get("answers_text") or ""),
            str(decision.get("why_not_other_paths") or ""),
            str(decision.get("why_this_path") or ""),
            str((report.get("facts_only") or {}).get("unknowns") or ""),
        ]
    ).lower().replace("ё", "е")

    career_rules = [
        ("не может выбрать между несколькими карьерными направлениями", ["не могу выбрать", "несколько направ", "сомневаюсь между"]),
        ("не понимает, как перевести прошлый опыт на язык нового рынка", ["перевести опыт", "как назвать опыт", "язык рынка"]),
        ("нужно переписать CV или LinkedIn под конкретную страну", ["cv", "резюме", "linkedin"]),
        ("есть опыт, но нет понятного профессионального позиционирования", ["не понимаю кем", "позиционирован", "как себя представить"]),
        ("нужно подготовиться к интервью", ["собесед", "интервью"]),
        ("не понимает, какие сертификаты реально нужны", ["сертификат", "какой курс", "что из обучения нужно"]),
        ("не понимает, нужна ли нострификация диплома", ["диплом", "ностриф", "признание квалификации"]),
        ("много откликов, но нет приглашений", ["много откликов", "нет приглаш", "нет ответов"]),
        ("нужно проверить стратегию поиска работы", ["стратегия поиска", "как искать", "план поиска"]),
    ]

    psych_rules = [
        ("паника или сильная тревога при откликах и собеседованиях", ["паник", "сильная трев", "страшно отклик", "страшно собесед"]),
        ("выгорание и отсутствие сил начать поиск", ["выгор", "нет сил", "устал", "истощ"]),
        ("стыд, самоуничижение, ощущение 'я никто'", ["стыд", "я никто", "самоуничиж", "бесполезен"]),
        ("человек избегает действий несмотря на понятный план", ["избегаю", "не делаю", "не могу начать", "прокрастин"]),
        ("сон, аппетит, концентрация или повседневное функционирование заметно ухудшились", ["сон", "аппетит", "концентра", "функционирован"]),
        ("переживание потери статуса, эмиграции или профессиональной идентичности", ["потеря статуса", "эмиграц", "идентичност"]),
        ("депрессивные симптомы или выраженное чувство безнадёжности", ["безнадеж", "депресс", "нет смысла"]),
    ]

    career_hits = [label for label, markers in career_rules if any(marker in answers_blob for marker in markers)]
    psych_hits = [label for label, markers in psych_rules if any(marker in answers_blob for marker in markers)]

    if not career_hits and str(data.get("career_strategy") or "") in {"need_decision", "upskill_for_profile", "long_transition"}:
        career_hits.append("нужно проверить стратегию поиска работы")
    if not psych_hits and any(token in answers_blob for token in ["тревог", "страх", "не знаю с чего начать", "перегруз"]):
        psych_hits.append("человек избегает действий несмотря на понятный план")

    return career_hits[:6], psych_hits[:6]


async def _handle_crisis_detected(message: Message, state: FSMContext, lang: str) -> None:
    """Handle crisis/safety signals by switching to crisis support mode."""
    data = await state.get_data()
    source = str(data.get("crisis_detected_source") or "unknown")
    await state.update_data(career_planning_paused=True, crisis_detected=True)
    await state.set_state(CareerFlow.CRISIS_SUPPORT)
    crisis_msg = t(lang, "crisis_detected_message")
    await message.answer(crisis_msg)
    
    # Show hotline info
    hotline_msg = t(lang, "crisis_hotline_info")
    await message.answer(hotline_msg)
    
    # Ask for next action
    support_msg = t(lang, "crisis_support_step")
    keyboard = crisis_support_keyboard()
    await message.answer(support_msg, reply_markup=keyboard)
    
    # Track crisis signal
    await _track_event(message, state, "crisis_signal_detected", meta={"source": source, "career_planning_paused": True})


def _specialist_guidance_text(report: dict[str, object], data: dict[str, object]) -> tuple[str, str, str, list[str], list[str]]:
    career_hits, psych_hits = _collect_specialist_signals(report, data)
    today_step = str(((report.get("action_plan") or {}).get("today") or {}).get("action") or "Сделайте один шаг 10-15 минут по плану.").strip()
    if len(career_hits) >= 2 and len(psych_hits) >= 2:
        title = "Здесь есть две разные задачи"
        body = (
            "Карьерный консультант поможет собрать внешний маршрут: целевые роли, CV, вакансии и стратегию поиска. "
            "Психолог поможет справиться с внутренним стопором: тревогой, выгоранием, стыдом или потерей уверенности. "
            "Не обязательно начинать с двух специалистов. Можно выбрать того, чей барьер сейчас сильнее."
        )
        mode = "both"
    elif len(career_hits) >= 2:
        title = "Сейчас основной барьер — карьерный"
        body = (
            "У вас уже есть опыт и понятная профессиональная база. Сейчас нужно перевести опыт на язык местного рынка, "
            "уточнить целевые роли и проверить резюме. Разовая консультация карьерного специалиста может ускорить этап."
        )
        mode = "career"
    elif len(psych_hits) >= 2:
        title = "Сейчас основной барьер — эмоциональный стопор"
        body = (
            "У вас есть понятный карьерный маршрут, но тревога и самокритика могут мешать им воспользоваться. "
            "Психологическая поддержка может помочь снизить внутренний стопор и вернуть способность действовать небольшими шагами."
        )
        mode = "psych"
    else:
        title = "Можно продолжать самостоятельно"
        body = "Сигналы к обязательной внешней поддержке сейчас не выражены. Двигайтесь по шагам и периодически проверяйте прогресс."
        mode = "self"

    text = (
        f"{title}.\n\n"
        f"Сегодня сначала практический шаг: {today_step}\n\n"
        f"{body}\n\n"
        "Выберите, какая помощь сейчас актуальнее:"
    )
    return text, mode, today_step, career_hits, psych_hits


def _apply_strategy_outputs(report: dict[str, object], route_context: dict[str, str], strategy_code: str) -> None:
    if not isinstance(report, dict):
        return
    chosen = str(strategy_code or "").strip()
    if chosen not in {"fast_income", "upskill_for_profile", "long_transition", "need_decision"}:
        chosen = "need_decision"

    strategy_label = {
        "fast_income": "Нужен доход в ближайшие 1–2 месяца",
        "upskill_for_profile": "Готов(а) добрать навыки 3–6 месяцев",
        "long_transition": "Готов(а) вложиться в переобучение и смену траектории",
        "need_decision": "Не уверен(а), помоги выбрать",
    }[chosen]

    bundles = {
        "fast_income": _build_fast_income_bundle(report, route_context),
        "upskill_for_profile": _build_upskill_bundle(report, route_context),
        "long_transition": _build_long_transition_bundle(report, route_context),
        "need_decision": _build_need_decision_bundle(report, route_context),
    }

    report["career_strategy"] = chosen
    report["career_strategy_label"] = strategy_label
    report[chosen] = bundles[chosen]


def _build_strategy_bundles(report: dict[str, object], route_context: dict[str, str]) -> dict[str, dict[str, object]]:
    return {
        "fast_income": _build_fast_income_bundle(report, route_context),
        "upskill_for_profile": _build_upskill_bundle(report, route_context),
        "long_transition": _build_long_transition_bundle(report, route_context),
    }


def _minimum_strategy_divergence(strategy_bundles: dict[str, dict[str, object]]) -> tuple[bool, int, dict[str, bool]]:
    items = [(code, bundle) for code, bundle in strategy_bundles.items() if isinstance(bundle, dict)]
    if len(items) < 2:
        return True, 6, {
            "target_roles": True,
            "timeline": True,
            "skills": True,
            "education": True,
            "income_path": True,
            "today_action": True,
        }

    min_score = 6
    min_compare = {
        "target_roles": True,
        "timeline": True,
        "skills": True,
        "education": True,
        "income_path": True,
        "today_action": True,
    }
    for idx in range(len(items)):
        for jdx in range(idx + 1, len(items)):
            _, left = items[idx]
            _, right = items[jdx]
            is_divergent, score, compare = _validate_route_divergence(left, right)
            if score < min_score:
                min_score = score
                min_compare = compare
            if not is_divergent:
                return False, score, compare
    return True, min_score, min_compare


def _route_divergence_regen_instruction() -> str:
    return (
        "Маршрут слишком похож на другой сценарий. "
        "Перестрой ответ с учётом выбранной стратегии, сроков, бюджета, "
        "языка, целевой профессии и ограничений пользователя."
    )


def _strategy_summary_text(report: dict[str, object]) -> str:
    code = str(report.get("career_strategy") or "").strip()
    bundle = report.get(code) if code and isinstance(report.get(code), dict) else {}
    if not code or not isinstance(bundle, dict):
        return ""
    if code == "fast_income":
        return f"Быстрый доход: {str(bundle.get('goal_30_days') or '').strip()}"
    if code == "upskill_for_profile":
        return f"Добор навыков 3-6 месяцев: {str(bundle.get('language_target') or '').strip()}"
    if code == "long_transition":
        return f"Долгий переход: {str(bundle.get('goal_30_days') or '').strip()}"
    if code == "need_decision":
        return str(bundle.get("message") or "Пока доступен только предварительный маршрут.").strip()
    return ""


def _set_mvp_questions(
    analysis: dict,
    limit: int = 8,
    mode: str = "calm_steps",
    story_text: str = "",
    user_segment: str = SEGMENT_SPECIALIST,
) -> dict:
    updated = dict(analysis or {})
    mode_key = str(mode or "calm_steps")
    effective_limit = max(1, int(limit) if int(limit) > 0 else _question_count_for_mode(mode_key))

    if mode_key == "fast":
        effective_limit = min(effective_limit, 5)
        normalized_fast: list[dict[str, object]] = []
        for idx, row in enumerate(_questions_fast()[:effective_limit], start=1):
            question_text = str(row.get("question", "")).strip() or f"Вопрос {idx}"
            opts = _normalize_question_options(question_text, row.get("options", []) if isinstance(row.get("options", []), list) else [])
            option_labels = [str(item).strip() for item in opts[:6] if str(item).strip()]
            allowed_button_ids: list[str] = []
            allowed_button_map: dict[str, str] = {}
            for option in option_labels:
                slug = _slugify(option)
                suffix = 2
                while slug in allowed_button_map:
                    slug = f"{slug}_{suffix}"
                    suffix += 1
                allowed_button_ids.append(slug)
                allowed_button_map[slug] = option
            normalized_fast.append(
                {
                    "id": idx,
                    "question": question_text,
                    "options": option_labels,
                    "question_id": str(row.get("question_id") or _slugify(question_text)),
                    "allowed_button_ids": allowed_button_ids,
                    "allowed_button_map": allowed_button_map,
                    "expected_answer_type": str(row.get("expected_answer_type") or _expected_answer_type(row)),
                    "semantic_intent": str(row.get("semantic_intent") or _question_semantic_intent(question_text)),
                    "source": _question_source(row, mode_key, idx - 1),
                    "validity_status": _question_validity_status(row),
                }
            )
        updated["follow_up_questions"] = normalized_fast[:effective_limit]
        return updated

    segment_specific = _segment_questions(user_segment)
    common = _segment_common_questions()
    mandatory = _mandatory_psych_social_questions()
    mode_base = _questions_fast() if mode_key == "fast" else (_questions_deep_route() if mode_key in {"deep_route", "support"} else _questions_calm())
    merged_base = _filter_known_questions(segment_specific + common + mode_base, story_text) + mandatory

    selected: list[dict[str, object]] = []
    seen: set[str] = set()

    raw_extra = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    if isinstance(raw_extra, list):
        for row in raw_extra:
            if not isinstance(row, dict):
                continue
            q_text = str(row.get("question", "")).strip()
            if not q_text:
                continue
            q_key = q_text.lower()
            if q_key in seen:
                continue
            opts = _normalize_question_options(q_text, row.get("options", []) if isinstance(row.get("options", []), list) else [])
            max_options = 15 if row.get("force_options_keyboard") else 6
            selected.append({"id": int(row.get("id", len(selected) + 1)), "question": q_text, "options": opts[:max_options]})
            seen.add(q_key)
            if len(selected) >= effective_limit:
                break

    for row in merged_base:
        if not isinstance(row, dict):
            continue
        q_key = str(row.get("question", "")).strip().lower()
        if not q_key or q_key in seen:
            continue
        selected.append(row)
        seen.add(q_key)
        if len(selected) >= effective_limit:
            break

    if len(selected) < effective_limit:
        for row in merged_base:
            if not isinstance(row, dict):
                continue
            q_key = str(row.get("question", "")).strip().lower()
            if not q_key or q_key in seen:
                continue
            selected.append(row)
            seen.add(q_key)
            if len(selected) >= effective_limit:
                break

    if len(selected) < 1:
        selected = [merged_base[0]] if merged_base and isinstance(merged_base[0], dict) else []

    trimmed = selected[:effective_limit]
    normalized: list[dict[str, object]] = []
    for idx, row in enumerate(trimmed, start=1):
        if not isinstance(row, dict):
            continue
        question_text = str(row.get("question", "")).strip() or f"Вопрос {idx}"
        opts = _normalize_question_options(question_text, row.get("options", []) if isinstance(row.get("options", []), list) else [])
        max_options = 15 if row.get("force_options_keyboard") else 6
        option_labels = [str(item).strip() for item in opts[:max_options] if str(item).strip()]
        allowed_button_ids: list[str] = []
        allowed_button_map: dict[str, str] = {}
        for option in option_labels:
            slug = _slugify(option)
            suffix = 2
            while slug in allowed_button_map:
                slug = f"{slug}_{suffix}"
                suffix += 1
            allowed_button_ids.append(slug)
            allowed_button_map[slug] = option

        question_id = str(row.get("question_id") or _slugify(question_text))
        normalized_row: dict[str, object] = {
            "id": idx,
            "question": question_text,
            "options": option_labels,
            "question_id": question_id,
            "allowed_button_ids": allowed_button_ids,
            "allowed_button_map": allowed_button_map,
            "expected_answer_type": str(row.get("expected_answer_type") or _expected_answer_type(row)),
            "semantic_intent": str(row.get("semantic_intent") or _question_semantic_intent(question_text)),
            "source": _question_source(row, mode_key, idx - 1),
            "validity_status": _question_validity_status(row),
        }
        if row.get("multi_key"):
            normalized_row["multi_key"] = str(row.get("multi_key"))
        if row.get("done_text"):
            normalized_row["done_text"] = str(row.get("done_text"))
        if row.get("max_select"):
            normalized_row["max_select"] = int(row.get("max_select") or 5)
        if row.get("force_options_keyboard"):
            normalized_row["force_options_keyboard"] = True
        normalized.append(normalized_row)

    normalized = _ensure_required_blocks(normalized[:effective_limit], mode_key)
    if len(normalized) > effective_limit:
        normalized = normalized[:effective_limit]
    for idx, row in enumerate(normalized, start=1):
        row["id"] = idx
    updated["follow_up_questions"] = normalized
    return updated


def _validate_answer(question_row: dict | object, answer: str, qa_answers: list[dict]) -> str | None:
    clean = (answer or "").strip()
    low = clean.lower()
    question_text = str(question_row.get("question", "")).lower() if isinstance(question_row, dict) else ""
    options = question_row.get("options", []) if isinstance(question_row, dict) else []

    is_income_question = "доход" in question_text and ("миним" in question_text or "нуж" in question_text)
    is_speed_question = "как быстро" in question_text and "доход" in question_text
    is_hours_question = "сколько часов" in question_text
    is_detail_question = any(token in question_text for token in ["чего точно не хотите", "какие ограничения", "какие направления", "какие варианты"])

    # Gibberish / empty signals — "не знаю" is handled separately via _is_dont_know_response
    if low in {"ничего", "ав", "ячзщык", "-"}:
        return "answer_validation_random"

    if len(clean) <= 3 and re.fullmatch(r"[a-zA-Zа-яА-Я]+", clean):
        return "answer_validation_random"

    if (is_income_question or is_hours_question) and not _extract_int_values(clean):
        return "answer_validation_need_number"

    if is_speed_question:
        if _looks_like_money_answer(clean):
            return "answer_validation_speed_mismatch"
        if not _looks_like_duration_answer(clean) and len(clean) > 40:
            return "answer_validation_need_choice"

    # Long narrative answers are accepted as story; fact extraction runs on them.
    if options and len(clean) <= 80:
        normalized = [str(item).strip().lower() for item in options if str(item).strip()]
        if normalized and all(opt not in low for opt in normalized) and len(clean) < 4:
            return "answer_validation_need_choice"

    if is_detail_question and len(clean) < 8:
        return "answer_validation_need_detail"

    if is_speed_question:
        income_answer = ""
        for row in qa_answers:
            if isinstance(row, dict) and "доход" in str(row.get("question", "")).lower():
                income_answer = str(row.get("answer", ""))
                break
        income_values = _extract_int_values(income_answer)
        if income_values and max(income_values) >= 15000 and ("2" in clean and "4" in clean):
            return "answer_validation_salary_conflict"

    return None


def _is_known_previous_button(questions: list[dict], current_index: int, answer_text: str) -> bool:
    candidate = str(answer_text or "").strip().lower()
    if not candidate:
        return False
    for row in questions[:max(0, current_index)]:
        if not isinstance(row, dict):
            continue
        options = row.get("options", [])
        if not isinstance(options, list):
            continue
        for option in options:
            if str(option).strip().lower() == candidate:
                return True
    return False


_DONT_KNOW_TOKENS: frozenset[str] = frozenset({
    "не знаю", "не знаю как", "хз", "затрудняюсь", "затрудняюсь ответить",
    "не понимаю", "непонятно", "сложно сказать", "трудно сказать",
    "не уверен", "не уверена", "пока не знаю", "не могу сказать",
    "понятия не имею", "сложно", "не могу ответить",
    "пропустить / не знаю", "пропустить",
})


def _is_dont_know_response(text: str) -> bool:
    # Only short bare "don't know" signals; narratives starting with "не знаю," are overload answers.
    low = (text or "").strip().lower().replace("ё", "е")
    return low in _DONT_KNOW_TOKENS


def _dont_know_simpler_question(current: dict, lang: str) -> tuple[str, list[str]]:
    """Return (intro_text, simplified_options) when user said 'не знаю'."""
    from services.interview_policy import _GAP_REGISTRY  # noqa: PLC0415
    gap_key = str(current.get("gap_key") or "").strip()
    original_options = current.get("options", []) if isinstance(current.get("options"), list) else []
    skip_option = "Пропустить / не знаю"

    if gap_key and gap_key in _GAP_REGISTRY and original_options:
        intro = "Тогда попробуем проще — выберите самое близкое:"
        return intro, [str(o) for o in original_options] + [skip_option]

    # Hypothesis prompts per gap without predefined options
    _hypothesis: dict[str, str] = {
        "personal_contribution": "Хорошо. Скажите самое простое: в последней работе — больше выполняли задачи по инструкции или сами решали, как их делать?",
        "demonstrated_result": "Понятно. Тогда просто: есть хоть один момент в работе, которым вы гордитесь? Не важно, насколько большой.",
        "explicit_refusal": "Понятно, тогда пропускаем. Если позже поймёте, что точно не хотите — просто скажите.",
        "regulated_profession_access": "Хорошо, пропускаем. Если позже появятся вопросы по документам — уточним.",
        "health_or_load_constraint": "Принято. Если есть что-то важное — скажите в любой момент.",
    }
    if gap_key in _hypothesis:
        return _hypothesis[gap_key], []

    # Generic fallback: just acknowledge and advance
    return "Понятно, пропускаем этот вопрос. Двигаемся дальше.", []


def _free_text_signal(question_row: dict | object, answer_text: str) -> dict[str, str] | None:
    if not isinstance(question_row, dict):
        return None
    expected = str(question_row.get("expected_answer_type") or "")
    if expected != "free_text":
        return None
    low = str(answer_text or "").strip().lower().replace("ё", "е")
    overwhelm_markers = [
        "не знаю, с чего начать",
        "не знаю с чего начать",
        "не понимаю с чего начать",
        "сложно начать",
        "не понимаю",
        "хаос",
        "растерян",
    ]
    if any(marker in low for marker in overwhelm_markers):
        return {
            "signal": "overwhelm",
            "meaning": "перегруз / неопределенность / трудность выбора",
            "not_equal_to": "новая карьерная цель",
        }
    return None


def _is_career_switch_choice(choice: object) -> bool:
    low = str(choice or "").strip().lower().replace("ё", "е")
    if not low:
        return False
    return "сменить сфер" in low or "сменить профес" in low


def format_cv_route_review(resume_analysis: dict, report: dict, lang: str) -> str:
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    market = report.get("market_analysis", []) if isinstance(report.get("market_analysis"), list) else []
    best = market[0] if market and isinstance(market[0], dict) else {}
    strengths = _list_block(resume_analysis.get("what_is_good", []) if isinstance(resume_analysis, dict) else [])
    gaps = _list_block(resume_analysis.get("what_is_missing", []) if isinstance(resume_analysis, dict) else [])
    inconsistencies = _list_block(resume_analysis.get("inconsistencies", []) if isinstance(resume_analysis, dict) else [])
    questions = _list_block(resume_analysis.get("clarifying_questions", []) if isinstance(resume_analysis, dict) else [])
    requirements = _list_block(best.get("requirements", []) if isinstance(best, dict) else [])

    bullet_examples = [
        "Организовал(а) документооборот команды из 6 человек, сократил(а) время обработки запросов на 20% за 2 месяца.",
        "Координировал(а) сроки и задачи между отделами, обеспечив(ла) выполнение 95% задач в дедлайн.",
        "Вел(а) базу и отчетность в Excel, снизив(ла) число ошибок в данных на 30%.",
    ]
    bullets_block = _list_block(bullet_examples)
    plan_48h = _list_block(
        [
            "День 1: переписать 5 bullet points под целевую роль.",
            "День 1: добавить 10 ключевых слов из вакансий.",
            "День 2: адаптировать заголовок и summary под маршрут.",
            "День 2: отправить 3 тестовых отклика и собрать обратную связь.",
        ]
    )

    return _clip(
        "\n\n".join(
            [
                f"{t(lang, 'cv_review_route')}:\n{decision.get('recommended_main_path') or '-'}",
                f"{t(lang, 'cv_review_strengths')}:\n{strengths}",
                f"{t(lang, 'cv_review_gaps')}:\n{gaps}",
                f"Несостыковки:\n{inconsistencies}",
                f"Вопросы для уточнения:\n{questions}",
                f"{t(lang, 'cv_review_keywords')}:\n{requirements}",
                f"{t(lang, 'cv_review_bullets')}:\n{bullets_block}",
                f"{t(lang, 'cv_review_48h')}:\n{plan_48h}",
                t(lang, "cv_review_next"),
            ]
        )
    )


def format_resume_analysis(resume_analysis: dict, lang: str) -> str:
    source = resume_analysis if isinstance(resume_analysis, dict) else {}
    professions = _list_block(source.get("professions", []))
    periods = _list_block(source.get("periods", []))
    tasks = _list_block(source.get("tasks", []))
    education = _list_block(source.get("education", []))
    languages = _list_block(source.get("languages", []))
    certificates = _list_block(source.get("certificates", []))
    achievements = _list_block(source.get("achievements", []))
    skills = _list_block(source.get("skills", []))
    inconsistencies = _list_block(source.get("inconsistencies", []))
    clarifying_questions = _list_block(source.get("clarifying_questions", []))
    good = source.get("what_is_good", [])
    missing = source.get("what_is_missing", [])
    good_block = _list_block(good)
    missing_block = _list_block(missing)
    if good_block == "-":
        good_block = t(lang, "resume_data_missing")
    if missing_block == "-":
        missing_block = t(lang, "resume_data_missing")
    return _clip(
        "\n\n".join(
            [
                f"Профессии и периоды:\n{professions}\n{periods}",
                f"Задачи и достижения:\n{tasks}\n{achievements}",
                f"Образование, языки, сертификаты:\n{education}\n{languages}\n{certificates}",
                f"Навыки:\n{skills}",
                f"{t(lang, 'resume_good_label')}:\n{good_block}",
                f"{t(lang, 'resume_missing_label')}:\n{missing_block}",
                f"Несостыковки:\n{inconsistencies}",
                f"Вопросы для уточнения:\n{clarifying_questions}",
            ]
        )
    )


def format_market_analysis(report: dict, lang: str) -> str:
    market = report.get("market_analysis", []) if isinstance(report.get("market_analysis"), list) else []
    lines = [f"=== {t(lang, 'market_analysis_label')} ===", "Рынок и скорость входа по направлениям"]
    for idx, item in enumerate(market[:5], start=1):
        if not isinstance(item, dict):
            continue
        lines.append(
            _clip(
                "\n".join(
                    [
                        f"[{idx}] {item.get('profession', '-')}",
                        f"• Соответствие: {item.get('fit_percent', 0)}%",
                        f"• Спрос: {item.get('demand', '-')}",
                        f"• Скорость входа: {item.get('entry_speed', '-')}",
                        f"• Конкуренция: {item.get('competition', '-')}",
                        f"• Требования: {_join_items(item.get('requirements', []), 6)}",
                        f"• Доход: {item.get('salary_range', '-')}",
                    ]
                ),
                950,
            )
        )
    return "\n\n".join(lines)


def format_real_solutions(report: dict, lang: str) -> str:
    solutions = report.get("real_solutions", []) if isinstance(report.get("real_solutions"), list) else []
    lines = [f"=== {t(lang, 'real_solutions_label')} ===", "Не просто варианты, а рабочие решения"]
    for idx, item in enumerate(solutions[:5], start=1):
        if not isinstance(item, dict):
            continue
        lines.append(
            _clip(
                "\n".join(
                    [
                        f"[{idx}] {item.get('title', '-')}",
                        f"• Приоритет: {item.get('recommendation_level', '-')}",
                        f"• Вероятность успеха: {item.get('success_probability', '-')}",
                        f"• Срок: {item.get('timeline', '-')}",
                        f"• Почему: {item.get('why', '-')}",
                        f"• Первый шаг: {item.get('first_step', '-')}",
                    ]
                ),
                950,
            )
        )
    return "\n\n".join(lines)


def format_career_translation(report: dict, lang: str) -> str:
    translations = report.get("career_translation", []) if isinstance(report.get("career_translation"), list) else []
    lines = [f"=== {t(lang, 'career_translation_label')} ==="]
    for idx, item in enumerate(translations[:8], start=1):
        if not isinstance(item, dict):
            continue
        suitable_roles = item.get("suitable_roles", [])
        lines.append(
            _clip(
                "\n".join(
                    [
                        f"[{idx}] Было в прошлой работе: {item.get('source_experience', '-')}",
                        f"• Как называется на рынке: {item.get('market_term', '-')}",
                        f"• Где использовать: {_join_items(suitable_roles, 3)}",
                    ]
                ),
                950,
            )
        )
    return "\n\n".join(lines)


def format_experience_layers(report: dict, lang: str) -> str:
    layers = report.get("experience_layers", []) if isinstance(report.get("experience_layers"), list) else []
    if not layers:
        return "=== В вашей истории есть несколько слоёв опыта ===\n-"
    return _clip("=== В вашей истории есть несколько слоёв опыта ===\n" + _list_block(layers[:3]))


def format_what_not_reset(report: dict, lang: str) -> str:
    items = report.get("what_not_reset", []) if isinstance(report.get("what_not_reset"), list) else []
    return _clip(f"=== Что не обнулилось ===\n{_list_block(items[:8])}")


def format_career_bridges(report: dict, lang: str) -> str:
    bridges = report.get("career_bridges", []) if isinstance(report.get("career_bridges"), list) else []
    lines = ["=== Карьерные мосты ==="]
    for idx, item in enumerate(bridges[:4], start=1):
        if not isinstance(item, dict):
            continue
        lines.append(
            _clip(
                "\n".join(
                    [
                        f"{idx}. {item.get('role', '-')}",
                        f"Почему это мост: {item.get('why_bridge', '-')}",
                        f"Первый тест рынка: {item.get('first_market_test', '-')}",
                    ]
                ),
                900,
            )
        )
    return "\n\n".join(lines)


def format_month_roadmap(report: dict, lang: str) -> str:
    development_map = report.get("development_map", {}) if isinstance(report.get("development_map"), dict) else {}
    first_month = development_map.get("first_month", []) if isinstance(development_map.get("first_month"), list) else []
    lines = [f"=== {t(lang, 'month_roadmap_label')} ==="]
    for week in first_month[:4]:
        if not isinstance(week, dict):
            continue
        lines.append(
            _clip(
                "\n".join(
                    [
                        f"Неделя {week.get('week', '-')}: {week.get('focus', '-')}",
                        f"• Что делать: {_join_items(week.get('tasks', []), 5)}",
                        f"• Результат недели: {week.get('output', '-')}",
                    ]
                ),
                950,
            )
        )
    return "\n\n".join(lines)


def format_action_plan(report: dict, lang: str) -> tuple[str, str, str]:
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    week_actions = action_plan.get("this_week", []) if isinstance(action_plan.get("this_week"), list) else []
    month_actions = action_plan.get("this_month", []) if isinstance(action_plan.get("this_month"), list) else []

    today_block = _clip(
        "\n".join(
            [
                f"=== {t(lang, 'today_action_label')} ===",
                f"• Действие: {today.get('action', '-')}",
                f"• Время: {today.get('timebox', '-')}",
                f"• Результат: {today.get('result', '-')}",
            ]
        )
    )
    week_block = _clip(f"=== {t(lang, 'week_actions_label')} ===\n{_list_block(week_actions)}")
    month_block = _clip(f"=== {t(lang, 'month_actions_label')} ===\n{_list_block(month_actions)}")
    return today_block, week_block, month_block


def format_barrier_analysis(report: dict, lang: str) -> str:
    barriers = report.get("career_barriers", []) if isinstance(report.get("career_barriers"), list) else []
    landscape = report.get("barrier_landscape", {}) if isinstance(report.get("barrier_landscape"), dict) else {}
    lines = [
        f"=== {t(lang, 'barrier_analysis_label')} ===",
        "",
        f"Внешние барьеры:\n{_list_block(landscape.get('external', []))}",
        "",
        f"Внутренние барьеры:\n{_list_block(landscape.get('internal', []))}",
        "",
        f"Поведенческий цикл:\n• {landscape.get('behavioral_risk', '-')}",
        "",
        f"Первое противодействие:\n• {landscape.get('first_counter_action', '-')}",
    ]
    if barriers:
        main = barriers[0] if isinstance(barriers[0], dict) else {}
        lines.extend(
            [
                "",
                f"Механизм блока:\n• {main.get('mechanism', '-')}",
            ]
        )
    return _clip("\n".join(lines))


def format_social_integration(report: dict, lang: str) -> str:
    integration = report.get("social_integration", {}) if isinstance(report.get("social_integration"), dict) else {}
    lines = ["=== Социальная и культурная интеграция ==="]
    lines.append(f"Среда:\n{_list_block(integration.get('environment', []))}")
    lines.append(f"Люди:\n{_list_block(integration.get('people', []))}")
    lines.append(f"Сообщества:\n{_list_block(integration.get('communities', []))}")
    lines.append(f"Возможности:\n{_list_block(integration.get('opportunities', []))}")
    lines.append(f"Вклад:\n{_list_block(integration.get('contribution', []))}")
    return _clip("\n\n".join(lines))


def _today_task_from_report(report: dict) -> str:
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    task = str(today.get("action", "")).strip()
    if task:
        return task
    weekly_plan = report.get("weekly_plan", []) if isinstance(report.get("weekly_plan"), list) else []
    if weekly_plan and isinstance(weekly_plan[0], dict):
        return str(weekly_plan[0].get("task", "Сделайте первый шаг по маршруту сегодня.")).strip()
    return "Сделайте первый шаг по маршруту сегодня."


def _optional_support_step_from_report(report: dict) -> str:
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}

    # Preferred explicit field from model output.
    direct = str(action_plan.get("optional_support_step") or "").strip()
    if direct:
        return direct

    # Backward-compatible aliases.
    legacy = str(today.get("optional_support") or today.get("support_step") or "").strip()
    if legacy:
        return legacy

    return ""


def _build_execution_steps(report: dict) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    guidance = report.get("next_step_guidance") if isinstance(report.get("next_step_guidance"), dict) else {}
    chat_task = guidance.get("first_chat_task") if isinstance(guidance.get("first_chat_task"), dict) else {}
    chat_action = str(chat_task.get("action") or "").strip()
    if chat_action:
        volume = str(chat_task.get("volume") or "").strip()
        result_to_send = str(chat_task.get("result_to_send") or "").strip()
        assistant_response = str(chat_task.get("assistant_response") or "").strip()
        steps.append({
            "day": "1",
            "focus": "Первый рыночный шаг",
            "task": f"{chat_action}{f' Объём: {volume}.' if volume else ''}",
            "time": "15-30 минут",
            "result": f"Пришлите в чат: {result_to_send}." if result_to_send else "Пришлите результат в чат.",
            "why": assistant_response or "Я разберу результат и дам следующий шаг без повторной диагностики.",
        })
    weekly_plan = report.get("weekly_plan", []) if isinstance(report.get("weekly_plan"), list) else []
    for item in weekly_plan[:7]:
        if not isinstance(item, dict):
            continue
        steps.append(
            {
                "day": str(len(steps) + 1),
                "focus": str(item.get("focus") or f"День {len(steps) + 1}"),
                "task": str(item.get("task") or "Сделайте шаг по плану."),
                "time": str(item.get("time") or "15-30 минут"),
                "result": str(item.get("result") or "Есть зафиксированный следующий шаг."),
                "why": str(item.get("why") or "Это продвигает вас по основному маршруту."),
            }
        )

    development = report.get("development_map", {}) if isinstance(report.get("development_map"), dict) else {}
    first_month = development.get("first_month", []) if isinstance(development.get("first_month"), list) else []
    for row in first_month:
        if not isinstance(row, dict):
            continue
        tasks = row.get("tasks", []) if isinstance(row.get("tasks"), list) else []
        for task in tasks:
            if len(steps) >= 14:
                break
            steps.append(
                {
                    "day": str(len(steps) + 1),
                    "focus": f"Неделя {row.get('week', '-')} · {row.get('focus', 'Следующий шаг')}",
                    "task": str(task or "Сделайте следующий шаг по карте."),
                    "time": "20-40 минут",
                    "result": str(row.get("output") or "Есть прогресс по маршруту."),
                    "why": str(row.get("focus") or "Это поддерживает движение по маршруту."),
                }
            )
        if len(steps) >= 14:
            break

    optional_support = _optional_support_step_from_report(report)

    if not steps:
        steps.append(
            {
                "day": "1",
                "focus": "Первый шаг",
                "task": _today_task_from_report(report),
                "time": "15 минут",
                "result": "Первое действие запущено.",
                "why": "Так карта превращается в реальное движение.",
                "support_optional": optional_support,
            }
        )
    else:
        # Product rule: one primary action per day, plus at most one optional support step.
        steps[0]["support_optional"] = optional_support

    return steps[:14]


def _execution_step_text(step: dict[str, str], progress: dict[str, dict[str, str]] | None = None) -> str:
    day = step.get("day", "1")
    status = "не отмечен"
    barrier_note = ""
    if isinstance(progress, dict):
        row = progress.get(str(day), {}) if isinstance(progress.get(str(day), {}), dict) else {}
        status = str(row.get("status") or status)
        barrier = str(row.get("barrier") or "").strip()
        if barrier:
            barrier_note = f"\n\nГде застрял(а):\n{barrier}"
    support_optional = str(step.get("support_optional") or "").strip()
    optional_block = f"\n\nНеобязательная поддержка:\n{support_optional}" if support_optional else ""
    return (
        f"День {day}\n\n"
        f"Фокус:\n{step.get('focus', '-')}\n\n"
        f"Задача:\n{step.get('task', '-')}\n\n"
        f"Время:\n{step.get('time', '-')}\n\n"
        f"Ожидаемый результат:\n{step.get('result', '-')}\n\n"
        f"Зачем это делать:\n{step.get('why', '-')}\n\n"
        f"Статус: {status}{optional_block}{barrier_note}"
    )


def _reframe_clarification(text: str) -> str:
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return "Уточнение не распознано."
    return f"Нужно учесть следующее уточнение пользователя: {clean}"


async def _download_bot_file(message: Message, file_id: str, suffix: str = ".tmp") -> str:
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp_file.name
    tmp_file.close()
    file_info = await message.bot.get_file(file_id)
    await message.bot.download(file_info, destination=tmp_path)
    return tmp_path


async def _rebuild_report_with_note(message: Message, state: FSMContext, lang: str, note_text: str) -> None:
    data = await state.get_data()
    story_analysis = data.get("story_analysis") or {}
    base_answers = (data.get("answers_text") or "").strip()
    updated_answers = (base_answers + "\n\nУточнение пользователя:\n" + note_text).strip()
    decision_layers = _build_decision_layers(data, story_analysis, updated_answers)
    await state.set_state(CareerFlow.REBUILDING_ROUTE)
    await message.answer(t(lang, "route_rebuild_progress"), reply_markup=result_actions_keyboard())
    report = await ai_client.build_report(
        (data.get("story_text") or "").strip(),
        story_analysis,
        updated_answers,
        decision_layers=decision_layers,
        resume_analysis=data.get("resume_analysis") or {},
        selected_barriers=data.get("selected_barriers") or [],
        selected_fears=data.get("selected_fears") or [],
        selected_psych_markers=data.get("selected_psych_markers") or [],
        selected_energy_sources=data.get("selected_energy_sources") or [],
        selected_career_priorities=data.get("selected_career_priorities") or [],
        user_segment=str(data.get("user_segment") or ""),
        user_segment_label=str(data.get("user_segment_label") or ""),
        language=lang,
    )
    chunks = report_chunks(report, lang)
    await state.update_data(final_report=report, report_chunks=chunks, final_report_generated=True)
    await message.answer(t(lang, "route_rebuild_result_intro"), reply_markup=route_choice_keyboard())
    await _present_route_selection(message, state, lang, report)


def _has_income_signal(report: dict) -> bool:
    market = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
    for item in market:
        if not isinstance(item, dict):
            continue
        salary = str(item.get("salary_range", "")).strip().lower()
        if salary and salary not in {"-", "данных недостаточно", "не уточнено"}:
            return True

    recs = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
    for item in recs:
        if not isinstance(item, dict):
            continue
        income = str(item.get("income_range", "")).strip().lower()
        if income and income not in {"-", "данных недостаточно", "не уточнено"}:
            return True

    return False


def _level_label(value: object) -> str:
    normalized = str(value or "").strip().lower()
    labels = {
        "high": "высокий",
        "medium": "средний",
        "low": "низкий",
    }
    return labels.get(normalized, str(value or "не уточнено").strip() or "не уточнено")


def _resource_human_message(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "low":
        return (
            "Сейчас ресурс ограничен.\n"
            "Вам важнее не брать на себя большой карьерный разворот, а выбрать путь, который дает доход "
            "и не требует резко учиться всему с нуля."
        )
    if normalized == "medium":
        return (
            "Сейчас ресурс частично ограничен.\n"
            "Лучше двигаться короткими шагами: сначала стабильный доход и понятный ритм, затем расширять траекторию."
        )
    if normalized == "high":
        return (
            "Сейчас ресурс устойчивый.\n"
            "Вы можете брать более амбициозные шаги, но сохранять контроль: измеримые действия и проверка гипотез на рынке."
        )
    return (
        "Ресурс пока нельзя оценить точно.\n"
        "Нужно уточнить, насколько стабильно у вас хватает времени, сил и темпа на регулярные карьерные действия."
    )


def _integration_human_message(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "low":
        return (
            "Интеграция пока начальная.\n"
            "Нужен щадящий маршрут: меньше зависимости от широких контактов и сложных локальных процессов на старте."
        )
    if normalized == "medium":
        return (
            "Интеграция пока частичная.\n"
            "Вы уже живете и работаете в стране, но язык, местные контакты и понимание рынка еще требуют укрепления."
        )
    if normalized == "high":
        return (
            "Интеграция уже устойчивая.\n"
            "Можно делать ставку на роли с более высокой планкой входа и активнее использовать локальный нетворк."
        )
    return (
        "Интеграцию пока нельзя оценить точно.\n"
        "Мы знаем, что вы уже живете в стране, но пока не понимаем, насколько уверенно вы используете язык, "
        "контакты и местные сервисы."
    )


def _professional_core_summary(report: dict) -> str:
    digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
    not_reset = report.get("what_not_reset") if isinstance(report.get("what_not_reset"), list) else []
    snapshot = " ".join(str(item) for item in not_reset[:6]).lower().replace("ё", "е")
    state_blob = " ".join(
        [
            str(digital_human.get("current_state", "")),
            str(digital_human.get("main_asset", "")),
            snapshot,
        ]
    ).lower().replace("ё", "е")

    worker_markers = ["плитк", "гипсокарт", "ремонт", "строит", "мебел", "рукам", "отделк"]
    if any(marker in state_blob for marker in worker_markers):
        return (
            "Вы не начинаете с нуля. Ваш основной капитал — практический опыт, способность работать руками, "
            "доводить задачу до результата и общаться с заказчиком.\n\n"
            "Сейчас вам нужен не абстрактный «новый старт», а перевод уже имеющегося опыта в понятный доход в новой стране."
        )

    return (
        "Вы не начинаете с нуля. У вас уже есть профессиональный капитал: практический опыт, рабочая дисциплина, "
        "умение доводить задачи до результата и взаимодействовать с людьми.\n\n"
        "Сейчас нужен не «новый старт с пустого места», а точная упаковка и перевод вашего опыта в понятный доход в новой стране."
    )


def _route_speed_label(raw: str) -> str:
    low = str(raw or "").lower()
    if any(token in low for token in ["1-3", "1–3", "2-4", "2–4", "быстр", "short"]):
        return "быстрее"
    if any(token in low for token in ["6", "12", "долг", "long"]):
        return "медленнее"
    return "средняя"


def _route_risk_label(raw: str) -> str:
    low = str(raw or "").lower()
    if any(token in low for token in ["выс", "high", "ниже", "низк", "low"]):
        return "ниже" if any(token in low for token in ["ниже", "низк", "low"]) else "выше"
    if any(token in low for token in ["сред", "medium", "умер"]):
        return "средний"
    return "средний"


def _route_income_label(raw: str) -> str:
    low = str(raw or "").lower()
    if any(token in low for token in ["9000", "10000", "12000", "выс", "high"]):
        return "выше"
    if any(token in low for token in ["позже", "later", "долгоср", "6-18", "6–18"]):
        return "позже"
    return "средний"


def _is_construction_estimation_domain(report: dict) -> bool:
    return str(report.get("profile_domain") or "").strip() == "construction_engineering_cost_estimation"


def _contains_any(text: str, terms: list[str]) -> bool:
    low = _normalize_text(text)
    return any(_normalize_text(term) in low for term in terms if str(term or "").strip())


def validate_final_report(profile_domain: str, selected_route: str, first_step: str, report_text: str) -> None:
    domain_required_terms = {
        "construction_engineering_cost_estimation": [
            "смет",
            "строитель",
            "проектной документац",
            "construction",
            "cost estimator",
            "quantity surveyor",
            "technical assistant",
        ]
    }

    domain_forbidden_terms = {
        "construction_engineering_cost_estimation": [
            "плитка",
            "гипсокартон",
            "мебель",
            "sales-метрики",
            "удержание клиентов",
            "мастер смены",
            "старший участка",
            "любая офисная работа",
        ]
    }

    required = domain_required_terms.get(str(profile_domain or "").strip(), [])
    forbidden = domain_forbidden_terms.get(str(profile_domain or "").strip(), [])
    full_text = "\n".join([str(selected_route or ""), str(first_step or ""), str(report_text or "")])

    if required and not _contains_any(full_text, required):
        raise ValueError("Report lost professional domain")

    if forbidden and _contains_any(full_text, forbidden):
        raise ValueError("Report contains foreign-domain template")


def _construction_final_case_block() -> str:
    return (
        "Ваш основной маршрут — возвращение в строительную сферу через адаптационный мост.\n\n"
        "Ближайшая цель на 3–6 месяцев: выйти на одну из ролей:\n"
        "- Assistant Cost Estimator;\n"
        "- Junior Quantity Surveyor;\n"
        "- Technical Assistant Construction;\n"
        "- Construction Documentation Specialist;\n"
        "- Construction Project Assistant.\n\n"
        "Что нужно добрать:\n"
        "- польский B1 с профессиональной строительной лексикой;\n"
        "- польские строительные нормы;\n"
        "- структура проектной документации;\n"
        "- Excel для смет;\n"
        "- программы, которые повторяются в вакансиях;\n"
        "- CV под construction / cost estimation.\n\n"
        "Временная работа: если доход нужен сейчас, ищите не любую офисную позицию, а вход в строительную компанию:\n"
        "- site office assistant;\n"
        "- technical assistant;\n"
        "- back-office in construction company;\n"
        "- documentation assistant.\n\n"
        "Первый шаг: за 15 минут найдите 10 вакансий по строительным запросам и выпишите повторяющиеся требования. Это покажет, чему учиться первым."
    )


def _rebuild_construction_report_for_final(report: dict) -> None:
    route_type = str(report.get("route_type") or "").strip()
    if route_type == "route_stable":
        payload = dict(_construction_route_stable())
        payload["risks"] = ["может быть ниже статус", "может быть ниже стартовый доход"]
        payload["specialist_recommendation"] = "карьерный консультант для ускорения откликов и адаптации CV под стройкомпании"
        _apply_selected_route_regeneration(report, payload, "route_stable")
        return

    payload = dict(_construction_route_upskill())
    payload["main_roles"] = [
        "Assistant Cost Estimator",
        "Junior Quantity Surveyor",
        "Technical Assistant Construction",
        "Construction Documentation Specialist",
        "Construction Project Assistant",
    ]
    payload["risks"] = ["нужно учить нормы и язык", "дольше до первого оффера"]
    payload["specialist_recommendation"] = "карьерный консультант + предметный разбор вакансий для ускорения возврата к сметам"
    _apply_selected_route_regeneration(report, payload, "route_upskill")


def _construction_route_stable() -> dict[str, object]:
    return {
        "main_roles": [
            "Site Office Assistant",
            "Construction Documentation Assistant",
            "Back-office Specialist in construction company",
            "Technical Assistant Construction",
        ],
        "goal": "быстрее войти в строительную компанию, даже не сразу сметчиком",
        "timeline": "1-3 месяца",
        "first_step": "найти 10 вакансий в строительных компаниях с низким порогом входа",
    }


def _construction_route_upskill() -> dict[str, object]:
    return {
        "main_roles": [
            "Assistant Cost Estimator",
            "Junior Quantity Surveyor",
            "Construction Project Assistant",
            "Construction Documentation Specialist",
        ],
        "goal": "за 3-6 месяцев добрать язык, нормы, программы и вернуться ближе к профессии",
        "skills_to_learn": [
            "польский B1 с профессиональной строительной лексикой",
            "польские строительные нормы",
            "структура проектной документации в Польше",
            "Excel для смет",
            "программы, которые повторяются в вакансиях",
            "CV и LinkedIn под construction / cost estimation",
        ],
        "timeline": "3-6 месяцев",
        "first_step": "собрать 10 вакансий и выписать требования",
    }


def _apply_selected_route_regeneration(report: dict, route_payload: dict[str, object], route_id: str) -> None:
    if not isinstance(report, dict):
        return

    roles = [str(item).strip() for item in route_payload.get("main_roles", []) if str(item).strip()] if isinstance(route_payload.get("main_roles"), list) else []
    skills = [str(item).strip() for item in route_payload.get("skills_to_learn", []) if str(item).strip()] if isinstance(route_payload.get("skills_to_learn"), list) else []
    risks = [str(item).strip() for item in route_payload.get("risks", []) if str(item).strip()] if isinstance(route_payload.get("risks"), list) else []
    timeline = str(route_payload.get("timeline") or "-").strip()
    first_step = str(route_payload.get("first_step") or "-").strip()
    goal = str(route_payload.get("goal") or "-").strip()
    specialist_reco = str(route_payload.get("specialist_recommendation") or "").strip()

    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    if roles:
        decision["recommended_main_path"] = " / ".join(roles[:2])
        # Keep the legacy and canonical representations synchronized.  Otherwise
        # _ensure_canonical_career_decision prefers the stale main_route value.
        decision["main_route"] = decision["recommended_main_path"]
        if len(roles) > 2:
            decision["backup_path"] = " / ".join(roles[2:4])
    decision["why_this_path"] = goal
    decision["why_not_other_paths"] = risks[:3] if risks else ["Сначала нужен маршрут с прогнозируемым входом и подтверждаемыми требованиями."]
    report["career_decision"] = decision

    action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
    action_plan["today"] = {
        "action": first_step,
        "timebox": "15 минут",
        "result": "Сделан первый измеримый шаг по выбранному маршруту.",
    }
    action_plan["this_week"] = [
        f"День 1: {first_step}",
        "День 2: адаптировать CV под выбранные роли",
        "День 3: собрать 10 ключевых требований и примеры формулировок",
        "День 4: отправить 3-5 прицельных откликов",
        "День 5: зафиксировать обратную связь и обновить CV",
        "День 6: усилить профиль LinkedIn под маршрут",
        "День 7: скорректировать план на следующую неделю",
    ]
    action_plan["this_month"] = [
        f"Закрепиться в выбранном маршруте ({timeline})",
        "Стабилизировать поток откликов и интервью",
        "Закрыть ключевые пробелы по требованиям рынка",
        "Получить измеримый прогресс: интервью/оффер/финальные этапы",
    ]
    report["action_plan"] = action_plan

    report["weekly_plan"] = [
        {
            "day": idx + 1,
            "focus": "Маршрут выбран и зафиксирован",
            "task": task,
            "time": "30-50 минут",
            "result": "Есть прогресс по выбранному маршруту",
            "why": "Чтобы маршрут превращался в измеримый результат",
        }
        for idx, task in enumerate(action_plan["this_week"][:7])
    ]

    development_map = report.get("development_map") if isinstance(report.get("development_map"), dict) else {}
    development_map["goal"] = goal
    development_map["gap"] = skills[:6] if skills else ["Уточнить требования вакансий и закрыть пробелы по ним."]
    development_map["first_month"] = [
        {"week": 1, "focus": "Рынок", "tasks": [first_step, "Собрать требования"], "output": "Карта рынка и требований"},
        {"week": 2, "focus": "Профиль", "tasks": ["Обновить CV", "Обновить LinkedIn"], "output": "Готовый профиль под маршрут"},
        {"week": 3, "focus": "Отклики", "tasks": ["5 откликов в день", "Трекер откликов"], "output": "Первые интервью"},
        {"week": 4, "focus": "Корректировка", "tasks": ["Разбор фидбэка", "Обновление тактики"], "output": "Улучшенная конверсия"},
    ]
    report["development_map"] = development_map

    if roles:
        report["market_analysis"] = [
            {
                "profession": role,
                "fit_percent": max(70, 88 - idx * 4),
                "demand": "средний",
                "entry_speed": "средняя" if idx > 0 else "быстрая",
                "competition": "средняя",
                "requirements": skills[:5] if skills else ["релевантный опыт", "язык", "документация"],
                "salary_range": "данных недостаточно",
                "profile_match_reason": goal,
            }
            for idx, role in enumerate(roles[:4])
        ]
        report["career_recommendations"] = [
            {
                "title": role,
                "match_percent": max(72, 90 - idx * 4),
                "why_fit": goal,
                "pros": ["понятный вход", "маршрут согласован пользователем"],
                "risks": risks[:3] if risks else ["нужна адаптация под рынок"],
                "entry_timeline": timeline,
                "income_range": "данных недостаточно",
            }
            for idx, role in enumerate(roles[:4])
        ]

    if skills:
        report["upskill_for_profile"] = {
            "target_roles_6_months": roles[:4] if roles else [],
            "required_tools_and_skills": skills[:6],
            "today_action": {"action": first_step, "timebox": "15 минут", "result": "Собраны требования рынка"},
        }

    report["route_selected_id"] = route_id
    if specialist_reco:
        report["specialist_recommendation"] = specialist_reco


def _construction_route_comparison() -> list[dict[str, object]]:
    return [
        {
            "name": "Быстрый вход в строительную компанию",
            "speed": "быстрее",
            "risk": "ниже",
            "roles": ["Site Office Assistant", "Technical Assistant"],
            "cost": "может быть ниже статус",
        },
        {
            "name": "Возврат к сметам через обучение",
            "speed": "средне",
            "risk": "средний",
            "roles": ["Assistant Cost Estimator", "Junior Quantity Surveyor"],
            "cost": "нужно учить нормы и язык",
        },
        {
            "name": "Переход в project coordination в строительстве",
            "speed": "средне",
            "risk": "средний",
            "roles": ["Construction Project Assistant", "Project Coordinator"],
            "cost": "нужны коммуникация и локальные процессы",
        },
    ]


def _build_route_comparison_rows(report: dict) -> list[dict[str, str]]:
    decision = _ensure_canonical_career_decision(report)
    if _is_construction_estimation_domain(report):
        stable = _construction_route_stable()
        upskill = _construction_route_upskill()
        comparison = _construction_route_comparison()
        report["route_stable"] = stable
        report["route_upskill"] = upskill
        report["route_comparison"] = comparison
        return [
            {
                "route": str(comparison[0].get("name") or "Быстрый вход в строительную компанию"),
                "income": "средний",
                "speed": str(comparison[0].get("speed") or "быстрее"),
                "risk": str(comparison[0].get("risk") or "ниже"),
                "need": str(comparison[0].get("cost") or "может быть ниже статус"),
                "why": str(stable.get("goal") or "Быстрее войти в строительную компанию."),
                "good": "Быстрый вход в строительную компанию с низким порогом входа.",
                "obstacle": str(comparison[0].get("cost") or "может быть ниже статус"),
                "first_step": str(stable.get("first_step") or "найти 10 вакансий в строительных компаниях с низким порогом входа"),
                "uncertainty": "низкая",
            },
            {
                "route": str(comparison[1].get("name") or "Возврат к сметам через обучение"),
                "income": "средний",
                "speed": str(comparison[1].get("speed") or "средне"),
                "risk": str(comparison[1].get("risk") or "средний"),
                "need": str(comparison[1].get("cost") or "нужно учить нормы и язык"),
                "why": str(upskill.get("goal") or "Вернуться ближе к профессии через добор навыков."),
                "good": "Ближе к профилю инженера-сметчика и выше долгосрочный потолок.",
                "obstacle": str(comparison[1].get("cost") or "нужно учить нормы и язык"),
                "first_step": str(upskill.get("first_step") or "собрать 10 вакансий и выписать требования"),
                "uncertainty": "средняя",
            },
            {
                "route": str(comparison[2].get("name") or "Переход в project coordination в строительстве"),
                "income": "средний",
                "speed": str(comparison[2].get("speed") or "средне"),
                "risk": str(comparison[2].get("risk") or "средний"),
                "need": str(comparison[2].get("cost") or "нужны коммуникация и локальные процессы"),
                "why": "Компромиссный трек между быстрым входом и возвратом к профильной инженерной среде.",
                "good": "Можно расти в координацию проектов в строительной компании.",
                "obstacle": str(comparison[2].get("cost") or "нужны коммуникация и локальные процессы"),
                "first_step": "собрать 10 вакансий Construction Project Assistant / Project Coordinator и выписать локальные требования",
                "uncertainty": "средняя",
            },
        ]

    recs = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
    solutions = report.get("real_solutions") if isinstance(report.get("real_solutions"), list) else []

    rows: list[dict[str, str]] = []

    main_title = str(decision.get("main_route") or decision.get("recommended_main_path") or "Основной маршрут").strip()
    main_rec = recs[0] if recs and isinstance(recs[0], dict) else {}
    rows.append(
        {
            "route": main_title,
            "income": _route_income_label(str(main_rec.get("income_range") or "")),
            "speed": _route_speed_label(str(main_rec.get("entry_timeline") or "")),
            "risk": _route_risk_label(_join_items(main_rec.get("risks", []), 3)),
            "need": _join_items(main_rec.get("pros", []), 2) or _join_items(main_rec.get("risks", []), 2) or "резюме, отклики",
            "why": str(decision.get("why_this_path") or main_rec.get("why_fit") or "Опирается на уже подтвержденный профессиональный капитал.").strip(),
            "good": _join_items(main_rec.get("pros", []), 4) or "Быстрый старт с текущими навыками.",
            "obstacle": _join_items(main_rec.get("risks", []), 4) or "Нужна проверка требований рынка.",
            "first_step": str(report.get("action_plan", {}).get("today", {}).get("action") or "Собрать 10 вакансий и проверить совпадения по требованиям.").strip(),
            "uncertainty": "низкая" if main_rec else "средняя",
        }
    )

    backup = str(decision.get("backup_path") or "").strip()
    if backup and backup.lower() != main_title.lower():
        backup_rec = recs[1] if len(recs) > 1 and isinstance(recs[1], dict) else {}
        rows.append(
            {
                "route": backup,
                "income": _route_income_label(str(backup_rec.get("income_range") or "")),
                "speed": _route_speed_label(str(backup_rec.get("entry_timeline") or "")),
                "risk": _route_risk_label(_join_items(backup_rec.get("risks", []), 3)),
                "need": _join_items(backup_rec.get("pros", []), 2) or "резюме, отклики",
                "why": str(backup_rec.get("why_fit") or "Хороший запасной трек, если основной маршрут слишком рискован.").strip(),
                "good": _join_items(backup_rec.get("pros", []), 4) or "Ниже порог входа, если нужен более простой старт.",
                "obstacle": _join_items(backup_rec.get("risks", []), 4) or "Может потребовать компромисса по роли или доходу.",
                "first_step": str(backup_rec.get("first_step") or "Сравнить 5 вакансий по требованиям и сроку входа.").strip(),
                "uncertainty": "средняя" if backup_rec else "высокая",
            }
        )

    long_route = ""
    for item in solutions:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        level = str(item.get("recommendation_level") or "").lower()
        if "долг" in level or "идеал" in level or "переобуч" in title.lower() or "смена" in title.lower():
            long_route = title
            break
    if not long_route:
        long_route = "Переобучение / долгий трек"
    if all(long_route.lower() != row["route"].lower() for row in rows):
        rows.append(
            {
                "route": long_route,
                "income": "позже",
                "speed": "медленнее",
                "risk": "средний",
                "need": "язык, время, деньги",
                "why": "Это долгосрочный трек для роста квалификации или переобучения, если быстрый вход не перекрывает потребности.",
                "good": "Потенциал более сильного роста и расширения карьерных опций.",
                "obstacle": "Потребует времени, ресурса и подтверждения готовности к обучению.",
                "first_step": "Проверить, можно ли начать с малого теста рынка без полной смены траектории.",
                "uncertainty": "средняя",
            }
        )

    return rows[:3]


def _format_route_comparison(rows: list[dict[str, str]]) -> str:
    blocks: list[str] = ["Сравнение маршрутов"]
    for idx, row in enumerate(rows, start=1):
        blocks.append(
            "\n".join(
                [
                    f"{idx}. {row.get('route', '-')}",
                    f"Почему предложен: {row.get('why', 'Данных недостаточно')}",
                    f"Что хорошего: {row.get('good', 'Данных недостаточно')}",
                    f"Что может помешать: {row.get('obstacle', 'Данных недостаточно')}",
                    f"Что нужно для первого шага: {row.get('first_step', 'Данных недостаточно')}",
                    f"Неопределённость: {row.get('uncertainty', 'средняя')}",
                    f"Потенциал дохода: {row.get('income', '-')}; скорость: {row.get('speed', '-')}; риск: {row.get('risk', '-')}; нужно: {row.get('need', '-')}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _format_alternative_route(route: dict[str, object]) -> str:
    name = str(route.get("name") or route.get("route") or "-").strip()
    roles = route.get("roles") if isinstance(route.get("roles"), list) else []
    skills = route.get("skills") if isinstance(route.get("skills"), list) else []
    risks = route.get("risks") if isinstance(route.get("risks"), list) else []
    return _clip(
        "\n".join(
            [
                f"Маршрут: {name}",
                f"Роли: {', '.join(str(item).strip() for item in roles if str(item).strip()) or '-'}",
                f"Срок: {str(route.get('timeline') or '-').strip()}",
                f"Первый шаг: {str(route.get('first_step') or '-').strip()}",
                f"Навыки: {', '.join(str(item).strip() for item in skills if str(item).strip()) or '-'}",
                f"Риски: {', '.join(str(item).strip() for item in risks if str(item).strip()) or '-'}",
            ]
        ),
        900,
    )


def _build_alternative_routes(report: dict, rows: list[dict[str, str]]) -> list[dict[str, object]]:
    if _is_construction_estimation_domain(report):
        stable = report.get("route_stable") if isinstance(report.get("route_stable"), dict) else _construction_route_stable()
        upskill = report.get("route_upskill") if isinstance(report.get("route_upskill"), dict) else _construction_route_upskill()
        comparison = report.get("route_comparison") if isinstance(report.get("route_comparison"), list) else _construction_route_comparison()

        route_project_coordination = {
            "name": "Переход в project coordination в строительстве",
            "roles": ["Construction Project Assistant", "Project Coordinator"],
            "timeline": "2-6 месяцев",
            "first_step": "собрать 10 вакансий Construction Project Assistant / Project Coordinator и выписать локальные процессы",
            "skills": [
                "коммуникация с подрядчиками",
                "локальные процессы строительной компании",
                "ведение задач и сроков",
            ],
            "risks": ["нужна быстрая адаптация к локальным процессам", "часто нужен уверенный рабочий польский"],
        }
        route_documentation = {
            "name": "Вход через строительную документацию",
            "roles": ["Construction Documentation Specialist", "Construction Documentation Assistant"],
            "timeline": "1-3 месяца",
            "first_step": "найти 10 вакансий по строительной документации и выписать повторяющиеся требования к документам и нормам",
            "skills": ["структура проектной документации", "строительные нормы", "Excel и аккуратный документооборот"],
            "risks": ["требуется точность и скорость", "может быть ниже стартовый статус"],
        }

        return [
            {
                "name": "Быстрый вход в строительную компанию",
                "roles": list(stable.get("main_roles", [])) if isinstance(stable.get("main_roles"), list) else [],
                "timeline": str(stable.get("timeline") or "1-3 месяца"),
                "first_step": str(stable.get("first_step") or "найти 10 вакансий в строительных компаниях с низким порогом входа"),
                "skills": ["базовый польский для рабочих задач", "документооборот в стройке", "базовый Excel"],
                "risks": ["может быть ниже статус", "может быть ниже стартовый доход"],
            },
            {
                "name": "Возврат к сметам через обучение",
                "roles": list(upskill.get("main_roles", [])) if isinstance(upskill.get("main_roles"), list) else [],
                "timeline": str(upskill.get("timeline") or "3-6 месяцев"),
                "first_step": str(upskill.get("first_step") or "собрать 10 вакансий и выписать требования"),
                "skills": list(upskill.get("skills_to_learn", [])) if isinstance(upskill.get("skills_to_learn"), list) else [],
                "risks": ["нужно учить нормы и язык", "более длинный путь до профильной роли"],
            },
            route_project_coordination,
            route_documentation,
        ]

    alternatives: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        alternatives.append(
            {
                "name": str(row.get("route") or "-").strip(),
                "roles": [str(row.get("route") or "-").strip()],
                "timeline": "-",
                "first_step": str(row.get("first_step") or "-").strip(),
                "skills": [str(row.get("need") or "-").strip()],
                "risks": [str(row.get("obstacle") or "-").strip()],
            }
        )
    return alternatives


def _apply_route_choice_to_report(report: dict, action: str, rows: list[dict[str, str]]) -> str:
    decision = _ensure_canonical_career_decision(report)
    if not decision:
        return ""

    route_id_map = {
        ROUTE_CHOICE_STABLE: "route_stable",
        ROUTE_CHOICE_PRIVATE: "route_private",
        ROUTE_CHOICE_RETRAIN: "route_retrain",
        ROUTE_CHOICE_HELP: "route_help",
        ROUTE_CHOICE_OTHER: "route_other",
        ROUTE_CHOICE_CLOSE: "route_close",
        ROUTE_CHOICE_NO_LOGIC: "route_no_logic",
    }
    selected_route_id = route_id_map.get(action, "")

    if _is_construction_estimation_domain(report):
        stable = _construction_route_stable()
        upskill = _construction_route_upskill()
        comparison = _construction_route_comparison()
        report["route_stable"] = stable
        report["route_upskill"] = upskill
        report["route_comparison"] = comparison

        action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
        today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}

        if action == ROUTE_CHOICE_STABLE:
            roles = stable.get("main_roles") if isinstance(stable.get("main_roles"), list) else []
            main_path = " / ".join(str(item).strip() for item in roles[:2] if str(item).strip()) or "Site Office Assistant / Construction Documentation Assistant"
            decision["recommended_main_path"] = main_path
            decision["backup_path"] = "Assistant Cost Estimator / Junior Quantity Surveyor"
            decision["why_this_path"] = str(stable.get("goal") or "быстрее войти в строительную компанию, даже не сразу сметчиком")
            today["action"] = str(stable.get("first_step") or "найти 10 вакансий в строительных компаниях с низким порогом входа")
            today["timebox"] = "15 минут"
            today["result"] = "Есть список из 10 вакансий в строительных компаниях с низким порогом входа."
            action_plan["today"] = today
            report["action_plan"] = action_plan
            report["route_type"] = "route_stable"
            stable_payload = dict(stable)
            stable_payload["risks"] = ["может быть ниже статус", "может быть ниже стартовый доход"]
            stable_payload["specialist_recommendation"] = "карьерный консультант для ускорения откликов и адаптации CV под стройкомпании"
            _apply_selected_route_regeneration(report, stable_payload, "route_stable")
        elif action == ROUTE_CHOICE_RETRAIN:
            roles = upskill.get("main_roles") if isinstance(upskill.get("main_roles"), list) else []
            main_path = " / ".join(str(item).strip() for item in roles[:2] if str(item).strip()) or "Assistant Cost Estimator / Junior Quantity Surveyor"
            decision["recommended_main_path"] = main_path
            decision["backup_path"] = "Site Office Assistant / Construction Documentation Assistant"
            decision["why_this_path"] = str(upskill.get("goal") or "за 3-6 месяцев добрать язык, нормы, программы и вернуться ближе к профессии")
            today["action"] = str(upskill.get("first_step") or "собрать 10 вакансий и выписать требования")
            today["timebox"] = "15 минут"
            today["result"] = "Есть 10 вакансий и выписаны повторяющиеся требования по возврату к сметной роли."
            action_plan["today"] = today
            report["action_plan"] = action_plan
            report["route_type"] = "route_upskill"
            upskill_payload = dict(upskill)
            upskill_payload["risks"] = ["нужно учить нормы и язык", "дольше до первого оффера"]
            upskill_payload["specialist_recommendation"] = "карьерный консультант + предметный разбор вакансий для ускорения возврата к сметам"
            _apply_selected_route_regeneration(report, upskill_payload, "route_upskill")
        elif action == ROUTE_CHOICE_HELP:
            report["route_type"] = "route_comparison"
            report["career_decision"] = decision
            return ""

        decision_summary = str(decision.get("decision_summary") or "").strip()
        suffix = "Маршрут зафиксирован совместно с пользователем на этапе выбора перед финальной картой."
        if suffix not in decision_summary:
            decision["decision_summary"] = f"{decision_summary} {suffix}".strip()
        decision["selected_route_id"] = selected_route_id or decision.get("selected_route_id") or ""
        report["career_decision"] = _ensure_canonical_career_decision(report, route_id=decision["selected_route_id"])
        return str(report["career_decision"].get("recommended_main_path") or "").strip()

    selected_route = str(decision.get("recommended_main_path") or "").strip()
    if action == ROUTE_CHOICE_STABLE:
        target = next((r for r in rows if "ниже" in str(r.get("risk", "")).lower() or "быстр" in str(r.get("speed", "")).lower()), rows[0] if rows else {})
        selected_route = str(target.get("route") or selected_route)
    elif action == ROUTE_CHOICE_PRIVATE:
        target = next((r for r in rows if "част" in str(r.get("route", "")).lower()), None)
        selected_route = str((target or {}).get("route") or "Постепенный выход на частные заказы")
    elif action == ROUTE_CHOICE_RETRAIN:
        target = next((r for r in rows if any(token in str(r.get("route", "")).lower() for token in ["переобуч", "долг", "смен"])), None)
        selected_route = str((target or {}).get("route") or "Переобучение / долгосрочный переход")
    elif action == ROUTE_CHOICE_HELP:
        target = next((r for r in rows if "ниже" in str(r.get("risk", "")).lower()), rows[0] if rows else {})
        selected_route = str(target.get("route") or selected_route)

    if selected_route:
        decision["recommended_main_path"] = selected_route
        decision["main_route"] = selected_route
        decision["selected_route_id"] = selected_route_id or decision.get("selected_route_id") or ""
        decision_summary = str(decision.get("decision_summary") or "").strip()
        suffix = "Маршрут зафиксирован совместно с пользователем на этапе выбора перед финальной картой."
        if suffix not in decision_summary:
            decision["decision_summary"] = f"{decision_summary} {suffix}".strip()
        report["career_decision"] = _ensure_canonical_career_decision(report, route_id=decision["selected_route_id"])
    return selected_route


def _short_conclusion_7_lines(report: dict) -> str:
    decision = _ensure_canonical_career_decision(report)
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    barriers = digital_human.get("barriers", {}) if isinstance(digital_human.get("barriers"), dict) else {}
    not_reset = report.get("what_not_reset", []) if isinstance(report.get("what_not_reset"), list) else []

    current_state = str(digital_human.get("current_state") or "").strip() or "данных пока недостаточно"
    market_value = str(digital_human.get("main_asset") or "").strip() or (str(not_reset[0]).strip() if not_reset else "данных пока недостаточно")
    main_limit = ""
    internal = [str(item).strip() for item in (barriers.get("internal") or []) if str(item).strip()]
    external = [str(item).strip() for item in (barriers.get("external") or []) if str(item).strip()]
    if internal:
        main_limit = internal[0]
    elif external:
        main_limit = external[0]
    else:
        main_limit = str(digital_human.get("main_barrier") or "").strip() or "данных пока недостаточно"

    resource_level = _level_label(report.get("resource_level"))
    readiness = str((digital_human.get("career_readiness") or {}).get("urgency") if isinstance(digital_human.get("career_readiness"), dict) else "").strip()
    readiness_text = readiness or "данных пока недостаточно"
    integration_level = _level_label(report.get("integration_level"))
    next_step = str(today.get("action") or "").strip() or "Сделайте 1 проверяемый шаг по маршруту сегодня (10-15 минут)."
    recommended_route = str(decision.get("main_route") or decision.get("recommended_main_path") or "").strip() or "маршрут уточняется"

    lines = [
        f"1. Кто вы как профессионал: {current_state}.",
        f"2. Ваша ценность на рынке труда: {market_value}.",
        f"3. Ограничения и ресурсы: ключевое ограничение — {main_limit}; уровень ресурса — {resource_level}.",
        f"4. Готовность к изменениям: {readiness_text}.",
        f"5. Интеграция в новой стране: уровень интеграции — {integration_level}.",
        f"6. Рекомендованный маршрут: {recommended_route}.",
        f"7. Следующий шаг: {next_step}",
    ]
    return "\n".join(lines)


def _full_conclusion_one_screen(report: dict) -> str:
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    barriers = digital_human.get("barriers", {}) if isinstance(digital_human.get("barriers"), dict) else {}
    facts_only = report.get("facts_only", {}) if isinstance(report.get("facts_only"), dict) else {}
    unknowns = [str(item).strip() for item in (facts_only.get("unknowns") or []) if str(item).strip()][:3]
    not_reset = report.get("what_not_reset", []) if isinstance(report.get("what_not_reset"), list) else []

    strengths = [str(item).strip() for item in not_reset if str(item).strip()][:3]
    internal = [str(item).strip() for item in (barriers.get("internal") or []) if str(item).strip()][:2]
    external = [str(item).strip() for item in (barriers.get("external") or []) if str(item).strip()][:2]
    next_step = str(today.get("action") or "").strip() or "Сделайте 1 проверяемый шаг по маршруту сегодня (10-15 минут)."

    lines = [
        "Полное заключение (1 экран)",
        "",
        f"Кто вы сейчас: {str(digital_human.get('current_state') or 'данных пока недостаточно').strip()}.",
        f"Что не обнулилось: {', '.join(strengths) if strengths else 'данных пока недостаточно'}.",
        f"Что помогает: {str(digital_human.get('main_asset') or 'данных пока недостаточно').strip()}.",
        f"Что тормозит: {', '.join(internal + external) if (internal or external) else str(digital_human.get('main_barrier') or 'данных пока недостаточно').strip()}.",
        f"Ресурс и устойчивость: {_resource_human_message(report.get('resource_level')).splitlines()[0]}",
        f"Интеграция: {_integration_human_message(report.get('integration_level')).splitlines()[0]}",
        f"Основной маршрут: {str(decision.get('recommended_main_path') or 'маршрут уточняется').strip()}.",
        f"Почему он: {str(decision.get('why_this_path') or 'опирается на подтвержденные факты профиля').strip()}.",
        f"Что уточнить: {', '.join(unknowns) if unknowns else 'критичных неизвестных сейчас нет'}.",
        f"Первый шаг: {next_step}",
    ]
    return "\n".join(lines)


def _written_conclusion_from_report(report: dict) -> str:
    decision = _ensure_canonical_career_decision(report)
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    weekly_plan = report.get("weekly_plan", []) if isinstance(report.get("weekly_plan"), list) else []
    first_month = (report.get("development_map") or {}).get("first_month", []) if isinstance((report.get("development_map") or {}).get("first_month"), list) else []
    facts_only = report.get("facts_only", {}) if isinstance(report.get("facts_only"), dict) else {}
    unknowns = [str(item).strip() for item in (facts_only.get("unknowns") or []) if str(item).strip()][:4]
    barriers = digital_human.get("barriers", {}) if isinstance(digital_human.get("barriers"), dict) else {}
    not_reset = report.get("what_not_reset", []) if isinstance(report.get("what_not_reset"), list) else []
    competency_signals = report.get("competency_signals", []) if isinstance(report.get("competency_signals"), list) else []
    energy_sources = report.get("energy_sources", []) if isinstance(report.get("energy_sources"), list) else []
    priorities = report.get("career_priorities", []) if isinstance(report.get("career_priorities"), list) else []
    resume_analysis = report.get("resume_analysis", {}) if isinstance(report.get("resume_analysis"), dict) else {}

    rows = _build_route_comparison_rows(report)
    route_lines = []
    labels = ["пессимистический", "базовый", "оптимистический"]
    for idx, row in enumerate(rows[:3]):
        label = labels[idx] if idx < len(labels) else f"вариант {idx + 1}"
        route_lines.append(
            f"- {label}: {row.get('route', '-')}; плюс: {row.get('good', '-')}; риск: {row.get('obstacle', '-')}; условие: {row.get('need', '-')}."
        )

    is_construction_domain = _is_construction_estimation_domain(report)
    route_stable = report.get("route_stable") if isinstance(report.get("route_stable"), dict) else {}
    route_upskill = report.get("route_upskill") if isinstance(report.get("route_upskill"), dict) else {}
    route_comparison = report.get("route_comparison") if isinstance(report.get("route_comparison"), list) else []

    if is_construction_domain:
        if not route_stable:
            route_stable = _construction_route_stable()
        if not route_upskill:
            route_upskill = _construction_route_upskill()
        if not route_comparison:
            route_comparison = _construction_route_comparison()

    route_stable_block = ""
    route_upskill_block = ""
    route_comparison_block = ""
    if is_construction_domain:
        stable_roles = ", ".join(str(item).strip() for item in (route_stable.get("main_roles") if isinstance(route_stable.get("main_roles"), list) else []) if str(item).strip()) or "-"
        upskill_roles = ", ".join(str(item).strip() for item in (route_upskill.get("main_roles") if isinstance(route_upskill.get("main_roles"), list) else []) if str(item).strip()) or "-"
        upskill_skills = ", ".join(str(item).strip() for item in (route_upskill.get("skills_to_learn") if isinstance(route_upskill.get("skills_to_learn"), list) else []) if str(item).strip()) or "-"
        comparison_rows = []
        for item in route_comparison[:3]:
            if not isinstance(item, dict):
                continue
            roles = ", ".join(str(role).strip() for role in (item.get("roles") if isinstance(item.get("roles"), list) else []) if str(role).strip()) or "-"
            comparison_rows.append(
                f"- {str(item.get('name') or '-').strip()}: speed={str(item.get('speed') or '-').strip()}, risk={str(item.get('risk') or '-').strip()}, roles={roles}, cost={str(item.get('cost') or '-').strip()}."
            )
        route_stable_block = (
            "route_stable:\n"
            f"main_roles={stable_roles}; goal={str(route_stable.get('goal') or '-').strip()}; "
            f"timeline={str(route_stable.get('timeline') or '-').strip()}; first_step={str(route_stable.get('first_step') or '-').strip()}."
        )
        route_upskill_block = (
            "route_upskill:\n"
            f"main_roles={upskill_roles}; goal={str(route_upskill.get('goal') or '-').strip()}; "
            f"skills_to_learn={upskill_skills}; timeline={str(route_upskill.get('timeline') or '-').strip()}; "
            f"first_step={str(route_upskill.get('first_step') or '-').strip()}."
        )
        route_comparison_block = "route_comparison:\n" + (" ".join(comparison_rows) if comparison_rows else "-")

    today_task = str(today.get("action") or "").strip() or "Сделайте 1 проверяемый шаг по маршруту сегодня (5-20 минут)."
    today_time = str(today.get("timebox") or "").strip() or "5-20 минут"
    week_goals = [str(item.get("focus") or item.get("task") or "").strip() for item in weekly_plan if isinstance(item, dict)][:4]
    if not week_goals and first_month:
        week_goals = [str(item.get("focus") or "").strip() for item in first_month if isinstance(item, dict) and str(item.get("focus") or "").strip()][:4]

    swot_strengths = [str(item).strip() for item in not_reset if str(item).strip()][:3]
    swot_weaknesses = [str(item).strip() for item in (barriers.get("internal") or []) if str(item).strip()][:2] + [str(item).strip() for item in (barriers.get("external") or []) if str(item).strip()][:2]
    swot_blind = [str(digital_human.get("main_risk") or "").strip(), str(digital_human.get("main_fear") or "").strip()]
    swot_blind = [item for item in swot_blind if item][:2]
    swot_consider = [f"ресурс: {_level_label(report.get('resource_level'))}", f"интеграция: {_level_label(report.get('integration_level'))}"]

    self_actions = []
    if swot_weaknesses:
        self_actions.append("действовать микрошагами 5-15 минут и фиксировать факт выполнения")
    self_actions.append("держать один основной маршрут минимум 7 дней без хаотичного переключения")
    specialist_actions = [
        "если тревога/перегруз держатся неделями и блокируют действия, полезен разбор со специалистом",
        "если маршрут понятен, но нет движения, полезен внешний разбор барьера и корректировка шага",
    ]

    heard_bits: list[str] = []
    if str(digital_human.get("current_state") or "").strip():
        heard_bits.append(str(digital_human.get("current_state") or "").strip())
    if str(digital_human.get("main_asset") or "").strip():
        heard_bits.append(f"главный актив: {str(digital_human.get('main_asset') or '').strip()}")
    if str(digital_human.get("main_risk") or "").strip():
        heard_bits.append(f"главный риск: {str(digital_human.get('main_risk') or '').strip()}")
    if str(digital_human.get("main_barrier") or "").strip():
        heard_bits.append(f"главное ограничение: {str(digital_human.get('main_barrier') or '').strip()}")
    heard_text = "; ".join(heard_bits[:4]) if heard_bits else "данных пока недостаточно"

    lines = [
        "Письменное заключение (полное по ТЗ)",
        "",
        f"Кто вы как профессионал: {str(digital_human.get('current_state') or 'данных пока недостаточно').strip()}.",
        f"Ваша ценность на рынке труда: {str(digital_human.get('main_asset') or 'данных пока недостаточно').strip()}.",
        f"Ограничения и ресурсы: уровень ресурса — {_level_label(report.get('resource_level'))}; ключевой барьер — {str(digital_human.get('main_barrier') or 'данных пока недостаточно').strip()}.",
        f"Готовность к изменениям: {str((digital_human.get('career_readiness') or {}).get('urgency') if isinstance(digital_human.get('career_readiness'), dict) else 'данных пока недостаточно').strip() or 'данных пока недостаточно'}.",
        f"Интеграция в новой стране: уровень интеграции — {_level_label(report.get('integration_level'))}.",
        f"Рекомендованный маршрут: {str(decision.get('main_route') or decision.get('recommended_main_path') or 'маршрут уточняется').strip()}.",
        f"Следующий шаг: {today_task}",
        "",
        f"1. Что я услышал: {heard_text}.",
        f"2. Профессиональное ядро: {_professional_core_summary(report)}",
        f"3. Сильные стороны и опоры: {', '.join([str(item).strip() for item in competency_signals if str(item).strip()][:5]) or 'данных пока недостаточно'}; источники энергии: {', '.join([str(item).strip() for item in energy_sources if str(item).strip()][:4]) or 'данных пока недостаточно'}.",
        f"4. Ограничения и неизвестные: {', '.join(swot_weaknesses) if swot_weaknesses else 'данных пока недостаточно'}. Уточнить: {', '.join(unknowns) if unknowns else 'критичных неизвестных сейчас нет'}.",
        f"SWOT: strengths={', '.join(swot_strengths) if swot_strengths else '-'}; weaknesses={', '.join(swot_weaknesses) if swot_weaknesses else '-'}; blind_spots={', '.join(swot_blind) if swot_blind else '-'}; important={', '.join(swot_consider)}.",
        f"Психо/соц (без диагнозов): самому — {', '.join(self_actions)}; со специалистом — {', '.join(specialist_actions)}.",
        f"5. Устойчивость в период изменений: {_resource_human_message(report.get('resource_level'))}",
        f"6. Интеграция в новой стране: {_integration_human_message(report.get('integration_level'))}",
        f"7. Сравнение маршрутов (быстрый доход / основной / долгосрочный; пессимистический-базовый-оптимистический): {' '.join(route_lines) if route_lines else 'данных пока недостаточно.'}",
        (
            "8. Выбранный маршрут и первый шаг: "
            f"{str(decision.get('main_route') or decision.get('recommended_main_path') or 'маршрут уточняется').strip()}. "
            f"Шаг: {today_task} ({today_time}). "
            "Кнопки: Сделал / Слишком сложно / Сделать проще / Другой шаг."
        ),
        f"9. План на 30 дней: {', '.join(week_goals) if week_goals else 'до 4 недельных целей, по одному основному действию в день и при необходимости одному дополнительному шагу поддержки.'}",
        (
            "10. Анализ резюме: "
            + (
                f"сильные стороны — {', '.join([str(item).strip() for item in (resume_analysis.get('what_is_good') or []) if str(item).strip()][:4]) or 'данных пока недостаточно'}; "
                f"пробелы/правки — {', '.join([str(item).strip() for item in (resume_analysis.get('what_is_missing') or []) if str(item).strip()][:4]) or 'данных пока недостаточно'}; "
                f"несостыковки — {', '.join([str(item).strip() for item in (resume_analysis.get('inconsistencies') or []) if str(item).strip()][:3]) or 'не выявлено'}"
            )
        )
        if resume_analysis
        else "10. Анализ резюме: CV не загружено: используйте кнопку «Загрузить резюме для анализа».",
        (
            "11. Что может быть не так в выводе: карта меняется при новых данных о языке, документах, резюме, приоритетах, контактах и рынке. "
            "Кнопки: Всё похоже на правду / Исправить факт / Изменить приоритет / Не согласен с маршрутом."
        ),
        (f"12. Отдельный блок route_stable: {route_stable_block}" if route_stable_block else ""),
        (f"13. Отдельный блок route_upskill: {route_upskill_block}" if route_upskill_block else ""),
        (f"14. Отдельный блок route_comparison: {route_comparison_block}" if route_comparison_block else ""),
        (f"15. Финал для construction-кейса:\n{_construction_final_case_block()}" if is_construction_domain else ""),
        f"Приоритеты сейчас: {', '.join([str(item).strip() for item in priorities if str(item).strip()][:4]) or 'данных пока недостаточно'}.",
    ]
    return "\n".join(line for line in lines if str(line).strip())


async def _send_final_map_bundle(message: Message, state: FSMContext, lang: str, report: dict) -> None:
    ensure_next_step_guidance(report)
    data = await state.get_data()
    report_generation_id = str(data.get("report_generation_id") or "").strip()

    selected_route = str((report.get("career_decision") or {}).get("recommended_main_path") if isinstance(report.get("career_decision"), dict) else "").strip()
    first_step = _today_task_from_report(report)
    validation_text = _written_conclusion_from_report(report)
    try:
        validate_final_report(str(report.get("profile_domain") or "").strip(), selected_route, first_step, validation_text)
    except ValueError:
        if not _is_construction_estimation_domain(report):
            raise
        _rebuild_construction_report_for_final(report)
        selected_route = str((report.get("career_decision") or {}).get("recommended_main_path") if isinstance(report.get("career_decision"), dict) else "").strip()
        first_step = _today_task_from_report(report)
        validation_text = _written_conclusion_from_report(report)
        validate_final_report(str(report.get("profile_domain") or "").strip(), selected_route, first_step, validation_text)
        await _track_event(
            message,
            state,
            "final_report_validated_after_rebuild",
            meta={"profile_domain": str(report.get("profile_domain") or ""), "selected_route": selected_route},
        )

    await state.set_state(CareerFlow.REPORT_GENERATING)
    await message.answer(t(lang, "final_short_intro"), reply_markup=route_choice_keyboard())

    short_conclusion = _short_conclusion_7_lines(report)
    await _answer_safe(message, _clip(short_conclusion, 3500), reply_markup=route_choice_keyboard())
    await message.answer(t(lang, "report_file_preparing_wait"), reply_markup=route_choice_keyboard())

    pdf_report_path = ""
    html_report_path = ""
    docx_report_path = ""
    rows = _build_route_comparison_rows(report)
    await state.update_data(route_compare_rows=rows)
    try:
        user_name = " ".join(
            part
            for part in [
                (message.from_user.first_name if message.from_user else "") or "",
                (message.from_user.last_name if message.from_user else "") or "",
            ]
            if part
        ).strip()

        # Required flow: HTML report is always prepared first.
        html_path = generate_html_report_file(
            report,
            output_dir=settings.report_output_dir,
            user_name=user_name,
            profile_version=report_generation_id,
        )
        html_report_path = _normalize_report_path(str(html_path))
        html_path = Path(html_report_path)
        html_url = _report_public_url(html_path)

        await _track_event(message, state, "html_ready", meta={"path": html_path.name})
        await message.answer_document(
            FSInputFile(html_report_path),
            caption=t(lang, "web_report_ready"),
            reply_markup=telegram_link_keyboard("📄 Открыть в браузере", html_url) if html_url else route_choice_keyboard(),
        )
        if html_url:
            await message.answer(t(lang, "web_report_ready"), reply_markup=telegram_link_keyboard("📄 Открыть полный разбор", html_url))

        _cancel_pdf_task(message.chat.id)
        _PDF_READY_BY_CHAT.pop(message.chat.id, None)
        _PDF_TASKS[message.chat.id] = asyncio.create_task(
            _run_pdf_generation_background(
                bot=message.bot,
                chat_id=message.chat.id,
                lang=lang,
                html_path=html_path,
                report_generation_id=report_generation_id,
            )
        )
        # HTML is the primary user-facing result. Keep optional exports silent.
        try:
            docx_path, _ = generate_docx_report_file(
                report,
                output_dir=settings.report_output_dir,
                user_name=user_name,
                profile_version=report_generation_id,
            )
            if docx_path:
                docx_report_path = _normalize_report_path(str(docx_path))
        except Exception as docx_exc:
            print(f"[docx] chat_id={message.chat.id} generation_error={type(docx_exc).__name__}: {docx_exc}", flush=True)
    except Exception as exc:
        print(f"[final-report] chat_id={message.chat.id} delivery_error={type(exc).__name__}: {exc}", flush=True)
        await _track_event(message, state, "pdf_generation_error", meta={"engine": settings.report_pdf_engine})
        await _send_text_report_fallback_document(message, lang, report)

    await state.set_state(CareerFlow.REPORT_READY)
    today_task = _today_task_from_report(report)
    await state.update_data(
        final_report=report,
        final_report_generated=True,
        skiller_today_task=today_task,
        chat_id=message.chat.id,
        pdf_report_path=pdf_report_path,
        html_report_path=html_report_path,
        docx_report_path=docx_report_path,
        execution_steps=_build_execution_steps(report),
        execution_progress={},
        current_execution_day=0,
    )
    if report_generation_id:
        update_report_files(
            report_generation_id,
            html_report_path=html_report_path,
            pdf_report_path=pdf_report_path,
            docx_report_path=docx_report_path,
        )

    # After route selection and report delivery, move user to action stage:
    # continue in bot steps, specialist route, or support group.
    await message.answer(t(lang, "post_result_hint"), reply_markup=next_step_cta_keyboard(report))


def _shorten_first_step_for_overload(report: dict) -> None:
    action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
    step = str(today.get("action") or "").strip()
    if not step:
        return
    lowered = step.lower()
    if any(token in lowered for token in ["не знаю", "страш", "нет сил", "сложно", "боюсь"]):
        today["action"] = "Открыть 3 вакансии и выбрать 1 черновик отклика"
        today["timebox"] = "5 минут"
        today["result"] = "Один черновик или одно сообщение"
        action_plan["today"] = today
        report["action_plan"] = action_plan


async def _present_route_selection(message: Message, state: FSMContext, lang: str, report: dict) -> None:
    rows = _build_route_comparison_rows(report)
    compare_text = _format_route_comparison(rows)
    await state.update_data(route_compare_rows=rows, alternative_routes=_build_alternative_routes(report, rows), current_route_index=-1)
    data = await state.get_data()
    strategy_code = str(data.get("career_strategy") or "").strip()
    await state.set_state(CareerFlow.ROUTE_SELECTION)
    if strategy_code not in {"fast_income", "upskill_for_profile", "long_transition", "need_decision"}:
        await state.update_data(awaiting_career_strategy_choice=True)
        await message.answer(t(lang, "career_strategy_intro"), reply_markup=career_strategy_keyboard())
        return

    await state.update_data(awaiting_career_strategy_choice=False)
    await message.answer(t(lang, "route_compare_intro"), reply_markup=route_choice_keyboard())
    await _answer_safe(message, f"{t(lang, 'route_compare_title')}\n\n{compare_text}", reply_markup=route_choice_keyboard())
    await message.answer(t(lang, "route_compare_question"), reply_markup=route_choice_keyboard())


def report_chunks(report: dict, lang: str) -> dict[str, str]:
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    recommendations = report.get("career_recommendations", [])
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    roadmap = report.get("development_map", {})
    week = report.get("weekly_plan", [])
    energy_sources = report.get("energy_sources", []) if isinstance(report.get("energy_sources"), list) else []
    career_priorities = report.get("career_priorities", []) if isinstance(report.get("career_priorities"), list) else []
    competency_signals = report.get("competency_signals", []) if isinstance(report.get("competency_signals"), list) else []
    resource_level = _resource_human_message(report.get("resource_level"))
    integration_level = _integration_human_message(report.get("integration_level"))

    header = _clip(
        "\n\n".join(
            [
                f"=== {t(lang, 'digital_human_label')} ===\n{digital_human.get('summary') or '-'}",
                f"Ваше профессиональное ядро:\n{_professional_core_summary(report)}",
                f"{t(lang, 'who_now_label')}:\n{digital_human.get('current_state') or '-'}",
                f"{t(lang, 'main_asset_label')}:\n{digital_human.get('main_asset') or '-'}",
                f"{t(lang, 'main_risk_label')}:\n{digital_human.get('main_risk') or '-'}",
                f"Главный барьер:\n{digital_human.get('main_barrier') or '-'}",
                f"Главный страх:\n{digital_human.get('main_fear') or '-'}",
                f"Источники энергии:\n{_list_block(energy_sources)}",
                f"Карьерные приоритеты:\n{_list_block(career_priorities)}",
                f"STAR-компетенции:\n{_list_block(competency_signals)}",
                f"Ресурс и рабочий темп:\n{resource_level}",
                f"Состояние интеграции:\n{integration_level}",
                f"Скрытые сильные стороны:\n{_list_block(digital_human.get('hidden_strengths', []))}",
                f"{t(lang, 'fast_income_path_label')}:\n{digital_human.get('fastest_path_to_income') or '-'}",
                f"{t(lang, 'strengths_label')}:\n{_list_block((digital_human.get('skills') or {}).get('professional', []))}",
                f"{t(lang, 'barriers_label')}:\n{_list_block((digital_human.get('barriers') or {}).get('critical', []))}",
            ]
        )
    )

    directions_lines = [t(lang, "directions_label")]
    for idx, rec in enumerate(recommendations[:5], start=1):
        if not isinstance(rec, dict):
            continue
        directions_lines.append(
            _clip(
                "\n".join(
                    [
                        f"{idx}. {rec.get('title', '-') } ({rec.get('match_percent', 0)}%)",
                        f"• Почему подходит: {rec.get('why_fit', '-')}",
                        f"• Плюсы: {_join_items(rec.get('pros', []), 4)}",
                        f"• Риски: {_join_items(rec.get('risks', []), 4)}",
                        f"• Срок входа: {rec.get('entry_timeline', '-')}",
                        f"• Доход: {rec.get('income_range', '-')}",
                    ]
                ),
                900,
            )
        )
    directions = "\n\n".join(directions_lines)

    decision_block = _clip(
        "\n".join(
            [
                f"=== {t(lang, 'decision_system_label')} ===",
                f"Рекомендуемый маршрут:\n{decision.get('recommended_main_path') or '-'}",
                f"Почему именно он:\n{decision.get('why_this_path') or '-'}",
                f"Почему не другие:\n{_list_block(decision.get('why_not_other_paths', []))}",
                f"Запасной маршрут:\n{decision.get('backup_path') or '-'}",
                f"Пока не стоит делать:\n{decision.get('avoid_for_now') or '-'}",
                f"Итог:\n{decision.get('decision_summary') or '-'}",
                f"Стратегия:\n{_strategy_summary_text(report) or '-'}",
            ]
        )
    )

    route_lines = [f"=== {t(lang, 'route_label')} ===", f"Где вы сейчас:\n{roadmap.get('current_state') or '-'}", f"Куда идем:\n{roadmap.get('goal') or '-'}", f"Чего не хватает:\n{_list_block(roadmap.get('gap', []))}"]
    for item in roadmap.get("route", [])[:5]:
        if not isinstance(item, dict):
            continue
        route_lines.append(f"\n{item.get('stage', '-')}")
        route_lines.append(f"• Цель: {item.get('objective', '-')}")
        route_lines.append(f"• Действия:\n{_list_block(item.get('actions', []))}")
        route_lines.append(f"• Результат: {item.get('output', '-')}")
        route_lines.append(f"• Срок: {item.get('timeline', '-')}")
    route = _clip("\n".join(route_lines))

    week_lines = [f"=== {t(lang, 'week_label')} ==="]
    for item in week[:7]:
        if not isinstance(item, dict):
            continue
        week_lines.append(
            f"День {item.get('day', '-')}: {item.get('focus', '-')}\n"
            f"• Задача: {item.get('task', '-')}\n"
            f"• Время: {item.get('time', '-')}\n"
            f"• Ожидаемый результат: {item.get('result', '-')}\n"
            f"• Зачем это делать: {item.get('why', '-')}"
        )
    week_block = _clip("\n".join(week_lines))

    market_block = format_market_analysis(report, lang)
    solutions_block = format_real_solutions(report, lang)
    translation_block = format_career_translation(report, lang)
    layers_block = format_experience_layers(report, lang)
    not_reset_block = format_what_not_reset(report, lang)
    bridges_block = format_career_bridges(report, lang)
    barrier_block = format_barrier_analysis(report, lang)
    integration_block = format_social_integration(report, lang)
    month_roadmap_block = format_month_roadmap(report, lang)
    today_block, week_actions_block, month_actions_block = format_action_plan(report, lang)
    closing = _clip(f"{t(lang, 'closing_label')}: {report.get('closing_message') or '-'}")

    return {
        "header": header,
        "layers": layers_block,
        "not_reset": not_reset_block,
        "market": market_block,
        "directions": directions,
        "solutions": solutions_block,
        "translation": translation_block,
        "bridges": bridges_block,
        "barrier": barrier_block,
        "integration": integration_block,
        "decision": decision_block,
        "route": route,
        "month_roadmap": month_roadmap_block,
        "today": today_block,
        "week_actions": week_actions_block,
        "month_actions": month_actions_block,
        "week": week_block,
        "closing": closing,
    }


def format_final_report(report: dict, lang: str) -> list[str]:
    chunks = report_chunks(report, lang)
    premium_blocks = [
        "\n\n".join([chunks["header"], chunks["layers"], chunks["not_reset"], chunks["translation"], chunks["bridges"], chunks["barrier"], chunks["integration"]]),
        "\n\n".join([chunks["decision"], chunks["month_roadmap"], chunks["week"]]),
        "\n\n".join([chunks["today"], chunks["week_actions"], chunks["month_actions"], chunks["closing"]]),
    ]
    return [_clip(block) for block in premium_blocks]


async def _start_barriers_module(message: Message, state: FSMContext, lang: str) -> None:
    sequence = [BARRIER_GROUP_INTERNAL, BARRIER_GROUP_BEHAVIOR, BARRIER_GROUP_LIFE]
    await state.update_data(
        selected_barriers=[],
        selected_fears=[],
        selected_psych_markers=[],
        barrier_group_sequence=sequence,
        barrier_group_index=0,
        barrier_current_group=sequence[0],
    )
    await state.set_state(CareerFlow.SELECTING_BARRIERS)
    await message.answer(t(lang, "step_barriers"), reply_markup=barriers_group_keyboard(sequence[0]))
    await message.answer(t(lang, "barriers_prompt_internal"), reply_markup=barriers_group_keyboard(sequence[0]))


def _barrier_options_for_group(group: str) -> list[str]:
    if group == BARRIER_GROUP_INTERNAL:
        return PSYCH_BARRIER_OPTIONS[:5]
    if group == BARRIER_GROUP_BEHAVIOR:
        return PSYCH_BARRIER_OPTIONS[5:10]
    if group == BARRIER_GROUP_LIFE:
        return PSYCH_BARRIER_OPTIONS[10:]
    return list(PSYCH_BARRIER_OPTIONS)


def _barrier_prompt_key(group: str) -> str:
    if group == BARRIER_GROUP_INTERNAL:
        return "barriers_prompt_internal"
    if group == BARRIER_GROUP_BEHAVIOR:
        return "barriers_prompt_behavior"
    if group == BARRIER_GROUP_LIFE:
        return "barriers_prompt_life"
    return "barriers_prompt"


async def _advance_barrier_group(message: Message, state: FSMContext) -> bool:
    data = await state.get_data()
    lang = _user_language(data)
    sequence = list(data.get("barrier_group_sequence") or [BARRIER_GROUP_INTERNAL, BARRIER_GROUP_BEHAVIOR, BARRIER_GROUP_LIFE])
    current_index = int(data.get("barrier_group_index", 0))
    next_index = current_index + 1

    if next_index >= len(sequence):
        return False

    next_group = sequence[next_index]
    await state.update_data(barrier_group_index=next_index, barrier_current_group=next_group)
    await message.answer(t(lang, "barriers_next_group"), reply_markup=barriers_group_keyboard(next_group))
    await message.answer(t(lang, _barrier_prompt_key(next_group)), reply_markup=barriers_group_keyboard(next_group))
    return True


async def _maybe_offer_extended_diagnostics(message: Message, state: FSMContext, lang: str) -> bool:
    data = await state.get_data()
    user_mode = str(data.get("user_mode") or "calm_steps")
    if user_mode != "fast":
        return False
    if bool(data.get("mandatory_diagnostics_done")):
        return False
    if bool(data.get("mandatory_diagnostics_in_progress")):
        return True

    analysis_ext = dict(data.get("story_analysis") or {})
    analysis_ext["follow_up_questions"] = _mandatory_psych_social_questions()
    await state.update_data(
        story_analysis=analysis_ext,
        qa_index=0,
        awaiting_extended_diagnostics_choice=False,
        mandatory_diagnostics_in_progress=True,
        mandatory_diagnostics_done=False,
        extended_diagnostics_done=True,
    )
    await _track_event(message, state, "extended_diag_forced_start", meta={"stage": "post_fast_questions"})
    await message.answer(t(lang, "extended_diag_started"))
    data_fresh = await state.get_data()
    context = _build_interview_context(data_fresh, analysis_ext)
    await _save_interview_context(state, context)
    asked = await _ask_next_interview_question(
        message,
        state,
        data_fresh,
        analysis_ext,
        context,
        qa_index=0,
        lang=lang,
        user_mode=user_mode,
    )
    if not asked:
        await _start_barriers_module(message, state, lang)
    return True


async def _advance_after_questions(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    if bool(data.get("mandatory_diagnostics_in_progress")):
        await state.update_data(mandatory_diagnostics_in_progress=False, mandatory_diagnostics_done=True)
        await _track_event(message, state, "extended_diag_forced_completed", meta={"stage": "post_fast_questions"})
        await _start_barriers_module(message, state, lang)
        return
    if await _maybe_offer_extended_diagnostics(message, state, lang):
        return
    await _start_barriers_module(message, state, lang)


async def _start_questions_module(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    current_state = await state.get_state()
    existing_answers = list(data.get("qa_answers") or [])
    if current_state == CareerFlow.INTERVIEW.state and (existing_answers or int(data.get("qa_index") or 0) > 0):
        return
    story_text = (data.get("story_text") or "").strip()
    analysis_raw = data.get("story_analysis") or {}
    profile = data.get("interaction_profile") or _build_interaction_profile(story_text, data)
    user_mode = str(data.get("user_mode") or "calm_steps")
    user_segment = str(data.get("user_segment") or _detect_user_segment(story_text, analysis_raw))
    cv_uploaded = bool(data.get("cv_uploaded"))
    evidence_profile = _load_evidence_profile(data, analysis_raw)
    questions = _build_evidence_questions(evidence_profile, lang, user_mode)
    analysis = dict(analysis_raw)
    analysis["follow_up_questions"] = questions
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    # Mandatory requirement: barrier analysis must run in every mode.
    quick_report_after_questions = False

    await state.update_data(
        story_analysis=analysis,
        user_segment=user_segment,
        user_segment_label=_segment_label(user_segment),
        interaction_profile=profile,
        qa_answers=[],
        qa_index=0,
        answers_text="",
        quick_report_after_questions=quick_report_after_questions,
        selected_psych_markers=[],
        selected_psych_state=[],
        selected_coping=[],
        selected_barriers=[],
        selected_fears=[],
        selected_social_state=[],
        selected_integration_state=[],
        selected_energy_sources=[],
        selected_career_priorities=[],
        psych_selected=[],
        psych_state_selected=[],
        coping_selected=[],
        social_selected=[],
        integration_selected=[],
        energy_selected=[],
        priorities_selected=[],
        selected_choice_reasons={},
        pending_choice_reason={},
        awaiting_extended_diagnostics_choice=False,
        mandatory_diagnostics_in_progress=False,
        mandatory_diagnostics_done=False,
        extended_diagnostics_done=False,
        promised_question_count=len(questions),
        evidence_profile=evidence_profile.model_dump(),
        asked_question_signatures=[],
    )

    # PATCH-29: initialize dynamic interview context in session data.
    interview_context = _build_interview_context(
        {
            **data,
            "story_analysis": analysis,
            "evidence_profile": evidence_profile.model_dump(),
            "asked_question_signatures": [],
        },
        analysis,
    )
    await _save_interview_context(state, interview_context)

    if not questions:
        await state.set_state(CareerFlow.INTERVIEW)
        if cv_uploaded:
            _resume_debug_log(message, "questions_empty_after_resume")
        await message.answer(t(lang, "questions_empty"))
        await state.update_data(answers_text=t(lang, "resume_continue_without"))
        await _start_barriers_module(message, state, lang)
        return

    await state.set_state(CareerFlow.INTERVIEW)
    if cv_uploaded:
        await message.answer(t(lang, "step_questions_dynamic"))
    else:
        await message.answer(t(lang, "step_questions_dynamic"))

    # PATCH-26: build initial hypotheses.
    from services.hypothesis_engine import build_hypotheses_from_analysis  # noqa: PLC0415
    _hypotheses = build_hypotheses_from_analysis(analysis_raw)
    _hyps_payload = [h.model_dump() for h in _hypotheses]
    await state.update_data(conversation_hypotheses=_hyps_payload)
    if _hyps_payload:
        await _track_event(
            message,
            state,
            "career_hypothesis_created",
            meta={
                "count": len(_hyps_payload),
                "seed_statement": str((_hyps_payload[0] or {}).get("statement") or "")[:240],
            },
        )
    data_after_hyp = await state.get_data()
    interview_context = _build_interview_context(data_after_hyp, analysis)
    await _save_interview_context(state, interview_context)
    asked = await _ask_next_interview_question(
        message,
        state,
        data_after_hyp,
        analysis,
        interview_context,
        qa_index=0,
        lang=lang,
        user_mode=user_mode,
    )
    if not asked:
        await state.update_data(answers_text=t(lang, "resume_continue_without"))
        await _start_barriers_module(message, state, lang)
        return

    first_question = questions[0] if questions and isinstance(questions[0], dict) else {}
    if cv_uploaded:
        _resume_debug_log(message, "question_1_sent", question_id=first_question.get("id", 1))


_REPORT_PLACEHOLDER_NAMES: frozenset[str] = frozenset({
    "-", "данных недостаточно", "возможный маршрут", "possible route",
    "потребуется проверить", "предварительная гипотеза",
})


def _ensure_canonical_career_decision(report: dict, route_id: str | None = None) -> dict[str, object]:
    """Single source of truth for the final decision used by comparison, summary and HTML generation."""
    if not isinstance(report, dict):
        return {
            "decision_id": "",
            "main_route": {"route_id": "", "title": "", "type": "main"},
            "alternative_routes": [],
            "selected_route_id": route_id or "",
            "first_step": "",
            "missing_data": [],
            "professional_core": "",
            "market_value": "",
            "country_code": "",
            "country_name": "",
            "city": "",
        }

    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    route_context = report.get("route_context") if isinstance(report.get("route_context"), dict) else {}
    market = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
    recommendations = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
    profile_snapshot = report.get("profile_snapshot") if isinstance(report.get("profile_snapshot"), dict) else {}

    def _route_object(value: object, route_type: str = "main") -> dict[str, object]:
        if isinstance(value, dict):
            title = str(value.get("title") or value.get("name") or value.get("route") or "").strip()
            route_id = str(value.get("route_id") or value.get("id") or "").strip()
            if not title and route_type == "main":
                title = str(decision.get("recommended_main_path") or decision.get("main_route") or value.get("title") or "").strip()
            return {
                "route_id": route_id or _slugify(title or "route"),
                "title": title,
                "type": str(value.get("type") or route_type).strip() or route_type,
                "supporting_evidence": list(value.get("supporting_evidence", []) if isinstance(value.get("supporting_evidence"), list) else []),
                "advantages": list(value.get("advantages", []) if isinstance(value.get("advantages"), list) else []),
                "gaps": list(value.get("gaps", []) if isinstance(value.get("gaps"), list) else []),
                "first_test": str(value.get("first_test") or "").strip(),
                "confidence": str(value.get("confidence") or "").strip(),
            }
        title = str(value or "").strip()
        return {
            "route_id": _slugify(title or "route"),
            "title": title,
            "type": route_type,
            "supporting_evidence": [],
            "advantages": [],
            "gaps": [],
            "first_test": "",
            "confidence": "",
        }

    main_route_value = (
        decision.get("main_route")
        or decision.get("recommended_main_path")
        or decision.get("route")
        or (market[0].get("profession") if market and isinstance(market[0], dict) else "")
        or (recommendations[0].get("title") if recommendations and isinstance(recommendations[0], dict) else "")
        or ""
    )
    main_route = _route_object(main_route_value, "main")
    backup_route = decision.get("backup_path") or decision.get("secondary_route") or ""
    alternative_routes = []
    for candidate in [backup_route, decision.get("alternative_routes")]:
        if isinstance(candidate, list):
            for item in candidate:
                route_obj = _route_object(item, "alternative")
                if route_obj["title"] and route_obj["title"].lower() not in _REPORT_PLACEHOLDER_NAMES:
                    alternative_routes.append(route_obj)
        elif str(candidate).strip():
            route_obj = _route_object(candidate, "alternative")
            if route_obj["title"] and route_obj["title"].lower() not in _REPORT_PLACEHOLDER_NAMES:
                alternative_routes.append(route_obj)
    unique_routes: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for route in [main_route, *alternative_routes]:
        route_key = str(route.get("route_id") or _slugify(str(route.get("title") or "route"))).strip()
        if route_key in seen_ids or not str(route.get("title") or "").strip():
            continue
        seen_ids.add(route_key)
        unique_routes.append(route)
    main_route = unique_routes[0] if unique_routes else main_route
    alternative_routes = [route for route in unique_routes[1:] if route.get("title")]

    missing_data = decision.get("missing_data") if isinstance(decision.get("missing_data"), list) else []
    missing_data = [str(item).strip() for item in missing_data if str(item).strip()]
    if not missing_data:
        # Only absent decision-changing facts are missing. Use human labels: this
        # collection can be rendered in HTML/PDF and must never expose schema keys.
        required_facts = [
            ("minimum_monthly_income", "обязательный минимум дохода"),
            ("income_urgency", "срок выхода на необходимый доход"),
            ("documents_and_work_rights", "право на работу на выбранном рынке"),
        ]
        for key, label in required_facts:
            if not str(route_context.get(key) or "").strip():
                missing_data.append(label)

    country_name = (
        str(decision.get("country_name") or profile_snapshot.get("country_name") or route_context.get("country") or report.get("country_name") or "").strip()
        or str(profile_snapshot.get("country_code") or "").strip() == "LT" and "Литва"
        or str(route_context.get("country_code") or "").strip() == "LT" and "Литва"
        or ""
    )
    city = str(decision.get("city") or profile_snapshot.get("city") or route_context.get("city") or report.get("city") or "").strip()
    country_code = str(decision.get("country_code") or profile_snapshot.get("country_code") or route_context.get("country_code") or report.get("country_code") or "").strip()
    if not country_code and country_name.lower().startswith("лит"):
        country_code = "LT"
    if not country_name and country_code == "LT":
        country_name = "Литва"

    if alternative_routes:
        backup_path_title = str(alternative_routes[0].get("title") or "").strip()
    else:
        backup_path_title = str(backup_route or "").strip()

    canonical = {
        "decision_id": str(decision.get("decision_id") or decision.get("report_generation_id") or report.get("report_generation_id") or "").strip(),
        "session_id": str(decision.get("session_id") or report.get("session_id") or "").strip(),
        "profile_version": str(decision.get("profile_version") or report.get("profile_version") or report.get("report_generation_id") or "").strip(),
        "status": str(decision.get("status") or "preliminary").strip() or "preliminary",
        "professional_core": str(decision.get("professional_core") or report.get("professional_core") or _professional_core_summary(report) or "").strip(),
        "market_value": str(decision.get("market_value") or report.get("market_value") or "").strip(),
        "country_code": country_code,
        "country_name": country_name,
        "city": city,
        "current_role": str(decision.get("current_role") or "").strip(),
        "target_change": list(decision.get("target_change", []) if isinstance(decision.get("target_change"), list) else []),
        "candidate_routes": [main_route, *alternative_routes],
        "recommended_route": main_route,
        "constraints": list(decision.get("constraints", []) if isinstance(decision.get("constraints"), list) else []),
        "resources": list(decision.get("resources", []) if isinstance(decision.get("resources"), list) else []),
        "main_route": main_route,
        "alternative_routes": alternative_routes,
        "selected_route_id": str(route_id or decision.get("selected_route_id") or decision.get("route_selected_id") or main_route.get("route_id") or "").strip(),
        "first_step": str(decision.get("first_step") or _today_task_from_report(report) or "").strip(),
        "missing_data": missing_data,
        "recommended_main_path": str(main_route.get("title") or "").strip(),
        "backup_path": backup_path_title,
    }
    canonical.update({key: decision.get(key) for key in ["why_this_path", "why_not_other_paths", "avoid_for_now", "decision_summary", "country_code", "country_name", "city", "professional_core", "market_value", "first_step"] if key in decision})
    canonical["main_route"] = main_route
    canonical["alternative_routes"] = alternative_routes
    if route_id:
        canonical["selected_route_id"] = str(route_id).strip()
    decision = {**decision, **canonical}
    decision["main_route"] = main_route
    decision["recommended_main_path"] = str(main_route.get("title") or "").strip()
    decision["backup_path"] = backup_path_title
    report["career_decision"] = decision
    return decision


def _report_draft_is_empty(report: dict) -> bool:
    """True if the generated report lacks a viable career decision or first step."""
    if not isinstance(report, dict):
        return True
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    main_path = str(decision.get("recommended_main_path") or "").strip()
    if not main_path or main_path.lower() in _REPORT_PLACEHOLDER_NAMES:
        return True
    if not (report.get("market_analysis") or report.get("career_recommendations")):
        return True
    today = (report.get("action_plan") or {}).get("today") if isinstance(report.get("action_plan"), dict) else {}
    first_step = str((today or {}).get("action") or "").strip()
    if not first_step or first_step == "-":
        return True
    return False


def _ensure_preliminary_report(report: dict, data: dict) -> dict:
    """Create a useful minimum map when readiness clarification reaches its limit."""
    if not isinstance(report, dict):
        report = {}
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    analysis = data.get("story_analysis") if isinstance(data.get("story_analysis"), dict) else {}
    hypotheses = [str(item).strip() for item in analysis.get("professional_core_hypotheses") or [] if str(item).strip()]
    current_identity = str(analysis.get("current_identity") or "").strip()
    main_hypothesis = hypotheses[0] if hypotheses else current_identity or "Маршрут на основе подтверждённых функций"
    backup_hypothesis = hypotheses[1] if len(hypotheses) > 1 else "Смежная роль с максимальным сохранением опыта"
    decision.setdefault("recommended_main_path", main_hypothesis)
    decision.setdefault("backup_path", backup_hypothesis)
    report["career_decision"] = decision
    report.setdefault("market_analysis", [{"signal": "Рыночная доступность и диапазон дохода требуют проверки по выбранной стране; цифры не оценивались без источника."}])
    report.setdefault("career_recommendations", [f"Проверить гипотезу «{main_hypothesis}» на вакансиях целевого рынка без увольнения."])
    digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
    digital_human.setdefault("current_state", str(data.get("story_text") or "Опытный специалист с переносимыми навыками" )[:500])
    digital_human.setdefault("main_asset", ", ".join(str(item) for item in (analysis.get("strengths") or [])[:4]) or "подтверждённые функции из истории")
    report["digital_human"] = digital_human
    action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
    today.setdefault("action", f"Найти пять вакансий «{main_hypothesis}» в выбранной стране и отметить требования, подтверждённые вашим опытом.")
    today.setdefault("timebox", "30 минут")
    action_plan["today"] = today
    report["action_plan"] = action_plan
    return report


async def _build_and_send_report(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()

    # Check for crisis signals before proceeding
    answers_text = str(data.get("answers_text") or "").strip()
    story_text = str(data.get("story_text") or "").strip()
    combined_input = f"{story_text} {answers_text}"
    
    if await _maybe_switch_to_crisis_support(message, state, lang, combined_input, source="report_build"):
        return

    report_generation_id = str(data.get("report_generation_id") or "").strip()
    if report_generation_id:
        stored = get_report_by_generation_id(report_generation_id)
        stored_report = (stored or {}).get("report") if isinstance(stored, dict) else {}
        if isinstance(stored_report, dict) and stored_report:
            route_context = data.get("route_context") if isinstance(data.get("route_context"), dict) else {}
            _apply_strategy_outputs(stored_report, {str(key): str(value) for key, value in route_context.items()}, str(data.get("career_strategy") or ""))
            chunks = report_chunks(stored_report, lang)
            await state.update_data(
                final_report=stored_report,
                report_chunks=chunks,
                post_result_stage="ready",
                final_report_generated=True,
                report_generation_id=report_generation_id,
            )
            await _track_event(message, state, "report_reused_idempotent", meta={"report_generation_id": report_generation_id})
            await _present_route_selection(message, state, lang, stored_report)
            return

    if not settings.legacy_career_report_enabled:
        await _build_and_send_career_assessment(message, state, lang, data)
        return

    story_text = (data.get("story_text") or "").strip()
    story_analysis = data.get("story_analysis") or {}
    answers_text = (data.get("answers_text") or "").strip()
    social_state = data.get("selected_social_state") or []
    if isinstance(social_state, list) and social_state:
        social_block = "\n".join(f"- {item}" for item in social_state[:6] if str(item).strip())
        if social_block:
            answers_text = (answers_text + "\n\nСоциальная поддержка и миграционный статус:\n" + social_block).strip()
    integration_state = data.get("selected_integration_state") or []
    if isinstance(integration_state, list) and integration_state:
        integration_state_block = "\n".join(f"- {item}" for item in integration_state[:5] if str(item).strip())
        if integration_state_block:
            answers_text = (answers_text + "\n\nИнтеграция пользователя:\n" + integration_state_block).strip()
    # Derive integration_level from time in country if mentioned in answers
    answers_text_low = answers_text.lower()
    if "больше 2 лет" in answers_text_low or "более 2 лет" in answers_text_low:
        pass  # Will be caught by _ensure_integration_level
    elif "меньше 6 месяцев" in answers_text_low or "менее 6 месяц" in answers_text_low:
        pass  # Will be caught by _ensure_integration_level
    energy_sources = data.get("selected_energy_sources") or []
    if isinstance(energy_sources, list) and energy_sources:
        energy_block = "\n".join(f"- {item}" for item in energy_sources[:5] if str(item).strip())
        if energy_block:
            answers_text = (answers_text + "\n\nИсточники энергии пользователя:\n" + energy_block).strip()
    career_priorities = data.get("selected_career_priorities") or []
    if isinstance(career_priorities, list) and career_priorities:
        priorities_block = "\n".join(f"- {item}" for item in career_priorities[:4] if str(item).strip())
        if priorities_block:
            answers_text = (answers_text + "\n\nКарьерные приоритеты пользователя:\n" + priorities_block).strip()
    # NEW: emotional state and coping strategies
    selected_psych_state = data.get("selected_psych_state") or []
    if isinstance(selected_psych_state, list) and selected_psych_state:
        psych_state_block = "\n".join(f"- {item}" for item in selected_psych_state[:3] if str(item).strip())
        if psych_state_block:
            answers_text = (answers_text + "\n\nЭмоциональное состояние сейчас:\n" + psych_state_block).strip()
    selected_coping = data.get("selected_coping") or []
    if isinstance(selected_coping, list) and selected_coping:
        coping_block = "\n".join(f"- {item}" for item in selected_coping[:4] if str(item).strip())
        if coping_block:
            answers_text = (answers_text + "\n\nЧто помогает справляться:\n" + coping_block).strip()
    resume_analysis = data.get("resume_analysis") or {}
    selected_barriers = data.get("selected_barriers") or []
    selected_fears = data.get("selected_fears") or []
    selected_psych_markers = data.get("selected_psych_markers") or []
    selected_choice_reasons = data.get("selected_choice_reasons") if isinstance(data.get("selected_choice_reasons"), dict) else {}
    if isinstance(selected_psych_markers, list) and selected_psych_markers:
        psych_block = "\n".join(f"- {item}" for item in selected_psych_markers[:6] if str(item).strip())
        if psych_block:
            answers_text = (answers_text + "\n\nПсихологические маркеры:\n" + psych_block).strip()
    if isinstance(selected_barriers, list) and selected_barriers:
        barrier_block = "\n".join(f"- {item}" for item in selected_barriers[:6] if str(item).strip())
        if barrier_block:
            answers_text = (answers_text + "\n\nВыбранные барьеры:\n" + barrier_block).strip()
    if selected_choice_reasons:
        reason_lines = [
            f"- {str(choice).strip()}: {str(reason).strip()}"
            for choice, reason in selected_choice_reasons.items()
            if str(choice).strip() and str(reason).strip()
        ]
        if reason_lines:
            answers_text = (answers_text + "\n\nПричины ключевых выборов:\n" + "\n".join(reason_lines)).strip()
    memory_context = str(data.get("memory_context") or "").strip()
    if memory_context:
        answers_text = (answers_text + "\n\nКонтекст предыдущих сессий:\n" + memory_context).strip()
    route_context = data.get("route_context") if isinstance(data.get("route_context"), dict) else {}
    answers_text, duration_note, story_duration_label = _reconcile_country_duration(story_text, data, answers_text)
    if duration_note:
        await message.answer(duration_note)
    if story_duration_label:
        route_context = {str(key): str(value) for key, value in route_context.items()}
        route_context["country_duration_primary"] = story_duration_label
        await state.update_data(route_context=route_context)
    if route_context:
        route_context_block = _route_context_section_text({str(key): str(value) for key, value in route_context.items()})
        if route_context_block:
            answers_text = (answers_text + "\n\nМинимальные данные для маршрута:\n" + route_context_block).strip()
    assessment_id = str(data.get("assessment_id") or uuid.uuid4().hex[:16])
    data = {**data, "assessment_id": assessment_id}
    snapshot = _build_profile_snapshot(data)
    if not _snapshot_is_ready_for_report(snapshot):
        missing_fields = _route_context_missing(data)
        snapshot["missing_fields"] = missing_fields
        snapshot["ready_for_report"] = False
        await state.update_data(
            route_context_missing_fields=missing_fields,
            awaiting_route_context=False,
        )
        # Missing optional facts narrow only their related conclusion. Never expose
        # the internal gap ledger and never block the assessment at this stage.
    await state.update_data(profile_snapshot=snapshot)
    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
    session_id = str(data.get("session_id") or "").strip()
    try:
        save_profile_version(public_user_id, "profile_snapshot", snapshot, session_id=session_id)
    except Exception:
        pass
    user_mode = str(data.get("user_mode") or "calm_steps")
    decision_layers = _build_decision_layers(data, story_analysis, answers_text)
    report_generation_id = report_generation_id or str(uuid.uuid4())
    await state.update_data(report_generation_id=report_generation_id)

    await state.set_state(CareerFlow.REPORT_GENERATING)
    await message.answer(t(lang, "report_generation_compact"), reply_markup=route_choice_keyboard())
    await _track_event(message, state, "report_started", meta={"mode": user_mode})

    try:
        report = await ai_client.build_report(
            story_text,
            story_analysis,
            answers_text,
            decision_layers=decision_layers,
            resume_analysis=resume_analysis,
            selected_barriers=selected_barriers,
            selected_fears=selected_fears,
            selected_psych_markers=selected_psych_markers,
            selected_energy_sources=energy_sources,
            selected_career_priorities=career_priorities,
            user_segment=str(data.get("user_segment") or ""),
            user_segment_label=str(data.get("user_segment_label") or ""),
            language=lang,
        )
        if isinstance(resume_analysis, dict) and resume_analysis:
            report["resume_analysis"] = resume_analysis
        _apply_strategy_outputs(report, {str(key): str(value) for key, value in route_context.items()}, str(data.get("career_strategy") or ""))

        # Ensure different strategies lead to truly different route blueprints.
        career_strategy = str(data.get("career_strategy") or "")
        if career_strategy in {"fast_income", "upskill_for_profile", "long_transition", "need_decision"}:
            bundles = _build_strategy_bundles(report, {str(key): str(value) for key, value in route_context.items()})
            is_divergent, score, compare = _minimum_strategy_divergence(bundles)
            if not is_divergent:
                await _track_event(message, state, "route_divergence_warning", meta={"score": score, "compare": compare})
                regenerated_answers = (
                    answers_text
                    + "\n\n[КОНТРОЛЬ РАСХОЖДЕНИЯ МАРШРУТОВ]\n"
                    + _route_divergence_regen_instruction()
                )
                regenerated = await ai_client.build_report(
                    story_text,
                    story_analysis,
                    regenerated_answers,
                    decision_layers=decision_layers,
                    resume_analysis=resume_analysis,
                    selected_barriers=selected_barriers,
                    selected_fears=selected_fears,
                    selected_psych_markers=selected_psych_markers,
                    selected_energy_sources=energy_sources,
                    selected_career_priorities=career_priorities,
                    user_segment=str(data.get("user_segment") or ""),
                    user_segment_label=str(data.get("user_segment_label") or ""),
                    language=lang,
                )
                if isinstance(resume_analysis, dict) and resume_analysis:
                    regenerated["resume_analysis"] = resume_analysis
                _apply_strategy_outputs(regenerated, {str(key): str(value) for key, value in route_context.items()}, str(data.get("career_strategy") or ""))

                regen_bundles = _build_strategy_bundles(regenerated, {str(key): str(value) for key, value in route_context.items()})
                regen_divergent, regen_score, regen_compare = _minimum_strategy_divergence(regen_bundles)
                await _track_event(
                    message,
                    state,
                    "route_divergence_recheck",
                    meta={"score": regen_score, "is_divergent": regen_divergent, "compare": regen_compare},
                )
                report = regenerated
    except Exception as exc:
        await _track_event(message, state, "report_failed", meta={"error": type(exc).__name__})
        await state.update_data(
            report_generation_status="REPORT_GENERATION_FAILED",
            report_generation_error=type(exc).__name__,
            report_generation_stage="route_generator",
        )
        await state.set_state(CareerFlow.REPORT_GENERATION_FAILED)
        await message.answer(
            "Я сохранил ваши ответы, но не смог собрать документ из-за технической ошибки. "
            "Попробовать сформировать его ещё раз?",
            reply_markup=route_choice_keyboard(),
        )
        return

    # ── PATCH-25: guardrail validation ──────────────────────────────────────
    try:
        from services.career_guardrails import validate_career_report, has_critical_errors  # noqa: PLC0415
        from services.evidence_profile import CareerEvidenceProfile as _CEP2, build_evidence_profile_from_analysis as _bep  # noqa: PLC0415
        _raw_ep = data.get("evidence_profile")
        _profile_ep = _CEP2.model_validate(_raw_ep) if isinstance(_raw_ep, dict) else _bep(story_analysis)
        _gr_errors = validate_career_report(_profile_ep, report)
        if _gr_errors:
            await _track_event(message, state, "guardrail_violations", meta={"errors": _gr_errors[:8]})
        if has_critical_errors(_gr_errors) and not data.get("guardrail_retry_done"):
            # One re-generation attempt with guardrail correction instruction
            _critical = [e for e in _gr_errors if e.startswith("[CRITICAL]")]
            _correction_note = "\n\n[GUARDRAIL CORRECTION REQUIRED]\n" + "\n".join(_critical)
            await _track_event(message, state, "guardrail_regen_triggered", meta={"critical_count": len(_critical)})
            await state.update_data(guardrail_retry_done=True)
            report = await ai_client.build_report(
                story_text,
                story_analysis,
                answers_text + _correction_note,
                decision_layers=decision_layers,
                resume_analysis=resume_analysis,
                selected_barriers=selected_barriers,
                selected_fears=selected_fears,
                selected_psych_markers=selected_psych_markers,
                selected_energy_sources=energy_sources,
                selected_career_priorities=career_priorities,
                user_segment=str(data.get("user_segment") or ""),
                user_segment_label=str(data.get("user_segment_label") or ""),
                language=lang,
            )
            if isinstance(resume_analysis, dict) and resume_analysis:
                report["resume_analysis"] = resume_analysis
            _apply_strategy_outputs(report, {str(key): str(value) for key, value in route_context.items()}, str(data.get("career_strategy") or ""))
    except Exception:
        pass  # guardrail failures must never block the user

    chunks = report_chunks(report, lang)
    await state.update_data(
        final_report=report,
        report_chunks=chunks,
        post_result_stage="ready",
        final_report_generated=True,
        report_generation_id=report_generation_id,
    )
    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
    session_id = str(data.get("session_id") or "").strip()
    save_report_version(
        report_generation_id,
        public_user_id,
        report,
        session_id=session_id,
    )
    save_profile_version(
        public_user_id,
        "report_generated",
        {
            "user_mode": user_mode,
            "answers_text": answers_text,
            "selected_barriers": selected_barriers,
            "selected_fears": selected_fears,
            "selected_psych_markers": selected_psych_markers,
            "selected_career_priorities": career_priorities,
            "selected_energy_sources": energy_sources,
            "route_context": route_context,
            "career_strategy": str(data.get("career_strategy") or ""),
        },
        session_id=session_id,
    )
    await _track_event(message, state, "report_generated", meta={"has_income_signal": _has_income_signal(report)})
    await _track_event(
        message,
        state,
        "report_profile_snapshot",
        meta={
            "user_segment": str(data.get("user_segment") or ""),
            "user_segment_label": str(data.get("user_segment_label") or ""),
            "resource_level": str(report.get("resource_level") or ""),
            "integration_level": str(report.get("integration_level") or ""),
            "recommended_main_path": str((report.get("career_decision") or {}).get("recommended_main_path") or ""),
            "energy_sources": list((report.get("energy_sources") or [])[:5]) if isinstance(report.get("energy_sources"), list) else [],
            "career_priorities": list((report.get("career_priorities") or [])[:4]) if isinstance(report.get("career_priorities"), list) else [],
        },
    )

    # Report Readiness Gate: ask exactly one highest-impact unresolved question.
    # The canonical state prevents resolved or skipped facts from being asked again.
    canonical = build_canonical_profile(data, assessment_id=assessment_id)
    clarification_count = canonical.question_state.question_count
    question = select_clarifying_question(canonical) if _report_draft_is_empty(report) else None
    if question is not None and clarification_count < 5:
        await state.set_state(CareerFlow.REPORT_NEEDS_CLARIFICATION)
        await _track_event(message, state, "report_draft_empty_blocked", meta={})
        await state.update_data(
            canonical_profile=canonical.model_dump(mode="json"),
            active_canonical_question=question.model_dump(mode="json"),
            question_state=canonical.question_state.model_dump(mode="json"),
        )
        await message.answer(
            question.text,
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if _report_draft_is_empty(report):
        report = _ensure_preliminary_report(report, data)
        await state.update_data(final_report=report, report_readiness_status="PRELIMINARY_REPORT_READY")
    await _send_final_map_bundle(message, state, lang, report)


async def _build_and_send_career_assessment(message: Message, state: FSMContext, lang: str, data: dict) -> None:
    build_meta = _runtime_build_metadata()
    runtime_meta = {
        **build_meta,
        "commit_sha": build_meta["build_commit"],
        "pipeline_version": CAREER_PIPELINE_VERSION,
        "telegram_renderer_version": CAREER_TELEGRAM_RENDERER_VERSION,
        "html_renderer_version": CAREER_HTML_RENDERER_VERSION,
    }
    stored_payload = data.get("career_assessment")
    if not isinstance(stored_payload, dict):
        candidate = data.get("final_report")
        stored_payload = candidate if isinstance(candidate, dict) and candidate.get("assessment_id") else None
    current_assessment_id = str(data.get("assessment_id") or "").strip()
    if isinstance(stored_payload, dict) and current_assessment_id and str(stored_payload.get("assessment_id") or "").strip() == current_assessment_id:
        try:
            stored_assessment = career_assessment_from_dict(stored_payload)
            validate_career_assessment(stored_assessment).require_valid()
            stored_generator = str(stored_assessment.metadata.get("generator_version") or "")
            if stored_generator != CAREER_PIPELINE_VERSION:
                raise ValueError("cached assessment was generated by an obsolete pipeline")
        except (TypeError, ValueError):
            stored_assessment = None
        if stored_assessment is not None:
            await message.answer(
                render_short_conclusion(validated_assessment_result(stored_assessment)),
                reply_markup=assessment_actions_keyboard(stored_assessment),
            )
            html_report_path = str(data.get("html_report_path") or "").strip()
            if not html_report_path or not Path(html_report_path).is_file():
                try:
                    html_report_path = _normalize_report_path(
                        str(generate_assessment_html_file(stored_assessment, settings.report_output_dir))
                    )
                    update_report_files(stored_assessment.assessment_id, html_report_path=html_report_path)
                except Exception as exc:
                    await state.set_state(CareerFlow.REPORT_GENERATION_FAILED)
                    await state.update_data(html_report_path="", report_generation_error=type(exc).__name__)
                    await message.answer(
                        "Краткая карта готова, но HTML не собрался. Профиль сохранён для повторной сборки.",
                        reply_markup=assessment_recovery_keyboard(),
                    )
                    return
            await state.set_state(CareerFlow.REPORT_READY)
            await state.update_data(
                career_assessment=stored_assessment.to_dict(),
                validated_assessment_result=validated_assessment_result(stored_assessment),
                final_report=stored_assessment.to_dict(),
                final_report_generated=True,
                assessment_id=stored_assessment.assessment_id,
                report_generation_id=stored_assessment.assessment_id,
                report_generation_status="ASSESSMENT_REUSED",
            )
            if Path(html_report_path).is_file():
                await message.answer_document(FSInputFile(html_report_path), caption=t(lang, "web_report_ready"))
            await _track_event(
                message,
                state,
                "report_reused_idempotent",
                meta={
                    **runtime_meta,
                    "assessment_id": stored_assessment.assessment_id,
                    "profile_version": stored_assessment.profile_version,
                },
            )
            return

    assessment_id = str(data.get("assessment_id") or uuid.uuid4().hex[:16])
    data = {**data, "assessment_id": assessment_id}
    snapshot = _build_profile_snapshot(data)
    _runtime_debug_log(
        "career_generation_started",
        assessment_id=assessment_id,
        question_id=None,
        target_fact_type=None,
        target_schema_path="profile_snapshot.canonical_profile",
        raw_answer=None,
        extracted_facts=(snapshot.get("canonical_profile") or {}).get("facts", []),
        canonical_profile_before=data.get("canonical_profile") or {},
        canonical_profile_after=snapshot.get("canonical_profile") or {},
        generator_version=CAREER_PIPELINE_VERSION,
        renderer_version=CAREER_TELEGRAM_RENDERER_VERSION,
        fallback_reason=None,
        validation_errors=[],
    )
    if not _snapshot_is_ready_for_report(snapshot):
        missing_fields = _route_context_missing(data)
        snapshot["missing_fields"] = missing_fields
        snapshot["ready_for_report"] = False
        await state.update_data(
            route_context_missing_fields=missing_fields,
            awaiting_route_context=False,
        )
        # Clarifications are selected one at a time during the interview. Report
        # generation must continue after the five-question cap.

    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
    session_id = str(data.get("session_id") or "").strip()
    profile_version = str(data.get("profile_version") or assessment_id)
    source_messages = list(data.get("source_messages") or [])
    source_messages.extend(
        {
            "assessment_id": assessment_id,
            "message_id": str(row.get("source_message_id") or ""),
            "text": str(row.get("answer") or ""),
            "created_at": str(row.get("created_at") or ""),
        }
        for row in (data.get("qa_answers") or [])
        if isinstance(row, dict) and row.get("source_message_id")
    )
    fact_ledger = build_fact_ledger(assessment_id, public_user_id, source_messages)
    snapshot["fact_ledger"] = fact_ledger
    integrity_audit = audit_facts(assessment_id, public_user_id, fact_ledger, source_messages)
    # Deliberately emitted immediately before generation for incident tracing.
    print(f"[assessment-integrity] {integrity_audit}", flush=True)
    try:
        save_profile_version(public_user_id, "profile_snapshot", snapshot, session_id=session_id)
    except Exception:
        pass
    # Freeze the sole generator input.  Deep serialization prevents later FSM
    # updates from mutating the profile while routes are being generated.
    snapshot = copy.deepcopy(snapshot)
    snapshot["assessment_id"] = assessment_id
    await state.update_data(
        profile_snapshot=snapshot,
        assessment_id=assessment_id,
        report_generation_id=assessment_id,
    )
    await state.set_state(CareerFlow.REPORT_GENERATING)
    await message.answer(t(lang, "report_generation_compact"), reply_markup=ReplyKeyboardRemove())
    await _track_event(
        message,
        state,
        "report_started",
        meta={**runtime_meta, "assessment_id": assessment_id, "profile_version": profile_version},
    )

    generation_error = ""
    try:
        assessment = await asyncio.wait_for(
            ai_client.build_career_assessment(
                snapshot,
                assessment_id=assessment_id,
                session_id=session_id,
                profile_version=profile_version,
                story_analysis=data.get("story_analysis") if isinstance(data.get("story_analysis"), dict) else {},
                resume_analysis=data.get("resume_analysis") if isinstance(data.get("resume_analysis"), dict) else {},
                language=lang,
            ),
            timeout=settings.career_assessment_timeout_seconds,
        )
    except Exception as exc:
        # A model request used to be able to occupy this handler for almost two
        # minutes (initial generation plus repair).  Telegram then showed only
        # "Собираю вашу карту".  A deterministic assessment is a complete,
        # renderable result, so continue through the normal HTML delivery path.
        generation_error = type(exc).__name__
        assessment = build_deterministic_assessment(
            snapshot,
            data.get("story_analysis") if isinstance(data.get("story_analysis"), dict) else {},
            data.get("resume_analysis") if isinstance(data.get("resume_analysis"), dict) else {},
            assessment_id=assessment_id,
            session_id=session_id,
            profile_version=profile_version,
        )
        assessment.metadata["recovered_by"] = "deterministic_fallback"
        assessment.metadata["generation_error"] = generation_error
        await _track_event(
            message,
            state,
            "report_generation_fallback",
            meta={
                **runtime_meta,
                "assessment_id": assessment_id,
                "profile_version": profile_version,
                "error": generation_error,
            },
        )

    consistency_failures = [
        *consistency_errors(assessment.to_dict(), integrity_audit),
        *contamination_errors(assessment.to_dict(), snapshot, assessment_id),
    ]
    if consistency_failures:
        # build_career_assessment already performs its model repair pass.  A
        # remaining contradiction is therefore reduced to a source-only map;
        # never reuse a stored or previous conclusion here.
        assessment = build_deterministic_assessment(
            snapshot,
            {},
            {},
            assessment_id=assessment_id,
            session_id=session_id,
            profile_version=profile_version,
        )
        assessment.metadata.update({
            "integrity_repair": "source_only_fallback",
            "consistency_errors": consistency_failures,
            "context_contamination": any(
                code.startswith(("FOREIGN_", "UNSUPPORTED_CROSS_DOMAIN", "UNSCOPED_ROUTE"))
                for code in consistency_failures
            ),
            "debug_log": integrity_audit,
        })

    validation = validate_career_assessment(
        assessment,
        snapshot_country_code=str(snapshot.get("country_code") or "") or None,
        snapshot_currency=str(snapshot.get("currency") or "") or None,
    )
    if not validation.valid:
        assessment = build_deterministic_assessment(
            snapshot,
            data.get("story_analysis") if isinstance(data.get("story_analysis"), dict) else {},
            data.get("resume_analysis") if isinstance(data.get("resume_analysis"), dict) else {},
            assessment_id=assessment_id,
            session_id=session_id,
            profile_version=profile_version,
        )
        validation = validate_career_assessment(
            assessment,
            snapshot_country_code=str(snapshot.get("country_code") or "") or None,
            snapshot_currency=str(snapshot.get("currency") or "") or None,
        )
    diagnostics = dict(assessment.metadata)
    diagnostics.update(runtime_meta)
    assessment.metadata.update(runtime_meta)
    assessment.metadata["generator_version"] = CAREER_PIPELINE_VERSION
    assessment.metadata["renderer_version"] = CAREER_TELEGRAM_RENDERER_VERSION
    recovered_by = str(diagnostics.get("recovered_by") or "initial_generation")
    generation_status = {
        "repair": "ASSESSMENT_REPAIRED",
        "deterministic_fallback": "ASSESSMENT_FALLBACK_READY",
    }.get(recovered_by, "ASSESSMENT_READY")
    assessment_payload = assessment.to_dict()
    _runtime_debug_log(
        "career_generation_finished",
        assessment_id=assessment_id,
        question_id=None,
        target_fact_type=None,
        target_schema_path="career_assessment",
        raw_answer=None,
        extracted_facts=(snapshot.get("canonical_profile") or {}).get("facts", []),
        canonical_profile_before=snapshot.get("canonical_profile") or {},
        canonical_profile_after=snapshot.get("canonical_profile") or {},
        generator_version=CAREER_PIPELINE_VERSION,
        renderer_version=CAREER_TELEGRAM_RENDERER_VERSION,
        fallback_reason=assessment.metadata.get("fallback_reason") or generation_error or None,
        validation_errors=validation.to_dict().get("errors", []),
    )
    await state.update_data(
        career_assessment=assessment_payload,
        validated_assessment_result=validated_assessment_result(assessment),
        final_report=assessment_payload,
        final_report_generated=True,
        report_generation_status=generation_status,
        report_generation_error=generation_error,
        assessment_diagnostics=diagnostics,
        assessment_validation=validation.to_dict(),
        route_comparison=render_route_comparison(assessment),
    )
    await _track_event(
        message,
        state,
        "report_generated",
        meta={
            **runtime_meta,
            "assessment_id": assessment_id,
            "profile_version": profile_version,
            "recovered_by": recovered_by,
            "validation": validation.to_dict(),
            "diagnostics": diagnostics,
        },
    )

    await message.answer(
        render_short_conclusion(validated_assessment_result(assessment)),
        reply_markup=assessment_actions_keyboard(assessment),
    )
    try:
        save_report_version(assessment_id, public_user_id, assessment_payload, session_id=session_id)
    except Exception:
        pass

    html_report_path = ""
    try:
        html_path = generate_assessment_html_file(assessment, settings.report_output_dir)
        html_report_path = _normalize_report_path(str(html_path))
        html_url = _report_public_url(Path(html_report_path))
        await message.answer_document(
            FSInputFile(html_report_path),
            caption=t(lang, "web_report_ready"),
            reply_markup=telegram_link_keyboard("📄 Открыть в браузере", html_url) if html_url else None,
        )
        await _track_event(
            message,
            state,
            "html_ready",
            meta={
                **runtime_meta,
                "assessment_id": assessment_id,
                "profile_version": profile_version,
                "path": Path(html_report_path).name,
            },
        )
    except Exception as exc:
        await _track_event(
            message,
            state,
            "html_failed",
            meta={
                **runtime_meta,
                "assessment_id": assessment_id,
                "profile_version": profile_version,
                "error": type(exc).__name__,
            },
        )
        await message.answer(
            "Краткая карта готова, но HTML не собрался. Профиль сохранён для повторной сборки.",
            reply_markup=assessment_recovery_keyboard(),
        )
        await state.set_state(CareerFlow.REPORT_GENERATION_FAILED)
        await state.update_data(html_report_path="", selected_first_step_id=None)
        update_report_files(assessment_id, html_report_path="")
        return

    await state.set_state(CareerFlow.REPORT_READY)
    await state.update_data(html_report_path=html_report_path, selected_first_step_id=None)
    update_report_files(assessment_id, html_report_path=html_report_path)


@router.callback_query(F.data.startswith("assessment_action:"))
async def assessment_followup_action(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    parts = str(callback.data or "").split(":", 2)
    payload = data.get("career_assessment")
    if len(parts) != 3 or not isinstance(payload, dict) or parts[1] != str(payload.get("assessment_id") or ""):
        await callback.answer("Заключение не найдено", show_alert=True)
        return
    assessment = career_assessment_from_dict(payload)
    result = data.get("validated_assessment_result")
    if not isinstance(result, dict):
        result = validated_assessment_result(assessment)
        await state.update_data(validated_assessment_result=result)
    action = parts[2]
    if callback.message and action == "full":
        path = str(data.get("html_report_path") or "")
        if path and Path(path).is_file():
            await callback.message.answer_document(FSInputFile(path), caption=t(_user_language(data), "web_report_ready"))
        else:
            await callback.message.answer("Полный отчёт ещё сохраняется. Попробуйте открыть его через несколько секунд.")
    elif callback.message and action == "guide":
        await state.set_state(CareerFlow.START_GUIDE)
        await callback.message.answer(start_guide_response(result), reply_markup=start_guide_keyboard(assessment.assessment_id))
    elif callback.message and action == "income":
        await callback.message.answer("Когда должен появиться дополнительный или новый доход?", reply_markup=income_urgency_keyboard(assessment.assessment_id))
    elif callback.message and action == "resume":
        await callback.message.answer("Пришлите резюме или описание одного результата — используем сохранённое профессиональное ядро и маршрут без повторного анализа профиля.")
    await callback.answer()


@router.callback_query(F.data.startswith("start_guide:"))
async def handle_start_guide_branch(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    parts = str(callback.data or "").split(":", 2)
    result = data.get("validated_assessment_result")
    if len(parts) != 3 or not isinstance(result, dict):
        await callback.answer("Заключение не найдено", show_alert=True)
        return
    if callback.message:
        await callback.message.answer(start_guide_response(result, parts[2]), reply_markup=guide_followup_keyboard(parts[1], parts[2]))
    await callback.answer()


@router.callback_query(F.data.startswith("guide_choice:"))
async def handle_start_guide_choice(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    parts = str(callback.data or "").split(":", 3)
    result = data.get("validated_assessment_result")
    if len(parts) != 4 or not isinstance(result, dict):
        await callback.answer("Заключение не найдено", show_alert=True)
        return
    if callback.message:
        await callback.message.answer(start_guide_response(result, parts[2], parts[3]))
    await callback.answer()


@router.callback_query(F.data.startswith("income_urgency:"))
async def handle_income_urgency(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    parts = str(callback.data or "").split(":", 2)
    result = data.get("validated_assessment_result")
    if len(parts) != 3 or not isinstance(result, dict):
        await callback.answer("Заключение не найдено", show_alert=True)
        return
    bridge = build_income_bridge(result, parts[2])
    if bridge is None:
        text = "Срочный финансовый мост не создаём. Сохраняем основной карьерный маршрут."
    else:
        result = {**result, "income_bridge": bridge}
        await state.update_data(validated_assessment_result=result)
        text = "\n".join([
            f"Что искать или предлагать: {bridge['offer']}", f"Кому: {bridge['audience']}",
            f"Срок проверки: {bridge['test_period']}", f"Подготовить: {bridge['prepare']}",
            f"Критерий спроса: {bridge['demand_signal']}", f"Защита основного перехода: {bridge['guardrail']}",
        ])
    if callback.message:
        await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("step_callback:"))
async def select_first_step(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    callback_token = str(callback.data or "")
    parts = callback_token.split(":", 3)
    payload = data.get("career_assessment")
    if len(parts) not in {3, 4} or not isinstance(payload, dict):
        await callback.answer("Заключение не найдено", show_alert=True)
        return
    assessment_id = parts[1]
    assessment = career_assessment_from_dict(payload)
    if assessment.assessment_id != assessment_id or (len(parts) == 4 and assessment.profile_version != parts[3]):
        await callback.answer("Это действие относится к другой версии заключения", show_alert=True)
        return
    step_reference = parts[2]
    if len(parts) == 3 and step_reference.isdigit() and int(step_reference) < len(assessment.first_steps):
        step_id = assessment.first_steps[int(step_reference)].step_id
    else:
        step_id = step_reference
    processed_callbacks = set(data.get("processed_step_callbacks") or [])
    if callback_token in processed_callbacks:
        await callback.answer("Этот шаг уже выбран")
        return
    try:
        instruction = render_first_step_instruction(assessment, step_id)
    except ValueError:
        await callback.answer("Шаг не найден", show_alert=True)
        return
    processed_callbacks.add(callback_token)
    await state.update_data(
        career_assessment=assessment.to_dict(),
        selected_first_step_id=step_id,
        processed_step_callbacks=sorted(processed_callbacks),
    )
    public_user_id = str(data.get("public_user_id") or "").strip()
    if public_user_id:
        save_report_version(
            assessment_id,
            public_user_id,
            assessment.to_dict(),
            session_id=str(data.get("session_id") or "").strip(),
            html_report_path=str(data.get("html_report_path") or "").strip(),
        )
    if callback.message:
        await callback.message.answer(instruction, reply_markup=selected_step_actions_keyboard(assessment, step_id))
    await callback.answer()


@router.callback_query(F.data.startswith("show_first_steps:"))
async def show_first_steps(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    payload = data.get("career_assessment")
    callback_token = str(callback.data or "")
    parts = callback_token.split(":", 2)
    if len(parts) not in {2, 3} or not isinstance(payload, dict):
        await callback.answer("Заключение не найдено", show_alert=True)
        return
    assessment_id = parts[1]
    assessment = career_assessment_from_dict(payload)
    if assessment.assessment_id != assessment_id or (len(parts) == 3 and assessment.profile_version != parts[2]):
        await callback.answer("Это действие относится к другой версии заключения", show_alert=True)
        return
    shown_menus = set(data.get("shown_step_menus") or [])
    if callback_token in shown_menus:
        await callback.answer("Варианты уже показаны")
        return
    shown_menus.add(callback_token)
    await state.update_data(shown_step_menus=sorted(shown_menus))
    if callback.message:
        await callback.message.answer(
            "С какого шага хотите начать?",
            reply_markup=first_step_selection_keyboard(assessment),
        )
    await callback.answer()


def _assessment_from_step_callback(data: dict, callback_data: str, expected_parts: int) -> tuple[CareerAssessment | None, list[str]]:
    parts = callback_data.split(":", expected_parts - 1)
    payload = data.get("career_assessment")
    if len(parts) not in {expected_parts - 1, expected_parts} or not isinstance(payload, dict):
        return None, parts
    assessment = career_assessment_from_dict(payload)
    if assessment.assessment_id != parts[1] or (len(parts) == expected_parts and assessment.profile_version != parts[-1]):
        return None, parts
    return assessment, parts


@router.callback_query(F.data.startswith("step_done:"))
async def mark_first_step_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    assessment, parts = _assessment_from_step_callback(data, str(callback.data or ""), 4)
    if assessment is None:
        await callback.answer("Это действие относится к другой версии заключения", show_alert=True)
        return
    step_reference = parts[2]
    step_id = (
        assessment.first_steps[int(step_reference)].step_id
        if len(parts) == 3 and step_reference.isdigit() and int(step_reference) < len(assessment.first_steps)
        else step_reference
    )
    completed = set(data.get("completed_first_step_ids") or [])
    completed.add(step_id)
    await state.update_data(completed_first_step_ids=sorted(completed))
    await callback.answer("Шаг отмечен выполненным")


@router.callback_query(F.data.startswith("step_simplify:"))
async def simplify_first_step(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    assessment, parts = _assessment_from_step_callback(data, str(callback.data or ""), 4)
    if assessment is None:
        await callback.answer("Это действие относится к другой версии заключения", show_alert=True)
        return
    step_reference = parts[2]
    step_id = (
        assessment.first_steps[int(step_reference)].step_id
        if len(parts) == 3 and step_reference.isdigit() and int(step_reference) < len(assessment.first_steps)
        else step_reference
    )
    step = next((item for item in assessment.first_steps if item.step_id == step_id), None)
    if step is None:
        await callback.answer("Шаг не найден", show_alert=True)
        return
    if callback.message:
        await callback.message.answer(
            f"Упрощённый вариант на 10 минут:\n{step.action}\n\nОстановитесь после первого конкретного результата.",
            reply_markup=selected_step_actions_keyboard(assessment, step.step_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("step_back:"))
async def return_to_assessment_map(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    assessment, _ = _assessment_from_step_callback(data, str(callback.data or ""), 3)
    if assessment is None:
        await callback.answer("Это действие относится к другой версии заключения", show_alert=True)
        return
    if callback.message:
        await callback.message.answer(render_telegram_map(assessment))
    await callback.answer()


@router.message(CareerFlow.REPORT_GENERATION_FAILED, F.text)
async def handle_report_generation_failed(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    action = (message.text or "").strip().lower()
    if "повтор" in action or "сформ" in action or "пересоб" in action or action == "retry":
        await state.set_state(CareerFlow.REPORT_READINESS_CHECK)
        await message.answer("Повторяю сборку из сохранённых ответов.", reply_markup=ReplyKeyboardRemove())
        await _build_and_send_report(message, state, lang)
        return
    payload = data.get("career_assessment")
    assessment = career_assessment_from_dict(payload) if isinstance(payload, dict) else None
    if "маршрут" in action and assessment:
        await message.answer(render_route_comparison(assessment))
        return
    if "первый шаг" in action and assessment:
        await message.answer("С какого шага хотите начать?", reply_markup=first_step_selection_keyboard(assessment))
        return
    if "уточнить цель" in action:
        await message.answer(
            "Правильно ли я понял: вы хотите сохранить маркетинговый опыт, но уйти от нынешнего формата работы?"
        )
        return
    if _is_restart_intent(action):
        await state.clear()
        await message.answer("Сессию сбросил по вашему явному запросу. Напишите /start, чтобы начать заново.", reply_markup=ReplyKeyboardRemove())
        return
    await message.answer("Ответы сохранены. Нажмите «Повторить генерацию», чтобы продолжить.")


def _question_reply_markup(analysis: dict, index: int):
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    if not questions or index < 0 or index >= len(questions):
        return None
    row = questions[index]
    if not isinstance(row, dict):
        return None
    if row.get("force_options_keyboard"):
        options = row.get("options", [])
        done_text = str(row.get("done_text") or "✅ Готово")
        # Ensure done_text is in options for multi-select questions
        if done_text and done_text not in options:
            options = list(options) + [done_text]
        return question_options_keyboard(options if isinstance(options, list) else [])
    q_text = str(row.get("question", "")).lower()
    semantic_intent = str(row.get("semantic_intent") or "").strip()
    if semantic_intent == "language_documents_work_right" or "языком, документами и правом работать" in q_text:
        return question_options_keyboard(list(LANGUAGE_DOCUMENTS_BUTTONS))
    if any(token in q_text for token in ["формат работы", "ближе", "50/50", "люд"]):
        return interview_work_format_keyboard()
    if "поддерж" in q_text:
        return interview_support_keyboard()
    options = _normalize_question_options(str(row.get("question") or ""), row.get("options", []) if isinstance(row.get("options", []), list) else [])
    return question_options_keyboard(options)


async def _download_document_bytes(message: Message, document: Document) -> bytes:
    tmp_file = tempfile.NamedTemporaryFile(delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()
    try:
        file_info = await message.bot.get_file(document.file_id)
        await message.bot.download(file_info, destination=tmp_path)
        with open(tmp_path, "rb") as fh:
            return fh.read()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def process_story_input(message: Message, state: FSMContext, text: str) -> None:
    clean = (text or "").strip()
    data = await state.get_data()
    lang = _user_language(data)

    if clean and await _maybe_switch_to_crisis_support(message, state, lang, clean, source="story_input"):
        return

    if clean in ALL_SHORT_STORY_OPTIONS:
        mapped_story = {
            "💸 Нужна работа срочно": "Нужна работа срочно, приоритет - быстрый доход.",
            "🧭 Не понимаю, кем могу быть": "Не понимаю, кем могу быть в новой стране, нужен маршрут по опыту.",
            "🌍 Мешает язык": "Мешает язык, нужен план с учетом текущего уровня.",
            "🧠 Мешает страх": "Мешает страх отказа и неуверенность.",
            "😞 Устал(а), нет сил": "Сейчас мало сил, нужен максимально короткий и реалистичный план.",
            "📄 Хочу начать с резюме": "Хочу начать с резюме и адаптировать его под рынок.",
        }
        clean = mapped_story.get(clean, clean)

    if not clean:
        await message.answer(t(lang, "story_too_short"))
        return

    # Clear all stale conclusion/interview/route data so a new story always produces a fresh result.
    await state.update_data(**_STORY_RESET_FIELDS)

    profile = _build_interaction_profile(clean, data)
    selected_mode = str(data.get("user_mode") or "calm_steps")
    preferred_input = str(data.get("preferred_input") or profile.get("preferred_input") or "text")
    if selected_mode == "fast":
        profile.update({"pace": "fast", "support_need": "low", "detail_preference": "brief"})
    elif selected_mode in {"deep_route", "support"}:
        profile.update({"pace": "normal", "support_need": "medium", "detail_preference": "detailed"})
    else:
        profile.update({"pace": "normal", "support_need": "medium", "detail_preference": "balanced"})
    profile["preferred_input"] = preferred_input

    assessment_id = uuid.uuid4().hex
    await state.update_data(
        assessment_id=assessment_id,
        source_messages=[{
            "assessment_id": assessment_id,
            "message_id": str(getattr(message, "message_id", "")),
            "text": clean,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }],
        story_text=clean,
        interaction_profile=profile,
        support_need=profile.get("support_need", "medium"),
        pace=profile.get("pace", "normal"),
        detail_preference=profile.get("detail_preference", "balanced"),
        preferred_input=preferred_input,
    )
    await _track_event(
        message,
        state,
        "story_submitted",
        meta={"chars": len(clean), "answer_length": profile.get("answer_length", ""), "tone": profile.get("emotional_tone", "")},
    )

    if profile.get("answer_length") == "long":
        await message.answer(t(lang, "adaptive_q_many"))
    elif profile.get("answer_length") == "short":
        await message.answer(t(lang, "adaptive_q_few"), reply_markup=short_story_keyboard())
    if profile.get("emotional_tone") in {"anxious", "ashamed", "tired", "confused"}:
        await message.answer(t(lang, "adaptive_transition_anxious"))
    if profile.get("structure_level") == "chaotic":
        await message.answer(t(lang, "adaptive_transition_chaotic"))

    await message.answer(t(lang, "processing_story"))
    # Assessment input is a security boundary.  Persistent memory may contain
    # another assessment and must never be submitted as user evidence.
    analysis = await ai_client.analyze_story(clean, lang)
    user_segment = _detect_user_segment(clean, analysis)
    evidence_profile = build_evidence_profile_from_analysis(analysis)
    questions = _build_evidence_questions(evidence_profile, lang, selected_mode)
    analysis = dict(analysis)
    analysis["follow_up_questions"] = questions
    q_count = len(questions)
    await state.update_data(
        story_analysis=analysis,
        user_segment=user_segment,
        user_segment_label=_segment_label(user_segment),
        promised_question_count=q_count,
        awaiting_story_correction=False,
        evidence_profile=evidence_profile.model_dump(),
    )
    await state.set_state(CareerFlow.CONFIRMING_STORY)
    await message.answer(_story_confirmation_text(analysis, q_count), reply_markup=story_confirmation_keyboard())
    await message.answer(t(lang, "story_confirmation_prompt"), reply_markup=story_confirmation_keyboard())


@router.message(StateFilter("*"), F.text.func(_is_restart_intent))
async def restart_from_any_state(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
    _cancel_reminder(message.chat.id)
    _cancel_pdf_task(message.chat.id)

    await state.clear()
    await state.update_data(
        public_user_id=public_user_id,
        language=lang,
        lang=lang,
        interaction_profile={},
        interview_context={},
        asked_question_signatures=[],
        preferred_input="unknown",
        user_mode="calm_steps",
        max_questions=10,
        support_level="medium",
        support_need="medium",
        pace="normal",
        detail_preference="balanced",
    )
    await state.set_state(CareerFlow.SELECTING_PACE)
    await message.answer(t(lang, "restart_prompt"))
    await message.answer(t(lang, "start_intro"))
    await message.answer(t(lang, "pace_prompt"), reply_markup=pace_keyboard())


@router.message(CareerFlow.CONFIRMING_STORY, F.text.in_(ALL_STORY_CONFIRM_ACTIONS))
async def handle_story_confirmation_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    action = (message.text or "").strip()

    if action == STORY_CONFIRM_OK:
        await state.update_data(awaiting_story_correction=False)
        user_mode = str(data.get("user_mode") or "calm_steps")
        await state.set_state(CareerFlow.ASK_CV)
        if user_mode in {"deep_route", "support"}:
            await message.answer(t(lang, "resume_offer_deep"), reply_markup=resume_choice_keyboard())
        else:
            await message.answer(t(lang, "resume_offer"), reply_markup=resume_choice_keyboard())
        return

    if action == STORY_CONFIRM_FIX:
        await state.update_data(awaiting_story_correction=True)
        await message.answer(t(lang, "story_correction_prompt"), reply_markup=input_method_keyboard())
        return


@router.message(CareerFlow.CONFIRMING_STORY, F.text)
async def handle_story_confirmation_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    clean = (message.text or "").strip()

    if clean and await _maybe_switch_to_crisis_support(message, state, lang, clean, source="story_confirmation"):
        return

    if not clean:
        await message.answer(t(lang, "story_confirmation_fallback"), reply_markup=story_confirmation_keyboard())
        return

    if not bool(data.get("awaiting_story_correction")):
        await message.answer(t(lang, "story_confirmation_fallback"), reply_markup=story_confirmation_keyboard())
        return

    story_text = (data.get("story_text") or "").strip()
    updated_story = (story_text + "\n\nУточнение пользователя:\n" + clean).strip()
    user_mode = str(data.get("user_mode") or "calm_steps")
    await state.update_data(story_text=updated_story, awaiting_story_correction=False)
    await message.answer(t(lang, "story_correction_applied"))
    await message.answer(t(lang, "processing_story"))
    analysis = await ai_client.analyze_story(updated_story, lang)
    user_segment = _detect_user_segment(updated_story, analysis)
    evidence_profile = build_evidence_profile_from_analysis(analysis)
    questions = _build_evidence_questions(evidence_profile, lang, user_mode)
    analysis = dict(analysis)
    analysis["follow_up_questions"] = questions
    q_count = len(questions)
    await state.update_data(
        story_analysis=analysis,
        user_segment=user_segment,
        user_segment_label=_segment_label(user_segment),
        promised_question_count=q_count,
        evidence_profile=evidence_profile.model_dump(),
    )
    await message.answer(_story_confirmation_text(analysis, q_count), reply_markup=story_confirmation_keyboard())
    await message.answer(t(lang, "story_confirmation_prompt"), reply_markup=story_confirmation_keyboard())


@_serialize_interview_update
async def process_answers_input(message: Message, state: FSMContext, text: str) -> None:
    clean = (text or "").strip()
    data = await state.get_data()
    lang = _user_language(data)

    if clean and await _maybe_switch_to_crisis_support(message, state, lang, clean, source="answers_input"):
        return

    analysis = data.get("story_analysis") or {}
    context = _build_interview_context(data, analysis if isinstance(analysis, dict) else None)
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    qa_index = int(data.get("qa_index", 0))
    qa_answers = list(data.get("qa_answers") or [])
    pending_review = data.get("pending_answer_review") or {}
    pending_append = data.get("pending_question_append") if isinstance(data.get("pending_question_append"), dict) else {}
    interaction_profile = dict(data.get("interaction_profile") or {})
    user_mode = str(data.get("user_mode") or "calm_steps")
    quick_report_after_questions = bool(data.get("quick_report_after_questions"))
    interaction_turn = int(data.get("interaction_turn", 0)) + 1
    interaction_profile["answer_length"] = _classify_answer_length(clean)
    interaction_profile["emotional_tone"] = _detect_emotional_tone(clean) if _detect_emotional_tone(clean) != "unknown" else interaction_profile.get("emotional_tone", "unknown")
    interaction_profile["structure_level"] = _detect_structure_level(clean)
    interaction_profile["agency_level"] = _detect_agency_level(clean)
    await state.update_data(interaction_profile=interaction_profile, interaction_turn=interaction_turn)

    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message)).strip()
    session_id = str(data.get("session_id") or "").strip()
    await _register_session_context(state, message, user_id=public_user_id, session_id=session_id)

    if clean and _is_preliminary_result_intent(clean):
        merged_answers = _merge_answers_text(qa_answers)
        await state.update_data(answers_text=merged_answers)
        await _track_event(message, state, "interview_stopped_by_user", meta={"question_index": qa_index + 1})
        await _advance_after_questions(message, state, lang)
        await _maybe_trigger_career_finalization(message, state, trigger="last_required_answer")
        return

    if clean == CLARIFY_MORE:
        # User chose to continue; show next question without re-offering
        await state.update_data(preliminary_offer_shown=True)
        if questions and qa_index < len(questions):
            data_fresh = await state.get_data()
            context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
            await _ask_next_interview_question(
                message,
                state,
                data_fresh,
                analysis,
                context,
                qa_index=qa_index,
                lang=lang,
                user_mode=user_mode,
            )
        return

    # PATCH-27: preliminary map button responses
    if clean == PRELIM_LOOKS_LIKE_ME:
        await _track_event(message, state, "prelim_map_confirmed")
        await _track_event(
            message,
            state,
            "career_hypothesis_confirmed",
            meta={"source": "preliminary_map", "question_index": qa_index + 1},
        )
        merged = _merge_answers_text(qa_answers)
        await state.update_data(answers_text=merged)
        await _advance_after_questions(message, state, lang)
        return

    if clean == PRELIM_HAS_ERROR:
        await _track_event(message, state, "prelim_map_error_flagged")
        await _track_event(
            message,
            state,
            "career_hypothesis_rejected",
            meta={"source": "preliminary_map", "question_index": qa_index + 1},
        )
        await state.update_data(preliminary_offer_shown=False)
        await message.answer(
            "Понял. Расскажите, что не так — я исправлю и покажу обновлённый вариант.",
            reply_markup=input_method_keyboard(),
        )
        return

    if clean == PRELIM_ADD_DETAIL:
        await _track_event(message, state, "prelim_map_add_detail")
        await state.update_data(preliminary_offer_shown=False)
        if questions and qa_index < len(questions):
            data_fresh = await state.get_data()
            context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
            await _ask_next_interview_question(
                message,
                state,
                data_fresh,
                analysis,
                context,
                qa_index=qa_index,
                lang=lang,
                user_mode=user_mode,
            )
        return

    # Route selection from preliminary map: store route and advance to report
    _route1_label = str(data.get("preliminary_map_route1") or "")
    _route2_label = str(data.get("preliminary_map_route2") or "")
    if (
        clean
        and (_route1_label or _route2_label)
        and (
            (_route1_label and _route1_label[:20].lower() in clean.lower())
            or (_route2_label and _route2_label[:20].lower() in clean.lower())
            or "разобрать" in clean.lower()
        )
    ):
        _sel_route = _route1_label if (_route1_label and _route1_label[:20].lower() in clean.lower()) else _route2_label
        await _track_event(message, state, "prelim_map_route_selected", meta={"route": _sel_route[:60]})
        merged = _merge_answers_text(qa_answers + [{"question": "Выбранный маршрут", "answer": _sel_route}])
        await state.update_data(
            answers_text=merged,
            selected_preliminary_route=_sel_route,
            preliminary_route_selected=True,
        )
        await _advance_after_questions(message, state, lang)
        return

    if clean:
        await _track_event(
            message,
            state,
            "answer_submitted",
            meta={"question_index": qa_index + 1, "chars": len(clean), "turn": interaction_turn},
        )

    if pending_review:
        await message.answer(t(lang, "answer_review_prompt"), reply_markup=answer_review_keyboard())
        return

    if bool(data.get("awaiting_extended_diagnostics_choice")):
        if clean == EXTENDED_DIAG_YES:
            await _track_event(message, state, "extended_diag_selected", action="yes")
            analysis_ext = dict(data.get("story_analysis") or {})
            analysis_ext["follow_up_questions"] = _mandatory_psych_social_questions()
            await state.update_data(
                story_analysis=analysis_ext,
                qa_index=0,
                awaiting_extended_diagnostics_choice=False,
                mandatory_diagnostics_in_progress=True,
                mandatory_diagnostics_done=False,
                extended_diagnostics_done=True,
            )
            await message.answer(t(lang, "extended_diag_started"))
            data_fresh = await state.get_data()
            context = _build_interview_context(data_fresh, analysis_ext)
            await _save_interview_context(state, context)
            asked = await _ask_next_interview_question(
                message,
                state,
                data_fresh,
                analysis_ext,
                context,
                qa_index=0,
                lang=lang,
                user_mode=user_mode,
            )
            if not asked:
                await _advance_after_questions(message, state, lang)
            return

        if clean == EXTENDED_DIAG_SKIP:
            await _track_event(message, state, "extended_diag_selected", action="skip")
            await state.update_data(
                awaiting_extended_diagnostics_choice=False,
                mandatory_diagnostics_in_progress=False,
                mandatory_diagnostics_done=True,
                extended_diagnostics_done=True,
            )
            await _advance_after_questions(message, state, lang)
            return

        await message.answer(t(lang, "extended_diag_choice_required"), reply_markup=extended_diagnostics_keyboard())
        return

    if pending_append:
        append_index = int(pending_append.get("index", -1))
        if append_index == qa_index and questions and qa_index < len(questions):
            current = questions[qa_index]
            question_text = current.get("question", f"Вопрос {qa_index + 1}") if isinstance(current, dict) else str(current)
            current_q_id = _question_id(current, qa_index)
            if isinstance(current, dict) and current.get("multi_key"):
                multi_key = str(current.get("multi_key") or "").strip()
                selected_key = f"{multi_key}_selected"
                selected_values = list(data.get(selected_key) or [])
                if clean not in selected_values:
                    selected_values.append(clean)
                await state.update_data(**{selected_key: selected_values, "pending_question_append": {}})
                await message.answer(
                    t(
                        lang,
                        "multi_select_selected",
                        count=len(selected_values),
                        items=_selection_to_text(selected_values),
                        done=str(current.get("done_text") or "✅ Готово"),
                    ),
                    reply_markup=_question_reply_markup(analysis, qa_index),
                )
                return

            qa_answers.append({"question": question_text, "question_id": current_q_id, "answer": clean, "source_message_id": str(getattr(message, "message_id", "")), "created_at": datetime.now(timezone.utc).isoformat()})
            qa_index += 1
            evidence_payload, is_ready = _update_evidence_after_answer(data, current, clean)
            await state.update_data(
                qa_answers=qa_answers,
                qa_index=qa_index,
                pending_answer_review={},
                pending_question_append={},
                evidence_profile=evidence_payload,
            )
            await _sync_interview_context_after_answer(state, data, evidence_payload, clean)
            if is_ready:
                merged_answers = _merge_answers_text(qa_answers)
                await state.update_data(answers_text=merged_answers)
                await _track_interview_ready_event(
                    message,
                    state,
                    question_index=qa_index,
                    evidence_payload=evidence_payload,
                )
                await _advance_after_questions(message, state, lang)
                return
            if qa_index < len(questions):
                data_fresh = await state.get_data()
                context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
                asked = await _ask_next_interview_question(
                    message,
                    state,
                    data_fresh,
                    analysis,
                    context,
                    qa_index=qa_index,
                    lang=lang,
                    user_mode=user_mode,
                )
                if asked:
                    return
                return

            merged_answers = _merge_answers_text(qa_answers)
            await state.update_data(answers_text=merged_answers)
            await _advance_after_questions(message, state, lang)
            return
        await state.update_data(pending_question_append={})

    pending_choice_reason = data.get("pending_choice_reason") if isinstance(data.get("pending_choice_reason"), dict) else {}
    if pending_choice_reason:
        if not clean:
            await message.answer(
                t(lang, "career_switch_reason_prompt", choice=str(pending_choice_reason.get("choice_label") or "Сменить профессию")),
                reply_markup=career_switch_reason_keyboard(),
            )
            return
        allowed_options = {str(item).strip().lower() for item in ALL_CAREER_SWITCH_REASON_OPTIONS}
        normalized = clean.strip().lower()
        reason_value = clean if normalized in allowed_options else f"Другое: {clean}"
        selected_choice_reasons = dict(data.get("selected_choice_reasons") or {})
        choice_label = str(pending_choice_reason.get("choice_label") or "Сменить профессию")
        selected_choice_reasons[choice_label] = reason_value
        await state.update_data(selected_choice_reasons=selected_choice_reasons, pending_choice_reason={})
        await message.answer(t(lang, "career_switch_reason_saved", reason=reason_value))
        if questions and qa_index < len(questions):
            data_fresh = await state.get_data()
            context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
            await _ask_next_interview_question(
                message,
                state,
                data_fresh,
                analysis,
                context,
                qa_index=qa_index,
                lang=lang,
                user_mode=user_mode,
            )
        return

    if not clean:
        await message.answer(t(lang, "answers_too_short"))
        return

    if questions and qa_index < len(questions):
        current = questions[qa_index]
        current_q_id = _question_id(current, qa_index)
        question_text = current.get("question", f"Вопрос {qa_index + 1}") if isinstance(current, dict) else str(current)
        current_options = current.get("options", []) if isinstance(current, dict) and isinstance(current.get("options", []), list) else []
        current_options_low = {str(item).strip().lower() for item in current_options if str(item).strip()}

        if clean == QUESTION_ADD_TEXT:
            await state.update_data(pending_question_append={"index": qa_index, "question_id": current_q_id})
            await message.answer(t(lang, "answer_add_prompt"), reply_markup=input_method_keyboard())
            return

        # Reject stale button answers from previous questions and require explicit confirmation.
        if clean.lower() not in current_options_low and _is_known_previous_button(questions, qa_index, clean):
            completed_multi = data.get("recent_completed_multi") if isinstance(data.get("recent_completed_multi"), dict) else {}
            completed_options = {
                str(item).strip().lower()
                for item in completed_multi.get("options", [])
                if str(item).strip()
            }
            completed_index = int(completed_multi.get("question_index", -2))
            # Telegram may deliver two rapid reply-keyboard taps out of order:
            # the user taps an option and then immediately taps Done, while the
            # Done update reaches us first.  This is not a semantic conflict.
            # Merge the late option into the just-completed multi-select answer
            # and keep the already displayed current question active.
            if completed_index == qa_index - 1 and clean.lower() in completed_options:
                selected_values = [str(item) for item in completed_multi.get("selected_values", []) if str(item).strip()]
                max_select = int(completed_multi.get("max_select") or 5)
                if clean not in selected_values and len(selected_values) < max_select:
                    selected_values.append(clean)
                    answer_index = int(completed_multi.get("answer_index", -1))
                    if 0 <= answer_index < len(qa_answers) and isinstance(qa_answers[answer_index], dict):
                        qa_answers[answer_index]["answer"] = ", ".join(selected_values)
                    multi_key = str(completed_multi.get("multi_key") or "")
                    update_payload: dict[str, object] = {
                        "qa_answers": qa_answers,
                        "recent_completed_multi": {**completed_multi, "selected_values": selected_values},
                    }
                    projection_keys = {
                        "psych": ("selected_psych_markers", "selected_barriers", "selected_fears"),
                        "psych_state": ("selected_psych_state",),
                        "coping": ("selected_coping",),
                        "social": ("selected_social_state",),
                        "integration": ("selected_integration_state",),
                        "energy": ("selected_energy_sources",),
                        "priorities": ("selected_career_priorities",),
                    }
                    for projection_key in projection_keys.get(multi_key, ()):
                        update_payload[projection_key] = selected_values[:max_select]
                    await state.update_data(**update_payload)
                await message.answer(
                    t(lang, "late_multi_choice_saved", choice=clean),
                    reply_markup=_question_reply_markup(analysis, qa_index),
                )
                return
            semantic_intent = str(current.get("semantic_intent") or "ответ по текущему вопросу") if isinstance(current, dict) else "ответ по текущему вопросу"
            inferred_meaning = f"{semantic_intent}: {clean}"
            await _track_event(
                message,
                state,
                "conflict_detected",
                meta={
                    "question_index": qa_index + 1,
                    "question_id": current_q_id,
                    "reason": "context_mismatch",
                },
            )
            review_payload = {
                "index": qa_index,
                "question": question_text,
                "question_id": current_q_id,
                "answer": clean,
                "review_type": "context_mismatch",
                "normalized_answer": inferred_meaning,
            }
            # Keep a recovery copy until the choice is consumed. Telegram can
            # deliver rapid reply-keyboard taps while another update is saving
            # FSM data; losing the transient pending value used to trap the chat.
            await state.update_data(
                pending_answer_review=review_payload,
                answer_review_snapshot=review_payload,
            )
            await message.answer(t(lang, "answer_context_mismatch_intro"), reply_markup=answer_review_keyboard(context_mismatch=True))
            await message.answer(
                t(lang, "answer_context_mismatch_question", meaning=inferred_meaning),
                reply_markup=answer_review_keyboard(context_mismatch=True),
            )
            return

        if isinstance(current, dict) and current.get("multi_key"):
            multi_key = str(current.get("multi_key") or "").strip()
            done_text = str(current.get("done_text") or "✅ Готово")
            try:
                max_select = int(current.get("max_select") or 5)
            except Exception:
                max_select = 5
            selected_key = f"{multi_key}_selected"
            selected_values = list(data.get(selected_key) or [])
            options_raw = current.get("options", [])
            options = [
                str(item).strip()
                for item in options_raw
                if str(item).strip()
            ] if isinstance(options_raw, list) else []
            # Ensure done_text is in options for display
            if done_text not in options:
                options.append(done_text)

            if clean == done_text:
                if not selected_values:
                    await message.answer(t(lang, "multi_select_empty"), reply_markup=_question_reply_markup(analysis, qa_index))
                    return
                if multi_key == "priorities":
                    selected_choice_reasons = dict(data.get("selected_choice_reasons") or {})
                    missing_reason_choice = next(
                        (
                            choice
                            for choice in selected_values
                            if _is_career_switch_choice(choice) and not str(selected_choice_reasons.get(choice) or "").strip()
                        ),
                        "",
                    )
                    if missing_reason_choice:
                        await state.update_data(
                            pending_choice_reason={
                                "question_index": qa_index,
                                "question_id": current_q_id,
                                "choice_label": missing_reason_choice,
                            }
                        )
                        await message.answer(
                            t(lang, "career_switch_reason_prompt", choice=missing_reason_choice),
                            reply_markup=career_switch_reason_keyboard(),
                        )
                        return
                qa_answers.append(
                    {
                        "question": question_text,
                        "question_id": current_q_id,
                        "answer": ", ".join(selected_values[:max_select]),
                    }
                )
                if multi_key == "priorities":
                    selected_choice_reasons = dict(data.get("selected_choice_reasons") or {})
                    for selected_item in selected_values:
                        if not _is_career_switch_choice(selected_item):
                            continue
                        reason_value = str(selected_choice_reasons.get(selected_item) or "").strip()
                        if reason_value:
                            qa_answers.append(
                                {
                                    "question": "Почему выбрана смена профессии",
                                    "question_id": "career_switch_reason",
                                    "answer": reason_value,
                                }
                            )
                        break
                qa_index += 1
                answer_blob = ", ".join(selected_values[:max_select])
                evidence_payload, is_ready = _update_evidence_after_answer(data, current, answer_blob)
                update_payload: dict[str, object] = {
                    "qa_answers": qa_answers,
                    "qa_index": qa_index,
                    "pending_answer_review": {},
                    selected_key: [],
                    "evidence_profile": evidence_payload,
                    "recent_completed_multi": {
                        "question_index": qa_index - 1,
                        "answer_index": len(qa_answers) - 1,
                        "multi_key": multi_key,
                        "options": [item for item in options if item != done_text],
                        "selected_values": selected_values[:max_select],
                        "max_select": max_select,
                    },
                }
                if multi_key == "psych":
                    update_payload["selected_psych_markers"] = selected_values[:5]
                    update_payload["selected_barriers"] = selected_values[:5]
                    update_payload["selected_fears"] = selected_values[:5]
                if multi_key == "psych_state":
                    update_payload["selected_psych_state"] = selected_values[:3]
                if multi_key == "coping":
                    update_payload["selected_coping"] = selected_values[:4]
                if multi_key == "social":
                    update_payload["selected_social_state"] = selected_values[:6]
                if multi_key == "integration":
                    update_payload["selected_integration_state"] = selected_values[:5]
                if multi_key == "energy":
                    update_payload["selected_energy_sources"] = selected_values[:5]
                if multi_key == "priorities":
                    update_payload["selected_career_priorities"] = selected_values[:4]
                await state.update_data(**update_payload)
                await _sync_interview_context_after_answer(state, data, evidence_payload, answer_blob)
                if is_ready:
                    merged_answers = _merge_answers_text(qa_answers)
                    await state.update_data(answers_text=merged_answers)
                    await _track_interview_ready_event(
                        message,
                        state,
                        question_index=qa_index,
                        evidence_payload=evidence_payload,
                    )
                    await _advance_after_questions(message, state, lang)
                    return
                if qa_index < len(questions):
                    data_fresh = await state.get_data()
                    context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
                    asked = await _ask_next_interview_question(
                        message,
                        state,
                        data_fresh,
                        analysis,
                        context,
                        qa_index=qa_index,
                        lang=lang,
                        user_mode=user_mode,
                    )
                    if asked:
                        return
                    return

                merged_answers = _merge_answers_text(qa_answers)
                await state.update_data(answers_text=merged_answers)
                await _advance_after_questions(message, state, lang)
                return

            if clean in options:
                if clean not in selected_values:
                    if len(selected_values) >= max_select:
                        await message.answer(t(lang, "multi_select_limit_reached", limit=max_select), reply_markup=_question_reply_markup(analysis, qa_index))
                        return
                    selected_values.append(clean)
                update_payload: dict[str, object] = {selected_key: selected_values}
                if multi_key == "psych":
                    update_payload["selected_psych_markers"] = selected_values[:5]
                    update_payload["selected_barriers"] = selected_values[:5]
                    update_payload["selected_fears"] = selected_values[:5]
                if multi_key == "psych_state":
                    update_payload["selected_psych_state"] = selected_values[:3]
                if multi_key == "coping":
                    update_payload["selected_coping"] = selected_values[:4]
                if multi_key == "social":
                    update_payload["selected_social_state"] = selected_values[:6]
                if multi_key == "integration":
                    update_payload["selected_integration_state"] = selected_values[:5]
                if multi_key == "energy":
                    update_payload["selected_energy_sources"] = selected_values[:5]
                if multi_key == "priorities":
                    update_payload["selected_career_priorities"] = selected_values[:4]
                    selected_choice_reasons = dict(data.get("selected_choice_reasons") or {})
                    if _is_career_switch_choice(clean) and not str(selected_choice_reasons.get(clean) or "").strip():
                        update_payload["pending_choice_reason"] = {
                            "question_index": qa_index,
                            "question_id": current_q_id,
                            "choice_label": clean,
                        }
                        await state.update_data(**update_payload)
                        await message.answer(t(lang, "career_switch_reason_prompt", choice=clean), reply_markup=career_switch_reason_keyboard())
                        return
                await state.update_data(**update_payload)
                await message.answer(
                    t(
                        lang,
                        "multi_select_selected",
                        count=len(selected_values),
                        items=_selection_to_text(selected_values),
                        done=done_text,
                    ),
                    reply_markup=_question_reply_markup(analysis, qa_index),
                )
                return

            if selected_values:
                await message.answer(t(lang, "multi_select_finish_hint", done=done_text), reply_markup=_question_reply_markup(analysis, qa_index))
                return

        # "не знаю" — never repeat the question; offer simpler choice or skip
        if _is_dont_know_response(clean):
            await _track_event(message, state, "dont_know_answer", meta={"question_index": qa_index + 1, "gap_key": current.get("gap_key") if isinstance(current, dict) else ""})
            intro, simpler_opts = _dont_know_simpler_question(current, lang)
            if simpler_opts:
                await message.answer(intro, reply_markup=question_options_keyboard(simpler_opts))
                return
            # No options — mark gap unknown and advance
            qa_answers.append({"question": question_text, "question_id": current_q_id, "answer": "не уточнено"})
            qa_index += 1
            evidence_payload, is_ready = _update_evidence_after_answer(data, current, "не уточнено")
            await state.update_data(qa_answers=qa_answers, qa_index=qa_index, evidence_profile=evidence_payload)
            await _sync_interview_context_after_answer(state, data, evidence_payload, "не уточнено")
            await message.answer(intro)
            if is_ready or qa_index >= len(questions):
                merged = _merge_answers_text(qa_answers)
                await state.update_data(answers_text=merged)
                await _advance_after_questions(message, state, lang)
            else:
                data_fresh = await state.get_data()
                context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
                await _ask_next_interview_question(
                    message,
                    state,
                    data_fresh,
                    analysis,
                    context,
                    qa_index=qa_index,
                    lang=lang,
                    user_mode=user_mode,
                )
            return

        issue_key = _validate_answer(current, clean, qa_answers)
        if issue_key:
            await _track_event(
                message,
                state,
                "invalid_answer",
                meta={"question_index": qa_index + 1, "question_id": _question_id(current, qa_index), "issue": issue_key},
            )
            if issue_key == "answer_validation_speed_mismatch":
                await message.answer(t(lang, issue_key))
                await message.answer(_question_prompt(analysis, qa_index, lang), reply_markup=_question_reply_markup(analysis, qa_index))
                return
            await state.update_data(
                pending_answer_review={
                    "index": qa_index,
                    "question": question_text,
                    "question_id": _question_id(current, qa_index),
                    "answer": clean,
                }
            )
            await message.answer(t(lang, issue_key), reply_markup=answer_review_keyboard())
            await message.answer(t(lang, "answer_review_prompt"), reply_markup=answer_review_keyboard())
            return

        qa_answers.append({"question": question_text, "question_id": _question_id(current, qa_index), "answer": clean, "source_message_id": str(getattr(message, "message_id", "")), "created_at": datetime.now(timezone.utc).isoformat()})
        signal_payload = _free_text_signal(current, clean)
        if signal_payload:
            qa_answers[-1]["signal"] = signal_payload["signal"]
            qa_answers[-1]["meaning"] = signal_payload["meaning"]
            qa_answers[-1]["not_equal_to"] = signal_payload["not_equal_to"]
        qa_index += 1
        evidence_payload, is_ready = _update_evidence_after_answer(data, current, clean)
        await state.update_data(
            qa_answers=qa_answers,
            qa_index=qa_index,
            pending_answer_review={},
            evidence_profile=evidence_payload,
        )
        context = await _sync_interview_context_after_answer(state, data, evidence_payload, clean)

        if interaction_turn % 3 == 0:
            if interaction_profile.get("support_need") == "high":
                await message.answer(t(lang, "contract_anchor"))
            elif interaction_profile.get("answer_length") == "short":
                await message.answer(t(lang, "adaptive_transition_buttons"))
            elif interaction_profile.get("answer_length") == "long":
                await message.answer(t(lang, "adaptive_transition_detailed"))

        if is_ready:
            merged_answers = _merge_answers_text(qa_answers)
            await state.update_data(answers_text=merged_answers)
            await _track_interview_ready_event(
                message,
                state,
                question_index=qa_index,
                evidence_payload=evidence_payload,
            )
            await _advance_after_questions(message, state, lang)
            await _maybe_trigger_career_finalization(message, state, trigger="last_required_answer")
            await _maybe_trigger_career_finalization(message, state, trigger="last_required_answer")
            return

        # PATCH-27: show preliminary map (replaces simple offer from PATCH-24)
        if qa_index >= 2 and not data.get("preliminary_offer_shown"):
            from services.interview_policy import evaluate_report_readiness  # noqa: PLC0415
            from services.evidence_profile import CareerEvidenceProfile as _CEP  # noqa: PLC0415
            _profile_check = _CEP.model_validate(evidence_payload)
            _readiness = evaluate_report_readiness(_profile_check)
            if _readiness.status in {"ready_with_uncertainty", "ready"}:
                _prelim_text, _r1, _r2 = _generate_preliminary_map(
                    _profile_check, data.get("story_analysis") or {}, lang
                )
                await state.update_data(
                    preliminary_offer_shown=True,
                    evidence_profile=evidence_payload,
                    preliminary_map_route1=_r1,
                    preliminary_map_route2=_r2,
                )
                await _track_event(message, state, "preliminary_map_shown", meta={"qa_index": qa_index, "status": _readiness.status})
                await message.answer(_prelim_text, reply_markup=preliminary_map_keyboard(_r1, _r2))
                return

        if qa_index < len(questions):
            data_fresh = await state.get_data()
            context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
            asked = await _ask_next_interview_question(
                message,
                state,
                data_fresh,
                analysis,
                context,
                qa_index=qa_index,
                lang=lang,
                user_mode=user_mode,
            )
            if asked:
                return

        merged_answers = _merge_answers_text(qa_answers)
        await state.update_data(answers_text=merged_answers)
        await _advance_after_questions(message, state, lang)
        return

    await state.update_data(answers_text=clean)
    await _advance_after_questions(message, state, lang)


@router.message(CareerFlow.waiting_for_resume_decision, F.text.in_(ALL_RESUME_SKIP))
async def skip_resume(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await state.update_data(resume_analysis={}, cv_uploaded=False)
    await message.answer(t(lang, "resume_continue_without"))
    await _start_questions_module(message, state, lang)


@router.message(CareerFlow.waiting_for_resume_decision, F.text.in_(ALL_RESUME_UPLOAD))
async def ask_resume_upload(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await state.set_state(CareerFlow.WAITING_CV)
    await message.answer(t(lang, "resume_upload_prompt"), reply_markup=resume_wait_keyboard())


@router.message(CareerFlow.waiting_for_resume, F.text)
async def handle_resume_text(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    resume_text = (message.text or "").strip()
    if resume_text in ALL_RESUME_UPLOAD:
        await message.answer(t(lang, "resume_upload_prompt"), reply_markup=resume_wait_keyboard())
        return
    if resume_text in ALL_RESUME_SKIP:
        await state.update_data(resume_analysis={})
        await _start_questions_module(message, state, lang)
        return
    if not resume_text or len(resume_text) < 60:
        await message.answer(t(lang, "resume_missing_payload"), reply_markup=resume_wait_keyboard())
        return
    _resume_debug_log(message, "resume_received", source="text", chars=len(resume_text))
    _resume_debug_log(message, "text_extracted", source="text", chars=len(resume_text))
    await state.set_state(CareerFlow.RESUME_ANALYZING)
    await message.answer(t(lang, "resume_analysis_processing"))
    resume_analysis = await ai_client.analyze_resume(resume_text, lang)
    await state.update_data(
        resume_analysis=resume_analysis,
        cv_uploaded=True,
        cv_summary=resume_analysis.get("what_is_good", []),
        cv_gaps=resume_analysis.get("what_is_missing", []),
        cv_strengths=resume_analysis.get("what_is_good", []),
    )
    _resume_debug_log(
        message,
        "analysis_completed",
        good=len(resume_analysis.get("what_is_good", [])),
        missing=len(resume_analysis.get("what_is_missing", [])),
    )
    await message.answer(format_resume_analysis(resume_analysis, lang))
    await _start_questions_module(message, state, lang)


@router.message(CareerFlow.waiting_for_resume, F.text.in_(ALL_RESUME_SKIP))
async def skip_resume_from_upload_step(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await state.update_data(resume_analysis={}, cv_uploaded=False)
    await message.answer(t(lang, "resume_continue_without"))
    await _start_questions_module(message, state, lang)


@router.message(CareerFlow.waiting_for_resume, F.document)
async def handle_resume_document(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    document = message.document
    if not document:
        await message.answer(t(lang, "resume_missing_payload"), reply_markup=resume_wait_keyboard())
        return
    _resume_debug_log(message, "resume_received", source="document", file_name=document.file_name or "unknown")

    try:
        raw_bytes = await _download_document_bytes(message, document)
        resume_text = _decode_resume_bytes(raw_bytes, document.file_name or "")
    except Exception:
        resume_text = ""

    if not resume_text:
        await message.answer(t(lang, "resume_doc_read_error"), reply_markup=resume_wait_keyboard())
        return

    if len(resume_text) < 60:
        await message.answer(t(lang, "resume_missing_payload"), reply_markup=resume_wait_keyboard())
        return

    _resume_debug_log(message, "text_extracted", source="document", chars=len(resume_text))
    await state.set_state(CareerFlow.RESUME_ANALYZING)
    await message.answer(t(lang, "resume_analysis_processing"))
    resume_analysis = await ai_client.analyze_resume(resume_text, lang)
    await state.update_data(
        resume_analysis=resume_analysis,
        cv_uploaded=True,
        cv_summary=resume_analysis.get("what_is_good", []),
        cv_gaps=resume_analysis.get("what_is_missing", []),
        cv_strengths=resume_analysis.get("what_is_good", []),
    )
    _resume_debug_log(
        message,
        "analysis_completed",
        good=len(resume_analysis.get("what_is_good", [])),
        missing=len(resume_analysis.get("what_is_missing", [])),
    )
    await message.answer(format_resume_analysis(resume_analysis, lang))
    await _start_questions_module(message, state, lang)


async def _save_barrier_choice(message: Message, state: FSMContext, choice: str) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    current_group = str(data.get("barrier_current_group") or BARRIER_GROUP_INTERNAL)
    selected = list(data.get("selected_psych_markers") or [])
    group_options = set(_barrier_options_for_group(current_group))
    group_selected_count = len([item for item in selected if item in group_options])
    already_selected = choice in selected
    if not already_selected and group_selected_count >= _BARRIER_GROUP_MAX_SELECT:
        await message.answer(
            t(lang, "barriers_group_limit_reached", limit=_BARRIER_GROUP_MAX_SELECT),
            reply_markup=barriers_group_keyboard(current_group),
        )
        return
    if not already_selected:
        selected.append(choice)
    await state.update_data(selected_psych_markers=selected, selected_barriers=selected)
    text_key = "barriers_already_selected" if already_selected else "barriers_selected"
    await message.answer(
        t(lang, text_key, count=len(selected), items=_selection_to_text(selected)),
        reply_markup=barriers_group_keyboard(current_group),
    )


async def complete_barriers(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message)).strip()
    session_id = str(data.get("session_id") or "").strip()
    await _register_session_context(state, message, user_id=public_user_id, session_id=session_id)
    selected = list(data.get("selected_psych_markers") or [])
    if not selected:
        selected = ["Не указано"]
    await state.update_data(
        selected_psych_markers=selected,
        selected_fears=selected[:6],
        required_questions_completed=True,
    )
    # All normal interview paths end here.  Go through the finalization wrapper
    # so an unexpected provider, persistence, or renderer exception still gives
    # the user a deterministic short conclusion instead of a silent dead end.
    await finalize_career_flow(public_user_id, session_id, "barriers_completed")


@router.message(CareerFlow.ROUTE_CONTEXT, F.text)
async def handle_route_context_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    raw = (message.text or "").strip()

    if raw and await _maybe_switch_to_crisis_support(message, state, lang, raw, source="route_context"):
        return

    if not raw:
        await _start_route_context_intake(message, state, lang)
        return

    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message)).strip()
    session_id = str(data.get("session_id") or "").strip()
    await _register_session_context(state, message, user_id=public_user_id, session_id=session_id)

    index = int(data.get("route_context_index") or 0)
    if raw == QUESTION_ADD_TEXT:
        await state.update_data(route_context_text_mode_for=str(_route_context_question(index, dict(data.get("route_context") or {})).get("id") or index))
        await message.answer("Ок, напишите ответ своими словами одним сообщением.", reply_markup=input_method_keyboard())
        return

    if _is_route_context_stale_input(raw):
        await message.answer("Пожалуйста, ответьте на текущий вопрос одним из вариантов или напишите свой ответ в свободной форме.", reply_markup=_route_context_reply_markup(_route_context_question(index, dict(data.get("route_context") or {}))))
        return

    index = int(data.get("route_context_index") or 0)
    route_context = _normalize_route_context(dict(data.get("route_context") or {}))
    if str(route_context.get("country") or "").strip() and "country_config" not in route_context:
        route_context["country_config"] = _resolve_country_config(str(route_context["country"]))
    question = _route_context_question(index, route_context)
    question_id = str(question.get("id") or index)
    options = _route_context_options(question)
    keys = [str(item) for item in question.get("keys", []) if str(item).strip()] if isinstance(question.get("keys", []), list) else []

    text_mode_for = str(data.get("route_context_text_mode_for") or "")
    if raw == QUESTION_ADD_TEXT and options:
        await state.update_data(route_context_text_mode_for=question_id)
        await message.answer("Ок, напишите ответ своими словами одним сообщением.", reply_markup=input_method_keyboard())
        return

    if options and text_mode_for != question_id and not _route_context_answer_is_valid(raw, options, question_id):
        await message.answer("Выберите вариант кнопкой, либо отправьте несколько подходящих вариантов через запятую/точку с запятой, либо нажмите «Другое / расскажу своими словами».", reply_markup=_route_context_reply_markup(question))
        return

    await state.update_data(route_context_text_mode_for="")
    parsed_values, next_index = _route_context_next_index(index, raw, keys)
    route_context.update(_normalize_route_context(parsed_values))

    # After country answer (Q1): compute and persist structured country_config
    if question_id == "country" and str(parsed_values.get("country") or "").strip():
        country_config = _resolve_country_config(str(parsed_values["country"]))
        route_context["country_config"] = country_config  # type: ignore[assignment]
        await state.update_data(country_config=country_config)

    await state.update_data(route_context=route_context, route_context_index=next_index, awaiting_route_context=True)

    if next_index >= len(_ROUTE_CONTEXT_FIELDS):
        public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
        session_id = str(data.get("session_id") or "").strip()
        route_context = _normalize_route_context(route_context)
        await state.update_data(awaiting_route_context=False)
        snapshot = _build_profile_snapshot({**data, "route_context": route_context})
        await state.update_data(profile_snapshot=snapshot)
        save_profile_version(
            public_user_id,
            "route_context_selected",
            {
                "country_code": snapshot.get("country_code"),
                "currency": snapshot.get("currency"),
                "route_context": snapshot.get("route_context"),
                "ready_for_report": snapshot.get("ready_for_report"),
                "user_mode": str(data.get("user_mode") or ""),
                "report_generation_id": str(data.get("report_generation_id") or ""),
            },
            session_id=session_id,
        )
        await state.set_state(CareerFlow.GENERATING_REPORT)
        await message.answer(t(lang, "route_context_complete"))
        await _build_and_send_report(message, state, lang)
        return

    await message.answer(t(lang, "route_context_saved", remaining_count=len(_ROUTE_CONTEXT_FIELDS) - next_index))
    await _start_route_context_intake(message, state, lang)


@router.message(CareerFlow.waiting_for_barriers, F.text)
async def barriers_fallback(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    raw = (message.text or "").strip()
    low = raw.lower()
    current_group = str(data.get("barrier_current_group") or BARRIER_GROUP_INTERNAL)
    current_options = set(_barrier_options_for_group(current_group))
    selected = list(data.get("selected_psych_markers") or [])

    if raw in ALL_PSYCH_GROUP_OPTIONS:
        if raw == PSYCH_SKIP:
            await complete_barriers(message, state)
            return
        await message.answer(t(lang, "barriers_only_hint"), reply_markup=barriers_group_keyboard(current_group))
        return

    is_done_text = (
        low in _BARRIER_DONE_ALIASES
        or low in _BARRIER_DONE_BY_LOWER
        or ("отмет" in low and "меша" in low)
    )
    if is_done_text:
        moved = await _advance_barrier_group(message, state)
        if moved:
            return
        await complete_barriers(message, state)
        return

    if raw in ALL_RESULT_ACTIONS:
        await message.answer(t(lang, "barriers_only_hint"), reply_markup=barriers_group_keyboard(current_group))
        return

    normalized_choice = _BARRIER_OPTION_BY_LOWER.get(low) or raw
    if normalized_choice in ALL_PSYCH_BARRIER_OPTIONS and normalized_choice not in current_options:
        if normalized_choice in selected:
            await message.answer(
                t(lang, "barriers_already_selected", count=len(selected), items=_selection_to_text(selected))
                + "\n\n"
                + t(lang, _barrier_prompt_key(current_group)),
                reply_markup=barriers_group_keyboard(current_group),
            )
            return
        await message.answer(
            t(lang, "barriers_only_hint") + "\n\n" + t(lang, _barrier_prompt_key(current_group)),
            reply_markup=barriers_group_keyboard(current_group),
        )
        return
    if normalized_choice not in current_options:
        await message.answer(t(lang, "barriers_only_hint"), reply_markup=barriers_group_keyboard(current_group))
        return
    await _save_barrier_choice(message, state, normalized_choice)


@router.message(CareerFlow.GENERATING_REPORT, F.text | F.voice | F.document | F.photo | F.sticker)
@router.message(CareerFlow.REPORT_GENERATING, F.text | F.voice | F.document | F.photo | F.sticker)
@router.message(CareerFlow.PDF_GENERATING, F.text | F.voice | F.document | F.photo | F.sticker)
async def generation_lock_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await _track_event(message, state, "invalid_answer", action="during_generation", meta={"kind": "stale_input_while_generating"})
    await message.answer(t(lang, "generation_lock_message"))


@router.message(CareerFlow.RESUME_ANALYZING, F.text | F.voice | F.document | F.photo | F.sticker)
async def resume_analysis_lock_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "resume_processing_lock_message"))


@router.message(CareerFlow.waiting_for_story, F.text.in_(ALL_RESTART))
@router.message(CareerFlow.waiting_for_post_result_action, F.text.in_(ALL_RESTART))
async def restart_flow(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    _cancel_reminder(message.chat.id)
    await state.update_data(
        story_text="",
        story_analysis={},
        answers_text="",
        qa_answers=[],
        qa_index=0,
        final_report={},
        resume_analysis={},
        selected_barriers=[],
        selected_fears=[],
        selected_psych_markers=[],
        selected_psych_state=[],
        selected_coping=[],
        selected_social_state=[],
        selected_integration_state=[],
        selected_energy_sources=[],
        selected_career_priorities=[],
        psych_selected=[],
        psych_state_selected=[],
        coping_selected=[],
        social_selected=[],
        integration_selected=[],
        energy_selected=[],
        priorities_selected=[],
        report_chunks={},
        skiller_today_task="",
        final_report_generated=False,
        pdf_report_path="",
        pending_answer_review={},
        selected_choice_reasons={},
        pending_choice_reason={},
        awaiting_extended_diagnostics_choice=False,
        extended_diagnostics_done=False,
        interview_context={},
        asked_question_signatures=[],
        reminder_due_at="",
        career_planning_paused=False,
        crisis_detected=False,
        crisis_detected_source="",
    )
    await state.set_state(CareerFlow.SELECTING_PACE)
    await message.answer(t(lang, "restart_prompt"))
    await message.answer(t(lang, "start_intro"))
    await message.answer(t(lang, "pace_prompt"), reply_markup=pace_keyboard())


@router.message(CareerFlow.waiting_for_story, F.text.in_(ALL_INPUT_TEXT))
async def prompt_story_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    await message.answer(t(lang, "story_text_prompt"), reply_markup=input_method_keyboard())
    if (data.get("interaction_profile") or {}).get("preferred_input") == "buttons":
        await message.answer(t(lang, "adaptive_transition_buttons"), reply_markup=short_story_keyboard())


@router.message(CareerFlow.waiting_for_story, F.text.in_(ALL_INPUT_VOICE))
async def prompt_story_voice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    await message.answer(t(lang, "story_voice_prompt"), reply_markup=input_method_keyboard())
    await state.update_data(preferred_input="voice")


@router.message(CareerFlow.waiting_for_story, F.text.in_(ALL_INPUT_DONT_KNOW))
async def prompt_story_dont_know(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "short_story_prompt"), reply_markup=short_story_keyboard())


@router.message(CareerFlow.waiting_for_story, F.text.in_(ALL_RESUME_UPLOAD))
async def prompt_resume_from_start(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "story_text_prompt"), reply_markup=input_method_keyboard())


@router.message(CareerFlow.waiting_for_story, F.text.in_(ALL_RESUME_SKIP))
async def prompt_resume_skip_from_start(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "story_text_prompt"), reply_markup=input_method_keyboard())


@router.message(CareerFlow.waiting_for_answers, F.text.in_(ALL_INPUT_TEXT))
async def prompt_answers_text(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "answers_text_prompt"))


@router.message(CareerFlow.waiting_for_answers, F.text.in_(ALL_INPUT_VOICE))
async def prompt_answers_voice(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "answers_voice_prompt"))


@router.message(CareerFlow.waiting_for_story, F.text)
async def handle_story_text(message: Message, state: FSMContext) -> None:
    await process_story_input(message, state, message.text or "")


@router.message(CareerFlow.waiting_for_answers, F.text.in_(ALL_ANSWER_REVIEW_ACTIONS))
@_serialize_interview_update
async def handle_answer_review_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    action = (message.text or "").strip()
    pending = data.get("pending_answer_review") or {}
    if not pending and action in {ANSWER_CONTEXT_YES, ANSWER_CONTEXT_NO}:
        snapshot = data.get("answer_review_snapshot") or {}
        if (
            isinstance(snapshot, dict)
            and snapshot.get("review_type") == "context_mismatch"
            and int(snapshot.get("index", -1)) == int(data.get("qa_index", 0))
        ):
            pending = snapshot
    if not pending:
        # A duplicate/stale confirmation must remove the obsolete yes/no
        # keyboard and restore the actual active question, never show a hint
        # that leaves the person on the same unusable keyboard.
        analysis = data.get("story_analysis") or {}
        qa_index = int(data.get("qa_index", 0))
        questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
        if action in {ANSWER_CONTEXT_YES, ANSWER_CONTEXT_NO} and qa_index < len(questions):
            await message.answer(
                _question_prompt(analysis, qa_index, lang),
                reply_markup=_question_reply_markup(analysis, qa_index),
            )
            return
        await message.answer(t(lang, "question_answer_hint"))
        return

    review_type = str(pending.get("review_type") or "").strip()
    if review_type == "context_mismatch":
        qa_index = int(data.get("qa_index", 0))
        analysis = data.get("story_analysis") or {}
        questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
        qa_answers = list(data.get("qa_answers") or [])
        user_mode = str(data.get("user_mode") or "calm_steps")
        quick_report_after_questions = bool(data.get("quick_report_after_questions"))

        if action == ANSWER_CONTEXT_NO:
            await state.update_data(pending_answer_review={}, answer_review_snapshot={})
            await message.answer(_question_prompt(analysis, qa_index, lang), reply_markup=_question_reply_markup(analysis, qa_index))
            next_q = questions[qa_index] if qa_index < len(questions) and isinstance(questions[qa_index], dict) else {}
            await _track_event(
                message,
                state,
                "question_shown",
                meta={
                    "question_index": qa_index + 1,
                    "question_id": _question_id(next_q, qa_index) if next_q else qa_index + 1,
                    "decision_that_may_change": _decision_that_may_change(next_q) if isinstance(next_q, dict) else "",
                },
            )
            return

        if action == ANSWER_CONTEXT_YES:
            accepted_answer = str(pending.get("normalized_answer") or str(pending.get("answer", "")).strip())
            qa_answers.append(
                {
                    "question": str(pending.get("question", f"Вопрос {qa_index + 1}")),
                    "question_id": int(pending.get("question_id", qa_index + 1)),
                    "answer": accepted_answer,
                    "source_message_id": str(getattr(message, "message_id", "")),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            qa_index += 1
            evidence_payload, is_ready = _update_evidence_after_answer(data, questions[qa_index - 1] if qa_index - 1 < len(questions) else {}, accepted_answer)
            await state.update_data(
                qa_answers=qa_answers,
                qa_index=qa_index,
                pending_answer_review={},
                answer_review_snapshot={},
                evidence_profile=evidence_payload,
            )
            await _sync_interview_context_after_answer(state, data, evidence_payload, accepted_answer)

            if is_ready:
                merged_answers = _merge_answers_text(qa_answers)
                await state.update_data(answers_text=merged_answers)
                await _track_interview_ready_event(
                    message,
                    state,
                    question_index=qa_index,
                    evidence_payload=evidence_payload,
                )
                await _start_barriers_module(message, state, lang)
                return

            questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
            if qa_index < len(questions):
                data_fresh = await state.get_data()
                context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
                asked = await _ask_next_interview_question(
                    message,
                    state,
                    data_fresh,
                    analysis,
                    context,
                    qa_index=qa_index,
                    lang=lang,
                    user_mode=user_mode,
                )
                if asked:
                    return
                return

            merged_answers = _merge_answers_text(qa_answers)
            await state.update_data(answers_text=merged_answers)
            await _start_barriers_module(message, state, lang)
            return

        await message.answer(t(lang, "answer_context_mismatch_intro"), reply_markup=answer_review_keyboard(context_mismatch=True))
        await message.answer(
            t(lang, "answer_context_mismatch_question", meaning=str(pending.get("normalized_answer") or "")),
            reply_markup=answer_review_keyboard(context_mismatch=True),
        )
        return

    qa_answers = list(data.get("qa_answers") or [])
    qa_index = int(data.get("qa_index", 0))
    analysis = data.get("story_analysis") or {}
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    user_mode = str(data.get("user_mode") or "calm_steps")
    quick_report_after_questions = bool(data.get("quick_report_after_questions"))

    if action == ANSWER_RETRY:
        await state.update_data(pending_answer_review={})
        await message.answer(_question_prompt(analysis, qa_index, lang), reply_markup=_question_reply_markup(analysis, qa_index))
        questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
        next_q = questions[qa_index] if qa_index < len(questions) and isinstance(questions[qa_index], dict) else {}
        await _track_event(
            message,
            state,
            "question_shown",
            meta={
                "question_index": qa_index + 1,
                "question_id": _question_id(next_q, qa_index) if next_q else qa_index + 1,
                "decision_that_may_change": _decision_that_may_change(next_q) if isinstance(next_q, dict) else "",
            },
        )
        return

    if action in {ANSWER_CONTEXT_YES, ANSWER_CONTEXT_NO}:
        await message.answer(t(lang, "answer_review_prompt"), reply_markup=answer_review_keyboard())
        return

    answer_text = str(pending.get("answer", "")).strip()
    if action == ANSWER_SKIP:
        answer_text = "(пропущено пользователем)"
        await _track_event(message, state, "user_skipped", meta={"question_index": qa_index + 1, "question_id": int(pending.get("question_id", qa_index + 1))})

    qa_answers.append(
        {
            "question": str(pending.get("question", f"Вопрос {qa_index + 1}")),
            "question_id": int(pending.get("question_id", qa_index + 1)),
            "answer": answer_text,
        }
    )
    qa_index += 1
    evidence_payload, is_ready = _update_evidence_after_answer(data, questions[qa_index - 1] if qa_index - 1 < len(questions) else {}, answer_text)
    await state.update_data(
        qa_answers=qa_answers,
        qa_index=qa_index,
        pending_answer_review={},
        evidence_profile=evidence_payload,
    )
    await _sync_interview_context_after_answer(state, data, evidence_payload, answer_text)

    if is_ready:
        merged_answers = _merge_answers_text(qa_answers)
        await state.update_data(answers_text=merged_answers)
        await _track_interview_ready_event(
            message,
            state,
            question_index=qa_index,
            evidence_payload=evidence_payload,
        )
        await _advance_after_questions(message, state, lang)
        return

    if qa_index < len(questions):
        data_fresh = await state.get_data()
        context = _build_interview_context(data_fresh, analysis if isinstance(analysis, dict) else None)
        asked = await _ask_next_interview_question(
            message,
            state,
            data_fresh,
            analysis,
            context,
            qa_index=qa_index,
            lang=lang,
            user_mode=user_mode,
        )
        if asked:
            return
        return

    merged_answers = _merge_answers_text(qa_answers)
    await state.update_data(answers_text=merged_answers)
    await _advance_after_questions(message, state, lang)


@router.message(CareerFlow.waiting_for_answers, F.text)
async def handle_answers_text(message: Message, state: FSMContext) -> None:
    await process_answers_input(message, state, message.text or "")


@router.message(CareerFlow.ROUTE_SELECTION, F.text.in_(ALL_ROUTE_SELECTION_ACTIONS))
@router.message(CareerFlow.FINAL_READY, F.text.in_(ALL_ROUTE_SELECTION_ACTIONS))
@router.message(CareerFlow.REPORT_READY, F.text.in_(ALL_ROUTE_SELECTION_ACTIONS))
async def handle_route_selection_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    report = data.get("final_report") or {}
    rows = data.get("route_compare_rows") if isinstance(data.get("route_compare_rows"), list) else _build_route_comparison_rows(report)
    raw_action = (message.text or "").strip()
    action = raw_action
    matched_strategy = _match_choice_action(raw_action, ALL_CAREER_STRATEGY_ACTIONS)
    if matched_strategy:
        action = matched_strategy

    if action and await _maybe_switch_to_crisis_support(message, state, lang, action, source="route_selection"):
        return

    if bool(data.get("awaiting_route_specific_questions")):
        gaps = data.get("route_specific_gaps") if isinstance(data.get("route_specific_gaps"), list) else []
        idx = int(data.get("route_specific_index", 0))
        if idx < 0:
            idx = 0
        if not gaps or idx >= len(gaps):
            await state.update_data(awaiting_route_specific_questions=False)
            report_ready = data.get("final_report") if isinstance(data.get("final_report"), dict) else {}
            await _send_final_map_bundle(message, state, lang, report_ready)
            return

        current = gaps[idx] if isinstance(gaps[idx], dict) else {}
        answers = data.get("route_specific_answers") if isinstance(data.get("route_specific_answers"), list) else []
        answers.append(
            {
                "gap_key": str(current.get("gap_key") or f"route_specific_{idx + 1}"),
                "question": str(current.get("prompt") or ""),
                "answer": action,
            }
        )
        idx += 1
        await state.update_data(route_specific_answers=answers, route_specific_index=idx)

        if idx < len(gaps):
            nxt = gaps[idx] if isinstance(gaps[idx], dict) else {}
            await message.answer(str(nxt.get("prompt") or ""), reply_markup=_route_specific_reply_markup(nxt))
            return

        summary = "\n".join(
            f"- {str(item.get('gap_key') or '')}: {str(item.get('answer') or '')}"
            for item in answers
            if isinstance(item, dict)
        )
        merged_answers = str(data.get("answers_text") or "").strip()
        merged_answers = (merged_answers + "\n\nМаршрутные уточнения:\n" + summary).strip()
        await state.update_data(
            awaiting_route_specific_questions=False,
            answers_text=merged_answers,
            route_specific_done=True,
        )
        await _track_event(
            message,
            state,
            "route_specific_clarification_done",
            meta={"count": len(answers), "route": str(data.get('route_specific_selected_route') or '')},
        )
        report_ready = data.get("final_report") if isinstance(data.get("final_report"), dict) else {}
        await _send_final_map_bundle(message, state, lang, report_ready)
        return

    if bool(data.get("awaiting_need_decision_questions")):
        answers = data.get("need_decision_answers") if isinstance(data.get("need_decision_answers"), list) else []
        q_index = int(data.get("need_decision_question_index", 0))
        if action:
            answers.append(action)
        q_index += 1
        if q_index < len(_NEED_DECISION_QUESTIONS):
            await state.update_data(need_decision_answers=answers, need_decision_question_index=q_index)
            await message.answer(_NEED_DECISION_QUESTIONS[q_index])
            return

        recommended_strategy = _recommend_strategy_from_need_decision_answers([str(item) for item in answers])
        recommended_action = _career_strategy_action_from_code(recommended_strategy)
        strategy_code, strategy_label = _career_strategy_from_action(recommended_action)
        public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
        session_id = str(data.get("session_id") or "").strip()
        await state.update_data(
            career_strategy=strategy_code,
            career_strategy_label=strategy_label,
            awaiting_career_strategy_choice=False,
            awaiting_need_decision_questions=False,
            need_decision_answers=answers,
            need_decision_question_index=len(_NEED_DECISION_QUESTIONS),
        )
        save_profile_version(
            public_user_id,
            "career_strategy_selected",
            {
                "career_strategy": strategy_code,
                "career_strategy_label": strategy_label,
                "report_generation_id": str(data.get("report_generation_id") or ""),
                "user_mode": str(data.get("user_mode") or ""),
                "source": "need_decision_questions",
            },
            session_id=session_id,
        )
        await _track_event(
            message,
            state,
            "career_strategy_selected",
            meta={"career_strategy": strategy_code, "career_strategy_label": strategy_label, "source": "need_decision_questions"},
        )
        route_context = data.get("route_context") if isinstance(data.get("route_context"), dict) else {}
        _apply_strategy_outputs(report, {str(key): str(value) for key, value in route_context.items()}, strategy_code)
        await state.update_data(final_report=report, report_chunks=report_chunks(report, lang))
        await message.answer(
            f"Предварительная рекомендация: {strategy_label}. Если захотите, позже можно сменить стратегию кнопкой.",
            reply_markup=career_strategy_keyboard(),
        )
        await message.answer(t(lang, "career_strategy_saved", choice=strategy_label), reply_markup=career_strategy_keyboard())
        await _present_route_selection(message, state, lang, report)
        return

    if bool(data.get("awaiting_career_strategy_choice")) or action in ALL_CAREER_STRATEGY_ACTIONS or matched_strategy:
        if action not in ALL_CAREER_STRATEGY_ACTIONS and not matched_strategy:
            await message.answer(t(lang, "career_strategy_intro"), reply_markup=career_strategy_keyboard())
            return

        if action == CAREER_STRATEGY_HELP:
            bundle = _build_need_decision_bundle(
                report if isinstance(report, dict) else {},
                data.get("route_context") if isinstance(data.get("route_context"), dict) else {},
            )
            mini_table = _need_decision_comparison_text(bundle)
            intro = _safe_default(bundle.get("message"), "Сравним три пути и выберем стратегию по вашим ограничениям.")
            await state.update_data(
                awaiting_need_decision_questions=True,
                need_decision_question_index=0,
                need_decision_answers=[],
            )
            await message.answer(f"{intro}\n\n{mini_table}".strip())
            await message.answer(_NEED_DECISION_QUESTIONS[0])
            return

        strategy_code, strategy_label = _career_strategy_from_action(action)
        public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
        session_id = str(data.get("session_id") or "").strip()
        await state.update_data(
            career_strategy=strategy_code,
            career_strategy_label=strategy_label,
            awaiting_career_strategy_choice=False,
        )
        save_profile_version(
            public_user_id,
            "career_strategy_selected",
            {
                "career_strategy": strategy_code,
                "career_strategy_label": strategy_label,
                "report_generation_id": str(data.get("report_generation_id") or ""),
                "user_mode": str(data.get("user_mode") or ""),
            },
            session_id=session_id,
        )
        await _track_event(
            message,
            state,
            "career_strategy_selected",
            meta={"career_strategy": strategy_code, "career_strategy_label": strategy_label},
        )
        route_context = data.get("route_context") if isinstance(data.get("route_context"), dict) else {}
        _apply_strategy_outputs(report, {str(key): str(value) for key, value in route_context.items()}, strategy_code)
        await state.update_data(final_report=report, report_chunks=report_chunks(report, lang))
        await message.answer(t(lang, "career_strategy_saved", choice=strategy_label), reply_markup=career_strategy_keyboard())
        await _present_route_selection(message, state, lang, report)
        return

    if action in {ROUTE_CHOICE_HELP, ROUTE_CHOICE_NO_LOGIC}:
        if _is_construction_estimation_domain(report) and action == ROUTE_CHOICE_HELP:
            _apply_route_choice_to_report(report, ROUTE_CHOICE_HELP, rows)
            await state.update_data(final_report=report, report_chunks=report_chunks(report, lang), route_compare_rows=rows)
            await message.answer(t(lang, "route_compare_intro"), reply_markup=route_choice_keyboard())
            await _answer_safe(message, f"{t(lang, 'route_compare_title')}\n\n{_format_route_comparison(rows)}", reply_markup=route_choice_keyboard())
            await message.answer(t(lang, "route_compare_question"), reply_markup=route_choice_keyboard())
            await _track_event(message, state, "route_help_requested", action=action, meta={"route_count": len(rows)})
            return
        await message.answer(t(lang, "route_choice_help"), reply_markup=route_choice_keyboard())
        return

    if action == ROUTE_CHOICE_OTHER:
        alternatives = data.get("alternative_routes") if isinstance(data.get("alternative_routes"), list) else _build_alternative_routes(report, rows)
        if alternatives:
            current_idx = int(data.get("current_route_index", -1)) + 1
            if current_idx >= len(alternatives):
                current_idx = 0
            await state.update_data(alternative_routes=alternatives, current_route_index=current_idx)
            route_payload = alternatives[current_idx] if isinstance(alternatives[current_idx], dict) else {}
            await message.answer(_format_alternative_route(route_payload), reply_markup=route_choice_keyboard())
        else:
            await message.answer(t(lang, "route_compare_question"), reply_markup=route_choice_keyboard())
        await _track_event(message, state, "route_other_requested", meta={"route_count": len(rows), "alternatives_count": len(alternatives) if isinstance(alternatives, list) else 0})
        return

    if action == ROUTE_CHOICE_CLOSE:
        selected_route = _apply_route_choice_to_report(report, ROUTE_CHOICE_STABLE, rows)
        chunks = report_chunks(report, lang)
        new_report_generation_id = str(uuid.uuid4())
        public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
        session_id = str(data.get("session_id") or "").strip()
        save_report_version(new_report_generation_id, public_user_id, report, session_id=session_id)
        save_profile_version(
            public_user_id,
            "route_selected_report_regenerated",
            {
                "selected_route": selected_route,
                "route_choice": action,
                "report_generation_id": new_report_generation_id,
            },
            session_id=session_id,
        )
        await state.update_data(
            final_report=report,
            report_chunks=chunks,
            final_report_generated=True,
            user_route_choice=action,
            route_compare_rows=rows,
            report_generation_id=new_report_generation_id,
        )
        await _track_event(
            message,
            state,
            "route_selected",
            action=action,
            meta={"selected_route": selected_route or "", "report_regenerated": True, "new_report_generation_id": new_report_generation_id},
        )
        await message.answer(t(lang, "route_choice_saved", choice=selected_route or action), reply_markup=route_choice_keyboard())
        if await _maybe_start_route_specific_clarification(message, state, lang, selected_route or action):
            return
        await _send_final_map_bundle(message, state, lang, report)
        return

    selected_route = _apply_route_choice_to_report(report, action, rows)
    chunks = report_chunks(report, lang)
    new_report_generation_id = str(uuid.uuid4())
    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
    session_id = str(data.get("session_id") or "").strip()
    save_report_version(new_report_generation_id, public_user_id, report, session_id=session_id)
    save_profile_version(
        public_user_id,
        "route_selected_report_regenerated",
        {
            "selected_route": selected_route,
            "route_choice": action,
            "report_generation_id": new_report_generation_id,
        },
        session_id=session_id,
    )
    await state.update_data(
        final_report=report,
        report_chunks=chunks,
        final_report_generated=True,
        user_route_choice=action,
        route_compare_rows=rows,
        report_generation_id=new_report_generation_id,
    )

    await _track_event(
        message,
        state,
        "route_selected",
        action=action,
        meta={"selected_route": selected_route or "", "report_regenerated": True, "new_report_generation_id": new_report_generation_id},
    )
    await message.answer(t(lang, "route_choice_saved", choice=selected_route or action), reply_markup=route_choice_keyboard())
    if await _maybe_start_route_specific_clarification(message, state, lang, selected_route or action):
        return
    await _send_final_map_bundle(message, state, lang, report)


@router.message(CareerFlow.ROUTE_SELECTION, F.text)
async def handle_route_selection_fallback(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    text = (message.text or "").strip()
    matched_strategy = _match_choice_action(text, ALL_CAREER_STRATEGY_ACTIONS)
    if matched_strategy:
        message.text = matched_strategy
        await handle_route_selection_actions(message, state)
        return
    if bool(data.get("awaiting_route_specific_questions")):
        gaps = data.get("route_specific_gaps") if isinstance(data.get("route_specific_gaps"), list) else []
        idx = int(data.get("route_specific_index", 0))
        if gaps and idx < len(gaps):
            current = gaps[idx] if isinstance(gaps[idx], dict) else {}
            await message.answer(str(current.get("prompt") or ""), reply_markup=_route_specific_reply_markup(current))
            return
    if bool(data.get("awaiting_need_decision_questions")):
        q_index = int(data.get("need_decision_question_index", 0))
        if q_index < len(_NEED_DECISION_QUESTIONS):
            await message.answer(_NEED_DECISION_QUESTIONS[q_index])
            return
    if bool(data.get("awaiting_career_strategy_choice")):
        await message.answer(t(lang, "career_strategy_intro"), reply_markup=career_strategy_keyboard())
        return
    await message.answer(t(lang, "route_compare_question"), reply_markup=route_choice_keyboard())


@router.message(CareerFlow.CRISIS_SUPPORT, F.text.in_(ALL_CRISIS_SUPPORT_ACTIONS))
async def handle_crisis_support_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    action = (message.text or "").strip()
    request_id = _ensure_public_id(data, message)
    await state.update_data(public_user_id=request_id)
    
    if action == CRISIS_HELP_HOTLINE:
        hotline_msg = t(lang, "crisis_hotline_info")
        await message.answer(hotline_msg)
        await message.answer("После того, как позвоните и почувствуете поддержку, дайте мне знать, и я помогу с карьерным маршрутом.", reply_markup=crisis_support_keyboard())
        await _track_event(message, state, "crisis_action_selected", action="hotline", meta={})
    
    elif action == CRISIS_SPECIALIST:
        await message.answer("Специалист поможет разобраться в том, что сейчас происходит. Это может быть психолог, психиатр или counselor в вашей стране.\n\nПосле консультации мы продолжим работу над карьерным маршрутом.", reply_markup=crisis_support_keyboard())
        await _track_event(message, state, "crisis_action_selected", action="specialist", meta={})
    
    elif action == CRISIS_TRUSTED_PERSON:
        await message.answer("Разговор с человеком, которому вы доверяете, может помочь почувствовать поддержку. Не стесняйтесь рассказать о том, что вы переживаете.\n\nВ любой момент вы можете вернуться к карьерному маршруту.", reply_markup=crisis_support_keyboard())
        await _track_event(message, state, "crisis_action_selected", action="trusted_person", meta={})
    
    elif action == CRISIS_CONTINUE_LATER:
        await message.answer("Договорились. Позаботьтесь о себе, и когда будете готовы, я помогу с карьерным маршрутом.\n\nМожете написать /start когда будете готовы начать заново.", reply_markup=ReplyKeyboardRemove())
        await _track_event(message, state, "crisis_action_selected", action="continue_later", meta={})
        await state.clear()


@router.message(CareerFlow.CRISIS_SUPPORT, F.text)
async def handle_crisis_support_fallback(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    text = (message.text or "").strip()
    if text and _detect_crisis_risk(text):
        await message.answer(t(lang, "crisis_hotline_info"))
    await message.answer(t(lang, "crisis_support_step"), reply_markup=crisis_support_keyboard())


@router.message(CareerFlow.waiting_for_post_result_action, F.text.in_(ALL_SPECIALIST_ROUTING_ACTIONS))
@router.message(CareerFlow.FINAL_READY, F.text.in_(ALL_SPECIALIST_ROUTING_ACTIONS))
async def handle_specialist_routing_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    action = (message.text or "").strip()
    request_id = _ensure_public_id(data, message)
    await state.update_data(public_user_id=request_id, awaiting_specialist_routing_choice=False)

    if action == SPECIALIST_ROUTE_SELF:
        await message.answer("Договорились. Двигаемся самостоятельно: начните с ближайшего практического шага в карте.", reply_markup=result_actions_keyboard())
        return

    notify_action = "career_consultant"
    followup = t(lang, "specialist_contact_intro", request_id=request_id)
    if action == SPECIALIST_ROUTE_PSYCH:
        notify_action = "psychologist"
        followup = f"{t(lang, 'specialist_contact_intro', request_id=request_id)}\n\nОтдельно отметил(а), что нужен психологический фокус: тревога/выгорание/внутренний стопор."
    elif action == SPECIALIST_ROUTE_BOTH:
        notify_action = "career_and_psychologist"
        followup = f"{t(lang, 'specialist_contact_intro', request_id=request_id)}\n\nЗафиксировал(а), что важны оба трека: карьерный маршрут и психологическая устойчивость."

    await _track_event(message, state, "specialist_routing_selected", action=action, meta={"notify_action": notify_action})
    await _notify_specialist_request_owner(message, state, notify_action)
    await state.set_state(CareerFlow.REPORT_GENERATING)
    await message.answer(followup, reply_markup=result_actions_keyboard())


@router.message(CareerFlow.waiting_for_post_result_action, F.text.in_(ALL_RESULT_ACTIONS))
@router.message(CareerFlow.FINAL_READY, F.text.in_(ALL_RESULT_ACTIONS))
@router.message(CareerFlow.REPORT_READY, F.text.in_(ALL_RESULT_ACTIONS))
async def handle_post_result_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    action = (message.text or "").strip()
    if not data.get("final_report_generated") and action != RESULT_OPEN_FULL_REPORT:
        await message.answer(t(lang, "generation_lock_message"))
        return

    await _track_event(message, state, "result_action_clicked", action=action)
    if action == MAP_CHECK_DISAGREE_ROUTE:
        await _track_event(message, state, "user_disagreed", action=action)

    if action == MAP_CHECK_TRUE:
        await state.set_state(CareerFlow.REPORT_GENERATING)
        await message.answer(t(lang, "map_validation_true_reply"), reply_markup=result_actions_keyboard())
        return

    if action == MAP_CHECK_FIX_FACT:
        await state.set_state(CareerFlow.REPORT_CLARIFICATION)
        await message.answer(t(lang, "map_validation_fix_fact_prompt"), reply_markup=input_method_keyboard())
        return

    if action == MAP_CHECK_CHANGE_PRIORITY:
        await state.set_state(CareerFlow.WAITING_ROUTE_CHANGES)
        await message.answer(t(lang, "map_validation_priority_prompt"), reply_markup=input_method_keyboard())
        return

    if action == MAP_CHECK_DISAGREE_ROUTE:
        await state.set_state(CareerFlow.WAITING_ROUTE_CHANGES)
        await message.answer(t(lang, "map_validation_disagree_prompt"), reply_markup=input_method_keyboard())
        return

    if action == RESULT_OPEN_FULL_REPORT:
        html_path = _resolve_html_report_path(data)
        if not html_path:
            report = data.get("final_report") or {}
            if isinstance(report, dict) and report:
                user_name = " ".join(
                    part
                    for part in [
                        (message.from_user.first_name if message.from_user else "") or "",
                        (message.from_user.last_name if message.from_user else "") or "",
                    ]
                    if part
                ).strip()
                try:
                    regenerated = generate_html_report_file(
                        report,
                        output_dir=settings.report_output_dir,
                        user_name=user_name,
                        profile_version=str(data.get("report_generation_id") or "").strip(),
                    )
                    html_path = _normalize_report_path(str(regenerated))
                    report_generation_id = str(data.get("report_generation_id") or "").strip()
                    await state.update_data(html_report_path=html_path)
                    if report_generation_id:
                        update_report_files(report_generation_id, html_report_path=html_path)
                except Exception:
                    html_path = ""

        if html_path and Path(html_path).exists():
            html_url = _report_public_url(Path(html_path))
            await message.answer_document(
                FSInputFile(html_path),
                caption=t(lang, "web_report_ready"),
                reply_markup=telegram_link_keyboard("📄 Открыть полный разбор", html_url) if html_url else result_actions_keyboard(),
            )
            return
        pdf_path = _resolve_pdf_report_path(data)
        if pdf_path and Path(pdf_path).exists():
            await message.answer_document(
                FSInputFile(pdf_path),
                caption=t(lang, "pdf_send_caption"),
                reply_markup=result_actions_keyboard(include_pdf_download=True),
            )
            return
        docx_path = _resolve_docx_report_path(data)
        if docx_path and Path(docx_path).exists():
            await message.answer_document(
                FSInputFile(docx_path),
                caption=t(lang, "docx_send_caption") or "Ваш отчёт в формате DOCX",
                reply_markup=result_actions_keyboard(include_pdf_download=True, include_docx_download=True),
            )
            return
        print(
            "[open-full-report] file_not_found "
            f"chat_id={message.chat.id} "
            f"report_generation_id={str(data.get('report_generation_id') or '').strip()} "
            f"html={_normalize_report_path(str(data.get('html_report_path') or ''))} "
            f"pdf={_normalize_report_path(str(data.get('pdf_report_path') or ''))} "
            f"docx={_normalize_report_path(str(data.get('docx_report_path') or ''))}",
            flush=True,
        )
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return

    if action in {RESULT_SELF_EXPLORE, RESULT_ANALYZE_MARKET}:
        await state.set_state(CareerFlow.SHOWING_DETAILS)
        await message.answer(t(lang, "self_exploration_intro"), reply_markup=self_exploration_keyboard())
        return

    if action in {RESULT_DO_STEPS, PDF_FALLBACK_STEPS, CTA_CAREER_CHAT, CTA_JOB_SEARCH_SUPPORT}:
        steps = data.get("execution_steps") or _build_execution_steps(data.get("final_report") or {})
        progress = data.get("execution_progress") or {}
        current_day = int(data.get("current_execution_day", 0))
        if current_day >= len(steps):
            current_day = max(0, len(steps) - 1)
        await state.update_data(execution_steps=steps, execution_progress=progress, current_execution_day=current_day)
        await state.set_state(CareerFlow.STEP_TRACKING)
        await message.answer(t(lang, "step_tracking_intro"), reply_markup=step_tracking_keyboard())
        await message.answer(t(lang, "step_tracking_current_day", day=current_day + 1, total=len(steps)), reply_markup=step_tracking_keyboard())
        return

    if action in {RESULT_CLARIFY, PDF_FALLBACK_CLARIFY, RESULT_FIX_FACT_OR_PRIORITY}:
        await state.set_state(CareerFlow.REPORT_CLARIFICATION)
        await message.answer(t(lang, "report_clarify_prompt"), reply_markup=input_method_keyboard())
        return

    if action in {RESULT_FIX_CV, RESULT_UPLOAD_OR_EDIT_RESUME}:
        await state.set_state(CareerFlow.CV_REVIEW_WAITING_FILE)
        await message.answer(t(lang, "offer_resume_reply"), reply_markup=resume_wait_keyboard())
        return

    if action == RESULT_KEYWORDS:
        await state.set_state(CareerFlow.SHOWING_DETAILS)
        report = data.get("final_report") or {}
        chunks = data.get("report_chunks") or report_chunks(report, lang)
        await message.answer(t(lang, "show_keywords_reply"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("market", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("translation", "-"), reply_markup=self_exploration_keyboard())
        return

    if action in {RESULT_SPECIALIST, PDF_FALLBACK_SPECIALIST, RESULT_SPECIALIST_EXPLICIT, CTA_CAREER_CONSULTANT}:
        await _track_event(message, state, "specialist_clicked", action=action)
        report = data.get("final_report") if isinstance(data.get("final_report"), dict) else {}
        guidance_text, mode, today_step, career_hits, psych_hits = _specialist_guidance_text(report, data)
        await state.update_data(
            awaiting_specialist_routing_choice=True,
            specialist_guidance_mode=mode,
            specialist_today_step=today_step,
            career_consultant_signals=career_hits,
            psychologist_signals=psych_hits,
        )
        await message.answer(guidance_text, reply_markup=specialist_routing_keyboard())
        return

    if action in {RESULT_SUPPORT_GROUP, RESULT_GROUP_EXPLICIT}:
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "support_group_contact_intro"), reply_markup=result_actions_keyboard())
        if settings.support_group_telegram_url:
            await message.answer(
                settings.support_group_telegram_url,
                reply_markup=telegram_link_keyboard("Хочу в группу поддержки", settings.support_group_telegram_url),
            )
        else:
            await message.answer(t(lang, "telegram_link_missing"), reply_markup=result_actions_keyboard())
        return

    if action == RESULT_START_FIRST_STEP:
        report = data.get("final_report") or {}
        _shorten_first_step_for_overload(report)
        steps = _build_execution_steps(report)
        progress = data.get("execution_progress") or {}
        current_day = int(data.get("current_execution_day", 0))
        if current_day >= len(steps):
            current_day = max(0, len(steps) - 1)
        if steps:
            await state.update_data(final_report=report, execution_steps=steps, execution_progress=progress, current_execution_day=current_day)
            await state.set_state(CareerFlow.STEP_TRACKING)
            await message.answer(t(lang, "step_tracking_intro"), reply_markup=step_tracking_keyboard())
            await message.answer(_execution_step_text(steps[current_day], progress), reply_markup=step_tracking_keyboard())
            return

    if action == RESULT_DOWNLOAD_PDF:
        current_data = await state.get_data()
        current_data["chat_id"] = message.chat.id
        pdf_path = _resolve_pdf_report_path(current_data)
        if pdf_path and Path(pdf_path).exists():
            await state.update_data(pdf_report_path=pdf_path, chat_id=message.chat.id)
            await message.answer_document(
                FSInputFile(pdf_path),
                caption=t(lang, "pdf_send_caption"),
                reply_markup=result_actions_keyboard(include_pdf_download=True),
            )
            return
        await message.answer(t(lang, "pdf_pending"), reply_markup=result_actions_keyboard())
        return

    if action == RESULT_DOWNLOAD_DOCX:
        current_data = await state.get_data()
        docx_path = _resolve_docx_report_path(current_data)
        if docx_path and Path(docx_path).exists():
            await message.answer_document(
                FSInputFile(docx_path),
                caption=t(lang, "docx_send_caption") or "Ваш отчёт в формате DOCX",
                reply_markup=result_actions_keyboard(include_pdf_download=True, include_docx_download=True),
            )
            return
        await message.answer(t(lang, "docx_pending") or "DOCX готовится, попробуйте позже", reply_markup=result_actions_keyboard(include_pdf_download=True, include_docx_download=True))
        return

    await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())


@router.message(CareerFlow.REPORT_NEEDS_CLARIFICATION, F.text)
async def handle_report_readiness_clarification(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    answer = (message.text or "").strip()
    if not answer:
        await message.answer("Выберите вариант, чтобы я завершил карту.", reply_markup=report_readiness_keyboard())
        return

    stored_profile = data.get("canonical_profile")
    stored_question = data.get("active_canonical_question")
    if isinstance(stored_profile, dict) and isinstance(stored_question, dict):
        canonical = CanonicalProfile.model_validate(stored_profile)
        question = ClarifyingQuestion.model_validate(stored_question)
        canonical = record_question_answer(
            canonical, question, answer, source_message_id=str(message.message_id)
        )
        qa_answers = list(data.get("qa_answers") or [])
        qa_answers.append({
            "question_id": question.question_id,
            "source_message_id": str(message.message_id),
            "answer": answer,
            "assessment_id": canonical.assessment_id,
        })
        await state.update_data(
            canonical_profile=canonical.model_dump(mode="json"),
            question_state=canonical.question_state.model_dump(mode="json"),
            qa_answers=qa_answers,
            active_canonical_question=None,
        )

    route_priority = "income_stability" if answer == ROUTE_CHOICE_STABLE else "route_experiment"
    system_may_select_route = answer in {
        ROUTE_CHOICE_STABLE,
        "⏭️ Не знаю, предложите сами",
        "🧪 Сравнить несколько вариантов",
    }
    clarification = {
        "question": str(stored_question.get("text") if isinstance(stored_question, dict) else "Уточняющий вопрос"),
        "answer": answer,
        "route_priority": route_priority,
        "preferred_first_experiment": None if system_may_select_route else answer,
        "system_may_select_route": system_may_select_route,
    }
    answers_text = str(data.get("answers_text") or "").strip()
    answers_text = (answers_text + "\n\nУточнение готовности маршрута:\n" + answer).strip()
    await state.update_data(
        answers_text=answers_text,
        readiness_clarification=clarification,
        route_priority=route_priority,
        preferred_first_experiment=clarification["preferred_first_experiment"],
        system_may_select_route=system_may_select_route,
        readiness_clarification_count=int(data.get("readiness_clarification_count") or 0) + 1,
    )
    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message))
    session_id = str(data.get("session_id") or "").strip()
    save_profile_version(
        public_user_id,
        "readiness_clarification",
        {
            "previous_snapshot": data.get("profile_snapshot") or {},
            "clarification_answer": clarification,
            "answers_text": answers_text,
            "route_priority": route_priority,
            "preferred_first_experiment": clarification["preferred_first_experiment"],
            "system_may_select_route": system_may_select_route,
        },
        session_id=session_id,
    )
    await _track_event(message, state, "report_readiness_clarification", meta=clarification)
    await state.set_state(CareerFlow.REPORT_READINESS_CHECK)
    await message.answer("Ответ сохранил. Проверяю готовность карты и собираю заключение.", reply_markup=ReplyKeyboardRemove())
    public_user_id = str(data.get("public_user_id") or _ensure_public_id(data, message)).strip()
    session_id = str(data.get("session_id") or "").strip()
    await _register_session_context(state, message, user_id=public_user_id, session_id=session_id)
    await _maybe_trigger_career_finalization(message, state, trigger="clarification_limit_reached")
    await _build_and_send_report(message, state, lang)


@router.message(CareerFlow.waiting_for_post_result_action, F.text)
async def handle_post_result_text_fallback(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    text = str(message.text or "").strip().lower().replace("ё", "е")

    overload_tokens = ["не знаю", "страш", "нет сил", "слишком сложно", "сложно", "перегруз", "устал"]
    if any(token in text for token in overload_tokens):
        report = data.get("final_report") or {}
        action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
        today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
        today["action"] = "Откройте заметки и напишите 3 типа работ, которые у вас реально получаются лучше всего."
        today["timebox"] = "5 минут"
        today["result"] = "Есть список из 3 вариантов, с которых можно начать без перегруза."
        action_plan["today"] = today
        report["action_plan"] = action_plan
        steps = _build_execution_steps(report)
        await state.update_data(
            final_report=report,
            execution_steps=steps,
            current_execution_day=0,
        )
        await state.set_state(CareerFlow.STEP_TRACKING)
        await message.answer(t(lang, "post_result_overload_reduce"), reply_markup=step_tracking_keyboard())
        if steps:
            await message.answer(_execution_step_text(steps[0], data.get("execution_progress") or {}), reply_markup=step_tracking_keyboard())
        return

    await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())


@router.message(CareerFlow.SHOWING_DETAILS, F.text.in_(ALL_SELF_EXPLORE_ACTIONS))
async def handle_self_exploration_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    report = data.get("final_report") or {}
    chunks = data.get("report_chunks") or report_chunks(report, lang)
    action = (message.text or "").strip()

    if action == RESULT_BACK_TO_MENU:
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return

    if action in {RESULT_REBUILD, RESULT_CLARIFY}:
        await state.set_state(CareerFlow.REPORT_CLARIFICATION)
        await message.answer(t(lang, "report_clarify_prompt"), reply_markup=input_method_keyboard())
        return

    if action == RESULT_DETAILS:
        await message.answer(t(lang, "details_intro"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("layers", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("not_reset", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("translation", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("bridges", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("barrier", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("integration", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("decision", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("month_roadmap", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("week", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("today", "-"), reply_markup=self_exploration_keyboard())
        return

    if action == RESULT_FIX_CV:
        await state.set_state(CareerFlow.CV_REVIEW_WAITING_FILE)
        await message.answer(t(lang, "offer_resume_reply"), reply_markup=resume_wait_keyboard())
        return

    if action == RESULT_KEYWORDS:
        await message.answer(t(lang, "show_keywords_reply"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("market", "-"), reply_markup=self_exploration_keyboard())
        await message.answer(chunks.get("translation", "-"), reply_markup=self_exploration_keyboard())
        return

    await message.answer(t(lang, "self_exploration_intro"), reply_markup=self_exploration_keyboard())


@router.message(CareerFlow.STEP_TRACKING, F.text.in_(ALL_STEP_TRACKING_ACTIONS))
async def handle_step_tracking_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    steps = data.get("execution_steps") or []
    progress = data.get("execution_progress") or {}
    current_day = int(data.get("current_execution_day", 0))
    action = (message.text or "").strip()
    if action == STEP_DONE_USER:
        action = STEP_DONE
    elif action == STEP_TOO_HARD:
        action = STEP_NOT_DONE
    elif action == STEP_MAKE_EASIER:
        action = STEP_BARRIERS
    elif action == STEP_OTHER_STEP:
        action = STEP_NEXT_DAY
    await _track_event(message, state, "step_action", action=action)

    if action == RESULT_BACK_TO_MENU:
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return

    if not steps:
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "step_tracking_finished"), reply_markup=result_actions_keyboard())
        return

    current_day = max(0, min(current_day, len(steps) - 1))
    current_step = steps[current_day]
    day_key = str(current_step.get("day", current_day + 1))

    if action == STEP_OPEN_TODAY:
        await message.answer(_execution_step_text(current_step, progress), reply_markup=step_tracking_keyboard())
        return

    if action == STEP_DONE:
        progress[day_key] = {"status": "сделал"}
        next_day = current_day + 1
        await state.update_data(execution_progress=progress, current_execution_day=next_day)
        await message.answer(t(lang, "step_tracking_done_reply"), reply_markup=step_tracking_keyboard())
        if next_day >= len(steps):
            await message.answer(t(lang, "step_tracking_finished"), reply_markup=result_actions_keyboard())
            await state.set_state(CareerFlow.FINAL_READY)
        else:
            await message.answer(t(lang, "step_tracking_current_day", day=next_day + 1, total=len(steps)), reply_markup=step_tracking_keyboard())
        return

    if action == STEP_NOT_DONE:
        progress[day_key] = {"status": "не сделал"}
        await state.update_data(execution_progress=progress)
        await message.answer(t(lang, "step_tracking_not_done_reply"), reply_markup=step_tracking_keyboard())
        return

    if action == STEP_BARRIERS:
        await state.update_data(step_barrier_day=day_key)
        await state.set_state(CareerFlow.STEP_BARRIER_INPUT)
        await message.answer(t(lang, "step_tracking_barrier_prompt"), reply_markup=step_tracking_keyboard())
        return

    if action == STEP_NEXT_DAY:
        if current_day + 1 >= len(steps):
            await message.answer(t(lang, "step_tracking_finished"), reply_markup=step_tracking_keyboard())
            return
        next_day = current_day + 1
        await state.update_data(current_execution_day=next_day)
        await message.answer(t(lang, "step_tracking_current_day", day=next_day + 1, total=len(steps)), reply_markup=step_tracking_keyboard())
        await message.answer(_execution_step_text(steps[next_day], progress), reply_markup=step_tracking_keyboard())
        return


@router.message(CareerFlow.STEP_BARRIER_INPUT, F.text)
async def handle_step_barrier_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    barrier_text = (message.text or "").strip()
    progress = data.get("execution_progress") or {}
    day_key = str(data.get("step_barrier_day") or "1")
    row = progress.get(day_key, {}) if isinstance(progress.get(day_key), dict) else {}
    row["status"] = "барьер"
    row["barrier"] = barrier_text or "не уточнено"
    progress[day_key] = row
    await state.update_data(execution_progress=progress, step_barrier_day="")
    await state.set_state(CareerFlow.STEP_TRACKING)
    await message.answer(t(lang, "step_tracking_barrier_saved"), reply_markup=step_tracking_keyboard())


@router.message(CareerFlow.REPORT_CLARIFICATION, F.text)
async def handle_report_clarification_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    clean = (message.text or "").strip()
    if not clean:
        await message.answer(t(lang, "report_clarify_prompt"), reply_markup=input_method_keyboard())
        return
    reframed = _reframe_clarification(clean)
    await message.answer(t(lang, "report_clarify_reframed", summary=reframed), reply_markup=result_actions_keyboard())
    await _rebuild_report_with_note(message, state, lang, reframed)


@router.message(CareerFlow.REPORT_CLARIFICATION, F.voice)
async def handle_report_clarification_voice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    voice = message.voice
    if not voice:
        await message.answer(t(lang, "report_clarify_prompt"), reply_markup=input_method_keyboard())
        return
    await message.answer(t(lang, "voice_clarify_processing"), reply_markup=result_actions_keyboard())
    temp_path = await _download_bot_file(message, voice.file_id, suffix=".ogg")
    try:
        transcript = (await ai_client.transcribe_voice(temp_path)).strip()
    except Exception:
        transcript = ""
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    if not transcript:
        await message.answer(t(lang, "report_clarify_prompt"), reply_markup=input_method_keyboard())
        return
    reframed = _reframe_clarification(transcript)
    await message.answer(t(lang, "report_clarify_reframed", summary=reframed), reply_markup=result_actions_keyboard())
    await _rebuild_report_with_note(message, state, lang, reframed)


@router.message(CareerFlow.BARRIER_ANALYSIS_MENU, F.text.in_(ALL_BARRIER_DETAIL_ACTIONS))
async def handle_barrier_detail_actions(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    action = (message.text or "").strip()

    if action == BARRIER_DETAIL_BACK:
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return

    key_by_action = {
        BARRIER_DETAIL_FEAR_REJECTION: "barrier_detail_fear_rejection",
        BARRIER_DETAIL_MONEY: "barrier_detail_money",
        BARRIER_DETAIL_CHAOS: "barrier_detail_chaos",
        BARRIER_DETAIL_FIRST_STEP: "barrier_detail_first_step",
    }
    detail_key = key_by_action.get(action)
    if not detail_key:
        await message.answer(t(lang, "barrier_detail_intro"), reply_markup=barrier_analysis_keyboard())
        return

    await state.set_state(CareerFlow.BARRIER_ANALYSIS_DETAIL)
    await message.answer(t(lang, detail_key), reply_markup=barrier_analysis_keyboard())
    await state.set_state(CareerFlow.BARRIER_ANALYSIS_MENU)


@router.message(CareerFlow.BARRIER_ANALYSIS_MENU, F.text.in_(ALL_PRACTICAL_BARRIER_ACTIONS))
async def handle_barrier_practical_actions(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    action = (message.text or "").strip()
    if action == PRACTICAL_BACK:
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return
    if action == PRACTICAL_STEP:
        await message.answer(t(lang, "barrier_practical_step"), reply_markup=practical_barrier_keyboard())
        return
    if action == PRACTICAL_DEEP:
        await message.answer(t(lang, "barrier_detail_intro"), reply_markup=barrier_analysis_keyboard())
        return


@router.message(CareerFlow.BARRIER_ANALYSIS_MENU, F.text)
async def handle_barrier_detail_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "barrier_detail_intro"), reply_markup=barrier_analysis_keyboard())


async def process_route_changes_input(message: Message, state: FSMContext, text: str) -> None:
    change_text = (text or "").strip()
    data = await state.get_data()
    lang = _user_language(data)

    if change_text and await _maybe_switch_to_crisis_support(message, state, lang, change_text, source="route_changes"):
        return

    if not change_text:
        await message.answer(t(lang, "route_changes_prompt"), reply_markup=result_actions_keyboard())
        return

    await state.set_state(CareerFlow.REBUILDING_ROUTE)
    await message.answer(t(lang, "route_rebuild_progress"), reply_markup=result_actions_keyboard())
    await _track_event(message, state, "report_started", meta={"mode": "rebuild"})

    story_analysis = data.get("story_analysis") or {}
    updated_answers = ((data.get("answers_text") or "").strip() + "\n\nИзменения пользователя:\n" + change_text).strip()
    decision_layers = _build_decision_layers(data, story_analysis, updated_answers)

    try:
        report = await ai_client.build_report(
            (data.get("story_text") or "").strip(),
            story_analysis,
            updated_answers,
            decision_layers=decision_layers,
            resume_analysis=data.get("resume_analysis") or {},
            selected_barriers=data.get("selected_barriers") or [],
            selected_fears=data.get("selected_fears") or [],
            selected_psych_markers=data.get("selected_psych_markers") or [],
            selected_energy_sources=data.get("selected_energy_sources") or [],
            selected_career_priorities=data.get("selected_career_priorities") or [],
            user_segment=str(data.get("user_segment") or ""),
            user_segment_label=str(data.get("user_segment_label") or ""),
            language=lang,
        )
    except Exception as exc:
        await _track_event(message, state, "report_failed", meta={"mode": "rebuild", "error": type(exc).__name__})
        raise
    chunks = report_chunks(report, lang)
    await state.update_data(final_report=report, report_chunks=chunks, final_report_generated=True)
    await message.answer(t(lang, "route_rebuild_result_intro"), reply_markup=route_choice_keyboard())
    await _present_route_selection(message, state, lang, report)


@router.message(CareerFlow.WAITING_ROUTE_CHANGES, F.text)
async def handle_route_changes_text(message: Message, state: FSMContext) -> None:
    await process_route_changes_input(message, state, message.text or "")


@router.message(CareerFlow.CV_REVIEW_WAITING_FILE, F.text)
async def handle_cv_review_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    resume_text = (message.text or "").strip()
    if resume_text in ALL_RESUME_SKIP:
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return
    if len(resume_text) < 60:
        await message.answer(t(lang, "resume_missing_payload"), reply_markup=resume_wait_keyboard())
        return

    resume_analysis = await ai_client.analyze_resume(resume_text, lang)
    await state.update_data(resume_analysis=resume_analysis, cv_uploaded=True)
    report = data.get("final_report") or {}
    review_text = format_cv_route_review(resume_analysis, report, lang)
    await state.set_state(CareerFlow.CV_REVIEW_READY)
    await message.answer(t(lang, "cv_review_title"))
    await message.answer(review_text, reply_markup=cv_review_actions_keyboard())


@router.message(CareerFlow.CV_REVIEW_WAITING_FILE, F.document)
async def handle_cv_review_doc(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    document = message.document
    if not document:
        await message.answer(t(lang, "resume_missing_payload"), reply_markup=resume_wait_keyboard())
        return

    try:
        raw_bytes = await _download_document_bytes(message, document)
        resume_text = _decode_resume_bytes(raw_bytes, document.file_name or "")
    except Exception:
        resume_text = ""

    if not resume_text:
        await message.answer(t(lang, "resume_doc_read_error"), reply_markup=resume_wait_keyboard())
        return

    if len(resume_text) < 60:
        await message.answer(t(lang, "resume_missing_payload"), reply_markup=resume_wait_keyboard())
        return

    resume_analysis = await ai_client.analyze_resume(resume_text, lang)
    await state.update_data(resume_analysis=resume_analysis, cv_uploaded=True)
    report = data.get("final_report") or {}
    review_text = format_cv_route_review(resume_analysis, report, lang)
    await state.set_state(CareerFlow.CV_REVIEW_READY)
    await message.answer(t(lang, "cv_review_title"))
    await message.answer(review_text, reply_markup=cv_review_actions_keyboard())


@router.message(CareerFlow.CV_REVIEW_READY, F.text.in_(ALL_CV_REVIEW_ACTIONS))
async def handle_cv_review_actions(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    action = (message.text or "").strip()
    if action == CV_REVIEW_BULLETS:
        await message.answer(t(lang, "cv_review_bullets_reply"), reply_markup=cv_review_actions_keyboard())
        return
    if action == CV_REVIEW_LETTER:
        await message.answer(t(lang, "cv_review_letter_reply"), reply_markup=cv_review_actions_keyboard())
        return
    if action == CV_REVIEW_BACK:
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return
    await message.answer(t(lang, "cv_review_next"), reply_markup=cv_review_actions_keyboard())


@router.message(CareerFlow.CV_REVIEW_READY, F.text)
async def handle_cv_review_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "cv_review_next"), reply_markup=cv_review_actions_keyboard())


@router.message(CareerFlow.SUPPORT_OFFER, F.text.in_(ALL_SUPPORT_MODE_ACTIONS))
async def handle_support_offer_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    report = data.get("final_report") or {}
    chunks = data.get("report_chunks") or report_chunks(report, lang)
    action = (message.text or "").strip()
    if action == RESULT_MY_MAP:
        await _track_event(message, state, "support_map_opened", action=action)
        await message.answer(t(lang, "support_map_reply"), reply_markup=support_mode_keyboard())
        await message.answer(chunks.get("month_roadmap", "-"), reply_markup=support_mode_keyboard())
        await message.answer(chunks.get("week", "-"), reply_markup=support_mode_keyboard())
        return
    if action == RESULT_TODAY_STEP:
        await _track_event(message, state, "today_step_opened", action=action)
        await message.answer(t(lang, "support_first_step_reply"), reply_markup=support_mode_keyboard())
        await message.answer(chunks.get("today", "-"), reply_markup=support_mode_keyboard())
        return
    if action == SUPPORT_BACK_TO_MAP:
        await _track_event(message, state, "support_back_to_map", action=action)
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return
    await message.answer(t(lang, "support_mode_fallback"), reply_markup=support_mode_keyboard())


@router.message(CareerFlow.THINKING_REMINDER, F.text)
async def handle_thinking_reminder(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    text = (message.text or "").strip()
    if text == "🔔 Да, напомнить через 2 дня":
        due_at = _schedule_reminder(message.bot, message.chat.id, lang)
        await state.update_data(reminder_due_at=due_at)
        await _track_event(message, state, "reminder_scheduled", action=text, meta={"due_at": due_at})
        await message.answer(t(lang, "thinking_saved"), reply_markup=result_actions_keyboard())
        await state.set_state(CareerFlow.FINAL_READY)
        return
    if text in {"Нет, я сам/сама вернусь", "↩️ Назад к карте"}:
        _cancel_reminder(message.chat.id)
        await state.update_data(reminder_due_at="")
        await _track_event(message, state, "reminder_declined", action=text)
        await state.set_state(CareerFlow.FINAL_READY)
        await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())
        return
    await message.answer(t(lang, "offer_think_reply"), reply_markup=think_reminder_keyboard())


@router.message(CareerFlow.waiting_for_story, F.photo | F.sticker)
@router.message(CareerFlow.waiting_for_resume_decision, F.photo | F.sticker)
@router.message(CareerFlow.waiting_for_resume, F.photo | F.sticker)
@router.message(CareerFlow.waiting_for_barriers, F.photo | F.sticker)
@router.message(CareerFlow.waiting_for_answers, F.photo | F.sticker)
@router.message(CareerFlow.waiting_for_post_result_action, F.photo | F.sticker)
@router.message(CareerFlow.SHOWING_DETAILS, F.photo | F.sticker)
@router.message(CareerFlow.STEP_TRACKING, F.photo | F.sticker)
@router.message(CareerFlow.STEP_BARRIER_INPUT, F.photo | F.sticker)
@router.message(CareerFlow.REPORT_CLARIFICATION, F.photo | F.sticker)
@router.message(CareerFlow.SUPPORT_OFFER, F.photo | F.sticker)
@router.message(CareerFlow.CV_REVIEW_WAITING_FILE, F.photo | F.sticker)
@router.message(CareerFlow.CV_REVIEW_READY, F.photo | F.sticker)
async def handle_media_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    if await state.get_state() == CareerFlow.waiting_for_resume.state:
        await message.answer(t(lang, "resume_missing_payload"), reply_markup=resume_wait_keyboard())
        return
    await message.answer(t(lang, "input_media_fallback"))


@router.message(CareerFlow.waiting_for_resume_decision, F.text)
async def resume_decision_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "resume_offer"), reply_markup=resume_choice_keyboard())


@router.message(CareerFlow.waiting_for_resume, F.voice)
@router.message(CareerFlow.waiting_for_barriers, F.voice)
@router.message(CareerFlow.waiting_for_post_result_action, F.voice)
@router.message(CareerFlow.SHOWING_DETAILS, F.voice)
@router.message(CareerFlow.STEP_BARRIER_INPUT, F.voice)
@router.message(CareerFlow.SUPPORT_OFFER, F.voice)
@router.message(CareerFlow.CV_REVIEW_WAITING_FILE, F.voice)
@router.message(CareerFlow.CV_REVIEW_READY, F.voice)
async def non_voice_step_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    if await state.get_state() == CareerFlow.waiting_for_resume.state:
        await message.answer(t(lang, "resume_missing_payload"), reply_markup=resume_wait_keyboard())
        return
    if await state.get_state() == CareerFlow.SUPPORT_OFFER.state:
        await message.answer(t(lang, "support_mode_fallback"), reply_markup=support_mode_keyboard())
        return
    await message.answer(t(lang, "input_media_fallback"))


@router.message(CareerFlow.STEP_TRACKING, F.voice)
async def handle_step_tracking_voice(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    if not message.voice:
        await message.answer(t(lang, "step_tracking_intro"), reply_markup=step_tracking_keyboard())
        return
    await message.answer("Расшифровываю результат шага…", reply_markup=ReplyKeyboardRemove())
    temp_path = await _download_bot_file(message, message.voice.file_id, suffix=".ogg")
    try:
        transcript = (await ai_client.transcribe_voice(temp_path)).strip()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    if not transcript:
        await message.answer("Не удалось разобрать запись. Пришлите результат текстом.", reply_markup=step_tracking_keyboard())
        return
    await _process_step_submission(message, state, transcript)


@router.message(CareerFlow.SUPPORT_OFFER, F.text)
async def support_offer_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "support_mode_fallback"), reply_markup=support_mode_keyboard())


@router.message(CareerFlow.SHOWING_DETAILS, F.text)
async def self_exploration_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "self_exploration_intro"), reply_markup=self_exploration_keyboard())


@router.message(CareerFlow.STEP_TRACKING, F.text)
async def step_tracking_fallback(message: Message, state: FSMContext) -> None:
    await _process_step_submission(message, state, str(message.text or "").strip())


async def _process_step_submission(message: Message, state: FSMContext, user_result: str) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    steps = data.get("execution_steps") or []
    current_day = int(data.get("current_execution_day", 0))
    if not steps:
        await message.answer(t(lang, "step_tracking_finished"), reply_markup=result_actions_keyboard())
        return

    current_day = max(0, min(current_day, len(steps) - 1))
    current_step = steps[current_day]
    report = data.get("final_report") if isinstance(data.get("final_report"), dict) else {}
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    layers = report.get("decision_layers") if isinstance(report.get("decision_layers"), dict) else {}
    constraints = [str(item) for item in layers.get("constraints", []) if str(item).strip()]
    previous_results = data.get("execution_result_history") if isinstance(data.get("execution_result_history"), list) else []
    await message.answer("Разбираю результат шага и сверяю его с выбранным маршрутом…", reply_markup=ReplyKeyboardRemove())
    review = await ai_client.analyze_execution_result(
        selected_route=str(decision.get("recommended_main_path") or "не уточнён"),
        constraints=constraints,
        current_step=current_step,
        user_result=user_result,
        previous_results=previous_results,
        language=lang,
    )

    confirmed = [str(item).strip() for item in review.get("confirmed_facts", []) if str(item).strip()]
    facts = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
    explicit = [str(item).strip() for item in facts.get("explicit_facts", []) if str(item).strip()]
    facts["explicit_facts"] = list(dict.fromkeys(explicit + confirmed))
    report["facts_only"] = facts
    history_item = {
        "step": str(current_step.get("task") or ""),
        "user_result": user_result,
        "result_summary": str(review.get("result_summary") or ""),
        "confirmed_facts": confirmed,
        "hypothesis_update": str(review.get("hypothesis_update") or ""),
    }
    previous_results.append(history_item)

    next_step = str(review.get("next_step") or "").strip()
    if next_step:
        generated_step = {
            "day": str(current_day + 2),
            "focus": "Следующий шаг по новым данным",
            "task": next_step,
            "time": "15-30 минут",
            "result": str(review.get("next_step_result") or "Пришлите результат в чат."),
            "why": str(review.get("hypothesis_update") or "Проверяем маршрут на новых фактах."),
        }
        steps = steps[: current_day + 1] + [generated_step] + steps[current_day + 1 :]

    progress = data.get("execution_progress") if isinstance(data.get("execution_progress"), dict) else {}
    progress[str(current_step.get("day") or current_day + 1)] = {"status": "результат разобран", "result": user_result[:1000]}
    next_day = min(current_day + 1, len(steps) - 1)
    escalation = bool(review.get("human_escalation_recommended"))
    response = str(review.get("response") or review.get("result_summary") or "Результат сохранён.").strip()
    if escalation:
        reason = str(review.get("human_escalation_reason") or "Здесь полезна персональная рабочая сессия.").strip()
        response += f"\n\nМягкая эскалация: {reason}\nЭто не блокирует самостоятельное продолжение плана в чате."
    await state.update_data(
        final_report=report,
        execution_steps=steps,
        execution_progress=progress,
        execution_result_history=previous_results[-20:],
        current_execution_day=next_day,
        execution_hypothesis_update=str(review.get("hypothesis_update") or ""),
    )
    await _track_event(message, state, "execution_result_analyzed", meta={"escalation": escalation, "confirmed_facts_count": len(confirmed)})
    await message.answer(response, reply_markup=step_tracking_keyboard())
    if next_step:
        await message.answer(_execution_step_text(steps[next_day], progress), reply_markup=step_tracking_keyboard())


@router.message(CareerFlow.REPORT_CLARIFICATION, F.text | F.document)
async def report_clarification_fallback(message: Message, state: FSMContext) -> None:
    if message.text:
        return
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "report_clarify_prompt"), reply_markup=input_method_keyboard())
