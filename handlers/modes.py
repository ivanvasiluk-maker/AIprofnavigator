from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards import (
    COUNCIL_BACK,
    ALL_COUNCIL_BACK,
    COUNCIL_LABEL_TO_MODE,
    LANG_BE,
    LANG_RU,
    MODE_BUTTON_TO_KEY,
    MODE_KEY_DIOGENES,
    ALL_FINAL_NEW,
    ALL_FINAL_COUNCIL,
    ALL_FINAL_REPHRASE,
    ALL_FINAL_SMASH,
    ALL_FINAL_DIOGENES_STAMP,
    ALL_FINAL_CHOOSE,
    ALL_FINAL_END,
    ALL_TONES,
    council_keyboard,
    final_keyboard,
    mode_keyboard,
    tone_keyboard,
)
from openai_client import ai_client
from localization import t
from states import ClarityFlow
from handlers.thought import format_diogenes

router = Router()


def _user_language(data: dict) -> str:
    return data.get("language") or data.get("lang", LANG_RU)


def _short_blocks(*blocks: str) -> str:
    cleaned = [block.strip() for block in blocks if block and block.strip()]
    return "\n\n".join(cleaned[:4])


def _clip(text: str, limit: int) -> str:
    clean = (text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"

MODE_PROMPTS = {
    "parmenid": (
        "🧭 NextYou\n\nФакт или вывод?"
    ),
    "aristotle": (
        "⚙️ Аристотель\n\nЧто мешает старту?"
    ),
    "aurelius": (
        "🛡️ Марк Аврелий\n\nВласть или нет?"
    ),
    "diogenes": (
        "🛢️ Диоген\n\nДрама? Срежем пафос."
    ),
}


def _mode_prompt(mode_key: str) -> str:
    return MODE_PROMPTS.get(mode_key, "Режим.")


MODE_PROMPTS_BY_LANG = {
    LANG_RU: MODE_PROMPTS,
    LANG_BE: {
        "parmenid": (
            "🧭 NextYou\n\nФакт ці выснова?"
        ),
        "aristotle": (
            "⚙️ Арыстоцель\n\nШто замінае старту?"
        ),
        "aurelius": (
            "🛡️ Марк Аўрэлій\n\nУлада ці не?"
        ),
        "diogenes": (
            "🛢️ Дыяген\n\nДрама? Зрэжам пафас."
        ),
    },
}


def _mode_prompt_by_lang(mode_key: str, lang: str) -> str:
    prompts = MODE_PROMPTS_BY_LANG.get(lang, MODE_PROMPTS_BY_LANG[LANG_RU])
    fallback = "Рэжым." if lang == LANG_BE else "Режим."
    return prompts.get(mode_key, fallback)


def _render_council_comment(data: dict, lang: str = "ru") -> str:
    title = (data.get("sage_title") or t(lang, "council_sage_title_default")).strip()
    comment = (data.get("comment") or "").strip()
    one_line = (data.get("one_line") or "").strip()
    rendered = _short_blocks(title, comment, f"{t(lang, 'council_one_line_label')}\n{one_line}" if one_line else "")
    return _clip(rendered, 300)


@router.message(ClarityFlow.choosing_mode, F.text.in_(list(MODE_BUTTON_TO_KEY.keys())))
@router.message(ClarityFlow.waiting_for_input, F.text.in_(list(MODE_BUTTON_TO_KEY.keys())))
@router.message(ClarityFlow.waiting_for_clarification, F.text.in_(list(MODE_BUTTON_TO_KEY.keys())))
@router.message(ClarityFlow.confirming_transcription, F.text.in_(list(MODE_BUTTON_TO_KEY.keys())))
@router.message(ClarityFlow.waiting_for_council_choice, F.text.in_(list(MODE_BUTTON_TO_KEY.keys())))
@router.message(ClarityFlow.waiting_for_tone_choice, F.text.in_(list(MODE_BUTTON_TO_KEY.keys())))
async def choose_mode(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    mode_key = MODE_BUTTON_TO_KEY[message.text]
    await state.update_data(
        mode=mode_key,
        current_mode=mode_key,
        last_mode=mode_key,
        user_text="",
        last_user_text="",
        transcribed_text="",
        last_result={},
        last_rendered_text="",
        last_main_rendered_text="",
    )
    await state.set_state(ClarityFlow.waiting_for_input)
    await message.answer(_mode_prompt_by_lang(mode_key, lang), reply_markup=mode_keyboard(lang))


@router.message(ClarityFlow.waiting_for_input, F.text.in_(ALL_FINAL_NEW))
async def new_analysis(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    mode = data.get("mode")
    if not mode:
        await state.set_state(ClarityFlow.choosing_mode)
        await message.answer(t(lang, "choose_mode"), reply_markup=mode_keyboard(lang))
        return

    await state.update_data(
        current_mode=mode,
        last_mode=mode,
        user_text="",
        last_user_text="",
        transcribed_text="",
        last_result={},
        last_rendered_text="",
        last_main_rendered_text="",
    )
    await state.set_state(ClarityFlow.waiting_for_input)
    await message.answer(_mode_prompt_by_lang(mode, lang), reply_markup=mode_keyboard(lang))


@router.message(ClarityFlow.waiting_for_input, F.text.in_(ALL_FINAL_CHOOSE))
async def choose_other_mode(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    await state.clear()
    await state.update_data(language=lang, lang=lang)
    await state.set_state(ClarityFlow.choosing_mode)
    await message.answer(t(lang, "choose_mode"), reply_markup=mode_keyboard(lang))


@router.message(ClarityFlow.waiting_for_input, F.text.in_(ALL_FINAL_END))
async def finish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    await state.clear()
    await message.answer(t(lang, "tavern_closed"))


@router.message(ClarityFlow.waiting_for_input, F.text.in_(ALL_FINAL_COUNCIL))
async def open_council(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    current_mode = data.get("current_mode") or data.get("mode")
    if not current_mode:
        await state.set_state(ClarityFlow.choosing_mode)
        await message.answer(t(lang, "need_mode_first"), reply_markup=mode_keyboard(lang))
        return
    await state.set_state(ClarityFlow.waiting_for_council_choice)
    await message.answer(t(lang, "council_prompt"), reply_markup=council_keyboard(current_mode, lang))



@router.message(ClarityFlow.waiting_for_council_choice, F.text.in_(ALL_COUNCIL_BACK))
async def council_back(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await state.set_state(ClarityFlow.waiting_for_input)
    await message.answer(t(lang, "council_back_msg"), reply_markup=final_keyboard(lang))


@router.message(ClarityFlow.waiting_for_council_choice, F.text.in_(list(COUNCIL_LABEL_TO_MODE.keys())))
async def choose_council_mode(message: Message, state: FSMContext) -> None:
    selected_mode = COUNCIL_LABEL_TO_MODE.get(message.text)
    if not selected_mode:
        data0 = await state.get_data()
        await message.answer(t(_user_language(data0), "council_sage_fallback"))
        return

    data = await state.get_data()
    lang = _user_language(data)
    original_text = (data.get("user_text") or "").strip()
    previous_result = data.get("last_result") or {}
    if not original_text:
        await state.set_state(ClarityFlow.waiting_for_input)
        await message.answer(t(lang, "council_no_analysis"), reply_markup=final_keyboard(lang))
        return

    council = await ai_client.run_council_comment(selected_mode, original_text, previous_result, lang)
    rendered = _render_council_comment(council, lang)
    await state.update_data(
        last_council_mode=selected_mode,
        last_council_result=council,
        last_council_rendered_text=rendered,
        last_rendered_text=rendered,
    )
    await state.set_state(ClarityFlow.waiting_for_input)
    await message.answer(rendered, reply_markup=final_keyboard(lang))


@router.message(ClarityFlow.waiting_for_input, F.text.in_(ALL_FINAL_REPHRASE))
async def choose_tone(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    if not data.get("last_result"):
        await message.answer(t(lang, "tone_no_analysis"), reply_markup=final_keyboard(lang))
        return
    await state.set_state(ClarityFlow.waiting_for_tone_choice)
    await message.answer(t(lang, "tone_prompt"), reply_markup=tone_keyboard(lang))


@router.message(ClarityFlow.waiting_for_tone_choice, F.text.in_(ALL_TONES))
async def apply_tone(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    tone = message.text or ""
    result = data.get("last_result") or {}
    rendered_text = (data.get("last_main_rendered_text") or data.get("last_rendered_text") or "").strip()
    rewritten = await ai_client.rewrite_tone(tone, result, rendered_text, lang)

    title = (rewritten.get("title") or t(lang, "tone_default_title")).strip()
    text = (rewritten.get("text") or rendered_text).strip()
    dry_summary = (rewritten.get("dry_summary") or "").strip()

    response = f"{title}\n\n{text}".strip()
    if dry_summary:
        response = f"{response}\n\n{t(lang, 'dry_summary_label')}\n{dry_summary}"
    response = _short_blocks(*response.split("\n\n"))
    response = _clip(response, 300)

    await state.update_data(last_rendered_text=response)
    await state.set_state(ClarityFlow.waiting_for_input)
    await message.answer(response, reply_markup=final_keyboard(lang))


@router.message(ClarityFlow.waiting_for_input, F.text.in_(ALL_FINAL_SMASH))
async def smash_thought(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    user_text = (data.get("last_user_text") or data.get("user_text") or "").strip()
    if not user_text:
        await state.update_data(mode=MODE_KEY_DIOGENES, current_mode=MODE_KEY_DIOGENES, last_mode=MODE_KEY_DIOGENES)
        await state.set_state(ClarityFlow.waiting_for_input)
        await message.answer(t(lang, "smash_need_drama"), reply_markup=final_keyboard(lang))
        return

    result = await ai_client.run_diogenes_mode(user_text, context_block="", pattern_block="", language=lang)
    rendered = format_diogenes(result, lang)
    await state.update_data(
        mode=MODE_KEY_DIOGENES,
        current_mode=MODE_KEY_DIOGENES,
        last_mode=MODE_KEY_DIOGENES,
        last_user_text=user_text,
        last_result=result,
        last_rendered_text=rendered,
        last_main_rendered_text=rendered,
    )
    await state.set_state(ClarityFlow.waiting_for_input)
    await message.answer(rendered, reply_markup=final_keyboard(lang))


@router.message(ClarityFlow.waiting_for_input, F.text.in_(ALL_FINAL_DIOGENES_STAMP))
async def diogenes_stamp(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    last_user_text = (
        data.get("last_user_text")
        or data.get("user_text")
        or ""
    ).strip()
    last_result = data.get("last_result") or {}

    if not last_user_text and not last_result:
        await message.answer(t(lang, "stamp_no_text"), reply_markup=final_keyboard(lang))
        return

    stamp_data = await ai_client.run_diogenes_stamp(last_user_text, last_result, lang)
    stamp = " ".join((stamp_data.get("stamp") or "").replace("\n", " ").split())
    if not stamp:
        stamp = t(lang, "stamp_fallback")
    stamp = _clip(stamp, 180)

    await state.update_data(last_rendered_text=stamp)
    await state.set_state(ClarityFlow.waiting_for_input)
    await message.answer(stamp, reply_markup=final_keyboard(lang))


@router.message(ClarityFlow.waiting_for_council_choice, F.text)
async def council_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "council_fallback"))


@router.message(ClarityFlow.waiting_for_tone_choice, F.text)
async def tone_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "tone_fallback"), reply_markup=tone_keyboard(lang))


@router.message(ClarityFlow.choosing_mode, F.voice)
async def choosing_mode_voice(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "choosing_mode_voice"), reply_markup=mode_keyboard(lang))


@router.message(ClarityFlow.choosing_mode, F.text)
async def choosing_mode_text_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "choosing_mode_text"), reply_markup=mode_keyboard(lang))


@router.message(ClarityFlow.choosing_mode, F.photo | F.sticker)
async def choosing_mode_media_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "choosing_mode_media"), reply_markup=mode_keyboard(lang))
