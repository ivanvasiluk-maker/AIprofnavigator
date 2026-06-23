from __future__ import annotations

import asyncio
import io
import os
import re
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Document, FSInputFile, Message
from pypdf import PdfReader

from config import settings
from keyboards import (
    ALL_INPUT_DONT_KNOW,
    ALL_SHORT_STORY_OPTIONS,
    ALL_SUPPORT_OPTIONS,
    ALL_INPUT_TEXT,
    ALL_INPUT_VOICE,
    ALL_PSYCH_BARRIER_DONE,
    ALL_PSYCH_GROUP_OPTIONS,
    ALL_PSYCH_BARRIER_OPTIONS,
    ALL_RESTART,
    ALL_RESUME_SKIP,
    ALL_RESUME_UPLOAD,
    ALL_SUPPORT_MODE_ACTIONS,
    ALL_ANSWER_REVIEW_ACTIONS,
    ALL_BARRIER_DETAIL_ACTIONS,
    ALL_CV_REVIEW_ACTIONS,
    ALL_PRACTICAL_BARRIER_ACTIONS,
    SUPPORT_DONE,
    ALL_RESULT_ACTIONS,
    RESULT_ANALYZE_FEARS,
    RESULT_DETAILS,
    RESULT_FIX_CV,
    RESULT_KEYWORDS,
    RESULT_REBUILD,
    RESULT_MY_MAP,
    RESULT_SUPPORT,
    RESULT_THINK,
    RESULT_TODAY_STEP,
    SUPPORT_BACK_TO_MAP,
    PSYCH_SKIP,
    BARRIER_GROUP_BEHAVIOR,
    BARRIER_GROUP_INTERNAL,
    BARRIER_GROUP_LIFE,
    ANSWER_KEEP,
    ANSWER_SKIP,
    ANSWER_RETRY,
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
    question_options_keyboard,
    result_actions_keyboard,
    short_story_keyboard,
    practical_barrier_keyboard,
    resume_choice_keyboard,
    resume_wait_keyboard,
    support_mode_keyboard,
    think_reminder_keyboard,
)
from localization import t
from openai_client import ai_client
from states import CareerFlow
from utils.analytics import behavior_insights, behavior_offer_snapshot, days_since_first_seen, ensure_public_user_id, log_behavior_event
from utils.reporting import build_telegram_summary, generate_pdf_report
from utils.reporting import generate_report_files

router = Router()
_REMINDER_TASKS: dict[int, asyncio.Task] = {}

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


def _resume_debug_log(message: Message, step: str, **fields: object) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    suffix = f" {details}" if details else ""
    print(f"[resume-flow] user_id={user_id} step={step}{suffix}", flush=True)


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


def _user_language(data: dict) -> str:
    return data.get("language") or data.get("lang", "ru")


def _ensure_public_id(data: dict, message: Message) -> str:
    existing = str(data.get("public_user_id") or "").strip()
    if existing:
        return existing
    source_id = message.from_user.id if message.from_user else message.chat.id
    return ensure_public_user_id(source_id)


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
    )
    await state.update_data(
        public_user_id=public_user_id,
        state_name=state_name,
        state_entered_at=state_entered_at_iso,
        last_event_at=now_iso,
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
        return f"Вопрос {safe_index + 1}/{total}\n\n{row}"

    q_num = row.get("id", safe_index + 1)
    try:
        q_num = int(q_num)
    except Exception:
        q_num = safe_index + 1
    text = row.get("question", "-")
    options = row.get("options", [])
    lines = [f"=== Вопрос {safe_index + 1}/{total} ===", f"№{q_num}. {text}"]
    if isinstance(options, list) and options:
        lines.append("Варианты: " + " | ".join(str(item) for item in options[:10]))
        lines.append(t(lang, "question_answer_hint_with_options"))
    else:
        lines.append(t(lang, "question_answer_hint_no_options"))
    return _clip("\n\n".join(lines))


def _questions_fast() -> list[dict[str, object]]:
    return [
        {"id": 1, "question": "Кем вы работали раньше и что умеете лучше всего?", "options": []},
        {
            "id": 2,
            "question": "Что сейчас сильнее мешает: тревога, усталость, страх отказов, прокрастинация или хаос?",
            "options": ["тревога", "усталость", "страх отказов", "прокрастинация", "хаос"],
        },
        {"id": 3, "question": "Какой минимальный доход нужен в месяц?", "options": []},
        {"id": 4, "question": "Какие языки вы знаете и примерно на каком уровне?", "options": []},
        {"id": 5, "question": "Есть ли сейчас поддержка: семья, друзья, контакты, сообщество?", "options": ["семья", "друзья", "контакты", "сообщество", "пока мало поддержки"]},
    ]


def _questions_calm() -> list[dict[str, object]]:
    return [
        {"id": 1, "question": "Кем вы работали раньше и что в вашем опыте получается лучше всего?", "options": []},
        {"id": 2, "question": "Какой минимальный доход нужен в месяц, чтобы выдохнуть?", "options": []},
        {
            "id": 3,
            "question": "Как быстро нужен первый стабильный доход?",
            "options": ["⚡ 2–4 недели", "📆 1–3 месяца", "📚 3–6 месяцев", "🧭 Можно дольше, если путь сильнее"],
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
        {"id": 2, "question": "Какой минимальный доход нужен в месяц?", "options": []},
        {
            "id": 3,
            "question": "Как быстро нужен доход?",
            "options": ["⚡ 2–4 недели", "📆 1–3 месяца", "📚 3–6 месяцев", "🧭 Могу менять траекторию год"],
        },
        {"id": 4, "question": "Какие языки и уровень?", "options": []},
        {"id": 5, "question": "Чего точно не хотите делать?", "options": []},
        {"id": 6, "question": "Какие варианты работы вам кажутся хоть немного возможными?", "options": []},
        {"id": 7, "question": "Сколько часов в неделю реально готовы уделять поиску или обучению?", "options": []},
        {
            "id": 8,
            "question": "Как вы живёте и адаптируетесь в новой стране: кто рядом, какие барьеры, есть ли сообщество?",
            "options": ["семья", "друзья", "профконтакты", "сообщество", "пока никто"],
        },
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
        {"id": 1, "question": "Какой минимальный доход нужен в месяц?", "options": []},
        {
            "id": 2,
            "question": "Как быстро нужен первый стабильный доход?",
            "options": ["⚡ 2–4 недели", "📆 1–3 месяца", "📚 3–6 месяцев", "🧭 Можно дольше"],
        },
        {"id": 3, "question": "Какие языки вы используете и на каком уровне?", "options": []},
        {"id": 4, "question": "Сколько часов в неделю реально готовы выделять на поиск/обучение?", "options": []},
    ]


def _segment_questions(segment: str) -> list[dict[str, object]]:
    if segment == SEGMENT_WORKER:
        return [
            {"id": 1, "question": "Что вы умеете делать руками лучше всего?", "options": []},
            {"id": 2, "question": "С каким оборудованием или техникой уже работали?", "options": []},
            {"id": 3, "question": "Есть ли права, сертификаты, допуски или лицензии?", "options": []},
            {"id": 4, "question": "Готовы ли к сменной работе и какой график вам подходит?", "options": ["готов(а) к сменам", "только дневной", "гибкий график"]},
            {"id": 5, "question": "Готовы ли к переезду или работе в соседнем городе?", "options": ["да", "нет", "только в пределах региона"]},
            {"id": 6, "question": "Есть ли опыт обучения новичков или управления бригадой?", "options": []},
        ]
    if segment == SEGMENT_SERVICE:
        return [
            {"id": 1, "question": "В какой сфере сервиса или ухода у вас больше всего опыта?", "options": []},
            {"id": 2, "question": "С какими категориями людей вам комфортнее работать?", "options": ["дети", "взрослые", "пожилые", "клиенты в сервисе"]},
            {"id": 3, "question": "Какие задачи у вас получаются лучше: уход, сервис, организация, коммуникация?", "options": []},
            {"id": 4, "question": "Есть ли у вас профильные курсы, сертификаты, медкнижка?", "options": []},
            {"id": 5, "question": "Готовы ли к сменному графику и работе в выходные?", "options": ["да", "нет", "частично"]},
            {"id": 6, "question": "Что готовы изучить в ближайшие 1-2 месяца для роста?", "options": []},
        ]
    if segment == SEGMENT_LOGISTICS:
        return [
            {"id": 1, "question": "Какой у вас опыт в логистике, транспорте или складе?", "options": []},
            {"id": 2, "question": "Какие категории прав и допуски у вас есть?", "options": []},
            {"id": 3, "question": "С какими системами или маршрутами работали (TMS, склад, международные рейсы)?", "options": []},
            {"id": 4, "question": "Готовы ли к ночным сменам, рейсам или плавающему графику?", "options": ["да", "нет", "частично"]},
            {"id": 5, "question": "Есть ли опыт координации перевозок или управления сменой/складом?", "options": []},
            {"id": 6, "question": "В какую роль хотите вырасти: диспетчер, координатор, логист, супервайзер?", "options": []},
        ]
    if segment == SEGMENT_OFFICE:
        return [
            {"id": 1, "question": "Какие офисные процессы вы вели: документы, отчеты, координация, поддержка клиентов?", "options": []},
            {"id": 2, "question": "Какими инструментами владеете (Excel, CRM, ERP, таблицы)?", "options": []},
            {"id": 3, "question": "Какой формат ближе: back-office, ассистент, администрирование, координатор?", "options": []},
            {"id": 4, "question": "Какие задачи хотите исключить из новой роли?", "options": []},
            {"id": 5, "question": "Готовы ли к гибриду или только удаленно/офлайн?", "options": ["офис", "гибрид", "удаленно"]},
            {"id": 6, "question": "Есть ли опыт обучения коллег или ведения небольших команд?", "options": []},
        ]
    if segment == SEGMENT_LEADER:
        return [
            {"id": 1, "question": "Опишите ситуацию, которой в работе особенно гордитесь (S/T/A/R).", "options": []},
            {"id": 2, "question": "Какую сложную проблему вы решили как руководитель?", "options": []},
            {"id": 3, "question": "Когда вам приходилось организовывать людей или процессы в кризисе?", "options": []},
            {"id": 4, "question": "Какой масштаб команды/бюджета/зоны ответственности у вас был?", "options": []},
            {"id": 5, "question": "Когда вы обучали или наставляли других и какой был результат?", "options": []},
            {"id": 6, "question": "Какую управленческую роль хотите взять сейчас как основной трек?", "options": []},
        ]
    if segment == SEGMENT_ENTREPRENEUR:
        return [
            {"id": 1, "question": "Опишите бизнес-ситуацию, где вы добились заметного результата (S/T/A/R).", "options": []},
            {"id": 2, "question": "Какую самую сложную проблему в бизнесе вам удалось решить?", "options": []},
            {"id": 3, "question": "Как вы организовывали людей, процессы или продажи?", "options": []},
            {"id": 4, "question": "Какие компетенции хотите монетизировать в новой стране в первую очередь?", "options": []},
            {"id": 5, "question": "Готовы ли параллельно идти по найму для стабилизации дохода?", "options": ["да", "нет", "только временно"]},
            {"id": 6, "question": "В какой модели хотите двигаться: услуги, микро-бизнес, партнерство, консультации?", "options": []},
        ]
    return [
        {"id": 1, "question": "Опишите рабочую ситуацию, которой вы особенно гордитесь (S/T/A/R).", "options": []},
        {"id": 2, "question": "Какую сложную проблему вы решали и за счет чего получилось?", "options": []},
        {"id": 3, "question": "Когда вам приходилось организовывать людей или процессы?", "options": []},
        {"id": 4, "question": "Когда вы обучали или наставляли других?", "options": []},
        {"id": 5, "question": "В какой тип задач сейчас хотите вложить максимум усилий?", "options": []},
        {"id": 6, "question": "Какие ограничения нужно учесть, чтобы выйти на доход без срыва?", "options": []},
    ]


def _mandatory_psych_social_questions() -> list[dict[str, object]]:
    return [
        {
            "question": "Психологические барьеры (до 5): отметьте, что мешает начать честно и стабильно.",
            "options": [
                "😰 Страх отказа",
                "🧩 Хаос в голове",
                "⏳ Прокрастинация",
                "🔁 Сомнения и откаты",
                "🪫 Усталость / выгорание",
                _INTERVIEW_PSYCH_DONE,
            ],
            "multi_key": "psych",
            "done_text": _INTERVIEW_PSYCH_DONE,
            "max_select": 5,
            "force_options_keyboard": True,
        },
        {
            "question": "Социальная опора и миграционный статус (до 5): что сейчас про вас наиболее точно?",
            "options": [
                "👨‍👩‍👧 Есть семья/партнер рядом",
                "👥 Есть друзья/контакты",
                "🌫 Почти нет поддержки",
                "🧭 Новая миграция (0-6 месяцев)",
                "🏠 Стадия стабилизации (6+ месяцев)",
                _INTERVIEW_SOCIAL_DONE,
            ],
            "multi_key": "social",
            "done_text": _INTERVIEW_SOCIAL_DONE,
            "max_select": 5,
            "force_options_keyboard": True,
        },
        {
            "question": "Источники энергии (до 5): что дает вам больше энергии в работе?",
            "options": [
                "Работа с людьми",
                "Помощь людям",
                "Обучение",
                "Организация процессов",
                "Управление",
                "Творчество",
                "Анализ",
                "Техника",
                "Исследования",
                "Продажи",
                "Проведение мероприятий",
                _INTERVIEW_ENERGY_DONE,
            ],
            "multi_key": "energy",
            "done_text": _INTERVIEW_ENERGY_DONE,
            "max_select": 5,
            "force_options_keyboard": True,
        },
        {
            "question": "Уровень внутреннего ресурса сейчас:",
            "options": [
                "Высокий: есть силы и устойчивость",
                "Средний: двигаюсь, но бывают просадки",
                "Низкий: тяжело держать темп, нужен щадящий режим",
            ],
        },
        {
            "question": "Интеграция в стране (до 4): что уже есть у вас сейчас?",
            "options": [
                "Использую местный язык в быту",
                "Есть местные знакомые/друзья",
                "Есть профессиональные контакты",
                "Участвую в сообществах",
                "Понимаю, как устроен рынок труда",
                "Живу в стране больше 12 месяцев",
                _INTERVIEW_INTEGRATION_DONE,
            ],
            "multi_key": "integration",
            "done_text": _INTERVIEW_INTEGRATION_DONE,
            "max_select": 4,
            "force_options_keyboard": True,
        },
        {
            "question": "Карьерные приоритеты (до 4): что для вас сейчас важнее всего?",
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


def _set_mvp_questions(
    analysis: dict,
    limit: int = 8,
    mode: str = "calm_steps",
    story_text: str = "",
    user_segment: str = SEGMENT_SPECIALIST,
) -> dict:
    updated = dict(analysis or {})
    segment_specific = _segment_questions(user_segment)
    common = _segment_common_questions()
    mode_base = _questions_fast() if mode == "fast" else _questions_support() if mode == "support" else _questions_calm()
    mandatory = _mandatory_psych_social_questions()
    mandatory_keys = {str(row.get("question", "")).strip().lower() for row in mandatory}
    effective_limit = max(int(limit), len(mandatory))
    regular_limit = max(0, effective_limit - len(mandatory))

    merged_base = segment_specific + common + mode_base
    deduped = _filter_known_questions(merged_base, story_text)
    selected: list[dict[str, object]] = []
    for row in deduped:
        if not isinstance(row, dict):
            continue
        q_key = str(row.get("question", "")).strip().lower()
        if not q_key or q_key in mandatory_keys:
            continue
        selected.append(row)
        if len(selected) >= regular_limit:
            break

    raw_extra = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    seen = {str(row.get("question", "")).strip().lower() for row in selected if isinstance(row, dict)} | mandatory_keys
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
            opts = row.get("options", [])
            if not isinstance(opts, list):
                opts = []
            max_options = 15 if row.get("force_options_keyboard") else 6
            selected.append({"id": int(row.get("id", len(selected) + 1)), "question": q_text, "options": opts[:max_options]})
            seen.add(q_key)
            if len(selected) >= regular_limit:
                break

    if len(selected) < 1 and regular_limit > 0:
        selected = [deduped[0]] if deduped and isinstance(deduped[0], dict) else []

    combined = selected[:regular_limit] + mandatory
    trimmed = combined[: max(1, min(effective_limit, len(combined)))]
    normalized: list[dict[str, object]] = []
    for idx, row in enumerate(trimmed, start=1):
        if not isinstance(row, dict):
            continue
        opts = row.get("options", [])
        if not isinstance(opts, list):
            opts = []
        max_options = 15 if row.get("force_options_keyboard") else 6
        normalized_row: dict[str, object] = {
            "id": idx,
            "question": str(row.get("question", "")).strip() or f"Вопрос {idx}",
            "options": opts[:max_options],
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

    updated["follow_up_questions"] = normalized[: max(1, min(effective_limit, len(normalized)))]
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

    if low in {"не знаю", "ничего", "ав", "ячзщык", "-"}:
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

    if options:
        normalized = [str(item).strip().lower() for item in options if str(item).strip()]
        if normalized and all(opt not in low for opt in normalized) and len(clean) > 80:
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


def format_cv_route_review(resume_analysis: dict, report: dict, lang: str) -> str:
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    market = report.get("market_analysis", []) if isinstance(report.get("market_analysis"), list) else []
    best = market[0] if market and isinstance(market[0], dict) else {}
    strengths = _list_block(resume_analysis.get("what_is_good", []) if isinstance(resume_analysis, dict) else [])
    gaps = _list_block(resume_analysis.get("what_is_missing", []) if isinstance(resume_analysis, dict) else [])
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
                f"{t(lang, 'cv_review_keywords')}:\n{requirements}",
                f"{t(lang, 'cv_review_bullets')}:\n{bullets_block}",
                f"{t(lang, 'cv_review_48h')}:\n{plan_48h}",
                t(lang, "cv_review_next"),
            ]
        )
    )


def format_resume_analysis(resume_analysis: dict, lang: str) -> str:
    good = resume_analysis.get("what_is_good", []) if isinstance(resume_analysis, dict) else []
    missing = resume_analysis.get("what_is_missing", []) if isinstance(resume_analysis, dict) else []
    good_block = _list_block(good)
    missing_block = _list_block(missing)
    if good_block == "-":
        good_block = t(lang, "resume_data_missing")
    if missing_block == "-":
        missing_block = t(lang, "resume_data_missing")
    return _clip(
        "\n\n".join(
            [
                f"{t(lang, 'resume_good_label')}:\n{good_block}",
                f"{t(lang, 'resume_missing_label')}:\n{missing_block}",
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


def report_chunks(report: dict, lang: str) -> dict[str, str]:
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    recommendations = report.get("career_recommendations", [])
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    roadmap = report.get("development_map", {})
    week = report.get("weekly_plan", [])
    energy_sources = report.get("energy_sources", []) if isinstance(report.get("energy_sources"), list) else []
    career_priorities = report.get("career_priorities", []) if isinstance(report.get("career_priorities"), list) else []
    competency_signals = report.get("competency_signals", []) if isinstance(report.get("competency_signals"), list) else []
    resource_level_raw = str(report.get("resource_level") or "не уточнено").strip() or "не уточнено"
    integration_level_raw = str(report.get("integration_level") or "не уточнено").strip() or "не уточнено"
    resource_level = (
        f"{resource_level_raw} ({_level_label(resource_level_raw)})"
        if resource_level_raw != "не уточнено"
        else resource_level_raw
    )
    integration_level = (
        f"{integration_level_raw} ({_level_label(integration_level_raw)})"
        if integration_level_raw != "не уточнено"
        else integration_level_raw
    )

    header = _clip(
        "\n\n".join(
            [
                f"=== {t(lang, 'digital_human_label')} ===\n{digital_human.get('summary') or '-'}",
                f"{t(lang, 'who_now_label')}:\n{digital_human.get('current_state') or '-'}",
                f"{t(lang, 'main_asset_label')}:\n{digital_human.get('main_asset') or '-'}",
                f"{t(lang, 'main_risk_label')}:\n{digital_human.get('main_risk') or '-'}",
                f"Главный барьер:\n{digital_human.get('main_barrier') or '-'}",
                f"Главный страх:\n{digital_human.get('main_fear') or '-'}",
                f"Источники энергии:\n{_list_block(energy_sources)}",
                f"Карьерные приоритеты:\n{_list_block(career_priorities)}",
                f"STAR-компетенции:\n{_list_block(competency_signals)}",
                f"Уровень ресурса:\n{resource_level}",
                f"Уровень интеграции:\n{integration_level}",
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
    await state.update_data(selected_barriers=[], selected_fears=[], selected_psych_markers=[])
    await state.set_state(CareerFlow.SELECTING_BARRIERS)
    await message.answer(t(lang, "step_barriers"), reply_markup=barriers_keyboard())
    await message.answer(t(lang, "barriers_prompt"), reply_markup=barriers_keyboard())


async def _start_questions_module(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    story_text = (data.get("story_text") or "").strip()
    analysis_raw = data.get("story_analysis") or {}
    profile = data.get("interaction_profile") or _build_interaction_profile(story_text, data)
    user_mode = str(data.get("user_mode") or "calm_steps")
    user_segment = str(data.get("user_segment") or _detect_user_segment(story_text, analysis_raw))
    mode_max = int(data.get("max_questions") or 8)
    cv_uploaded = bool(data.get("cv_uploaded"))
    q_count = min(3, max(1, mode_max)) if cv_uploaded else max(1, mode_max)
    analysis = _set_mvp_questions(
        analysis_raw,
        limit=q_count,
        mode=user_mode,
        story_text=story_text,
        user_segment=user_segment,
    )
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    quick_report_after_questions = cv_uploaded or user_mode == "fast"

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
        selected_barriers=[],
        selected_fears=[],
        selected_social_state=[],
        selected_integration_state=[],
        selected_energy_sources=[],
        selected_career_priorities=[],
        psych_selected=[],
        social_selected=[],
        integration_selected=[],
        energy_selected=[],
        priorities_selected=[],
    )

    if not questions:
        await state.set_state(CareerFlow.INTERVIEW)
        if cv_uploaded:
            _resume_debug_log(message, "questions_empty_after_resume")
        await message.answer(t(lang, "questions_empty"))
        if quick_report_after_questions:
            await state.update_data(answers_text=t(lang, "resume_continue_without"))
            await _build_and_send_report(message, state, lang)
        return

    await state.set_state(CareerFlow.INTERVIEW)
    if cv_uploaded:
        await message.answer(t(lang, "step_questions_resume_fast"))
    elif user_mode == "fast":
        await message.answer(t(lang, "step_questions_short"))
    else:
        await message.answer(t(lang, "step_questions"))
    await message.answer(_question_prompt(analysis, 0, lang), reply_markup=_question_reply_markup(analysis, 0))
    if cv_uploaded:
        first_question = questions[0] if questions and isinstance(questions[0], dict) else {}
        _resume_debug_log(message, "question_1_sent", question_id=first_question.get("id", 1))


async def _build_and_send_report(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    story_text = (data.get("story_text") or "").strip()
    story_analysis = data.get("story_analysis") or {}
    answers_text = (data.get("answers_text") or "").strip()
    social_state = data.get("selected_social_state") or []
    if isinstance(social_state, list) and social_state:
        social_block = "\n".join(f"- {item}" for item in social_state[:5] if str(item).strip())
        if social_block:
            answers_text = (answers_text + "\n\nСоциальная поддержка и миграционный статус:\n" + social_block).strip()
    integration_state = data.get("selected_integration_state") or []
    if isinstance(integration_state, list) and integration_state:
        integration_state_block = "\n".join(f"- {item}" for item in integration_state[:4] if str(item).strip())
        if integration_state_block:
            answers_text = (answers_text + "\n\nИнтеграция пользователя:\n" + integration_state_block).strip()
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
    resume_analysis = data.get("resume_analysis") or {}
    selected_barriers = data.get("selected_barriers") or []
    selected_fears = data.get("selected_fears") or []
    selected_psych_markers = data.get("selected_psych_markers") or []
    user_mode = str(data.get("user_mode") or "calm_steps")

    await state.set_state(CareerFlow.GENERATING_REPORT)
    if user_mode == "support":
        await message.answer(t(lang, "support_before_map"))
    await message.answer(t(lang, "step_report"))
    await message.answer(t(lang, "processing_answers"))

    report = await ai_client.build_report(
        story_text,
        story_analysis,
        answers_text,
        resume_analysis=resume_analysis,
        selected_barriers=selected_barriers,
        selected_fears=selected_fears,
        selected_psych_markers=selected_psych_markers,
        selected_energy_sources=energy_sources,
        selected_career_priorities=career_priorities,
        language=lang,
    )
    chunks = report_chunks(report, lang)
    await state.update_data(
        final_report=report,
        report_chunks=chunks,
        post_result_stage="ready",
        final_report_generated=True,
    )
    await _track_event(message, state, "report_generated", meta={"has_income_signal": _has_income_signal(report)})
    await state.set_state(CareerFlow.FINAL_READY)

    await message.answer(t(lang, "contract_anchor"), reply_markup=result_actions_keyboard())
    await message.answer(t(lang, "final_short_intro"), reply_markup=result_actions_keyboard())
    await message.answer(build_telegram_summary(report), reply_markup=result_actions_keyboard())

    pdf_report_path = ""
    html_report_path = ""
    try:
        user_name = " ".join(
            part
            for part in [
                (message.from_user.first_name if message.from_user else "") or "",
                (message.from_user.last_name if message.from_user else "") or "",
            ]
            if part
        ).strip()
        await state.set_state(CareerFlow.PDF_GENERATING)
        pdf_path, html_path = generate_report_files(report, output_dir=settings.report_output_dir, user_name=user_name)
        html_report_path = str(html_path)

        if pdf_path is not None:
            pdf_report_path = str(pdf_path)
            await _track_event(message, state, "pdf_ready", meta={"engine": settings.report_pdf_engine})
            await state.set_state(CareerFlow.PDF_READY)
            await message.answer_document(
                FSInputFile(str(pdf_path)),
                caption=t(lang, "pdf_send_caption"),
                reply_markup=result_actions_keyboard(),
            )
        else:
            await _track_event(message, state, "pdf_fallback_html", meta={"engine": settings.report_pdf_engine})
            await message.answer_document(
                FSInputFile(str(html_path)),
                caption=t(lang, "pdf_send_error"),
                reply_markup=result_actions_keyboard(),
            )
    except Exception:
        await _track_event(message, state, "pdf_generation_error", meta={"engine": settings.report_pdf_engine})
        if html_report_path and os.path.exists(html_report_path):
            await message.answer_document(
                FSInputFile(html_report_path),
                caption=t(lang, "pdf_send_error"),
                reply_markup=result_actions_keyboard(),
            )
        else:
            await message.answer(t(lang, "pdf_send_error"), reply_markup=result_actions_keyboard())

    await state.set_state(CareerFlow.FINAL_READY)
    today_task = _today_task_from_report(report)
    await state.update_data(
        skiller_today_task=today_task,
        pdf_report_path=pdf_report_path,
        html_report_path=html_report_path,
    )


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
    if any(token in q_text for token in ["формат работы", "ближе", "50/50", "документ", "люд"]):
        return interview_work_format_keyboard()
    if "поддерж" in q_text:
        return interview_support_keyboard()
    options = row.get("options", [])
    return question_options_keyboard(options if isinstance(options, list) else [])


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

    profile = _build_interaction_profile(clean, data)
    selected_mode = str(data.get("user_mode") or "calm_steps")
    preferred_input = str(data.get("preferred_input") or profile.get("preferred_input") or "text")
    if selected_mode == "fast":
        profile.update({"pace": "fast", "support_need": "low", "detail_preference": "brief"})
    elif selected_mode == "support":
        profile.update({"pace": "slow", "support_need": "high", "detail_preference": "balanced"})
    else:
        profile.update({"pace": "normal", "support_need": "medium", "detail_preference": "balanced"})
    profile["preferred_input"] = preferred_input

    await state.update_data(
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
    analysis = await ai_client.analyze_story(clean, lang)
    user_segment = _detect_user_segment(clean, analysis)
    q_count = int(data.get("max_questions") or 8)
    if profile.get("emotional_tone") in {"tired", "angry"}:
        q_count = min(q_count, 3)
    analysis = _set_mvp_questions(
        analysis,
        limit=q_count,
        mode=selected_mode,
        story_text=clean,
        user_segment=user_segment,
    )
    await state.update_data(
        story_analysis=analysis,
        user_segment=user_segment,
        user_segment_label=_segment_label(user_segment),
    )
    await state.set_state(CareerFlow.ASK_CV)
    await message.answer(t(lang, "story_after_received"))
    await message.answer(t(lang, "step_resume"), reply_markup=resume_choice_keyboard())
    await message.answer(t(lang, "resume_offer"), reply_markup=resume_choice_keyboard())


async def process_answers_input(message: Message, state: FSMContext, text: str) -> None:
    clean = (text or "").strip()
    data = await state.get_data()
    lang = _user_language(data)
    analysis = data.get("story_analysis") or {}
    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    qa_index = int(data.get("qa_index", 0))
    qa_answers = list(data.get("qa_answers") or [])
    pending_review = data.get("pending_answer_review") or {}
    interaction_profile = dict(data.get("interaction_profile") or {})
    user_mode = str(data.get("user_mode") or "calm_steps")
    quick_report_after_questions = bool(data.get("quick_report_after_questions"))
    interaction_turn = int(data.get("interaction_turn", 0)) + 1
    interaction_profile["answer_length"] = _classify_answer_length(clean)
    interaction_profile["emotional_tone"] = _detect_emotional_tone(clean) if _detect_emotional_tone(clean) != "unknown" else interaction_profile.get("emotional_tone", "unknown")
    interaction_profile["structure_level"] = _detect_structure_level(clean)
    interaction_profile["agency_level"] = _detect_agency_level(clean)
    await state.update_data(interaction_profile=interaction_profile, interaction_turn=interaction_turn)

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

    if not clean:
        await message.answer(t(lang, "answers_too_short"))
        return

    if questions and qa_index < len(questions):
        current = questions[qa_index]
        current_q_id = _question_id(current, qa_index)
        question_text = current.get("question", f"Вопрос {qa_index + 1}") if isinstance(current, dict) else str(current)

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
                qa_answers.append(
                    {
                        "question": question_text,
                        "question_id": current_q_id,
                        "answer": ", ".join(selected_values[:max_select]),
                    }
                )
                qa_index += 1
                update_payload: dict[str, object] = {
                    "qa_answers": qa_answers,
                    "qa_index": qa_index,
                    "pending_answer_review": {},
                    selected_key: [],
                }
                if multi_key == "psych":
                    update_payload["selected_psych_markers"] = selected_values[:5]
                    update_payload["selected_barriers"] = selected_values[:5]
                    update_payload["selected_fears"] = selected_values[:5]
                if multi_key == "social":
                    update_payload["selected_social_state"] = selected_values[:5]
                if multi_key == "integration":
                    update_payload["selected_integration_state"] = selected_values[:4]
                if multi_key == "energy":
                    update_payload["selected_energy_sources"] = selected_values[:5]
                if multi_key == "priorities":
                    update_payload["selected_career_priorities"] = selected_values[:4]
                await state.update_data(**update_payload)
                if qa_index < len(questions):
                    await message.answer(_question_prompt(analysis, qa_index, lang), reply_markup=_question_reply_markup(analysis, qa_index))
                    return

                merged_answers = "\n".join(
                    f"{idx + 1}. {row.get('question', '-')}: {row.get('answer', '-')}"
                    for idx, row in enumerate(qa_answers)
                    if isinstance(row, dict)
                )
                await state.update_data(answers_text=merged_answers)
                if quick_report_after_questions or user_mode == "fast":
                    await _build_and_send_report(message, state, lang)
                    return
                await _start_barriers_module(message, state, lang)
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
                if multi_key == "social":
                    update_payload["selected_social_state"] = selected_values[:5]
                if multi_key == "integration":
                    update_payload["selected_integration_state"] = selected_values[:4]
                if multi_key == "energy":
                    update_payload["selected_energy_sources"] = selected_values[:5]
                if multi_key == "priorities":
                    update_payload["selected_career_priorities"] = selected_values[:4]
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

        issue_key = _validate_answer(current, clean, qa_answers)
        if issue_key:
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

        qa_answers.append({"question": question_text, "question_id": _question_id(current, qa_index), "answer": clean})
        qa_index += 1
        await state.update_data(qa_answers=qa_answers, qa_index=qa_index, pending_answer_review={})

        if interaction_turn % 3 == 0:
            if interaction_profile.get("support_need") == "high":
                await message.answer(t(lang, "contract_anchor"))
            elif interaction_profile.get("answer_length") == "short":
                await message.answer(t(lang, "adaptive_transition_buttons"))
            elif interaction_profile.get("answer_length") == "long":
                await message.answer(t(lang, "adaptive_transition_detailed"))

        if qa_index < len(questions):
            await message.answer(_question_prompt(analysis, qa_index, lang), reply_markup=_question_reply_markup(analysis, qa_index))
            return

        merged_answers = "\n".join(
            f"{idx + 1}. {row.get('question', '-')}: {row.get('answer', '-')}"
            for idx, row in enumerate(qa_answers)
            if isinstance(row, dict)
        )
        await state.update_data(answers_text=merged_answers)
        if quick_report_after_questions or user_mode == "fast":
            await _build_and_send_report(message, state, lang)
            return
        await _start_barriers_module(message, state, lang)
        return

    await state.update_data(answers_text=clean)
    if user_mode == "fast":
        await _build_and_send_report(message, state, lang)
        return
    await _start_barriers_module(message, state, lang)


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
    selected = list(data.get("selected_psych_markers") or [])
    already_selected = choice in selected
    if not already_selected:
        selected.append(choice)
    await state.update_data(selected_psych_markers=selected, selected_barriers=selected)
    text_key = "barriers_already_selected" if already_selected else "barriers_selected"
    await message.answer(t(lang, text_key, count=len(selected), items=_selection_to_text(selected)), reply_markup=barriers_keyboard())


async def complete_barriers(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    selected = list(data.get("selected_psych_markers") or [])
    if not selected:
        selected = ["Не указано"]
    await state.update_data(selected_psych_markers=selected, selected_fears=selected[:6])
    await _build_and_send_report(message, state, lang)


@router.message(CareerFlow.waiting_for_barriers, F.text)
async def barriers_fallback(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    low = raw.lower()

    if raw in ALL_PSYCH_GROUP_OPTIONS:
        if raw == PSYCH_SKIP:
            await complete_barriers(message, state)
            return
        await message.answer(t(_user_language(await state.get_data()), "barriers_prompt"), reply_markup=barriers_group_keyboard(raw))
        return

    if low in _BARRIER_DONE_ALIASES or low in _BARRIER_DONE_BY_LOWER:
        await complete_barriers(message, state)
        return

    if raw in ALL_RESULT_ACTIONS:
        lang = _user_language(await state.get_data())
        await message.answer(t(lang, "barriers_only_hint"), reply_markup=barriers_keyboard())
        return

    normalized_choice = _BARRIER_OPTION_BY_LOWER.get(low) or raw
    if normalized_choice not in ALL_PSYCH_BARRIER_OPTIONS:
        lang = _user_language(await state.get_data())
        await message.answer(t(lang, "barriers_only_hint"), reply_markup=barriers_keyboard())
        return
    await _save_barrier_choice(message, state, normalized_choice)


@router.message(CareerFlow.GENERATING_REPORT, F.text | F.voice | F.document | F.photo | F.sticker)
@router.message(CareerFlow.PDF_GENERATING, F.text | F.voice | F.document | F.photo | F.sticker)
async def generation_lock_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
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
        selected_social_state=[],
        selected_energy_sources=[],
        selected_career_priorities=[],
        psych_selected=[],
        social_selected=[],
        energy_selected=[],
        priorities_selected=[],
        report_chunks={},
        skiller_today_task="",
        final_report_generated=False,
        pdf_report_path="",
        pending_answer_review={},
        reminder_due_at="",
    )
    await state.set_state(CareerFlow.WAITING_STORY)
    await message.answer(t(lang, "restart_prompt"), reply_markup=input_method_keyboard())


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
async def handle_answer_review_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    action = (message.text or "").strip()
    pending = data.get("pending_answer_review") or {}
    if not pending:
        await message.answer(t(lang, "question_answer_hint"))
        return

    qa_answers = list(data.get("qa_answers") or [])
    qa_index = int(data.get("qa_index", 0))
    analysis = data.get("story_analysis") or {}
    user_mode = str(data.get("user_mode") or "calm_steps")
    quick_report_after_questions = bool(data.get("quick_report_after_questions"))

    if action == ANSWER_RETRY:
        await state.update_data(pending_answer_review={})
        await message.answer(_question_prompt(analysis, qa_index, lang), reply_markup=_question_reply_markup(analysis, qa_index))
        return

    answer_text = str(pending.get("answer", "")).strip()
    if action == ANSWER_SKIP:
        answer_text = "(пропущено пользователем)"

    qa_answers.append(
        {
            "question": str(pending.get("question", f"Вопрос {qa_index + 1}")),
            "question_id": int(pending.get("question_id", qa_index + 1)),
            "answer": answer_text,
        }
    )
    qa_index += 1
    await state.update_data(qa_answers=qa_answers, qa_index=qa_index, pending_answer_review={})

    questions = analysis.get("follow_up_questions", []) if isinstance(analysis, dict) else []
    if qa_index < len(questions):
        await message.answer(_question_prompt(analysis, qa_index, lang), reply_markup=_question_reply_markup(analysis, qa_index))
        return

    merged_answers = "\n".join(
        f"{idx + 1}. {row.get('question', '-')}: {row.get('answer', '-')}"
        for idx, row in enumerate(qa_answers)
        if isinstance(row, dict)
    )
    await state.update_data(answers_text=merged_answers)
    if quick_report_after_questions or user_mode == "fast":
        await _build_and_send_report(message, state, lang)
        return
    await _start_barriers_module(message, state, lang)


@router.message(CareerFlow.waiting_for_answers, F.text)
async def handle_answers_text(message: Message, state: FSMContext) -> None:
    await process_answers_input(message, state, message.text or "")


@router.message(CareerFlow.waiting_for_post_result_action, F.text.in_(ALL_RESULT_ACTIONS))
async def handle_post_result_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    if not data.get("final_report_generated"):
        await message.answer(t(lang, "generation_lock_message"))
        return

    report = data.get("final_report") or {}
    chunks = data.get("report_chunks") or report_chunks(report, lang)
    action = (message.text or "").strip()
    await _track_event(message, state, "result_action_clicked", action=action)

    if action in {RESULT_REBUILD, "➕ Добавить детали"}:
        await state.set_state(CareerFlow.WAITING_ROUTE_CHANGES)
        await message.answer(t(lang, "route_changes_prompt"), reply_markup=result_actions_keyboard())
        return

    if action == RESULT_DETAILS:
        await state.set_state(CareerFlow.SHOWING_DETAILS)
        await message.answer(t(lang, "details_intro"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("layers", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("not_reset", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("translation", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("bridges", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("barrier", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("integration", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("decision", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("month_roadmap", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("week", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("today", "-"), reply_markup=result_actions_keyboard())
        await state.set_state(CareerFlow.FINAL_READY)
        await _track_event(message, state, "details_opened")
        return

    if action == RESULT_FIX_CV:
        await state.set_state(CareerFlow.CV_REVIEW_WAITING_FILE)
        await message.answer(t(lang, "offer_resume_reply"), reply_markup=resume_wait_keyboard())
        return

    if action == RESULT_KEYWORDS:
        await state.set_state(CareerFlow.KEYWORDS_MODE)
        await message.answer(t(lang, "show_keywords_reply"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("market", "-"), reply_markup=result_actions_keyboard())
        await message.answer(chunks.get("translation", "-"), reply_markup=result_actions_keyboard())
        await state.set_state(CareerFlow.FINAL_READY)
        await _track_event(message, state, "keywords_opened")
        return

    if action == RESULT_ANALYZE_FEARS:
        await state.set_state(CareerFlow.BARRIER_ANALYSIS_MENU)
        await message.answer(t(lang, "barrier_practical_intro"), reply_markup=practical_barrier_keyboard())
        await message.answer(chunks.get("barrier", "-"), reply_markup=practical_barrier_keyboard())
        await _track_event(message, state, "barrier_analysis_opened")
        return

    if action == RESULT_SUPPORT:
        await state.set_state(CareerFlow.SUPPORT_OFFER)
        await message.answer(_build_system_offer_text(data), reply_markup=support_mode_keyboard())
        await message.answer(t(lang, "support_free_hint"), reply_markup=support_mode_keyboard())
        await _track_event(message, state, "support_offer_opened")
        return

    if action == RESULT_THINK:
        await state.set_state(CareerFlow.THINKING_REMINDER)
        await message.answer(t(lang, "offer_think_reply"), reply_markup=think_reminder_keyboard())
        await _track_event(message, state, "thinking_mode_opened")
        return

    await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())


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
    if not change_text:
        await message.answer(t(lang, "route_changes_prompt"), reply_markup=result_actions_keyboard())
        return

    await state.set_state(CareerFlow.REBUILDING_ROUTE)
    await message.answer(t(lang, "route_rebuild_progress"), reply_markup=result_actions_keyboard())

    report = await ai_client.build_report(
        (data.get("story_text") or "").strip(),
        data.get("story_analysis") or {},
        ((data.get("answers_text") or "").strip() + "\n\nИзменения пользователя:\n" + change_text).strip(),
        resume_analysis=data.get("resume_analysis") or {},
        selected_barriers=data.get("selected_barriers") or [],
        selected_fears=data.get("selected_fears") or [],
        selected_psych_markers=data.get("selected_psych_markers") or [],
        selected_energy_sources=data.get("selected_energy_sources") or [],
        selected_career_priorities=data.get("selected_career_priorities") or [],
        language=lang,
    )
    chunks = report_chunks(report, lang)
    await state.update_data(final_report=report, report_chunks=chunks, final_report_generated=True)
    await state.set_state(CareerFlow.FINAL_READY)
    await message.answer(t(lang, "route_rebuild_result_intro"), reply_markup=result_actions_keyboard())
    await message.answer(build_telegram_summary(report), reply_markup=result_actions_keyboard())


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


@router.message(CareerFlow.SUPPORT_OFFER, F.text)
async def support_offer_fallback(message: Message, state: FSMContext) -> None:
    lang = _user_language(await state.get_data())
    await message.answer(t(lang, "support_mode_fallback"), reply_markup=support_mode_keyboard())