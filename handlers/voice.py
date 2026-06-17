import os
import tempfile

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards import (
    CONFIRM_EDIT,
    CONFIRM_RETRY,
    CONFIRM_YES,
    ALL_CONFIRM_YES,
    ALL_CONFIRM_EDIT,
    ALL_CONFIRM_RETRY,
    confirm_transcription_keyboard,
)
from localization import t
from openai_client import ai_client
from states import CareerFlow
from handlers.career import process_answers_input, process_route_changes_input, process_story_input

router = Router()


def _user_language(data: dict) -> str:
    return data.get("language") or data.get("lang", "ru")


@router.message(CareerFlow.waiting_for_story, F.voice)
@router.message(CareerFlow.waiting_for_answers, F.voice)
@router.message(CareerFlow.WAITING_ROUTE_CHANGES, F.voice)
async def handle_voice(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state == CareerFlow.waiting_for_answers.state:
        voice_target = "answers"
    elif current_state == CareerFlow.WAITING_ROUTE_CHANGES.state:
        voice_target = "route_changes"
    else:
        voice_target = "story"
    lang = _user_language(await state.get_data())

    voice = message.voice
    if not voice:
        await message.answer(t(lang, "voice_read_error"))
        return

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
    tmp_path = tmp_file.name
    tmp_file.close()

    try:
        file_info = await message.bot.get_file(voice.file_id)
        await message.bot.download(file_info, destination=tmp_path)
        transcribed_text = await ai_client.transcribe_voice(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not transcribed_text:
        await message.answer(t(lang, "voice_recognition_error"))
        return

    await state.update_data(transcribed_text=transcribed_text, voice_target=voice_target)
    await state.set_state(CareerFlow.confirming_transcription)
    await message.answer(
        t(lang, "voice_confirmation", text=transcribed_text),
        reply_markup=confirm_transcription_keyboard(lang),
    )


@router.message(CareerFlow.confirming_transcription, F.text.in_(ALL_CONFIRM_YES))
async def confirm_transcription_yes(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    transcribed_text = (data.get("transcribed_text") or "").strip()
    voice_target = data.get("voice_target", "story")
    if not transcribed_text:
        await state.set_state(CareerFlow.waiting_for_story)
        await message.answer(t(lang, "voice_text_not_found"))
        return

    await state.update_data(
        transcribed_text="",
        voice_target="story",
    )

    if voice_target == "answers":
        await state.set_state(CareerFlow.waiting_for_answers)
        await process_answers_input(message, state, transcribed_text)
        return

    if voice_target == "route_changes":
        await state.set_state(CareerFlow.WAITING_ROUTE_CHANGES)
        await process_route_changes_input(message, state, transcribed_text)
        return

    await process_story_input(message, state, transcribed_text)


@router.message(CareerFlow.confirming_transcription, F.text.in_(ALL_CONFIRM_EDIT))
async def confirm_transcription_edit(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    voice_target = data.get("voice_target", "story")
    if voice_target == "answers":
        await state.set_state(CareerFlow.waiting_for_answers)
    elif voice_target == "route_changes":
        await state.set_state(CareerFlow.WAITING_ROUTE_CHANGES)
    else:
        await state.set_state(CareerFlow.waiting_for_story)
    await message.answer(t(lang, "voice_edit_prompt"))


@router.message(CareerFlow.confirming_transcription, F.text.in_(ALL_CONFIRM_RETRY))
async def confirm_transcription_retry(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    voice_target = data.get("voice_target", "story")
    if voice_target == "answers":
        await state.set_state(CareerFlow.waiting_for_answers)
    elif voice_target == "route_changes":
        await state.set_state(CareerFlow.WAITING_ROUTE_CHANGES)
    else:
        await state.set_state(CareerFlow.waiting_for_story)
    await message.answer(t(lang, "voice_retry_prompt"))


@router.message(CareerFlow.confirming_transcription, F.text)
async def confirm_transcription_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "voice_confirm_fallback"))


@router.message(CareerFlow.confirming_transcription, F.photo | F.sticker)
async def confirm_transcription_media_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "voice_confirm_media_fallback"))
