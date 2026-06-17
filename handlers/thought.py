from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards import (
    ALL_CONFIRM_EDIT,
    ALL_CONFIRM_RETRY,
    ALL_CONFIRM_YES,
    MODE_BUTTON_TO_KEY,
    final_keyboard,
    mode_keyboard,
    safety_keyboard,
)
from localization import t
from openai_client import ai_client
from states import ClarityFlow
from utils.safety import has_crisis_content

router = Router()
MAX_MAIN_RESPONSE_LEN = 500
VOICE_CONFIRM_BUTTONS = ALL_CONFIRM_YES | ALL_CONFIRM_EDIT | ALL_CONFIRM_RETRY


def _user_language(data: dict) -> str:
    return data.get("language") or data.get("lang", "ru")


def _short_blocks(*blocks: str) -> str:
    cleaned = [block.strip() for block in blocks if block and block.strip()]
    return "\n\n".join(cleaned[:4])


def _clip(text: str, limit: int) -> str:
    clean = (text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _is_duplicate(a: str | None, b: str | None) -> bool:
    na = _norm(a or "")
    nb = _norm(b or "")
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def _pick(*values: str | None) -> str:
    for value in values:
        clean = (value or "").strip()
        if clean:
            return clean
    return ""


def _render_flow(
    mode_title: str,
    lang: str,
    fog: str,
    cut: str,
    step: str,
    final_text: str,
    final_label_key: str = "flow_verdict",
) -> str:
    blocks = [
        f"{mode_title}\n{t(lang, 'flow_fog')}: {_clip(_pick(fog, '—'), 120)}",
        f"{t(lang, 'flow_cut')}: {_clip(_pick(cut, '—'), 220)}",
        f"{t(lang, 'flow_step')}: {_clip(_pick(step, '—'), 180)}",
        f"{t(lang, final_label_key)}: {_clip(_pick(final_text, '—'), 120 if final_label_key == 'flow_stamp' else 180)}",
    ]
    return _clip(_short_blocks(*blocks), MAX_MAIN_RESPONSE_LEN)


def _short_field(label: str, value: str | None) -> str:
    text = (value or "").strip()
    return f"{label}: {text}" if text else ""


def _l(lang: str, ru: str, be: str) -> str:
    return be if lang == "be" else ru


def _normalize_for_match(text: str) -> str:
    return " ".join((text or "").lower().replace("ё", "е").split())


HIGH_AROUSAL_MARKERS = (
    # RU
    "дико напряжен",
    "дико напряженная",
    "нервный",
    "нервная",
    "меня трясет",
    "на взводе",
    "сейчас сорвусь",
    "паника",
    "бесит",
    "не могу успокоиться",
    # BE
    "дзіка напружаны",
    "напружаная",
    "нервовы",
    "нервовая",
    "мяне трасе",
    "я на узводзе",
    "зараз сарвуся",
    "паніка",
    "бесіць",
    "не магу супакоіцца",
)


def _has_high_arousal(text: str) -> bool:
    low = _normalize_for_match(text)
    if not low:
        return False
    return any(marker in low for marker in HIGH_AROUSAL_MARKERS)


def _render_high_arousal_emergency(lang: str) -> str:
    if lang == "be":
        return _clip(
            _short_blocks(
                "⚠️ Высокая напружанасць\nЦяпер цела цісне на газ.",
                "Не вырашай жыццё ў такім рэжыме.",
                "Крок (30-120 секунд):\nтэлефон экранам уніз на 2 хвіліны.\nразціснуць сківіцу.\nапусціць плечы.\nадзін доўгі выдых.",
                "📌 Штамп:\nПік шуміць, але не камандуе табой.\nПотым адно пытанне:\nшто рэальна здарылася?",
            ),
            MAX_MAIN_RESPONSE_LEN,
        )

    return _clip(
        _short_blocks(
            "⚠️ Высокое напряжение\nСейчас тело жмет газ.",
            "Не решай жизнь в таком режиме.",
            "Шаг (30-120 секунд):\nтелефон экраном вниз на 2 минуты.\nчелюсть разжать.\nплечи опустить.\nодин длинный выдох.",
            "📌 Штамп:\nПик шумный, но рулить ему нельзя.\nПотом один вопрос:\nчто реально произошло?",
        ),
        MAX_MAIN_RESPONSE_LEN,
    )


def _build_context_block(text: str, lang: str) -> str:
    if not _has_high_arousal(text):
        return ""
    if lang == "be":
        return (
            "ВЫСОКАЯ НАПРЯЖАНАСЦЬ: спачатку дай цялесны крок на 10-20 секунд. "
            "Без філасофіі і доўгіх тлумачэнняў."
        )
    return (
        "ВЫСОКОЕ НАПРЯЖЕНИЕ: сначала дай телесный шаг на 10-20 секунд. "
        "Без философии и длинных объяснений."
    )

SELF_ATTACK_WORDS = {
    # Russian
    "тупой", "тупая", "идиот", "идиотка", "слабый", "слабая", "не справлюсь",
    "не справляюсь", "не могу", "плохой", "плохая", "неудачник", "неудачница",
    "провал", "провалю", "провалился", "провалилась", "ничтожество",
    # Belarusian
    "тупы", "тупая", "ідыёт", "ідыётка", "слабы", "слабая", "не справлюся",
    "не справляюся", "не магу", "дрэнны", "дрэнная", "няўдачнік", "няўдачніца",
    "правал", "правалюся", "правалiўся", "правалілася", "нікчэмнасць",
}
AVOIDANCE_WORDS = {
    # Russian
    "откладываю", "не начинаю", "прокрастинация", "избегаю", "не могу начать",
    "откладываю на потом", "не берусь", "не хочу начинать",
    # Belarusian
    "адкладваю", "не пачынаю", "пракрасцінацыя", "пазбягаю", "не магу пачаць",
    "адкладваю на потым", "не бяруся", "не хачу пачынаць",
}
OVERWHELM_WORDS = {
    # Russian
    "слишком много", "не справляюсь", "все навалилось", "всё навалилось", "перегрузка",
    "слишком много задач", "не успеваю", "тону",
    # Belarusian
    "занадта шмат", "не справляюся", "усё навалілася", "перагрузка",
    "занадта шмат задач", "не паспяваю", "тану",
}


def _detect_patterns(text: str, patterns: dict) -> dict:
    text_low = text.lower()
    new_patterns = dict(patterns)
    if any(w in text_low for w in SELF_ATTACK_WORDS):
        new_patterns["self_attack"] = new_patterns.get("self_attack", 0) + 1
    if any(w in text_low for w in AVOIDANCE_WORDS):
        new_patterns["avoidance"] = new_patterns.get("avoidance", 0) + 1
    if any(w in text_low for w in OVERWHELM_WORDS):
        new_patterns["overwhelm"] = new_patterns.get("overwhelm", 0) + 1
    return new_patterns


def _build_pattern_block(patterns: dict, lang: str = "ru") -> str:
    alerts = []
    if patterns.get("self_attack", 0) >= 3:
        if lang == "be":
            alerts.append("Патэрн: самаатака паўтараецца.")
        else:
            alerts.append("Паттерн: самоатака повторяется.")
    if patterns.get("avoidance", 0) >= 3:
        if lang == "be":
            alerts.append("Патэрн: пазбяганне паўтараецца.")
        else:
            alerts.append("Паттерн: избегание повторяется.")
    if patterns.get("overwhelm", 0) >= 3:
        if lang == "be":
            alerts.append("Патэрн: перагрузка паўтараецца.")
        else:
            alerts.append("Паттерн: перегрузка повторяется.")
    if not alerts:
        return ""
    title = "СХЕМА КАРЫСТАЛЬНІКА:" if lang == "be" else "СХЕМА ПОЛЬЗОВАТЕЛЯ:"
    return f"\n\n{title}\n" + "\n".join(alerts)


def _fmt_big_words(words: list[str]) -> str:
    return ", ".join(words) if words else "—"


def _is_emoji_or_symbols_only(text: str) -> bool:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return False
    if any(ch.isalnum() for ch in chars):
        return False
    return all(ord(ch) > 1000 or ch in "!?.,:;()[]{}+-_/\\'\"" for ch in chars)


def is_invalid_user_input(text: str) -> bool:
    clean = (text or "").strip()
    if not clean:
        return True
    if clean.startswith("@"):
        return True
    if len(clean) < 3:
        return True
    if len(clean) == 1:
        return True
    if _is_emoji_or_symbols_only(clean):
        return True
    return False


def format_diogenes(data: dict, lang: str = "ru") -> str:
    title = data.get("mode_title") or _l(lang, "🛢️ Диоген", "🛢️ Дыяген")
    fog = _clip(_pick(data.get("fog_type"), "—"), 120)
    hit = _clip(_pick(data.get("diogenes_hit"), data.get("strike"), data.get("what_is_the_drama"), data.get("drama_spot"), "—"), 220)
    truth = _clip(_pick(data.get("earthly_truth"), data.get("what_is_really_happening"), data.get("reality"), data.get("ground_truth"), "—"), 200)
    step = _clip(_pick(data.get("small_step"), data.get("ground_truth"), "—"), 180)
    stamp = _clip(_pick(data.get("stamp"), data.get("dry_summary"), data.get("phrase"), "—"), 110)
    dry_summary = _clip(_pick(data.get("dry_summary"), data.get("phrase"), "—"), 150)
    verdict = _clip(_pick(data.get("verdict"), data.get("dry_summary"), data.get("phrase"), "—"), 150)

    return _clip(
        _short_blocks(
            title,
            f"{_l(lang, 'Туман', 'Туман')}:\n{fog}",
            f"{hit}\n{_l(lang, 'Земля', 'Зямля')}:\n{truth}",
            (
                f"{_l(lang, 'Шаг', 'Крок')}:\n{step}\n"
                f"{_l(lang, '📌 Штамп', '📌 Штамп')}:\n{stamp}\n"
                f"{_l(lang, '📌 Сухой вывод', '📌 Сухі вынік')}:\n{dry_summary}\n"
                f"{_l(lang, '🏛️ Вердикт трактира', '🏛️ Вердыкт карчмы')}:\n{verdict}"
            ),
        ),
        MAX_MAIN_RESPONSE_LEN,
    )


def format_parmenid(data: dict, lang: str = "ru") -> str:
    title = data.get("mode_title") or _l(lang, "🧭 NextYou", "🧭 NextYou")
    fog = _clip(_pick(data.get("fog_type"), "—"), 120)
    fact = (data.get("fact") or "").strip()
    conclusion = _clip(_pick(data.get("conclusion"), "—"), 180)
    step = _clip(_pick(data.get("small_step"), "—"), 180)
    dry_summary = _clip(_pick(data.get("dry_summary"), data.get("phrase"), "—"), 150)
    verdict = _clip(_pick(data.get("verdict"), data.get("dry_summary"), data.get("phrase"), "—"), 180)

    if not fact:
        core = _clip(_pick(data.get("core_thought"), "—"), 220)
        return _clip(
            _short_blocks(
                title,
                f"{_l(lang, 'Туман', 'Туман')}:\n{fog}",
                f"{_l(lang, 'Мысль', 'Думка')}:\n«{core}»\n{_l(lang, 'Пока это вывод, не факт.', 'Пакуль гэта выснова, не факт.')}",
                _l(lang, 'Что конкретно произошло?', 'Што канкрэтна адбылося?'),
            ),
            MAX_MAIN_RESPONSE_LEN,
        )

    return _clip(
        _short_blocks(
            title,
            f"{_l(lang, 'Туман', 'Туман')}:\n{fog}",
            f"{_l(lang, 'Есть', 'Ёсць')}:\n{_clip(fact, 180)}\n{_l(lang, 'Не следует', 'Не вынікае')}:\n{conclusion}",
            (
                f"{_l(lang, 'Шаг', 'Крок')}:\n{step}\n"
                f"{_l(lang, '📌 Сухой вывод', '📌 Сухі вынік')}:\n{dry_summary}\n"
                f"{_l(lang, '🏛️ Вердикт трактира', '🏛️ Вердыкт карчмы')}:\n{verdict}"
            ),
        ),
        MAX_MAIN_RESPONSE_LEN,
    )


def format_aristotle(data: dict, lang: str = "ru") -> str:
    title = data.get("mode_title") or _l(lang, "⚙️ Аристотель", "⚙️ Арыстоцель")
    fog = _clip(_pick(data.get("fog_type"), "—"), 120)
    wrong_frame = _clip(_pick(data.get("wrong_frame"), data.get("obstacle"), data.get("cause"), "—"), 180)
    smaller_task = _clip(_pick(data.get("smaller_task"), "—"), 180)
    first_step = _clip(_pick(data.get("first_step"), data.get("small_step"), "—"), 180)
    dry_summary = _clip(_pick(data.get("dry_summary"), data.get("phrase"), "—"), 150)
    verdict = _clip(_pick(data.get("verdict"), data.get("dry_summary"), data.get("phrase"), "—"), 180)

    return _clip(
        _short_blocks(
            title,
            f"{_l(lang, 'Туман', 'Туман')}:\n{fog}",
            f"{_l(lang, 'Не', 'Не')}:\n{wrong_frame}\n{_l(lang, 'А', 'А')}:\n{smaller_task}",
            (
                f"{_l(lang, 'Шаг', 'Крок')}:\n{first_step}\n"
                f"{_l(lang, '📌 Сухой вывод', '📌 Сухі вынік')}:\n{dry_summary}\n"
                f"{_l(lang, '🏛️ Вердикт трактира', '🏛️ Вердыкт карчмы')}:\n{verdict}"
            ),
        ),
        MAX_MAIN_RESPONSE_LEN,
    )


def format_aurelius(data: dict, lang: str = "ru") -> str:
    title = data.get("mode_title") or _l(lang, "🛡️ Марк Аврелий", "🛡️ Марк Аўрэлій")
    not_under = _clip(_pick(data.get("not_under_control"), "—"), 220)
    under_control = _clip(_pick(data.get("under_control"), "—"), 220)
    step = _clip(_pick(data.get("small_step"), data.get("worthy_action"), "—"), 180)
    dry_summary = _clip(_pick(data.get("dry_summary"), data.get("phrase"), "—"), 150)
    verdict = _clip(_pick(data.get("verdict"), data.get("dry_summary"), data.get("phrase"), "—"), 180)

    return _clip(
        _short_blocks(
            title,
            f"{_l(lang, 'Не в твоей власти', 'Не ў тваёй уладзе')}:\n{not_under}",
            f"{_l(lang, 'В твоей власти', 'У тваёй уладзе')}:\n{under_control}",
            (
                f"{_l(lang, 'Шаг', 'Крок')}:\n{step}\n"
                f"{_l(lang, '📌 Сухой вывод', '📌 Сухі вынік')}:\n{dry_summary}\n"
                f"{_l(lang, '🏛️ Вердикт трактира', '🏛️ Вердыкт карчмы')}:\n{verdict}"
            ),
        ),
        MAX_MAIN_RESPONSE_LEN,
    )


async def process_mode_input(message: Message, state: FSMContext, user_text: str) -> None:
    clean_text = (user_text or "").strip()
    data = await state.get_data()
    lang = _user_language(data)
    mode = data.get("mode")
    if is_invalid_user_input(clean_text):
        await message.answer(t(lang, "invalid_input"))
        return

    if has_crisis_content(clean_text):
        await message.answer(t(lang, "safety_text"), reply_markup=safety_keyboard(lang))
        await state.set_state(ClarityFlow.waiting_for_input)
        return

    if _has_high_arousal(clean_text) and mode != "diogenes":
        rendered = _render_high_arousal_emergency(lang)
        await state.update_data(
            last_result={"high_arousal": True},
            last_rendered_text=rendered,
            last_main_rendered_text=rendered,
            user_text=clean_text,
            last_user_text=clean_text,
            last_mode=mode,
        )
        await message.answer(rendered, reply_markup=final_keyboard(lang))
        await state.set_state(ClarityFlow.waiting_for_input)
        return

    if not mode:
        await state.set_state(ClarityFlow.choosing_mode)
        await message.answer(t(lang, "no_mode_prompt"), reply_markup=mode_keyboard(lang))
        return

    patterns = _detect_patterns(clean_text, data.get("patterns", {}))
    await state.update_data(patterns=patterns, user_text=clean_text, last_user_text=clean_text, current_mode=mode, last_mode=mode)
    pattern_block = _build_pattern_block(patterns, lang)
    context_block = _build_context_block(clean_text, lang)

    if mode == "diogenes":
        result = await ai_client.run_diogenes_mode(clean_text, context_block, pattern_block, lang)
        if result.get("needs_clarification"):
            q = (result.get("clarification_question") or t(lang, "clarify_diogenes_default")).strip()
            await message.answer(q)
            await state.set_state(ClarityFlow.waiting_for_clarification)
            return
        rendered = format_diogenes(result, lang)
        await state.update_data(
            last_result=result,
            last_rendered_text=rendered,
            last_main_rendered_text=rendered,
            last_mode=mode,
            last_user_text=clean_text,
        )
        await message.answer(rendered, reply_markup=final_keyboard(lang))
        await state.set_state(ClarityFlow.waiting_for_input)
        return

    if mode == "parmenid":
        result = await ai_client.run_parmenid_mode(clean_text, context_block, pattern_block, lang)
        if result.get("needs_clarification"):
            await state.update_data(core_thought=result.get("core_thought", clean_text))
            q = (result.get("clarification_question") or t(lang, "clarify_parmenid_default")).strip()
            await message.answer(q)
            await state.set_state(ClarityFlow.waiting_for_clarification)
            return
        rendered = format_parmenid(result, lang)
        await state.update_data(
            last_result=result,
            last_rendered_text=rendered,
            last_main_rendered_text=rendered,
            last_mode=mode,
            last_user_text=clean_text,
        )
        await message.answer(rendered, reply_markup=final_keyboard(lang))
        await state.set_state(ClarityFlow.waiting_for_input)
        return

    if mode == "aristotle":
        result = await ai_client.run_aristotle_mode(clean_text, context_block, pattern_block, lang)
        if result.get("needs_clarification"):
            q = (result.get("clarification_question") or t(lang, "clarify_aristotle_default")).strip()
            await message.answer(q)
            await state.set_state(ClarityFlow.waiting_for_clarification)
            return
        rendered = format_aristotle(result, lang)
        await state.update_data(
            last_result=result,
            last_rendered_text=rendered,
            last_main_rendered_text=rendered,
            last_mode=mode,
            last_user_text=clean_text,
        )
        await message.answer(rendered, reply_markup=final_keyboard(lang))
        await state.set_state(ClarityFlow.waiting_for_input)
        return

    if mode == "aurelius":
        result = await ai_client.run_aurelius_mode(clean_text, context_block, pattern_block, lang)
        rendered = format_aurelius(result, lang)
        await state.update_data(
            last_result=result,
            last_rendered_text=rendered,
            last_main_rendered_text=rendered,
            last_mode=mode,
            last_user_text=clean_text,
        )
        await message.answer(rendered, reply_markup=final_keyboard(lang))
        await state.set_state(ClarityFlow.waiting_for_input)
        return

    await state.set_state(ClarityFlow.choosing_mode)
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "mode_not_recognized"), reply_markup=mode_keyboard(lang))


async def process_parmenid_clarification(message: Message, state: FSMContext, clarification: str) -> None:
    clean = (clarification or "").strip()
    data = await state.get_data()
    lang = _user_language(data)
    mode = data.get("mode")
    if is_invalid_user_input(clean):
        await message.answer(t(lang, "invalid_input"))
        return

    if _has_high_arousal(clean) and mode != "diogenes":
        rendered = _render_high_arousal_emergency(lang)
        await state.update_data(
            user_text=clean,
            last_user_text=clean,
            last_result={"high_arousal": True},
            last_rendered_text=rendered,
            last_main_rendered_text=rendered,
            last_mode=mode,
        )
        await state.set_state(ClarityFlow.waiting_for_input)
        await message.answer(rendered, reply_markup=final_keyboard(lang))
        return

    if mode == "parmenid":
        core_thought = data.get("core_thought", "")
        if lang == "be":
            combined_text = f"Думка: {core_thought}\nФакт: {clean}".strip()
        else:
            combined_text = f"Мысль: {core_thought}\nФакт: {clean}".strip()
        result = await ai_client.run_parmenid_mode(combined_text, _build_context_block(clean, lang), "", language=lang)
        rendered = format_parmenid(result, lang)
    elif mode == "aristotle":
        result = await ai_client.run_aristotle_mode(clean, _build_context_block(clean, lang), "", language=lang)
        rendered = format_aristotle(result, lang)
    elif mode == "diogenes":
        result = await ai_client.run_diogenes_mode(clean, _build_context_block(clean, lang), "", language=lang)
        rendered = format_diogenes(result, lang)
    else:
        result = await ai_client.run_aurelius_mode(clean, _build_context_block(clean, lang), "", language=lang)
        rendered = format_aurelius(result, lang)

    await state.update_data(
        user_text=clean,
        last_user_text=clean,
        last_result=result,
        last_rendered_text=rendered,
        last_main_rendered_text=rendered,
        last_mode=mode,
    )
    await state.set_state(ClarityFlow.waiting_for_input)
    await message.answer(rendered, reply_markup=final_keyboard(lang))


@router.message(
    ClarityFlow.waiting_for_input,
    F.text,
    ~F.text.in_(list(MODE_BUTTON_TO_KEY.keys())),
    ~F.text.in_(list(VOICE_CONFIRM_BUTTONS)),
)
async def handle_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    await process_mode_input(message, state, text)


@router.message(ClarityFlow.waiting_for_clarification, F.text, ~F.text.in_(list(MODE_BUTTON_TO_KEY.keys())))
async def handle_clarification(message: Message, state: FSMContext) -> None:
    clarification = (message.text or "").strip()
    await process_parmenid_clarification(message, state, clarification)


@router.message(ClarityFlow.waiting_for_input, F.photo | F.sticker)
async def handle_input_media_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "input_media_fallback"))


@router.message(ClarityFlow.waiting_for_clarification, F.photo | F.sticker)
async def handle_clarification_media_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "clarification_media_fallback"))
