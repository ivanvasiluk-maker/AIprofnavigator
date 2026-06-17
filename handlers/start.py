from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards import (
    ALL_PACE_OPTIONS,
    ALL_VOICE_PACE_OPTIONS,
    INPUT_DONT_KNOW,
    LANG_RU,
    PACE_FAST,
    PACE_NORMAL,
    PACE_SUPPORT,
    PACE_VOICE,
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

router = Router()


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
        "support": {
            "user_mode": "support",
            "max_questions": 8,
            "support_level": "high",
            "explanation_level": "gentle",
            "plan_depth": "today_3days_week",
            "psychological_block_depth": "expanded",
            "task_size": "micro",
            "preferred_input": preferred_input,
            "support_need": "high",
            "pace": "slow",
            "detail_preference": "balanced",
        },
    }
    return mapping.get(mode_key, mapping["calm_steps"])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(
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
        mode_settings = _apply_mode_settings("support")
        profile.update({"pace": "slow", "support_need": "high", "detail_preference": "balanced", "emotional_tone": "anxious", "preferred_input": "text"})
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
        mode_settings = _apply_mode_settings("support", preferred_input="voice")
        key = "pace_selected_support"
        profile.update({"pace": "slow", "support_need": "high", "detail_preference": "balanced", "emotional_tone": "anxious"})
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
