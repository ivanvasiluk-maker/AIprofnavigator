from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


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
PACE_NORMAL = "🧭 Нормальный разбор"
PACE_SUPPORT = "🔎 Глубокий маршрут"
PACE_VOICE = "🎙 Хочу голосом"

ROUTE_FIND_JOB = "Найти работу"
ROUTE_SWITCH_FIELD = "Сменить сферу"
ROUTE_REPACK_EXPERIENCE = "Перепаковать опыт"
ROUTE_UNKNOWN = "Я не понимаю, кем могу быть теперь"

VOICE_PACE_FAST = "⚡ Быстро"
VOICE_PACE_NORMAL = "🧭 Нормально"
VOICE_PACE_SUPPORT = "🔎 Глубоко"

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
STORY_CONFIRM_OK = "✅ Да, вы поняли верно"
STORY_CONFIRM_FIX = "✍️ Хочу поправить"

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
RESULT_OPEN_FULL_REPORT = "📄 Открыть полный разбор"
RESULT_SELF_EXPLORE = "🔎 Продолжить самоисследование"
RESULT_DO_STEPS = "🚀 Делать шаги в боте"
RESULT_CLARIFY = "✍️ Немного уточнить"
RESULT_SPECIALIST = "🧭 Продолжить со специалистом"
RESULT_SUPPORT_GROUP = "👥 В группу поддержки поиска работы"
RESULT_BACK_TO_MENU = "↩️ К выбору сценария"
RESULT_START_FIRST_STEP = "🧭 Начать первый шаг"
RESULT_FIX_FACT_OR_PRIORITY = "✍️ Исправить факт или приоритет"
RESULT_UPLOAD_OR_EDIT_RESUME = "📄 Загрузить / доработать резюме"
RESULT_ANALYZE_MARKET = "🔎 Разобрать рынок и вакансии"
RESULT_SPECIALIST_EXPLICIT = "👤 Разобрать со специалистом"
RESULT_GROUP_EXPLICIT = "👥 Найти группу / сообщество"
PDF_FALLBACK_STEPS = "🧭 Продолжить по шагам"
PDF_FALLBACK_CLARIFY = "✍️ Уточнить карту"
PDF_FALLBACK_SPECIALIST = "👤 Разобрать со специалистом"
STEP_OPEN_TODAY = "📅 Открыть текущий день"
STEP_DONE = "✅ Сделал"
STEP_NOT_DONE = "❌ Не сделал"
STEP_BARRIERS = "🧩 Какие есть барьеры"
STEP_NEXT_DAY = "➡️ Следующий день"
STEP_DONE_USER = "Сделал"
STEP_TOO_HARD = "Слишком сложно"
STEP_MAKE_EASIER = "Сделать проще"
STEP_OTHER_STEP = "Другой шаг"

RESULT_DOWNLOAD_PDF = "📄 Скачать PDF"
ANSWER_RETRY = "✍️ Ответить заново"
ANSWER_SKIP = "⏭️ Пропустить этот вопрос"
ANSWER_KEEP = "✅ Оставить как есть"
ANSWER_CONTEXT_YES = "✅ Да, именно так"
ANSWER_CONTEXT_NO = "↩️ Нет, выбрать другой ответ"

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

MAP_CHECK_TRUE = "✅ Всё похоже на правду"
MAP_CHECK_FIX_FACT = "✍️ Исправить один факт"
MAP_CHECK_CHANGE_PRIORITY = "🧭 Изменить приоритет"
MAP_CHECK_DISAGREE_ROUTE = "❓ Я не согласен с маршрутом"

ROUTE_CHOICE_STABLE = "🧱 Сначала стабильная работа"
ROUTE_CHOICE_PRIVATE = "🔨 Хочу постепенно выйти на частные заказы"
ROUTE_CHOICE_RETRAIN = "🎓 Рассматриваю переобучение"
ROUTE_CHOICE_HELP = "🧭 Пока не знаю — помоги выбрать"
ROUTE_CHOICE_CLOSE = "Этот маршрут ближе"
ROUTE_CHOICE_OTHER = "Показать другой"
ROUTE_CHOICE_NO_LOGIC = "Не согласен с логикой"

CAREER_SWITCH_REASON_DISLIKE = "Не нравится сама сфера"
CAREER_SWITCH_REASON_MONEY = "Кажется, что здесь мало денег"
CAREER_SWITCH_REASON_DOCS_LANG = "Нет документов / языка"
CAREER_SWITCH_REASON_GROWTH_UNKNOWN = "Хочу рост, но пока не знаю куда"
CAREER_SWITCH_REASON_OTHER = "Другое"
CAREER_SWITCH_REASON_OPTIONS = [
    CAREER_SWITCH_REASON_DISLIKE,
    CAREER_SWITCH_REASON_MONEY,
    CAREER_SWITCH_REASON_DOCS_LANG,
    CAREER_SWITCH_REASON_GROWTH_UNKNOWN,
    CAREER_SWITCH_REASON_OTHER,
]

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
ALL_ROUTE_CHOICE_ACTIONS = {
    ROUTE_CHOICE_STABLE,
    ROUTE_CHOICE_PRIVATE,
    ROUTE_CHOICE_RETRAIN,
    ROUTE_CHOICE_HELP,
    ROUTE_CHOICE_CLOSE,
    ROUTE_CHOICE_OTHER,
    ROUTE_CHOICE_NO_LOGIC,
}
ALL_VOICE_PACE_OPTIONS = {VOICE_PACE_FAST, VOICE_PACE_NORMAL, VOICE_PACE_SUPPORT}
ALL_SHORT_STORY_OPTIONS = {SHORT_NEED_JOB, SHORT_NO_DIRECTION, SHORT_LANGUAGE, SHORT_FEAR, SHORT_TIRED, SHORT_RESUME}
ALL_SUPPORT_OPTIONS = set(SUPPORT_OPTIONS)
ALL_SUPPORT_MULTI_ACTIONS = set(SUPPORT_OPTIONS) | {SUPPORT_DONE}
ALL_RESUME_UPLOAD = {RESUME_UPLOAD, RESUME_SEND}
ALL_RESUME_SKIP = {RESUME_SKIP, RESUME_CONTINUE}
ALL_STORY_CONFIRM_ACTIONS = {STORY_CONFIRM_OK, STORY_CONFIRM_FIX}
ALL_PSYCH_BARRIER_OPTIONS = set(PSYCH_BARRIER_OPTIONS)
ALL_PSYCH_BARRIER_DONE = {PSYCH_BARRIER_DONE}
ALL_PSYCH_GROUP_OPTIONS = {BARRIER_GROUP_INTERNAL, BARRIER_GROUP_BEHAVIOR, BARRIER_GROUP_LIFE, BARRIER_GROUP_MORE, PSYCH_SKIP}
ALL_RESULT_ACTIONS = {
    RESULT_OPEN_FULL_REPORT,
    RESULT_SELF_EXPLORE,
    RESULT_DO_STEPS,
    PDF_FALLBACK_STEPS,
    RESULT_CLARIFY,
    PDF_FALLBACK_CLARIFY,
    RESULT_FIX_CV,
    RESULT_KEYWORDS,
    RESULT_SPECIALIST,
    PDF_FALLBACK_SPECIALIST,
    RESULT_SUPPORT_GROUP,
    RESULT_START_FIRST_STEP,
    RESULT_FIX_FACT_OR_PRIORITY,
    RESULT_UPLOAD_OR_EDIT_RESUME,
    RESULT_ANALYZE_MARKET,
    RESULT_SPECIALIST_EXPLICIT,
    RESULT_GROUP_EXPLICIT,
    MAP_CHECK_TRUE,
    MAP_CHECK_FIX_FACT,
    MAP_CHECK_CHANGE_PRIORITY,
    MAP_CHECK_DISAGREE_ROUTE,
}
ALL_SELF_EXPLORE_ACTIONS = {
    RESULT_DETAILS,
    RESULT_FIX_CV,
    RESULT_KEYWORDS,
    RESULT_REBUILD,
    RESULT_CLARIFY,
    RESULT_BACK_TO_MENU,
}
ALL_STEP_TRACKING_ACTIONS = {
    STEP_OPEN_TODAY,
    STEP_DONE,
    STEP_NOT_DONE,
    STEP_BARRIERS,
    STEP_NEXT_DAY,
    STEP_DONE_USER,
    STEP_TOO_HARD,
    STEP_MAKE_EASIER,
    STEP_OTHER_STEP,
    RESULT_BACK_TO_MENU,
}
ALL_ANSWER_REVIEW_ACTIONS = {
    ANSWER_RETRY,
    ANSWER_SKIP,
    ANSWER_KEEP,
    ANSWER_CONTEXT_YES,
    ANSWER_CONTEXT_NO,
}
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
ALL_ROUTE_CHOICE_ACTIONS = {
    ROUTE_CHOICE_STABLE,
    ROUTE_CHOICE_PRIVATE,
    ROUTE_CHOICE_RETRAIN,
    ROUTE_CHOICE_HELP,
    ROUTE_CHOICE_CLOSE,
    ROUTE_CHOICE_OTHER,
    ROUTE_CHOICE_NO_LOGIC,
}
ALL_CAREER_SWITCH_REASON_OPTIONS = set(CAREER_SWITCH_REASON_OPTIONS)


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


def story_confirmation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=STORY_CONFIRM_OK)],
            [KeyboardButton(text=STORY_CONFIRM_FIX)],
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
            [KeyboardButton(text=RESULT_START_FIRST_STEP)],
            [KeyboardButton(text=RESULT_FIX_FACT_OR_PRIORITY)],
            [KeyboardButton(text=RESULT_UPLOAD_OR_EDIT_RESUME)],
            [KeyboardButton(text=RESULT_ANALYZE_MARKET)],
            [KeyboardButton(text=RESULT_SPECIALIST_EXPLICIT)],
            [KeyboardButton(text=RESULT_GROUP_EXPLICIT)],
            [KeyboardButton(text=RESULT_DO_STEPS)],
            [KeyboardButton(text=RESULT_CLARIFY)],
            [KeyboardButton(text=RESULT_FIX_CV)],
            [KeyboardButton(text=RESULT_KEYWORDS)],
            [KeyboardButton(text=RESULT_SPECIALIST)],
            [KeyboardButton(text=RESULT_SUPPORT_GROUP)],
            [KeyboardButton(text=RESTART)],
        ],
        resize_keyboard=True,
    )


def pdf_fallback_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RESULT_OPEN_FULL_REPORT)],
            [KeyboardButton(text=PDF_FALLBACK_STEPS)],
            [KeyboardButton(text=PDF_FALLBACK_CLARIFY)],
            [KeyboardButton(text=PDF_FALLBACK_SPECIALIST)],
        ],
        resize_keyboard=True,
    )


def map_validation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAP_CHECK_TRUE)],
            [KeyboardButton(text=MAP_CHECK_FIX_FACT)],
            [KeyboardButton(text=MAP_CHECK_CHANGE_PRIORITY)],
            [KeyboardButton(text=MAP_CHECK_DISAGREE_ROUTE)],
        ],
        resize_keyboard=True,
    )


def self_exploration_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RESULT_DETAILS)],
            [KeyboardButton(text=RESULT_FIX_CV), KeyboardButton(text=RESULT_KEYWORDS)],
            [KeyboardButton(text=RESULT_REBUILD), KeyboardButton(text=RESULT_CLARIFY)],
            [KeyboardButton(text=RESULT_START_FIRST_STEP)],
            [KeyboardButton(text=RESULT_FIX_FACT_OR_PRIORITY)],
            [KeyboardButton(text=RESULT_UPLOAD_OR_EDIT_RESUME)],
            [KeyboardButton(text=RESULT_ANALYZE_MARKET)],
            [KeyboardButton(text=RESULT_SPECIALIST_EXPLICIT)],
            [KeyboardButton(text=RESULT_GROUP_EXPLICIT)],
            [KeyboardButton(text=RESULT_BACK_TO_MENU)],
        ],
        resize_keyboard=True,
    )


def step_tracking_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=STEP_OPEN_TODAY)],
            [KeyboardButton(text=STEP_DONE_USER), KeyboardButton(text=STEP_TOO_HARD)],
            [KeyboardButton(text=STEP_MAKE_EASIER), KeyboardButton(text=STEP_OTHER_STEP)],
            [KeyboardButton(text=STEP_DONE), KeyboardButton(text=STEP_NOT_DONE)],
            [KeyboardButton(text=STEP_BARRIERS), KeyboardButton(text=STEP_NEXT_DAY)],
            [KeyboardButton(text=RESULT_BACK_TO_MENU)],
        ],
        resize_keyboard=True,
    )


def telegram_link_keyboard(button_text: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, url=url)],
        ]
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


def route_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ROUTE_CHOICE_CLOSE), KeyboardButton(text=ROUTE_CHOICE_OTHER)],
            [KeyboardButton(text=ROUTE_CHOICE_HELP), KeyboardButton(text=ROUTE_CHOICE_NO_LOGIC)],
            [KeyboardButton(text=ROUTE_CHOICE_STABLE)],
            [KeyboardButton(text=ROUTE_CHOICE_PRIVATE)],
            [KeyboardButton(text=ROUTE_CHOICE_RETRAIN)],
        ],
        resize_keyboard=True,
    )


def career_switch_reason_keyboard() -> ReplyKeyboardMarkup | None:
    return question_options_keyboard(CAREER_SWITCH_REASON_OPTIONS)


def answer_review_keyboard(context_mismatch: bool = False) -> ReplyKeyboardMarkup:
    if context_mismatch:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=ANSWER_CONTEXT_YES), KeyboardButton(text=ANSWER_CONTEXT_NO)],
            ],
            resize_keyboard=True,
        )
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
