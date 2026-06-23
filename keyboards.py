from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


LANG_RU = "ru"
LANG_BE = "be"
LANG_RU_BUTTON = "Русский"
LANG_BE_BUTTON = "Беларуская"
LANG_BUTTON_TO_CODE = {
    LANG_RU_BUTTON: LANG_RU,
    LANG_BE_BUTTON: LANG_BE,
}

CONFIRM_YES = "✅ Да, использовать"
CONFIRM_EDIT = "✍️ Исправить текстом"
CONFIRM_RETRY = "🔁 Перезаписать"
CONFIRM_YES_BE = "Так, выкарыстаць"
CONFIRM_EDIT_BE = "Выправіць тэкст"
CONFIRM_RETRY_BE = "Запісаць нанова"

INPUT_TEXT = "✍️ Написать историю"
INPUT_VOICE = "🎙️ Рассказать голосом"
INPUT_DONT_KNOW = "🧭 Не знаю, с чего начать"

PACE_FAST = "⚡ Быстро и по делу"
PACE_NORMAL = "🧭 Спокойно по шагам"
PACE_SUPPORT = "🧠 С поддержкой, я тревожусь"
PACE_VOICE = "🎙 Хочу голосом"

ROUTE_FIND_JOB = "Найти работу"
ROUTE_SWITCH_FIELD = "Сменить сферу"
ROUTE_REPACK_EXPERIENCE = "Перепаковать опыт"
ROUTE_UNKNOWN = "Я не понимаю, кем могу быть теперь"

VOICE_PACE_FAST = "⚡ Быстро"
VOICE_PACE_NORMAL = "🧭 Спокойно"
VOICE_PACE_SUPPORT = "🧠 С поддержкой"

SHORT_NEED_JOB = "💸 Нужна работа срочно"
SHORT_NO_DIRECTION = "🧭 Не понимаю, кем могу быть"
SHORT_LANGUAGE = "🌍 Мешает язык"
SHORT_FEAR = "🧠 Мешает страх"
SHORT_TIRED = "😞 Устал(а), нет сил"
SHORT_RESUME = "📄 Хочу начать с резюме"

RESUME_UPLOAD = "📄 Загрузить резюме"
RESUME_SKIP = "➡️ Продолжить без резюме"
RESUME_SEND = "📄 Пришлю резюме"
RESUME_CONTINUE = "➡️ Продолжить без резюме"

PSYCH_BARRIER_OPTIONS = [
    "Боюсь отказов",
    "Боюсь выглядеть глупо",
    "Потерял(а) уверенность",
    "Хаос в голове",
    "Не понимаю, с чего начать",
    "Откладываю",
    "Избегаю откликов",
    "Начинаю и бросаю",
    "Постоянно меняю решение",
    "Жду идеального плана",
    "Дети",
    "Деньги",
    "Язык",
    "Здоровье",
    "Документы",
    "Усталость",
    "Нет поддержки",
]
PSYCH_BARRIER_DONE = "✅ Отметил(а), что мешает"
PSYCH_SKIP = "✅ Пропустить барьеры"

BARRIER_GROUP_INTERNAL = "🧠 Внутреннее состояние"
BARRIER_GROUP_BEHAVIOR = "🚶 Поведение"
BARRIER_GROUP_LIFE = "🌍 Жизненные обстоятельства"
BARRIER_GROUP_MORE = "➕ Больше вариантов"

WORK_FORMAT_OPTIONS = [
    "📄 Больше с документами",
    "👥 Больше с людьми",
    "⚖️ 50/50",
    "🚫 Лучше без активных продаж",
    "✅ Могу общаться, если есть понятные правила",
]

SUPPORT_OPTIONS = [
    "👨‍👩‍👧 Есть семья/партнёр",
    "👥 Есть друзья",
    "💼 Есть профессиональные контакты",
    "🌫 Почти нет поддержки",
    "🧭 Нужна помощь с адаптацией",
]
SUPPORT_DONE = "✅ Поддержка выбрана"

SKILLER_DONE = "🚀 Сделаю сегодня"
SKILLER_NOT_DONE = "😬 Слишком сложно"
SKILLER_REASON_FORGOT = "🔽 Дай проще"
SKILLER_REASON_SCARED = "❓ Не понимаю зачем"
SKILLER_REASON_HARD = "Сложно"
SKILLER_REASON_NO_TIME = "Не было времени"

RESULT_DETAILS = "📘 Подробнее"
RESULT_FIX_CV = "📄 Исправить резюме"
RESULT_KEYWORDS = "🔍 Ключевые слова вакансий"
RESULT_REBUILD = "🔄 Внести изменения"
RESULT_ANALYZE_FEARS = "🧠 Разобрать барьеры"
RESULT_SUPPORT = "🤝 Сопровождение в боте"
RESULT_THINK = "🤔 Хочу подумать"

RESULT_DOWNLOAD_PDF = "📄 Скачать PDF"
ANSWER_RETRY = "✍️ Ответить заново"
ANSWER_SKIP = "⏭️ Пропустить этот вопрос"
ANSWER_KEEP = "✅ Оставить как есть"

BARRIER_DETAIL_FEAR_REJECTION = "😰 Страх отказа"
BARRIER_DETAIL_MONEY = "💸 Страх за деньги"
BARRIER_DETAIL_CHAOS = "🧩 Хаос в голове"
BARRIER_DETAIL_FIRST_STEP = "🪜 Не понимаю первый шаг"
BARRIER_DETAIL_BACK = "↩️ Назад к карте"

CV_REVIEW_BULLETS = "🧩 Переписать bullet points"
CV_REVIEW_LETTER = "✉️ Черновик сопроводительного"
CV_REVIEW_BACK = "↩️ Назад к карте"
RESULT_UPLOAD_RESUME = RESULT_FIX_CV
RESULT_OTHER_PROF = "💼 Показать альтернативы"
RESULT_MONTH_PLAN = "📅 План на месяц"
RESULT_TODAY_STEP = "🚀 Сделать первый шаг"
RESULT_MY_MAP = "🗺️ Моя карта: неделя/месяц"
SUPPORT_BACK_TO_MAP = "↩️ Назад к карте"
RESULT_CV_ROUTE = "📄 Сделать CV под этот маршрут"
RESULT_BACKUP_ROUTE = "🧭 Показать запасной маршрут"
RESULT_FEAR_CYCLE = "🧠 Разобрать страх отказов"
RESULT_PLAN_7 = "📆 Дать план на 7 дней"
RESULT_COVER_LETTER = "✉️ Написать сопроводительное письмо"
RESULT_AGREE = "👍 Согласен"
RESULT_DOUBTS = "🤔 Есть сомнения"

OFFER_CV = "📄 Хочу разбор CV"
OFFER_CONSULT = "🧭 Хочу карьерную консультацию"
OFFER_SUPPORT = "🚀 Хочу сопровождение"
OFFER_DETAILS = "📘 Сначала посмотреть подробный разбор"
OFFER_THINK = "🤔 Хочу подумать"
OFFER_REMIND = "🔔 Напомнить через 2 дня"

PRACTICAL_STEP = "🚶 Дать практический шаг"
PRACTICAL_DEEP = "🧠 Всё же разобрать страх"
PRACTICAL_BACK = "↩️ Назад к карте"

RESTART = "🔁 Пройти заново"
RESTART_BE = "🔁 Прайсці нанова"

ALL_CONFIRM_YES = {CONFIRM_YES, CONFIRM_YES_BE}
ALL_CONFIRM_EDIT = {CONFIRM_EDIT, CONFIRM_EDIT_BE}
ALL_CONFIRM_RETRY = {CONFIRM_RETRY, CONFIRM_RETRY_BE}
ALL_RESTART = {RESTART, RESTART_BE}
ALL_INPUT_TEXT = {INPUT_TEXT}
ALL_INPUT_VOICE = {INPUT_VOICE}
ALL_INPUT_DONT_KNOW = {INPUT_DONT_KNOW}
ALL_PACE_OPTIONS = {PACE_FAST, PACE_NORMAL, PACE_SUPPORT, PACE_VOICE}
ALL_ROUTE_OPTIONS = {ROUTE_FIND_JOB, ROUTE_SWITCH_FIELD, ROUTE_REPACK_EXPERIENCE, ROUTE_UNKNOWN}
ALL_VOICE_PACE_OPTIONS = {VOICE_PACE_FAST, VOICE_PACE_NORMAL, VOICE_PACE_SUPPORT}
ALL_SHORT_STORY_OPTIONS = {SHORT_NEED_JOB, SHORT_NO_DIRECTION, SHORT_LANGUAGE, SHORT_FEAR, SHORT_TIRED, SHORT_RESUME}
ALL_SUPPORT_OPTIONS = set(SUPPORT_OPTIONS)
ALL_SUPPORT_MULTI_ACTIONS = set(SUPPORT_OPTIONS) | {SUPPORT_DONE}
ALL_RESUME_UPLOAD = {RESUME_UPLOAD, RESUME_SEND}
ALL_RESUME_SKIP = {RESUME_SKIP, RESUME_CONTINUE}
ALL_PSYCH_BARRIER_OPTIONS = set(PSYCH_BARRIER_OPTIONS)
ALL_PSYCH_BARRIER_DONE = {PSYCH_BARRIER_DONE}
ALL_PSYCH_GROUP_OPTIONS = {BARRIER_GROUP_INTERNAL, BARRIER_GROUP_BEHAVIOR, BARRIER_GROUP_LIFE, BARRIER_GROUP_MORE, PSYCH_SKIP}
ALL_RESULT_ACTIONS = {
    RESULT_DETAILS,
    RESULT_FIX_CV,
    RESULT_KEYWORDS,
    RESULT_REBUILD,
    RESULT_ANALYZE_FEARS,
    RESULT_SUPPORT,
    RESULT_THINK,
    "➕ Добавить детали",
}
ALL_ANSWER_REVIEW_ACTIONS = {ANSWER_RETRY, ANSWER_SKIP, ANSWER_KEEP}
ALL_BARRIER_DETAIL_ACTIONS = {
    BARRIER_DETAIL_FEAR_REJECTION,
    BARRIER_DETAIL_MONEY,
    BARRIER_DETAIL_CHAOS,
    BARRIER_DETAIL_FIRST_STEP,
    BARRIER_DETAIL_BACK,
}
ALL_CV_REVIEW_ACTIONS = {CV_REVIEW_BULLETS, CV_REVIEW_LETTER, CV_REVIEW_BACK}
ALL_SKILLER_CHECK = {SKILLER_DONE, SKILLER_NOT_DONE}
ALL_SKILLER_REASONS = {
    SKILLER_REASON_FORGOT,
    SKILLER_REASON_SCARED,
    SKILLER_REASON_HARD,
    SKILLER_REASON_NO_TIME,
}
ALL_OFFER_ACTIONS = {OFFER_CV, OFFER_CONSULT, OFFER_SUPPORT, OFFER_DETAILS, OFFER_THINK, OFFER_REMIND}
ALL_PRACTICAL_BARRIER_ACTIONS = {PRACTICAL_STEP, PRACTICAL_DEEP, PRACTICAL_BACK}
ALL_SUPPORT_MODE_ACTIONS = {RESULT_MY_MAP, RESULT_TODAY_STEP, SUPPORT_BACK_TO_MAP}


def language_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=LANG_RU_BUTTON)],
            [KeyboardButton(text=LANG_BE_BUTTON)],
        ],
        resize_keyboard=True,
    )


def confirm_transcription_keyboard(lang: str = LANG_RU) -> ReplyKeyboardMarkup:
    if lang == LANG_BE:
        yes, edit, retry = CONFIRM_YES_BE, CONFIRM_EDIT_BE, CONFIRM_RETRY_BE
    else:
        yes, edit, retry = CONFIRM_YES, CONFIRM_EDIT, CONFIRM_RETRY
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=yes)],
            [KeyboardButton(text=edit)],
            [KeyboardButton(text=retry)],
        ],
        resize_keyboard=True,
    )


def input_method_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=INPUT_TEXT)],
            [KeyboardButton(text=INPUT_VOICE)],
            [KeyboardButton(text=INPUT_DONT_KNOW)],
        ],
        resize_keyboard=True,
    )


def pace_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=PACE_FAST)],
            [KeyboardButton(text=PACE_NORMAL)],
            [KeyboardButton(text=PACE_SUPPORT)],
            [KeyboardButton(text=PACE_VOICE)],
        ],
        resize_keyboard=True,
    )


def route_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ROUTE_FIND_JOB)],
            [KeyboardButton(text=ROUTE_SWITCH_FIELD)],
            [KeyboardButton(text=ROUTE_REPACK_EXPERIENCE)],
            [KeyboardButton(text=ROUTE_UNKNOWN)],
        ],
        resize_keyboard=True,
    )


def voice_pace_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=VOICE_PACE_FAST)],
            [KeyboardButton(text=VOICE_PACE_NORMAL)],
            [KeyboardButton(text=VOICE_PACE_SUPPORT)],
        ],
        resize_keyboard=True,
    )


def short_story_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SHORT_NEED_JOB), KeyboardButton(text=SHORT_NO_DIRECTION)],
            [KeyboardButton(text=SHORT_LANGUAGE), KeyboardButton(text=SHORT_FEAR)],
            [KeyboardButton(text=SHORT_TIRED), KeyboardButton(text=SHORT_RESUME)],
            [KeyboardButton(text=INPUT_TEXT), KeyboardButton(text=INPUT_VOICE)],
        ],
        resize_keyboard=True,
    )


def question_options_keyboard(options: list[str]) -> ReplyKeyboardMarkup | None:
    cleaned = [str(item).strip() for item in options if str(item).strip()]
    if not cleaned:
        return None

    # Keep explicit completion actions visible as the last dedicated row.
    done_options = [item for item in cleaned if "готово" in item.lower()]
    regular_options = [item for item in cleaned if item not in done_options]

    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for item in regular_options[:14]:
        row.append(KeyboardButton(text=item))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    if done_options:
        rows.append([KeyboardButton(text=done_options[0])])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def restart_keyboard(lang: str = LANG_RU) -> ReplyKeyboardMarkup:
    button = RESTART_BE if lang == LANG_BE else RESTART
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=button)],
        ],
        resize_keyboard=True,
    )


def resume_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RESUME_UPLOAD)],
            [KeyboardButton(text=RESUME_SKIP)],
        ],
        resize_keyboard=True,
    )


def resume_wait_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RESUME_SEND)],
            [KeyboardButton(text=RESUME_CONTINUE)],
        ],
        resize_keyboard=True,
    )


def barriers_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BARRIER_GROUP_INTERNAL)],
        [KeyboardButton(text=BARRIER_GROUP_BEHAVIOR)],
        [KeyboardButton(text=BARRIER_GROUP_LIFE)],
        [KeyboardButton(text=BARRIER_GROUP_MORE)],
        [KeyboardButton(text=PSYCH_SKIP)],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def barriers_group_keyboard(group: str) -> ReplyKeyboardMarkup:
    if group == BARRIER_GROUP_INTERNAL:
        options = PSYCH_BARRIER_OPTIONS[:5]
    elif group == BARRIER_GROUP_BEHAVIOR:
        options = PSYCH_BARRIER_OPTIONS[5:10]
    elif group == BARRIER_GROUP_LIFE:
        options = PSYCH_BARRIER_OPTIONS[10:]
    else:
        options = PSYCH_BARRIER_OPTIONS
    rows = [[KeyboardButton(text=item)] for item in options]
    rows.append([KeyboardButton(text=PSYCH_BARRIER_DONE)])
    rows.append([KeyboardButton(text=PSYCH_SKIP)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def skiller_check_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SKILLER_DONE), KeyboardButton(text=SKILLER_NOT_DONE)],
        ],
        resize_keyboard=True,
    )


def skiller_reason_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SKILLER_REASON_FORGOT), KeyboardButton(text=SKILLER_REASON_SCARED)],
            [KeyboardButton(text=SKILLER_REASON_HARD), KeyboardButton(text=SKILLER_REASON_NO_TIME)],
        ],
        resize_keyboard=True,
    )


def result_actions_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RESULT_DETAILS)],
            [KeyboardButton(text=RESULT_FIX_CV), KeyboardButton(text=RESULT_KEYWORDS)],
            [KeyboardButton(text=RESULT_REBUILD)],
            [KeyboardButton(text=RESULT_ANALYZE_FEARS)],
            [KeyboardButton(text=RESULT_SUPPORT), KeyboardButton(text=RESULT_THINK)],
            [KeyboardButton(text=RESTART)],
        ],
        resize_keyboard=True,
    )


def feedback_keyboard() -> ReplyKeyboardMarkup:
    return result_actions_keyboard()


def first_step_keyboard() -> ReplyKeyboardMarkup:
    return result_actions_keyboard()


def offer_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=OFFER_CV), KeyboardButton(text=OFFER_CONSULT)],
            [KeyboardButton(text=OFFER_SUPPORT)],
            [KeyboardButton(text=OFFER_DETAILS), KeyboardButton(text=OFFER_THINK)],
            [KeyboardButton(text=OFFER_REMIND)],
        ],
        resize_keyboard=True,
    )


def support_mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RESULT_MY_MAP)],
            [KeyboardButton(text=RESULT_TODAY_STEP)],
            [KeyboardButton(text=SUPPORT_BACK_TO_MAP)],
        ],
        resize_keyboard=True,
    )


def answer_review_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ANSWER_RETRY)],
            [KeyboardButton(text=ANSWER_SKIP), KeyboardButton(text=ANSWER_KEEP)],
        ],
        resize_keyboard=True,
    )


def barrier_analysis_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BARRIER_DETAIL_FEAR_REJECTION), KeyboardButton(text=BARRIER_DETAIL_MONEY)],
            [KeyboardButton(text=BARRIER_DETAIL_CHAOS), KeyboardButton(text=BARRIER_DETAIL_FIRST_STEP)],
            [KeyboardButton(text=BARRIER_DETAIL_BACK)],
        ],
        resize_keyboard=True,
    )


def cv_review_actions_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CV_REVIEW_BULLETS), KeyboardButton(text=CV_REVIEW_LETTER)],
            [KeyboardButton(text=CV_REVIEW_BACK)],
        ],
        resize_keyboard=True,
    )


def interview_work_format_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=item)] for item in WORK_FORMAT_OPTIONS], resize_keyboard=True)


def interview_support_keyboard() -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=item)] for item in SUPPORT_OPTIONS]
    rows.append([KeyboardButton(text=SUPPORT_DONE)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def think_reminder_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔔 Да, напомнить через 2 дня")],
            [KeyboardButton(text="Нет, я сам/сама вернусь")],
            [KeyboardButton(text="↩️ Назад к карте")],
        ],
        resize_keyboard=True,
    )


def practical_barrier_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=PRACTICAL_STEP), KeyboardButton(text=PRACTICAL_DEEP)],
            [KeyboardButton(text=PRACTICAL_BACK)],
        ],
        resize_keyboard=True,
    )
