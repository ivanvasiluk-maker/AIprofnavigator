from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
import uuid

from keyboards import (
    ALL_PACE_OPTIONS,
    ALL_VOICE_PACE_OPTIONS,
    INPUT_DONT_KNOW,
    LANG_RU,
    PACE_FAST,
    PACE_NORMAL,
    PACE_SUPPORT,
    PACE_VOICE,
    result_actions_keyboard,
    VOICE_PACE_FAST,
    VOICE_PACE_NORMAL,
    VOICE_PACE_SUPPORT,
    input_method_keyboard,
    pace_keyboard,
    short_story_keyboard,
    voice_pace_keyboard,
)
from localization import t
from states import CareerFlow
from utils.analytics import ensure_public_user_id, log_behavior_event
from utils.persistence import create_session, load_recovery_bundle, save_profile_version

router = Router()


def _is_final_like_state(state_name: str) -> bool:
    low = str(state_name or "").strip().lower()
    return any(token in low for token in ["final_ready", "pdf_ready", "showing_details", "route_selection", "step_tracking"])


def _recover_target_state(state_name: str):
    raw = str(state_name or "").strip().lower()
    if "selecting_pace" in raw:
        return CareerFlow.SELECTING_PACE
    if "confirming_story" in raw:
        return CareerFlow.CONFIRMING_STORY
    if "waiting_cv" in raw or "waiting_for_resume" in raw:
        return CareerFlow.WAITING_CV
    if "interview" in raw or "waiting_for_answers" in raw:
        return CareerFlow.INTERVIEW
    if "route_selection" in raw:
        return CareerFlow.ROUTE_SELECTION
    if "final_ready" in raw or "pdf_ready" in raw:
        return CareerFlow.FINAL_READY
    if "waiting_story" in raw:
        return CareerFlow.waiting_for_story
    return CareerFlow.waiting_for_story


def _extract_start_source(message_text: str) -> str:
    raw = (message_text or "").strip()
    if not raw:
        return ""
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    source = parts[1].strip()
    # Keep only compact source tags for analytics/deep links.
    return source[:120]


def _apply_mode_settings(mode_key: str, preferred_input: str = "text") -> dict:
    mapping = {
        "fast": {
            "user_mode": "fast",
            "max_questions": 5,
            "support_level": "low",
            "explanation_level": "short",
            "plan_depth": "today_3days_week",
            "psychological_block_depth": "optional",
            "task_size": "practical",
            "preferred_input": preferred_input,
            "support_need": "low",
            "pace": "fast",
            "detail_preference": "brief",
        },
        "calm_steps": {
            "user_mode": "calm_steps",
            "max_questions": 10,
            "support_level": "medium",
            "explanation_level": "medium",
            "plan_depth": "today_week_month",
            "psychological_block_depth": "standard",
            "task_size": "normal",
            "preferred_input": preferred_input,
            "support_need": "medium",
            "pace": "normal",
            "detail_preference": "balanced",
        },
        "deep_route": {
            "user_mode": "deep_route",
            "max_questions": 15,
            "support_level": "medium",
            "explanation_level": "detailed",
            "plan_depth": "today_week_month_deep",
            "psychological_block_depth": "expanded",
            "task_size": "normal",
            "preferred_input": preferred_input,
            "support_need": "medium",
            "pace": "normal",
            "detail_preference": "detailed",
        },
    }
    return mapping.get(mode_key, mapping["calm_steps"])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    source_tag = _extract_start_source(message.text or "")
    public_user_id = ensure_public_user_id(
        message.from_user.id if message.from_user else message.chat.id,
        source_tag=source_tag,
    )
    session_id = str(uuid.uuid4())
    await state.update_data(
        public_user_id=public_user_id,
        session_id=session_id,
        source_tag=source_tag,
        language=LANG_RU,
        lang=LANG_RU,
        interaction_profile={},
        user_mode="calm_steps",
        max_questions=10,
        support_level="medium",
        explanation_level="medium",
        plan_depth="today_week_month",
        psychological_block_depth="standard",
        task_size="normal",
        support_need="medium",
        pace="normal",
        detail_preference="balanced",
        preferred_input="unknown",
    )
    create_session(
        session_id,
        public_user_id,
        source_tag=source_tag,
        language=LANG_RU,
        user_mode="calm_steps",
        state_name="SELECTING_PACE",
    )
    save_profile_version(
        public_user_id,
        "session_started",
        {
            "language": LANG_RU,
            "user_mode": "calm_steps",
            "max_questions": 10,
            "support_level": "medium",
            "pace": "normal",
            "detail_preference": "balanced",
            "source_tag": source_tag,
        },
        session_id=session_id,
    )
    await log_behavior_event(
        public_user_id=public_user_id,
        event="session_started",
        state_name="SELECTING_PACE",
        language=LANG_RU,
        meta={"source_tag": source_tag} if source_tag else {},
        session_id=session_id,
    )
    await state.set_state(CareerFlow.SELECTING_PACE)
    await message.answer(t(LANG_RU, "start_intro"))
    await message.answer(t(LANG_RU, "pace_prompt"), reply_markup=pace_keyboard())


@router.message(CareerFlow.SELECTING_PACE, F.text.in_(ALL_PACE_OPTIONS))
async def choose_pace(message: Message, state: FSMContext) -> None:
    choice = (message.text or "").strip()
    profile = {
        "answer_length": "medium",
        "emotional_tone": "unknown",
        "structure_level": "structured",
        "support_need": "medium",
        "pace": "normal",
        "preferred_input": "text",
        "detail_preference": "balanced",
        "agency_level": "medium",
    }

    if choice == PACE_FAST:
        mode_settings = _apply_mode_settings("fast")
        profile.update({"pace": "fast", "support_need": "low", "detail_preference": "brief", "preferred_input": "text"})
        key = "pace_selected_fast"
    elif choice == PACE_NORMAL:
        mode_settings = _apply_mode_settings("calm_steps")
        profile.update({"pace": "normal", "support_need": "medium", "detail_preference": "balanced", "preferred_input": "text"})
        key = "pace_selected_normal"
    elif choice == PACE_SUPPORT:
        mode_settings = _apply_mode_settings("deep_route")
        profile.update({"pace": "normal", "support_need": "medium", "detail_preference": "detailed", "preferred_input": "text"})
        key = "pace_selected_support"
    else:
        await state.update_data(preferred_input="voice")
        await state.set_state(CareerFlow.SELECTING_VOICE_PACE)
        await message.answer(t(LANG_RU, "pace_selected_voice"))
        await message.answer(t(LANG_RU, "voice_mode_tempo_prompt"), reply_markup=voice_pace_keyboard())
        return

    await state.update_data(
        interaction_profile=profile,
        user_mode=mode_settings["user_mode"],
        max_questions=mode_settings["max_questions"],
        support_level=mode_settings["support_level"],
        explanation_level=mode_settings["explanation_level"],
        plan_depth=mode_settings["plan_depth"],
        psychological_block_depth=mode_settings["psychological_block_depth"],
        task_size=mode_settings["task_size"],
        support_need=profile["support_need"],
        pace=profile["pace"],
        detail_preference=profile["detail_preference"],
        preferred_input=profile["preferred_input"],
    )
    data = await state.get_data()
    public_user_id = str(data.get("public_user_id") or ensure_public_user_id(message.from_user.id if message.from_user else message.chat.id))
    await log_behavior_event(
        public_user_id=public_user_id,
        event="pace_selected",
        state_name="WAITING_STORY",
        action=choice,
        user_mode=str(mode_settings["user_mode"]),
        language=LANG_RU,
        session_id=str(data.get("session_id") or "").strip(),
    )
    await state.set_state(CareerFlow.waiting_for_story)
    await message.answer(t(LANG_RU, key))
    await message.answer(t(LANG_RU, "contract_anchor"), reply_markup=input_method_keyboard())


@router.message(CareerFlow.SELECTING_PACE, F.text)
async def choose_pace_fallback(message: Message) -> None:
    await message.answer(t(LANG_RU, "pace_prompt"), reply_markup=pace_keyboard())


@router.message(CareerFlow.SELECTING_VOICE_PACE, F.text.in_(ALL_VOICE_PACE_OPTIONS))
async def choose_voice_pace(message: Message, state: FSMContext) -> None:
    choice = (message.text or "").strip()
    profile = {
        "answer_length": "medium",
        "emotional_tone": "unknown",
        "structure_level": "structured",
        "support_need": "medium",
        "pace": "normal",
        "preferred_input": "voice",
        "detail_preference": "balanced",
        "agency_level": "medium",
    }
    if choice == VOICE_PACE_FAST:
        mode_settings = _apply_mode_settings("fast", preferred_input="voice")
        key = "pace_selected_fast"
        profile.update({"pace": "fast", "support_need": "low", "detail_preference": "brief"})
    elif choice == VOICE_PACE_SUPPORT:
        mode_settings = _apply_mode_settings("deep_route", preferred_input="voice")
        key = "pace_selected_support"
        profile.update({"pace": "normal", "support_need": "medium", "detail_preference": "detailed"})
    else:
        mode_settings = _apply_mode_settings("calm_steps", preferred_input="voice")
        key = "pace_selected_normal"

    await state.update_data(
        interaction_profile=profile,
        user_mode=mode_settings["user_mode"],
        max_questions=mode_settings["max_questions"],
        support_level=mode_settings["support_level"],
        explanation_level=mode_settings["explanation_level"],
        plan_depth=mode_settings["plan_depth"],
        psychological_block_depth=mode_settings["psychological_block_depth"],
        task_size=mode_settings["task_size"],
        support_need=profile["support_need"],
        pace=profile["pace"],
        detail_preference=profile["detail_preference"],
        preferred_input="voice",
    )
    data = await state.get_data()
    public_user_id = str(data.get("public_user_id") or ensure_public_user_id(message.from_user.id if message.from_user else message.chat.id))
    await log_behavior_event(
        public_user_id=public_user_id,
        event="voice_pace_selected",
        state_name="WAITING_STORY",
        action=choice,
        user_mode=str(mode_settings["user_mode"]),
        language=LANG_RU,
        session_id=str(data.get("session_id") or "").strip(),
    )
    await state.set_state(CareerFlow.waiting_for_story)
    await message.answer(t(LANG_RU, key))
    await message.answer(t(LANG_RU, "contract_anchor"), reply_markup=input_method_keyboard())


@router.message(CareerFlow.SELECTING_VOICE_PACE, F.text)
async def choose_voice_pace_fallback(message: Message) -> None:
    await message.answer(t(LANG_RU, "voice_mode_tempo_prompt"), reply_markup=voice_pace_keyboard())


@router.message(CareerFlow.choosing_language, F.text)
async def choose_language_fallback(message: Message) -> None:
    await message.answer(t(LANG_RU, "start_intro"), reply_markup=input_method_keyboard())


@router.message(CareerFlow.waiting_for_story, F.text == INPUT_DONT_KNOW)
async def dont_know_start(message: Message, state: FSMContext) -> None:
    await state.update_data(answer_length="short", preferred_input="buttons", pace="slow", detail_preference="brief")
    await message.answer(t(LANG_RU, "short_story_prompt"), reply_markup=short_story_keyboard())


@router.message(StateFilter(None), F.text)
async def recover_without_fsm_state(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    public_user_id = ensure_public_user_id(message.from_user.id if message.from_user else message.chat.id)
    bundle = load_recovery_bundle(public_user_id)
    session_row = bundle.get("session") if isinstance(bundle.get("session"), dict) else {}
    profile_row = bundle.get("profile") if isinstance(bundle.get("profile"), dict) else {}
    report_row = bundle.get("report") if isinstance(bundle.get("report"), dict) else {}

    if not session_row:
        await state.set_state(CareerFlow.SELECTING_PACE)
        await message.answer(t(LANG_RU, "start_intro"))
        await message.answer(t(LANG_RU, "pace_prompt"), reply_markup=pace_keyboard())
        return

    recovered_state_name = str(session_row.get("state_name") or "")
    recovered_state = _recover_target_state(recovered_state_name)
    session_id = str(session_row.get("session_id") or "") or str(uuid.uuid4())

    profile_payload = profile_row.get("profile") if isinstance(profile_row.get("profile"), dict) else {}
    user_mode = str(profile_payload.get("user_mode") or session_row.get("user_mode") or "calm_steps")
    language = str(profile_payload.get("language") or session_row.get("language") or LANG_RU)

    await state.update_data(
        public_user_id=public_user_id,
        session_id=session_id,
        language=language,
        lang=language,
        user_mode=user_mode,
        max_questions=5 if user_mode == "fast" else (15 if user_mode == "deep_route" else 10),
        support_level=profile_payload.get("support_level", "medium"),
        support_need=profile_payload.get("support_need", "medium"),
        pace=profile_payload.get("pace", "normal"),
        detail_preference=profile_payload.get("detail_preference", "balanced"),
        interaction_profile=profile_payload if isinstance(profile_payload, dict) else {},
    )

    if _is_final_like_state(recovered_state_name) and isinstance(report_row.get("report"), dict) and report_row.get("report"):
        await state.set_state(CareerFlow.FINAL_READY)
        await state.update_data(
            final_report=report_row.get("report"),
            final_report_generated=True,
            report_generation_id=str(report_row.get("report_generation_id") or ""),
            html_report_path=str(report_row.get("html_report_path") or ""),
            pdf_report_path=str(report_row.get("pdf_report_path") or ""),
        )
        await message.answer(
            "Восстановил ваш прогресс после перезапуска. Готова последняя версия карты и следующий шаг.",
            reply_markup=result_actions_keyboard(),
        )
        return

    await state.set_state(recovered_state)
    await message.answer(
        "Восстановил ваш прогресс после перезапуска. Можно продолжить с того же места.",
        reply_markup=input_method_keyboard(),
    )
