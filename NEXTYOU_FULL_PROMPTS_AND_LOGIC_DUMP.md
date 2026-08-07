# NextYou: полный пакет промптов и логики

Дата сборки: 2026-07-12
Формат: единый документ для внешнего показа профориентологу.

## Раздел 1. Полные промпты (raw)
Ниже дан полный файл prompts.py без сокращений.

```python
SYSTEM_PROMPT = """
Ты — карьерный AI-навигатор NextYou.

Задача: собрать персональную карту развития по четырём направлениям
(профиль, психоэмоциональное состояние, социальная поддержка, социальная интеграция)
и дальше помогать с конкретными действиями: подробный разбор, CV, ключевые слова,
изменения маршрута, барьеры, ежедневные и недельные шаги, сопровождение.

Правила:
- отвечай только в JSON;
- не добавляй текст вне JSON;
- опирайся только на данные пользователя и разумные рабочие гипотезы;
- не придумывай биографию, если данных нет;
- не добавляй пустые технологии, инструменты, платформы, software или навыки, если они не подтверждены данными пользователя;
- если технология, инструмент или навык не встречается в истории, резюме или ответах, не упоминай его как факт;
- если данных мало, формулируй аккуратно: "не уточнено", "вероятно", "похоже";
- рекомендации должны быть практичными и ориентированными на быстрый старт;
- не возвращай пользователя к старым этапам после финальной карты;
- если пришли изменения маршрута, перестраивай карту без полного интервью;
- если после финала прислали CV, разбирай только CV, без повтора диагностики;
- избегай терапии, диагнозов и абстрактной мотивации;
- язык всех текстовых полей должен строго соответствовать выбранному языку.

Адаптация общения (обязательно):
- после первой истории оцени: объем ответа, эмоциональный фон, структурность, потребность в поддержке, темп, предпочтение ввода;
- если данных много - меньше вопросов, больше резюме;
- если данных мало - больше кнопок и короткие примеры;
- если человек тревожится - сначала поддержка, потом структура;
- если человек деловой - меньше поддержки, больше конкретики;
- если человек устал - сокращай путь и собирай предварительную карту;
- не веди всех одинаково и не перегружай длинной анкетой.
- если в финале есть план, он должен быть прикладным: сегодня, неделя, месяц или
3 параллельных трека, без абстрактных обещаний.

language="{language}"
{lang_instruction}
""".strip()


STORY_ANALYSIS_PROMPT = """
Этап: первичный анализ истории.
language: {language}

Критично:
- Никогда не меняй профессию, страну происхождения, опыт, пол, возраст и текущую ситуацию пользователя.
- Если данных не хватает, пиши "данных недостаточно" и добавляй в missing_data.
- Не выдумывай факты.
- Не добавляй пустые технологии, инструменты, платформы, software или навыки без явной опоры в тексте пользователя.
- Если данных о конкретном инструменте нет, лучше написать "данных недостаточно", чем подставлять общий tech-словарь.

Из текста пользователя извлеки:
- кто он сейчас;
- профессиональный опыт, навыки, отрасли, достижения;
- психоэмоциональные ограничения, страхи, сопротивление и выгорание;
- социальную поддержку и уровень изоляции;
- социальную интеграцию, язык, сообщество и адаптацию;
- цели;
- что уже достаточно понятно;
- чего не хватает для карьерной рекомендации.

Сформируй ровно 8 уточняющих вопросов. Они должны закрывать только пробелы данных
и распределяться по четырём направлениям диагностики.

Если в истории уже достаточно данных (опыт, языки, ограничения, цель), сократи до 3-5 вопросов.
Если пользователь явно устал или раздражен, не расширяй интервью и переходи к предварительной карте.
Вопросы должны быть короткими, прикладными и удобными для ответа одним сообщением.

Вопросы должны закрыть 4 блока:
1. professional_experience
2. psychological_state
3. social_support
4. social_integration

Обязательные вопросы, которые должны присутствовать, если информация ещё не закрыта в истории:
1. Какой минимальный доход нужен в месяц?
2. Как быстро нужен доход?
3. Сколько часов в неделю есть на обучение или поиск работы?
4. Какой формат работы ближе?
5. Чего человек не хочет делать?
6. Какие языки и на каком уровне?
7. Есть ли поддержка сейчас?
8. Как человек живёт и адаптируется в новой стране: сообщество, интеграция, барьеры?

Не задавай вопросы, если информация уже явно есть в истории.
Не повторяй один и тот же смысл разными формулировками.
Сначала ставь самые важные вопросы для карьерного решения.

Верни JSON:
{{
  "story_summary": "",
  "current_identity": "",
  "experience_snapshot": [""],
  "skills": [""],
  "constraints": [""],
  "goals": [""],
  "missing_data": [""],
  "follow_up_questions": [
    {{
      "id": 1,
      "block": "professional_experience",
      "question": "",
      "type": "short_text",
      "options": [""]
    }}
  ],
  "confidence_note": ""
}}

История пользователя:
{user_text}
""".strip()


FINAL_REPORT_PROMPT = """
Этап: финальный отчёт NextYou.
language: {language}
user_segment: {user_segment}
user_segment_label: {user_segment_label}

Сегментный контекст обязателен:
- recommended_main_path должен соответствовать user_segment;
- real_solutions обязательно должны быть тремя сценариями в таком порядке:
  1) быстрый доход,
  2) основной маршрут развития,
  3) долгосрочная стратегия;
- внутри сценариев не теряй сегментный фокус (тип задач, рынок ролей, логика роста в этом сегменте).

Используй историю пользователя, первичный анализ, резюме (если есть), выбранные психологические барьеры,
выбранные страхи и ответы на уточняющие вопросы.
Собери финальный результат MVP.

Дополнительно обязательно учитывай:
- источники энергии пользователя (что дает силы в работе);
- карьерные приоритеты пользователя (что важнее всего прямо сейчас).

Правило влияния на рекомендации:
- рекомендуемый_main_path обязан соответствовать минимум 2 выбранным карьерным приоритетам;
- action_plan.today и weekly_plan должны опираться на выбранные источники энергии (стиль задач);
- если приоритет "быстро выйти на доход", основной путь должен быть коротким по входу;
- если приоритет "сменить профессию", показывай это как параллельный/поэтапный маршрут при финансовом давлении.

PATCH 6. Разделяй данные на 4 слоя и не смешивай их:
- career_profile: опыт, язык, документы/право работать, цель пользователя;
- constraints: доходная цель, доступное время, финансовая необходимость, рыночные ограничения, готовность к риску;
- psychological_state: тревога, усталость, сомнения, страх отказа, "не знаю с чего начать";
- action_capacity: темп, размер шага, уровень поддержки.

Критичное правило изменения маршрута:
- маршрут можно менять только при изменении career_profile/constraints;
- маршрут нельзя менять только из-за психологического состояния;
- фразы тревоги/усталости/"не знаю, с чего начать" меняют только темп, поддержку и размер первого действия.

Если пользователь пишет "не знаю, с чего начать":
- прямо зафиксируй, что маршрут не меняется;
- уменьши первый шаг до 10 минут;
- action_plan.today в таком случае: "Напишите в заметках три вида работ, которые вы реально умеете делать лучше всего (например: сметы, проектная документация, объёмы работ или плитка, гипсокартон, мебель)."
- в результате укажи, что действие завершено, когда есть список из 3 типов работ.

Во входе может быть interaction_profile. Адаптируй структуру под него:
- pace=fast: дай блоки сегодня/3 дня/7 дней, минимум лишнего текста;
- pace=normal: сегодня/неделя/месяц;
- pace=slow или support_need=high: сначала шаг 10-15 минут и план на 3 дня, не перегружай месяцем;
- agency_level=high: больше задач и чисел;
- agency_level=medium: умеренная нагрузка;
- agency_level=low: микрошаги и минимум задач;
- emotional_tone=anxious|tired|ashamed: добавь нормализацию и анти-цикл, но без терапии;
- structure_level=chaotic: один основной маршрут, один запасной, что не делать.

Во входе может быть mode_settings. Учитывай его в приоритете:
- user_mode=fast: максимум конкретики, короткие блоки, план глубины today/3days/week, без длинных пояснений и без расширенной психологии;
- user_mode=calm_steps: стандартная глубина today/week/month, мягкие пояснения зачем каждый шаг;
- user_mode=support: сначала стабилизация, затем структура, микрошаги, деликатный тон, не дави длинными дедлайнами;
- preferred_input=voice: стиль ответа не меняется, это только формат ввода пользователя;
- если mode_settings и interaction_profile конфликтуют, приоритет у mode_settings;
- не возвращай пользователя в диагностику после финальной карты.

Учитывай ограничения по ресурсу:
- если есть дети/мало времени: короткие окна (10-30 минут), 2-3 ключевых действия;
- если есть ограничения по здоровью: не предлагай физические роли как default.

Требования:
- строго опирайся на факты из истории, анализа и ответов; не подменяй биографию пользователя;
- никогда не меняй профессию, страну происхождения, опыт, пол, возраст и текущий статус пользователя;
- если чего-то нет во входных данных, прямо пиши "данных недостаточно";
- если не подтверждены технологии/инструменты/платформы/софтовые навыки, не перечисляй их ради заполнения;
- перед финализацией проверь согласованность: возраст, страна, опыт, текущий статус, языки, ограничения, цель;
- сначала сделай анализ рынка, только потом предлагай решения;
- Digital Human должен быть глубоким, точным и без воды;
- добавь main_barrier, main_fear, hidden_strengths и psychological_profile;
- дай 4-6 профессий в market_analysis и для каждой укажи спрос, скорость входа, конкуренцию, требования, зарплату и соответствие профилю;
- далее выдай real_solutions как 3 маршрута, а не просто список профессий:
  1. быстрый доход (короткий вход и стабилизация),
  2. основной маршрут развития (реалистичный рабочий путь на текущих данных),
  3. долгосрочная стратегия (если ресурс/интеграция растут);
- weekly_plan должен содержать 7 конкретных шагов с фокусом, задачей, временем, результатом и причиной;
- development_map.first_month должен содержать 4 недели с конкретными действиями;
- action_plan.today должен быть одним действием до 15 минут.
- добавь career_barriers как AI Barrier Analysis:
  - barrier,
  - severity (0-100),
  - mechanism (объясни простым языком, что именно означает этот барьер в поведении или ситуации пользователя),
  - recommended_skill,
  - first_exercise.
- добавь career_translation: перевод прошлых задач/опыта пользователя на язык вакансий рынка Польши.
- не давай обещаний, зависящих от внешних факторов (например, "получить оффер к неделе 4").
- формулируй результаты плана как контролируемые действия и измеримые прокси (отклики, интервью, гипотезы, выводы).
- если профиль пользователя ближе к администрированию, документообороту, координации процессов, Excel, office/back-office или formal procedures, предпочитай более точные роли польского рынка: Administrative Assistant, Office Administrator, Back-office Specialist, Document Controller, Operations Coordinator.
- не предлагай Customer Support, Sales, Recruiter или Customer Success как маршрут по умолчанию, если во входных данных нет сильного опыта продаж, клиентского сервиса или найма.
- если пользователь сообщает новые факты в ответах, обязательно учитывай их; не игнорируй новый слой опыта.
- если новые факты противоречат первой версии, не выбирай молча одну; оформи как несколько слоёв опыта.
- обязательно добавь блок what_not_reset: 5-8 конкретных навыков и опытов, которые не обнулились после переезда.
- обязательно добавь блок experience_layers: 1-3 слоя опыта (например административный/коммерческий), если данные на это указывают.
- ответь по сути на SWOT-логику через существующие поля:
  - strengths = main_asset + hidden_strengths + what_not_reset,
  - weaknesses = internal/external barriers и слабые места входа на рынок,
  - blind spots = main_risk + avoid_for_now + behavioral_risk,
  - important to consider = resource_level, integration_level, career_priorities.
- обязательно добавь блок career_translation в структуре:
  - source_experience,
  - market_term,
  - suitable_roles.
- перед финальным выводом проверь дубли направлений; одинаковые профессии объедини.
- не ставь изучение языка первым действием, если цель пользователя — работа и доход; язык укажи как параллельный трек.
- делай финальный ответ компактным: без повторения одинаковых тезисов между блоками.
- пиши коротко и предметно: избегай общих фраз вроде "важно", "нужно развиваться", "следует учитывать" без конкретного действия.
- каждый блок должен давать практический выход: что делать, сколько, за какой срок, какой измеримый результат.
- при формулировке итогов явно держи структуру из 11 блоков для web/PDF отчёта:
  1) что услышал,
  2) профессиональное ядро,
  3) сильные стороны и опоры,
  4) ограничения и неизвестные,
  5) устойчивость в период изменений,
  6) интеграция в новой стране,
  7) сравнение маршрутов,
  8) выбранный маршрут и первый шаг,
  9) план на 30 дней,
  10) анализ резюме,
  11) что может быть не так в выводе.

Обязательный слой FACTS_ONLY перед формированием отчёта:
- сначала собери внутренний объект facts_only со структурой:
  {{
    "explicit_facts": [],
    "resume_facts": [],
    "inferences": [],
    "unknowns": [],
    "contradictions": [],
    "career_profile": {{"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []}},
    "constraints": {{"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []}},
    "psychological_state": {{"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []}},
    "action_capacity": {{"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []}},
    "integration": {{"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []}},
    "route_preferences": {{"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []}}
  }}
- в explicit_facts добавляй только то, что прямо подтверждено историей и ответами пользователя;
- в resume_facts добавляй только то, что прямо подтверждено текстом резюме;
- если это вывод, пиши его осторожно и только в inferences, например:
  "Похоже, у вас есть опыт самостоятельного ведения небольших задач.";
  "Вероятно, вам может подойти маршрут с частными заказами, потому что вы уже договаривались с клиентами.";
- каждую запись по слоям (`career_profile`, `constraints`, `psychological_state`, `action_capacity`, `integration`, `route_preferences`) раскладывай по источникам: `from_story`, `from_answers`, `from_resume`, `inferred`, `unknown`;
- если данных не хватает, не фантазируй и добавляй в unknowns формулировки вида:
  "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах.";
- запрещено без подтверждения писать утверждения вида:
  "У вас есть опыт документов", "Вы умеете управлять процессами", "Вы понимаете местный рынок",
  "У вас есть профессиональные контакты", "У вас высокий уровень интеграции", "Вы готовы к переучиванию".
- в inferences используй только осторожные маркеры начала фразы: "Похоже", "Вероятно", "Можно предположить".
- если в contradictions есть записи, не используй противоречивые факты для смены маршрута и не пересчитывай маршрут до подтверждения.
- финальный отчёт не должен содержать фактов о пользователе, которых нет в explicit_facts или корректно маркированных inferences.

Требования к рыночной привязке (Польша):
- для каждой профессии в market_analysis укажи salary_range в формате диапазона PLN (например: "5500-8000 PLN brutto").
- для каждой профессии дай минимум 3 конкретных требования рынка (инструменты, язык, процессы, тип задач).
- profile_match_reason формулируй через конкретные совпадения из опыта пользователя, а не абстрактные слова.
- fit_percent и match_percent должны быть реалистичными и согласованными между блоками.
- если данных для конкретной цифры недостаточно, прямо пиши "данных недостаточно" и не выдумывай.

Требования к плану действий:
- weekly_plan: 7 дней, каждый день с конкретной задачей и измеримым результатом (число вакансий, число откликов, число кейсов, число правок CV).
- action_plan.today: только 1 действие до 15 минут и с измеримым результатом.
- this_week и this_month: только контролируемые действия (что пользователь делает сам), без обещаний оффера.
- язык и обучение описывай как параллельный трек; не ставь язык первым шагом при финансовом давлении.
- в career_bridges.first_market_test всегда давай проверяемый тест рынка с числом (например: "10 вакансий", "5 откликов", "3 интервью-скрипта").

Требования к тону и оформлению:
- стиль: деловой, ясный, без психотерапевтических формулировок и без "мотивационной воды".
- короткие формулировки: 1-2 предложения на поле, если поле текстовое.
- не дублируй одинаковую мысль в digital_human, decision, route и closing_message.
- closing_message — это короткий финал отчёта, который человек унесёт с собой. Он должен быть живым, персонализированным и сильным.
  Структура (2-3 предложений):
  1. Отзеркаль конкретный факт из истории пользователя или главный барьер — покажи, что ты его услышал(а).
  2. Укажи одно самое важное: что у него уже есть, что не обнулилось.
  3. Дай один честный практический инсайт о следующем шаге — без воды, без «всё получится».
  Запрещено: общие фразы «вы молодец», «успехов вам», «в вас есть потенциал», обещания результата зависящего от внешних факторов.
  Разрешено: имя пользователя, профессия, конкретная страна, реальный следующий шаг, честная оговорка.

Правило для рабочих профессий (производство, строительство, сварка, логистика, склад, сфера услуг):
Если пользователь относится к рабочим профессиям, используй следующие треки роста как основу для recommended_main_path и market_analysis:
- Сварщик / монтажник / слесарь → Мастер смены → Прораб / Руководитель участка
- Водитель / курьер / экспедитор → Диспетчер / Логист → Координатор перевозок / Менеджер транспортного отдела
- Оператор склада / кладовщик → Старший кладовщик / Бригадир склада → Начальник склада
- Повар / официант / бариста → Шеф / Су-шеф → Управляющий заведением
- Нянечка / сиделка / санитар → Старшая медсестра / Координатор ухода → Менеджер по уходу
- Швея / оператор машины → Технолог / Контролёр качества → Руководитель производственного участка
Важно: показывай не только текущую профессию, но и вероятный трек развития через 1-3 года.
В real_solutions обязательно укажи карьерный трек роста как отдельное решение.

Ключевое правило принятия решения:
Если у человека есть сильный прошлый опыт и высокий финансовый стресс,
не выбирай долгую смену профессии как основной путь.
Основной путь должен использовать уже имеющиеся компетенции.
Долгую смену профессии можно давать только как параллельный или долгосрочный маршрут.

Ты карьерный стратег для взрослых мигрантов.
Твоя задача - не просто перечислить профессии, а принять карьерное решение.

Проверка качества перед ответом (внутренний чек-лист):
1) Нет ли подмены биографии/фактов пользователя.
2) Есть ли в market_analysis реальные роли рынка Польши и диапазоны PLN.
3) Есть ли конкретные числа в шагах (вакансии/отклики/кейсы/правки).
4) Нет ли language-first в первом шаге.
5) Нет ли повторов одного и того же тезиса между блоками.

Верни JSON:
{{
  "digital_human": {{
    "summary": "",
    "previous_identity": "",
    "current_state": "",
    "main_asset": "",
    "main_risk": "",
    "main_barrier": "",
    "main_fear": "",
    "hidden_strengths": [""],
    "psychological_profile": {{
      "dominant_barriers": [""],
      "dominant_fears": [""],
      "coping_style": "",
      "support_needed": ""
    }},
    "fastest_path_to_income": "",
    "long_term_path": "",
    "skills": {{
      "professional": [""],
      "transferable": [""],
      "hidden": [""]
    }},
    "barriers": {{
      "external": [""],
      "internal": [""],
      "critical": [""]
    }},
    "motivation": {{
      "money": 0,
      "stability": 0,
      "freedom": 0,
      "meaning": 0,
      "status": 0,
      "entrepreneurship": 0
    }},
    "career_readiness": {{
      "urgency": "",
      "learning_capacity": "",
      "risk_tolerance": "",
      "language_readiness": "",
      "mobility": ""
    }},
    "strategy_mode": "Survival|Transition|Growth"
  }},
  "experience_layers": [""],
  "what_not_reset": [""],
  "market_analysis": [
    {{
      "profession": "",
      "fit_percent": 0,
      "demand": "",
      "entry_speed": "",
      "competition": "",
      "requirements": [""],
      "salary_range": "",
      "profile_match_reason": ""
    }}
  ],
  "career_translation": [
    {{
      "source_experience": "",
      "market_term": "",
      "suitable_roles": [""]
    }}
  ],
  "career_bridges": [
    {{
      "role": "",
      "why_bridge": "",
      "first_market_test": ""
    }}
  ],
  "career_recommendations": [
    {{
      "title": "",
      "match_percent": 0,
      "why_fit": "",
      "pros": [""],
      "risks": [""],
      "entry_timeline": "",
      "income_range": ""
    }}
  ],
  "real_solutions": [
    {{
      "title": "",
      "recommendation_level": "",
      "success_probability": "",
      "timeline": "",
      "why": "",
      "first_step": ""
    }}
  ],
  "career_decision": {{
    "recommended_main_path": "",
    "why_this_path": "",
    "why_not_other_paths": [""],
    "backup_path": "",
    "avoid_for_now": "",
    "decision_summary": ""
  }},
  "development_map": {{
    "current_state": "",
    "goal": "",
    "gap": [""],
    "route": [
      {{
        "stage": "",
        "objective": "",
        "actions": [""],
        "output": "",
        "timeline": ""
      }}
    ],
    "first_month": [
      {{
        "week": 1,
        "focus": "",
        "tasks": [""],
        "output": ""
      }}
    ]
  }},
  "action_plan": {{
    "today": {{
      "action": "",
      "timebox": "",
      "result": ""
    }},
    "this_week": [""],
    "this_month": [""]
  }},
  "weekly_plan": [
    {{
      "day": 1,
      "focus": "",
      "task": "",
      "time": "",
      "result": "",
      "why": ""
    }}
  ],
  "career_barriers": [
    {{
      "barrier": "",
      "severity": 0,
      "mechanism": "",
      "recommended_skill": "",
      "first_exercise": ""
    }}
  ],
  "social_integration": {{
    "environment": [""],
    "people": [""],
    "communities": [""],
    "opportunities": [""],
    "contribution": [""]
  }},
  "energy_sources": [""],
  "career_priorities": [""],
  "competency_signals": [""],
  "decision_layers": {{
    "career_profile": [""],
    "constraints": [""],
    "psychological_state": [""],
    "action_capacity": [""]
  }},
  "facts_only": {{
    "explicit_facts": [""],
    "inferences": [""],
    "unknowns": [""],
    "contradictions": [""]
  }},
  "closing_message": ""
}}

История пользователя:
{story}

Первичный анализ:
{analysis_json}

Анализ резюме:
{resume_analysis_json}

Слои для принятия решения:
{decision_layers_json}

Психологические барьеры пользователя:
{selected_barriers}

Страхи пользователя:
{selected_fears}

Что мешает двигаться (страхи/поведение/состояние):
{selected_psych_markers}

Источники энергии пользователя:
{selected_energy_sources}

Карьерные приоритеты пользователя:
{selected_career_priorities}

Предсобранный FACTS_ONLY слой:
{facts_only_json}

Ответы на уточняющие вопросы:
{answers}
""".strip()


RESUME_ANALYSIS_PROMPT = """
Этап: анализ резюме.
language: {language}

Извлеки из резюме:
- профессии;
- периоды работы;
- ключевые задачи;
- образование;
- языки;
- сертификаты;
- достижения;
- навыки;
- пробелы;
- несостыковки с историей пользователя;
- уровень карьеры.

Сформируй краткий, практичный результат.
Не переписывай биографию и не добавляй опыт, которого нет.
Несостыковки формулируй как вопросы для уточнения, а не как ошибки.

Верни JSON:
{{
  "professions": [""],
  "periods": [""],
  "tasks": [""],
  "education": [""],
  "languages": [""],
  "certificates": [""],
  "achievements": [""],
  "skills": [""],
  "gaps": [""],
  "inconsistencies": [""],
  "clarifying_questions": [""],
  "career_level": "",
  "what_is_good": [""],
  "what_is_missing": [""]
}}

Текст резюме:
{resume_text}
""".strip()


ARISTOTLE_PROMPT = """
Режим: Аристотель — первый шаг.
language: {language}

Задача:
превратить туман в действие.

Правила:
- не давать общую психологическую цель типа “улучшить самооценку”;
- цель должна быть конкретной задачей;
- если пользователь принёс только самокритику, но нет задачи, needs_clarification=true;
- если задача есть, выдели её;
- first_step должен занимать 5–10 минут;
- if_too_hard должен быть микрошагом на 30–60 секунд;
- не писать “каждый шаг важен”;
- не писать generic motivation;
- если language="be", усё па-беларуску.

{lang_instruction}
{context_block}
{pattern_block}

Верни JSON:

{{
  "mode_title": "",
  "needs_clarification": false,
  "clarification_question": "",
  "fog_type": "",
  "goal": "",
  "obstacle": "",
  "cause": "",
  "wrong_frame": "",
  "smaller_task": "",
  "first_step": "",
  "if_too_hard": "",
  "dry_summary": "",
  "verdict": "",
  "phrase": ""
}}

RU example:
Input: “я тупой мне кажется не могу выучить стихи”
goal: “выучить стих”
wrong_frame: “доказать, что ты не тупой”
smaller_task: “не весь стих, а первая строка”
first_step: “прочитать первую строку вслух 3 раза”
verdict: “Не учи весь стих. Начни с куска нормального размера.”

BE example:
Input: “я дурны мне здаецца не магу вывучыць верш”
goal: “вывучыць верш”
wrong_frame: “даказаць, што ты не дурны”
smaller_task: “не ўвесь верш, а першы радок”
first_step: “прачытаць першы радок услых 3 разы”
verdict: “Не вучы ўвесь верш. Пачні з кавалка нармальнага памеру.”

Текст пользователя:
{user_text}
""".strip()


AURELIUS_PROMPT = """
Режим: Марк Аврелий — вернуть контроль.
language: {language}

Задача:
отделить то, что в твоей власти, от того, что не в твоей власти.

Правила:
- не выдумывать чужое мнение, если его нет в тексте;
- не давать generic advice;
- не писать “не бойся”;
- не обещать, что всё получится;
- всегда структура: control_attempt, not_under_control, under_control, false_control, worthy_action, small_step, dry_summary, verdict;
- если речь про ИИ, не писать просто “используй ИИ как инструмент”; нужно конкретнее: какой шаг в твоей власти сегодня;
- если language="be", усё па-беларуску.

{lang_instruction}

Верни JSON:

{{
  "mode_title": "",
  "fog_type": "",
  "control_attempt": "",
  "not_under_control": "",
  "under_control": "",
  "false_control": "",
  "worthy_action": "",
  "small_step": "",
  "dry_summary": "",
  "verdict": "",
  "phrase": ""
}}

RU example:
Input: “Мне сложно думать как предприниматель, потому что боюсь, что меня заменит ИИ”
not_under_control: “как быстро будет меняться рынок и какие профессии затронет ИИ”
under_control: “какой продуктовый шаг ты сделаешь сегодня и как используешь ИИ в своей работе”
false_control: “пытаться заранее отменить будущее тревогой”
small_step: “выбрать одну задачу и спросить: как ИИ может усилить меня здесь, а не заменить?”
verdict: “Не контролируй эпоху. Контролируй сегодняшний эксперимент.”

BE example:
Input: “Мне цяжка думаць як прадпрымальніку, бо баюся, што мяне заменіць ІІ”
not_under_control: “як хутка будзе змяняцца рынак і якія прафесіі закране ІІ”
under_control: “які прадуктовы крок ты зробіш сёння і як выкарыстаеш ІІ у сваёй працы”
small_step: “выбраць адну задачу і спытаць: як ІІ можа ўзмацніць мяне тут, а не замяніць?”
verdict: “Не кантралюй эпоху. Кантралюй сённяшні эксперымент.”

Текст пользователя:
{user_text}
""".strip()


COUNCIL_PROMPT = """
Пользователь уже получил основной разбор.
Теперь он позвал другого мудреца.

language: {language}
selected_mode: {selected_mode}

Задача:
дать короткий взгляд выбранного мудреца.
Не полный разбор.
Не общий совет.
3-6 строк максимум.

Правила:
- сохраняй стиль выбранного мудреца;
- не повторяй предыдущий ответ;
- не говори generic "это нормально";
- дай один острый угол зрения;
- дай одну строку-вывод;
- если language="be", адказвай па-беларуску.

Стили:
NextYou: режет до факта. "Где факт? Где вывод? Что имеет предмет?"
Аристотель: режет до действия. "Какая цель? Какой первый шаг? Что сделать за 5 минут?"
Марк Аврелий: режет до власти/невласти. "Что в твоей власти? Что не в твоей власти? Какое достойное действие?"
Диоген: режет пафос. "Меньше театра. Больше земного действия."

{lang_instruction}

Верни JSON:

{{
  "sage_title": "",
  "comment": "",
  "one_line": ""
}}

RU example Марк Аврелий:
comment: "Ты не управляешь будущим рынка. Но ты управляешь сегодняшним экспериментом. Тревога хочет предсказать эпоху, а тебе нужен один продуктовый шаг."
one_line: "Не контролируй ИИ-эпоху. Контролируй сегодняшний ход."

BE example Дыяген:
comment: "Ты ўжо пахаваў будучыню, хоць яшчэ не адкрыў файл. Менш пахаванняў прафесіі, больш аднаго кроку."
one_line: "Не хавай сябе загадзя. Адкрый файл."

Исходный текст:
{original_text}

Предыдущий разбор:
{previous_result}
""".strip()


TONE_PROMPT = """
Перепиши последний вывод в выбранном тоне.

language: {language}
tone: {tone}

Не меняй смысл.
Не добавляй новую диагностику.
Не повторяй весь длинный разбор.
Дай короткий текст 3-5 строк.
Сохрани маленький шаг.

Тоны:
Мягче — бережно, но без сладкой терапии.
Жёстче — прямо, коротко, без унижения.
Смешнее — иронично, мемно, но полезно.
Как древний дед — ворчливый мудрый старик, немного архаично, но понятно.
На беларускім — "як стары мудры дзед": крыху бурчыць, але па справе.

{lang_instruction}

RU пример:
title: "🎭 Как древний дед"
text: "Сынок, незнание квантовой физики ещё не делает тебя дураком. А вот судить всю голову по одной теме — это уже ярмарка тщеславия. Возьми один вопрос и разбери его спокойно."
dry_summary: "Не суди всю голову. Разбери один вопрос."

BE пример:
title: "🎭 Як стары дзед"
text: "Сынок, калі ты не ведаеш квантавую фізіку, гэта яшчэ не прысуд. Не цягні ўсю асобу на суд з-за адной тэмы. Вазьмі адно пытанне і разбяры яго спакойна."
dry_summary: "Не судзі ўсю галаву. Разбяры адно пытанне."

last_result:
{last_result}

Верни JSON:

{{
  "title": "",
  "text": "",
  "dry_summary": ""
}}
""".strip()

```

## Раздел 2. Логика OpenAI слоя (raw фрагменты)
Ниже ключевые функции из openai_client.py:
- analyze_story
- analyze_resume
- build_report
- _align_report_with_story
- _build_facts_only
- _enforce_route_change_guardrails
- _detect_profile_domain
- _enforce_domain_specific_routes

```python
# --- async def analyze_story ---
        return trimmed

    async def analyze_story(self, user_text: str, language: str = "ru") -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        prompt = STORY_ANALYSIS_PROMPT.format(
            user_text=user_text,
            language=language,
        )
        fallback = STORY_ANALYSIS_FALLBACK_BE if language == "be" else STORY_ANALYSIS_FALLBACK
        data = await self._run_json(prompt, fallback, STORY_ANALYSIS_SCHEMA, language)
        data["follow_up_questions"] = self._normalize_question_count(data.get("follow_up_questions"), language)
        return data

    async def analyze_resume(self, resume_text: str, language: str = "ru") -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        prompt = RESUME_ANALYSIS_PROMPT.format(
            resume_text=resume_text,
            language=language,
        )
        return await self._run_json(prompt, RESUME_ANALYSIS_FALLBACK, RESUME_ANALYSIS_SCHEMA, language)

    async def build_report(
        self,
        story: str,
        story_analysis: dict[str, Any],
        answers: str,
        decision_layers: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
        selected_barriers: list[str] | None = None,
        selected_fears: list[str] | None = None,
        selected_psych_markers: list[str] | None = None,
        selected_energy_sources: list[str] | None = None,
        selected_career_priorities: list[str] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
        language: str = "ru",
    ) -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        facts_only = self._build_facts_only(story, story_analysis, answers, decision_layers, resume_analysis)
        prompt = FINAL_REPORT_PROMPT.format(
            story=story,
            analysis_json=json.dumps(story_analysis or {}, ensure_ascii=False),
            resume_analysis_json=json.dumps(resume_analysis or {}, ensure_ascii=False),
            decision_layers_json=json.dumps(self._normalize_decision_layers(decision_layers), ensure_ascii=False),
            selected_barriers=json.dumps(selected_barriers or [], ensure_ascii=False),
            selected_fears=json.dumps(selected_fears or [], ensure_ascii=False),
            selected_psych_markers=json.dumps(selected_psych_markers or [], ensure_ascii=False),
            selected_energy_sources=json.dumps(selected_energy_sources or [], ensure_ascii=False),
            selected_career_priorities=json.dumps(selected_career_priorities or [], ensure_ascii=False),
            user_segment=str(user_segment or "").strip(),
            user_segment_label=str(user_segment_label or "").strip(),
            facts_only_json=json.dumps(facts_only, ensure_ascii=False),
            answers=answers,
            language=language,
        )
        fallback = FINAL_REPORT_FALLBACK_BE if language == "be" else FINAL_REPORT_FALLBACK
        report = await self._run_json(prompt, fallback, FINAL_REPORT_SCHEMA, language)
        return self._align_report_with_story(
            report,
            story_analysis,
            answers,
            story,
            facts_only,
            decision_layers,
            user_segment=user_segment,
            user_segment_label=user_segment_label,
        )

    def _align_report_with_story(
        self,
        report: dict[str, Any],
        story_analysis: dict[str, Any],
        answers_text: str = "",
        story_text: str = "",
        facts_only: dict[str, Any] | None = None,
        decision_layers: dict[str, Any] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
    ) -> dict[str, Any]:
        if not isinstance(report, dict):
            return copy.deepcopy(FINAL_REPORT_FALLBACK)

        normalized_facts = self._normalize_facts_only(
            report.get("facts_only"),
            base=(
                self._build_facts_only(story_text, story_analysis, answers_text, decision_layers, None)
                if facts_only is None
                else facts_only
            ),
        )
        report["facts_only"] = normalized_facts

        digital_human = report.get("digital_human")
        if isinstance(digital_human, dict):
            current_identity = str(story_analysis.get("current_identity", "")).strip()
            if current_identity:
                digital_human["current_state"] = current_identity

            snapshot = story_analysis.get("experience_snapshot", [])
            if isinstance(snapshot, list) and snapshot:
                first = str(snapshot[0]).strip()
                if first and not str(digital_human.get("previous_identity", "")).strip():
                    digital_human["previous_identity"] = first

        preferred_titles = self._preferred_polish_roles(story_analysis)
        if preferred_titles:
            self._normalize_admin_backoffice_roles(report, preferred_titles)

        profile_domain = self._detect_profile_domain(story_analysis, answers_text, story_text)
        if profile_domain:
            report["profile_domain"] = profile_domain

        self._deduplicate_directions(report)
        self._enrich_layers_and_non_reset(report, story_analysis, answers_text)
        self._inject_signal_roles(report, story_analysis, answers_text)
        self._ensure_strategy_mode(report)
        self._ensure_social_integration(report)
        self._ensure_resource_level(report, answers_text)
        self._ensure_integration_level(report, answers_text)
        self._ensure_competency_signals(report, story_analysis, answers_text)
        self._normalize_market_geography(report, story_text, story_analysis, answers_text)
        self._ensure_career_first_today_action(report)
        self._ensure_barrier_driven_today_action(report, answers_text)
        self._enforce_segment_routes(report, user_segment, user_segment_label)
        normalized_layers = self._normalize_decision_layers(decision_layers)
        self._enforce_route_change_guardrails(report, story_analysis, answers_text, normalized_layers)
        self._enforce_domain_specific_routes(report, profile_domain)
        self._sanitize_unconfirmed_claims(report, normalized_facts)

        return report

    def _normalize_decision_layers(self, payload: Any) -> dict[str, list[str]]:
        source = payload if isinstance(payload, dict) else {}
        normalized: dict[str, list[str]] = {}
        for key in ("career_profile", "constraints", "psychological_state", "action_capacity"):
            values = source.get(key, []) if isinstance(source.get(key), list) else []
            bucket: list[str] = []
            for item in values:
                text = str(item or "").strip()
                if text and text not in bucket:
                    bucket.append(text)
            normalized[key] = bucket
        return normalized

# --- async def analyze_resume ---
        return data

    async def analyze_resume(self, resume_text: str, language: str = "ru") -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        prompt = RESUME_ANALYSIS_PROMPT.format(
            resume_text=resume_text,
            language=language,
        )
        return await self._run_json(prompt, RESUME_ANALYSIS_FALLBACK, RESUME_ANALYSIS_SCHEMA, language)

    async def build_report(
        self,
        story: str,
        story_analysis: dict[str, Any],
        answers: str,
        decision_layers: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
        selected_barriers: list[str] | None = None,
        selected_fears: list[str] | None = None,
        selected_psych_markers: list[str] | None = None,
        selected_energy_sources: list[str] | None = None,
        selected_career_priorities: list[str] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
        language: str = "ru",
    ) -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        facts_only = self._build_facts_only(story, story_analysis, answers, decision_layers, resume_analysis)
        prompt = FINAL_REPORT_PROMPT.format(
            story=story,
            analysis_json=json.dumps(story_analysis or {}, ensure_ascii=False),
            resume_analysis_json=json.dumps(resume_analysis or {}, ensure_ascii=False),
            decision_layers_json=json.dumps(self._normalize_decision_layers(decision_layers), ensure_ascii=False),
            selected_barriers=json.dumps(selected_barriers or [], ensure_ascii=False),
            selected_fears=json.dumps(selected_fears or [], ensure_ascii=False),
            selected_psych_markers=json.dumps(selected_psych_markers or [], ensure_ascii=False),
            selected_energy_sources=json.dumps(selected_energy_sources or [], ensure_ascii=False),
            selected_career_priorities=json.dumps(selected_career_priorities or [], ensure_ascii=False),
            user_segment=str(user_segment or "").strip(),
            user_segment_label=str(user_segment_label or "").strip(),
            facts_only_json=json.dumps(facts_only, ensure_ascii=False),
            answers=answers,
            language=language,
        )
        fallback = FINAL_REPORT_FALLBACK_BE if language == "be" else FINAL_REPORT_FALLBACK
        report = await self._run_json(prompt, fallback, FINAL_REPORT_SCHEMA, language)
        return self._align_report_with_story(
            report,
            story_analysis,
            answers,
            story,
            facts_only,
            decision_layers,
            user_segment=user_segment,
            user_segment_label=user_segment_label,
        )

    def _align_report_with_story(
        self,
        report: dict[str, Any],
        story_analysis: dict[str, Any],
        answers_text: str = "",
        story_text: str = "",
        facts_only: dict[str, Any] | None = None,
        decision_layers: dict[str, Any] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
    ) -> dict[str, Any]:
        if not isinstance(report, dict):
            return copy.deepcopy(FINAL_REPORT_FALLBACK)

        normalized_facts = self._normalize_facts_only(
            report.get("facts_only"),
            base=(
                self._build_facts_only(story_text, story_analysis, answers_text, decision_layers, None)
                if facts_only is None
                else facts_only
            ),
        )
        report["facts_only"] = normalized_facts

        digital_human = report.get("digital_human")
        if isinstance(digital_human, dict):
            current_identity = str(story_analysis.get("current_identity", "")).strip()
            if current_identity:
                digital_human["current_state"] = current_identity

            snapshot = story_analysis.get("experience_snapshot", [])
            if isinstance(snapshot, list) and snapshot:
                first = str(snapshot[0]).strip()
                if first and not str(digital_human.get("previous_identity", "")).strip():
                    digital_human["previous_identity"] = first

        preferred_titles = self._preferred_polish_roles(story_analysis)
        if preferred_titles:
            self._normalize_admin_backoffice_roles(report, preferred_titles)

        profile_domain = self._detect_profile_domain(story_analysis, answers_text, story_text)
        if profile_domain:
            report["profile_domain"] = profile_domain

        self._deduplicate_directions(report)
        self._enrich_layers_and_non_reset(report, story_analysis, answers_text)
        self._inject_signal_roles(report, story_analysis, answers_text)
        self._ensure_strategy_mode(report)
        self._ensure_social_integration(report)
        self._ensure_resource_level(report, answers_text)
        self._ensure_integration_level(report, answers_text)
        self._ensure_competency_signals(report, story_analysis, answers_text)
        self._normalize_market_geography(report, story_text, story_analysis, answers_text)
        self._ensure_career_first_today_action(report)
        self._ensure_barrier_driven_today_action(report, answers_text)
        self._enforce_segment_routes(report, user_segment, user_segment_label)
        normalized_layers = self._normalize_decision_layers(decision_layers)
        self._enforce_route_change_guardrails(report, story_analysis, answers_text, normalized_layers)
        self._enforce_domain_specific_routes(report, profile_domain)
        self._sanitize_unconfirmed_claims(report, normalized_facts)

        return report

    def _normalize_decision_layers(self, payload: Any) -> dict[str, list[str]]:
        source = payload if isinstance(payload, dict) else {}
        normalized: dict[str, list[str]] = {}
        for key in ("career_profile", "constraints", "psychological_state", "action_capacity"):
            values = source.get(key, []) if isinstance(source.get(key), list) else []
            bucket: list[str] = []
            for item in values:
                text = str(item or "").strip()
                if text and text not in bucket:
                    bucket.append(text)
            normalized[key] = bucket
        return normalized

    def _contains_emotional_overload(self, layers: dict[str, list[str]], answers_text: str) -> bool:
        blob = " ".join([*(layers.get("psychological_state", []) or []), str(answers_text or "")]).lower().replace("ё", "е")
        markers = [
            "не знаю, с чего начать",
            "не знаю с чего начать",
            "слишком сложно",
            "тревог",
            "устал",
            "сомне",
            "страх отказ",

# --- async def build_report ---
        return await self._run_json(prompt, RESUME_ANALYSIS_FALLBACK, RESUME_ANALYSIS_SCHEMA, language)

    async def build_report(
        self,
        story: str,
        story_analysis: dict[str, Any],
        answers: str,
        decision_layers: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
        selected_barriers: list[str] | None = None,
        selected_fears: list[str] | None = None,
        selected_psych_markers: list[str] | None = None,
        selected_energy_sources: list[str] | None = None,
        selected_career_priorities: list[str] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
        language: str = "ru",
    ) -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        facts_only = self._build_facts_only(story, story_analysis, answers, decision_layers, resume_analysis)
        prompt = FINAL_REPORT_PROMPT.format(
            story=story,
            analysis_json=json.dumps(story_analysis or {}, ensure_ascii=False),
            resume_analysis_json=json.dumps(resume_analysis or {}, ensure_ascii=False),
            decision_layers_json=json.dumps(self._normalize_decision_layers(decision_layers), ensure_ascii=False),
            selected_barriers=json.dumps(selected_barriers or [], ensure_ascii=False),
            selected_fears=json.dumps(selected_fears or [], ensure_ascii=False),
            selected_psych_markers=json.dumps(selected_psych_markers or [], ensure_ascii=False),
            selected_energy_sources=json.dumps(selected_energy_sources or [], ensure_ascii=False),
            selected_career_priorities=json.dumps(selected_career_priorities or [], ensure_ascii=False),
            user_segment=str(user_segment or "").strip(),
            user_segment_label=str(user_segment_label or "").strip(),
            facts_only_json=json.dumps(facts_only, ensure_ascii=False),
            answers=answers,
            language=language,
        )
        fallback = FINAL_REPORT_FALLBACK_BE if language == "be" else FINAL_REPORT_FALLBACK
        report = await self._run_json(prompt, fallback, FINAL_REPORT_SCHEMA, language)
        return self._align_report_with_story(
            report,
            story_analysis,
            answers,
            story,
            facts_only,
            decision_layers,
            user_segment=user_segment,
            user_segment_label=user_segment_label,
        )

    def _align_report_with_story(
        self,
        report: dict[str, Any],
        story_analysis: dict[str, Any],
        answers_text: str = "",
        story_text: str = "",
        facts_only: dict[str, Any] | None = None,
        decision_layers: dict[str, Any] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
    ) -> dict[str, Any]:
        if not isinstance(report, dict):
            return copy.deepcopy(FINAL_REPORT_FALLBACK)

        normalized_facts = self._normalize_facts_only(
            report.get("facts_only"),
            base=(
                self._build_facts_only(story_text, story_analysis, answers_text, decision_layers, None)
                if facts_only is None
                else facts_only
            ),
        )
        report["facts_only"] = normalized_facts

        digital_human = report.get("digital_human")
        if isinstance(digital_human, dict):
            current_identity = str(story_analysis.get("current_identity", "")).strip()
            if current_identity:
                digital_human["current_state"] = current_identity

            snapshot = story_analysis.get("experience_snapshot", [])
            if isinstance(snapshot, list) and snapshot:
                first = str(snapshot[0]).strip()
                if first and not str(digital_human.get("previous_identity", "")).strip():
                    digital_human["previous_identity"] = first

        preferred_titles = self._preferred_polish_roles(story_analysis)
        if preferred_titles:
            self._normalize_admin_backoffice_roles(report, preferred_titles)

        profile_domain = self._detect_profile_domain(story_analysis, answers_text, story_text)
        if profile_domain:
            report["profile_domain"] = profile_domain

        self._deduplicate_directions(report)
        self._enrich_layers_and_non_reset(report, story_analysis, answers_text)
        self._inject_signal_roles(report, story_analysis, answers_text)
        self._ensure_strategy_mode(report)
        self._ensure_social_integration(report)
        self._ensure_resource_level(report, answers_text)
        self._ensure_integration_level(report, answers_text)
        self._ensure_competency_signals(report, story_analysis, answers_text)
        self._normalize_market_geography(report, story_text, story_analysis, answers_text)
        self._ensure_career_first_today_action(report)
        self._ensure_barrier_driven_today_action(report, answers_text)
        self._enforce_segment_routes(report, user_segment, user_segment_label)
        normalized_layers = self._normalize_decision_layers(decision_layers)
        self._enforce_route_change_guardrails(report, story_analysis, answers_text, normalized_layers)
        self._enforce_domain_specific_routes(report, profile_domain)
        self._sanitize_unconfirmed_claims(report, normalized_facts)

        return report

    def _normalize_decision_layers(self, payload: Any) -> dict[str, list[str]]:
        source = payload if isinstance(payload, dict) else {}
        normalized: dict[str, list[str]] = {}
        for key in ("career_profile", "constraints", "psychological_state", "action_capacity"):
            values = source.get(key, []) if isinstance(source.get(key), list) else []
            bucket: list[str] = []
            for item in values:
                text = str(item or "").strip()
                if text and text not in bucket:
                    bucket.append(text)
            normalized[key] = bucket
        return normalized

    def _contains_emotional_overload(self, layers: dict[str, list[str]], answers_text: str) -> bool:
        blob = " ".join([*(layers.get("psychological_state", []) or []), str(answers_text or "")]).lower().replace("ё", "е")
        markers = [
            "не знаю, с чего начать",
            "не знаю с чего начать",
            "слишком сложно",
            "тревог",
            "устал",
            "сомне",
            "страх отказ",
            "перегруз",
            "хаос",
            "signal: overwhelm",
        ]
        return any(marker in blob for marker in markers)

    def _has_route_change_driver(self, layers: dict[str, list[str]], answers_text: str) -> bool:
        blob = " ".join([

# --- def _align_report_with_story ---
        )

    def _align_report_with_story(
        self,
        report: dict[str, Any],
        story_analysis: dict[str, Any],
        answers_text: str = "",
        story_text: str = "",
        facts_only: dict[str, Any] | None = None,
        decision_layers: dict[str, Any] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
    ) -> dict[str, Any]:
        if not isinstance(report, dict):
            return copy.deepcopy(FINAL_REPORT_FALLBACK)

        normalized_facts = self._normalize_facts_only(
            report.get("facts_only"),
            base=(
                self._build_facts_only(story_text, story_analysis, answers_text, decision_layers, None)
                if facts_only is None
                else facts_only
            ),
        )
        report["facts_only"] = normalized_facts

        digital_human = report.get("digital_human")
        if isinstance(digital_human, dict):
            current_identity = str(story_analysis.get("current_identity", "")).strip()
            if current_identity:
                digital_human["current_state"] = current_identity

            snapshot = story_analysis.get("experience_snapshot", [])
            if isinstance(snapshot, list) and snapshot:
                first = str(snapshot[0]).strip()
                if first and not str(digital_human.get("previous_identity", "")).strip():
                    digital_human["previous_identity"] = first

        preferred_titles = self._preferred_polish_roles(story_analysis)
        if preferred_titles:
            self._normalize_admin_backoffice_roles(report, preferred_titles)

        profile_domain = self._detect_profile_domain(story_analysis, answers_text, story_text)
        if profile_domain:
            report["profile_domain"] = profile_domain

        self._deduplicate_directions(report)
        self._enrich_layers_and_non_reset(report, story_analysis, answers_text)
        self._inject_signal_roles(report, story_analysis, answers_text)
        self._ensure_strategy_mode(report)
        self._ensure_social_integration(report)
        self._ensure_resource_level(report, answers_text)
        self._ensure_integration_level(report, answers_text)
        self._ensure_competency_signals(report, story_analysis, answers_text)
        self._normalize_market_geography(report, story_text, story_analysis, answers_text)
        self._ensure_career_first_today_action(report)
        self._ensure_barrier_driven_today_action(report, answers_text)
        self._enforce_segment_routes(report, user_segment, user_segment_label)
        normalized_layers = self._normalize_decision_layers(decision_layers)
        self._enforce_route_change_guardrails(report, story_analysis, answers_text, normalized_layers)
        self._enforce_domain_specific_routes(report, profile_domain)
        self._sanitize_unconfirmed_claims(report, normalized_facts)

        return report

    def _normalize_decision_layers(self, payload: Any) -> dict[str, list[str]]:
        source = payload if isinstance(payload, dict) else {}
        normalized: dict[str, list[str]] = {}
        for key in ("career_profile", "constraints", "psychological_state", "action_capacity"):
            values = source.get(key, []) if isinstance(source.get(key), list) else []
            bucket: list[str] = []
            for item in values:
                text = str(item or "").strip()
                if text and text not in bucket:
                    bucket.append(text)
            normalized[key] = bucket
        return normalized

    def _contains_emotional_overload(self, layers: dict[str, list[str]], answers_text: str) -> bool:
        blob = " ".join([*(layers.get("psychological_state", []) or []), str(answers_text or "")]).lower().replace("ё", "е")
        markers = [
            "не знаю, с чего начать",
            "не знаю с чего начать",
            "слишком сложно",
            "тревог",
            "устал",
            "сомне",
            "страх отказ",
            "перегруз",
            "хаос",
            "signal: overwhelm",
        ]
        return any(marker in blob for marker in markers)

    def _has_route_change_driver(self, layers: dict[str, list[str]], answers_text: str) -> bool:
        blob = " ".join([
            *(layers.get("career_profile", []) or []),
            *(layers.get("constraints", []) or []),
            str(answers_text or ""),
        ]).lower().replace("ё", "е")
        drivers = [
            "опыт",
            "язык",
            "документ",
            "право работать",
            "доход",
            "доступное время",
            "финансов",
            "рынок",
            "риск",
            "реальная цель",
            "сменить профес",
            "поменял",
            "изменил",
        ]
        return any(marker in blob for marker in drivers)

    def _enforce_route_change_guardrails(
        self,
        report: dict[str, Any],
        story_analysis: dict[str, Any],
        answers_text: str,
        decision_layers: dict[str, list[str]],
    ) -> None:
        report["decision_layers"] = decision_layers
        profile_domain = self._detect_profile_domain(story_analysis, answers_text)
        facts_only_payload = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
        contradictions = facts_only_payload.get("contradictions", []) if isinstance(facts_only_payload, dict) else []
        has_contradictions = isinstance(contradictions, list) and any(str(item).strip() for item in contradictions)
        overload = self._contains_emotional_overload(decision_layers, answers_text)
        has_driver = self._has_route_change_driver(decision_layers, answers_text)

        if overload:
            action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
            today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
            example_roles = "плитка, гипсокартон, мебель"
            if profile_domain == CONSTRUCTION_ESTIMATION_DOMAIN:
                example_roles = "сметы, проверка проектной документации, расчёт объёмов работ"
            today["action"] = (
                "Напишите в заметках три вида работ, которые вы реально умеете делать лучше всего "
                f"(например: {example_roles})."
            )
            today["timebox"] = "10 минут"

# --- def _build_facts_only ---
                    decision["recommended_main_path"] = f"{preferred_titles[0]} / {preferred_titles[1]}"

    def _build_facts_only(
        self,
        story_text: str,
        story_analysis: dict[str, Any],
        answers_text: str,
        decision_layers: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        explicit_facts: list[str] = []
        resume_facts: list[str] = []

        def _append_unique(target: list[str], value: str) -> None:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in target:
                target.append(cleaned)

        def _make_layer() -> dict[str, list[str]]:
            return {
                "from_story": [],
                "from_answers": [],
                "from_resume": [],
                "inferred": [],
                "unknown": [],
            }

        source_layers: dict[str, dict[str, list[str]]] = {
            "career_profile": _make_layer(),
            "constraints": _make_layer(),
            "psychological_state": _make_layer(),
            "action_capacity": _make_layer(),
            "integration": _make_layer(),
            "route_preferences": _make_layer(),
        }

        def _append_layer(layer: str, bucket: str, value: str) -> None:
            cleaned = str(value or "").strip()
            if not cleaned:
                return
            target = source_layers.get(layer, {}).get(bucket)
            if isinstance(target, list) and cleaned not in target:
                target.append(cleaned)

        for value in [story_analysis.get("current_identity"), story_analysis.get("story_summary")]:
            _append_unique(explicit_facts, value)
            _append_layer("career_profile", "from_story", str(value or ""))

        for key in ("experience_snapshot", "skills", "constraints", "goals"):
            items = story_analysis.get(key)
            if isinstance(items, list):
                for item in items:
                    _append_unique(explicit_facts, item)
                    if key in {"experience_snapshot", "skills"}:
                        _append_layer("career_profile", "from_story", str(item))
                    elif key == "constraints":
                        _append_layer("constraints", "from_story", str(item))
                    elif key == "goals":
                        _append_layer("route_preferences", "from_story", str(item))

        for raw_line in str(answers_text or "").splitlines():
            line = raw_line.strip().strip("-•")
            if len(line) >= 3:
                _append_unique(explicit_facts, f"Ответ пользователя: {line}")
                lowered = line.lower()
                if any(token in lowered for token in ["срок", "документ", "деньг", "доход", "огранич"]):
                    _append_layer("constraints", "from_answers", line)
                if any(token in lowered for token in ["устал", "трев", "ресурс", "выгор", "сил"]):
                    _append_layer("psychological_state", "from_answers", line)
                if any(token in lowered for token in ["время", "час", "действ", "делать", "каждый день"]):
                    _append_layer("action_capacity", "from_answers", line)
                if any(token in lowered for token in ["язык", "рынок", "польша", "контакт", "сообще", "интеграц"]):
                    _append_layer("integration", "from_answers", line)
                if any(token in lowered for token in ["хочу", "предпоч", "направлен", "роль", "маршрут"]):
                    _append_layer("route_preferences", "from_answers", line)

        if isinstance(resume_analysis, dict):
            for key in ("professions", "achievements", "skills", "what_is_good"):
                items = resume_analysis.get(key)
                if isinstance(items, list):
                    for item in items:
                        text = str(item or "").strip()
                        if text:
                            _append_unique(resume_facts, text)
                            _append_layer("career_profile", "from_resume", text)
            for key in ("gaps", "what_is_missing"):
                items = resume_analysis.get(key)
                if isinstance(items, list):
                    for item in items:
                        text = str(item or "").strip()
                        if text:
                            _append_unique(resume_facts, text)
                            _append_layer("constraints", "from_resume", text)

        if isinstance(decision_layers, dict):
            mapping = {
                "career_profile": "career_profile",
                "constraints": "constraints",
                "psychological_state": "psychological_state",
                "action_capacity": "action_capacity",
            }
            for src, dst in mapping.items():
                values = decision_layers.get(src)
                if isinstance(values, list):
                    for value in values:
                        _append_layer(dst, "from_answers", str(value))

        blob = " ".join([str(story_text or ""), str(answers_text or ""), " ".join(explicit_facts)]).lower()

        inferences: list[str] = []
        if any(token in blob for token in ["клиент", "общ", "коммуника", "договар", "переговор"]):
            inference = "Похоже, у вас есть опыт коммуникации и взаимодействия с людьми в рабочих задачах."
            inferences.append(inference)
            _append_layer("career_profile", "inferred", inference)
        if any(token in blob for token in ["задач", "срок", "организ", "координа"]):
            inference = "Похоже, у вас есть опыт самостоятельного ведения небольших задач."
            inferences.append(inference)
            _append_layer("action_capacity", "inferred", inference)
        if any(token in blob for token in ["клиент", "договор", "переговор", "заказ"]):
            inference = "Вероятно, вам может подойти маршрут с частными заказами, потому что вы уже договаривались с клиентами."
            inferences.append(inference)
            _append_layer("route_preferences", "inferred", inference)

        allowed_inference_prefixes = ("Похоже", "Вероятно", "Можно предположить")
        inferences = [item for item in inferences if item.startswith(allowed_inference_prefixes)]

        unknowns: list[str] = []
        if not any(token in blob for token in ["рынок", "ваканс", "рынка труда"]):
            unknown = "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах."
            unknowns.append(unknown)
            _append_layer("integration", "unknown", unknown)
        if not any(token in blob for token in ["контакт", "сообще", "нетворк", "знаком"]):
            unknown = "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах."
            unknowns.append(unknown)
            _append_layer("integration", "unknown", unknown)
        if not any(token in blob for token in ["учиться", "обуч", "переуч", "курс"]):
            unknown = "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах."
            unknowns.append(unknown)
            _append_layer("action_capacity", "unknown", unknown)

        for layer_name, payload in source_layers.items():
            # Keep at least one unknown marker in each layer if no direct evidence exists.
            if not payload["from_story"] and not payload["from_answers"] and not payload["from_resume"]:

# --- def _enforce_route_change_guardrails ---
        return any(marker in blob for marker in drivers)

    def _enforce_route_change_guardrails(
        self,
        report: dict[str, Any],
        story_analysis: dict[str, Any],
        answers_text: str,
        decision_layers: dict[str, list[str]],
    ) -> None:
        report["decision_layers"] = decision_layers
        profile_domain = self._detect_profile_domain(story_analysis, answers_text)
        facts_only_payload = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
        contradictions = facts_only_payload.get("contradictions", []) if isinstance(facts_only_payload, dict) else []
        has_contradictions = isinstance(contradictions, list) and any(str(item).strip() for item in contradictions)
        overload = self._contains_emotional_overload(decision_layers, answers_text)
        has_driver = self._has_route_change_driver(decision_layers, answers_text)

        if overload:
            action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
            today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
            example_roles = "плитка, гипсокартон, мебель"
            if profile_domain == CONSTRUCTION_ESTIMATION_DOMAIN:
                example_roles = "сметы, проверка проектной документации, расчёт объёмов работ"
            today["action"] = (
                "Напишите в заметках три вида работ, которые вы реально умеете делать лучше всего "
                f"(например: {example_roles})."
            )
            today["timebox"] = "10 минут"
            today["result"] = "Есть список из 3 конкретных типов работ без смены текущего маршрута."
            action_plan["today"] = today
            report["action_plan"] = action_plan

            digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
            if digital_human:
                digital_human["strategy_mode"] = "Survival"

            decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
            if decision:
                summary = str(decision.get("decision_summary", "")).strip()
                lock_note = "Эмоциональное состояние влияет на темп и размер шага, но не меняет профессиональный маршрут."
                if lock_note not in summary:
                    decision["decision_summary"] = f"{lock_note} {summary}".strip()

            full_blob = " ".join(
                [
                    str(story_analysis.get("current_identity", "")),
                    " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
                    " ".join(decision_layers.get("career_profile", [])),
                ]
            ).lower().replace("ё", "е")
            has_private_orders_anchor = any(token in full_blob for token in ["частн", "плитк", "гипсокарт", "мебел", "ремонт"])
            if has_private_orders_anchor and decision:
                current_main = str(decision.get("recommended_main_path", "")).lower()
                if "частн" not in current_main and "самозан" not in current_main:
                    decision["recommended_main_path"] = "Частные заказы в текущем профиле / Смежные роли по вашему опыту"
                    backup = str(decision.get("backup_path", "")).strip()
                    if not backup:
                        decision["backup_path"] = "Локальный найм по текущему профилю как стабилизирующий трек"

            if overload and (not has_driver or has_contradictions):
                preferred_titles = self._preferred_polish_roles(story_analysis)
                if preferred_titles and decision:
                    decision["recommended_main_path"] = f"{preferred_titles[0]} / {preferred_titles[1]}"

    def _build_facts_only(
        self,
        story_text: str,
        story_analysis: dict[str, Any],
        answers_text: str,
        decision_layers: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        explicit_facts: list[str] = []
        resume_facts: list[str] = []

        def _append_unique(target: list[str], value: str) -> None:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in target:
                target.append(cleaned)

        def _make_layer() -> dict[str, list[str]]:
            return {
                "from_story": [],
                "from_answers": [],
                "from_resume": [],
                "inferred": [],
                "unknown": [],
            }

        source_layers: dict[str, dict[str, list[str]]] = {
            "career_profile": _make_layer(),
            "constraints": _make_layer(),
            "psychological_state": _make_layer(),
            "action_capacity": _make_layer(),
            "integration": _make_layer(),
            "route_preferences": _make_layer(),
        }

        def _append_layer(layer: str, bucket: str, value: str) -> None:
            cleaned = str(value or "").strip()
            if not cleaned:
                return
            target = source_layers.get(layer, {}).get(bucket)
            if isinstance(target, list) and cleaned not in target:
                target.append(cleaned)

        for value in [story_analysis.get("current_identity"), story_analysis.get("story_summary")]:
            _append_unique(explicit_facts, value)
            _append_layer("career_profile", "from_story", str(value or ""))

        for key in ("experience_snapshot", "skills", "constraints", "goals"):
            items = story_analysis.get(key)
            if isinstance(items, list):
                for item in items:
                    _append_unique(explicit_facts, item)
                    if key in {"experience_snapshot", "skills"}:
                        _append_layer("career_profile", "from_story", str(item))
                    elif key == "constraints":
                        _append_layer("constraints", "from_story", str(item))
                    elif key == "goals":
                        _append_layer("route_preferences", "from_story", str(item))

        for raw_line in str(answers_text or "").splitlines():
            line = raw_line.strip().strip("-•")
            if len(line) >= 3:
                _append_unique(explicit_facts, f"Ответ пользователя: {line}")
                lowered = line.lower()
                if any(token in lowered for token in ["срок", "документ", "деньг", "доход", "огранич"]):
                    _append_layer("constraints", "from_answers", line)
                if any(token in lowered for token in ["устал", "трев", "ресурс", "выгор", "сил"]):
                    _append_layer("psychological_state", "from_answers", line)
                if any(token in lowered for token in ["время", "час", "действ", "делать", "каждый день"]):
                    _append_layer("action_capacity", "from_answers", line)
                if any(token in lowered for token in ["язык", "рынок", "польша", "контакт", "сообще", "интеграц"]):
                    _append_layer("integration", "from_answers", line)
                if any(token in lowered for token in ["хочу", "предпоч", "направлен", "роль", "маршрут"]):
                    _append_layer("route_preferences", "from_answers", line)

        if isinstance(resume_analysis, dict):
            for key in ("professions", "achievements", "skills", "what_is_good"):
                items = resume_analysis.get(key)
                if isinstance(items, list):
                    for item in items:

# --- def _detect_profile_domain ---
        report["social_integration"] = integration

    def _detect_profile_domain(
        self,
        story_analysis: dict[str, Any],
        answers_text: str = "",
        story_text: str = "",
    ) -> str:
        chunks = [
            str(story_analysis.get("current_identity", "")),
            str(story_analysis.get("story_summary", "")),
            " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
            " ".join(str(item) for item in story_analysis.get("skills", []) if isinstance(item, str)),
            str(answers_text or ""),
            str(story_text or ""),
        ]
        blob = " ".join(chunks).lower().replace("ё", "е")

        core_signals = [
            "инженер-сметчик",
            "инженер сметчик",
            "сметчик",
            "смет",
            "quantity surveyor",
            "cost estimator",
        ]
        support_signals = [
            "строитель",
            "construction",
            "проектная документац",
            "документац",
            "материал",
            "обьем работ",
            "объем работ",
            "подрядчик",
            "проектировщик",
            "строительные нормы",
            "помощник инженера",
            "координатор строительных проектов",
            "site office",
            "construction project assistant",
        ]

        core_hits = {token for token in core_signals if token in blob}
        support_hits = {token for token in support_signals if token in blob}

        if core_hits and (support_hits or len(core_hits) >= 2):
            return CONSTRUCTION_ESTIMATION_DOMAIN
        return ""

    def _is_forbidden_construction_main_path(self, value: str) -> bool:
        text = str(value or "").strip().lower().replace("ё", "е")
        if not text:
            return True

        allowed_markers = [
            "assistant cost estimator",
            "junior quantity surveyor",
            "construction documentation specialist",
            "technical assistant construction",
            "construction project assistant",
            "site office assistant",
            "project coordinator in construction company",
            "back-office specialist in construction / engineering company",
            "administrative assistant in construction / engineering company",
        ]
        if any(marker in text for marker in allowed_markers):
            return False

        forbidden_markers = [
            "generic back-office specialist",
            "sales operations assistant",
            "master of shift",
            "warehouse team lead",
            "courier",
            "private repair jobs",
            "tile",
            "drywall",
            "furniture work",
            "частные заказы",
            "плитк",
            "гипсокарт",
            "покраск",
            "ремонт",
            "курьер",
            "кладов",
            "склад",
        ]
        if any(marker in text for marker in forbidden_markers):
            return True

        if "administrative assistant" in text and "construction" not in text and "engineering" not in text:
            return True
        if "back-office specialist" in text and "construction" not in text and "engineering" not in text:
            return True

        return False

    def _contains_forbidden_construction_first_step_terms(self, value: str) -> bool:
        text = str(value or "").lower().replace("ё", "е")
        return any(term in text for term in CONSTRUCTION_FORBIDDEN_FIRST_STEP_TERMS)

    def _enforce_domain_specific_routes(self, report: dict[str, Any], profile_domain: str) -> None:
        if profile_domain != CONSTRUCTION_ESTIMATION_DOMAIN:
            return

        decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
        main_path = str(decision.get("recommended_main_path", "")).strip()
        if self._is_forbidden_construction_main_path(main_path):
            decision["recommended_main_path"] = "Assistant Cost Estimator / Junior Quantity Surveyor"

        backup_path = str(decision.get("backup_path", "")).strip()
        if self._is_forbidden_construction_main_path(backup_path):
            decision["backup_path"] = "Construction Documentation Specialist / Technical Assistant Construction"

        avoid_for_now = str(decision.get("avoid_for_now", "")).strip()
        avoid_note = "Избегать generic office ролей и несвязанных с construction подработок как основного пути."
        if avoid_note not in avoid_for_now:
            decision["avoid_for_now"] = f"{avoid_note} {avoid_for_now}".strip()

        why_this_path = str(decision.get("why_this_path", "")).strip()
        domain_note = "Профиль зафиксирован в домене construction engineering / cost estimation."
        if domain_note not in why_this_path:
            decision["why_this_path"] = f"{domain_note} {why_this_path}".strip()

        report["career_decision"] = decision

        market_analysis = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
        for idx, item in enumerate(market_analysis):
            if not isinstance(item, dict):
                continue
            profession = str(item.get("profession", "")).strip()
            if self._is_forbidden_construction_main_path(profession):
                replacement = CONSTRUCTION_ESTIMATION_ROLES[min(idx, len(CONSTRUCTION_ESTIMATION_ROLES) - 1)]
                item["profession"] = replacement
        report["market_analysis"] = market_analysis

        recommendations = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
        for idx, item in enumerate(recommendations):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if self._is_forbidden_construction_main_path(title):

# --- def _enforce_domain_specific_routes ---
        return any(term in text for term in CONSTRUCTION_FORBIDDEN_FIRST_STEP_TERMS)

    def _enforce_domain_specific_routes(self, report: dict[str, Any], profile_domain: str) -> None:
        if profile_domain != CONSTRUCTION_ESTIMATION_DOMAIN:
            return

        decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
        main_path = str(decision.get("recommended_main_path", "")).strip()
        if self._is_forbidden_construction_main_path(main_path):
            decision["recommended_main_path"] = "Assistant Cost Estimator / Junior Quantity Surveyor"

        backup_path = str(decision.get("backup_path", "")).strip()
        if self._is_forbidden_construction_main_path(backup_path):
            decision["backup_path"] = "Construction Documentation Specialist / Technical Assistant Construction"

        avoid_for_now = str(decision.get("avoid_for_now", "")).strip()
        avoid_note = "Избегать generic office ролей и несвязанных с construction подработок как основного пути."
        if avoid_note not in avoid_for_now:
            decision["avoid_for_now"] = f"{avoid_note} {avoid_for_now}".strip()

        why_this_path = str(decision.get("why_this_path", "")).strip()
        domain_note = "Профиль зафиксирован в домене construction engineering / cost estimation."
        if domain_note not in why_this_path:
            decision["why_this_path"] = f"{domain_note} {why_this_path}".strip()

        report["career_decision"] = decision

        market_analysis = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
        for idx, item in enumerate(market_analysis):
            if not isinstance(item, dict):
                continue
            profession = str(item.get("profession", "")).strip()
            if self._is_forbidden_construction_main_path(profession):
                replacement = CONSTRUCTION_ESTIMATION_ROLES[min(idx, len(CONSTRUCTION_ESTIMATION_ROLES) - 1)]
                item["profession"] = replacement
        report["market_analysis"] = market_analysis

        recommendations = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
        for idx, item in enumerate(recommendations):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if self._is_forbidden_construction_main_path(title):
                item["title"] = CONSTRUCTION_ESTIMATION_ROLES[min(idx, len(CONSTRUCTION_ESTIMATION_ROLES) - 1)]
        report["career_recommendations"] = recommendations

        bridges = report.get("career_bridges") if isinstance(report.get("career_bridges"), list) else []
        for item in bridges:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            if role == "administrative assistant":
                item["role"] = "Administrative Assistant in construction / engineering company"
            elif role == "back-office specialist":
                item["role"] = "Back-office Specialist in construction / engineering company"
        report["career_bridges"] = bridges

        solutions = report.get("real_solutions") if isinstance(report.get("real_solutions"), list) else []
        if solutions:
            first = solutions[0] if isinstance(solutions[0], dict) else {}
            first_title = str(first.get("title", "")).strip()
            if self._is_forbidden_construction_main_path(first_title):
                first["title"] = "Решение №1: Assistant Cost Estimator / Junior Quantity Surveyor"
            first["first_step"] = CONSTRUCTION_DOMAIN_FIRST_STEP_ACTION
            first["timeline"] = str(first.get("timeline") or "1-3 недели")
            solutions[0] = first
        report["real_solutions"] = solutions

        action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
        today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
        current_today_action = str(today.get("action", "")).strip()

        # Domain lock: always keep the first step market-check oriented for estimator track.
        if not current_today_action or self._contains_forbidden_construction_first_step_terms(current_today_action):
            today["action"] = CONSTRUCTION_DOMAIN_FIRST_STEP_ACTION
        else:
            today["action"] = CONSTRUCTION_DOMAIN_FIRST_STEP_ACTION

        today["timebox"] = "15 минут"
        today["result"] = (
            "Есть список из 10 вакансий и перечень повторяющихся требований рынка "
            "для маршрута инженера-сметчика."
        )
        action_plan["today"] = today
        report["action_plan"] = action_plan
        report["first_step_buttons"] = list(CONSTRUCTION_DOMAIN_FIRST_STEP_BUTTONS)

    def _preferred_polish_roles(self, story_analysis: dict[str, Any]) -> list[str]:
        chunks = [
            str(story_analysis.get("current_identity", "")),
            " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
            " ".join(str(item) for item in story_analysis.get("skills", []) if isinstance(item, str)),
        ]
        haystack = " ".join(chunks).lower()

        profile_domain = self._detect_profile_domain(story_analysis)
        if profile_domain == CONSTRUCTION_ESTIMATION_DOMAIN:
            return CONSTRUCTION_ESTIMATION_ROLES[:4]

        project_ops_keywords = ["проект", "ngo", "education", "participant", "участник", "program", "координатор"]
        if sum(1 for keyword in project_ops_keywords if keyword in haystack) >= 2:
            return [
                "Operations Coordinator",
                "Project Coordinator",
                "Program Assistant",
                "Back-office Specialist",
            ]

        sales_ops_keywords = ["продаж", "sales", "crm", "sap", "erp", "аккаунт", "клиент", "лид"]
        if sum(1 for keyword in sales_ops_keywords if keyword in haystack) >= 2:
            return [
                "Sales Operations Assistant",
                "CRM Specialist",
                "Sales Support Specialist",
                "Administrative Assistant",
            ]

        admin_keywords = [
            "админ",
            "администра",
            "докумен",
            "документооборот",
            "office",
            "back-office",
            "координа",
            "поручен",
            "срок",
            "процесс",
            "excel",
            "гос",
            "formal procedure",
        ]
        if sum(1 for keyword in admin_keywords if keyword in haystack) >= 2:
            return [
                "Administrative Assistant",
                "Back-office Specialist",
                "Document Controller",
                "Operations Coordinator",
            ]

        return []

    def _normalize_admin_backoffice_roles(self, report: dict[str, Any], preferred_titles: list[str]) -> None:

```

## Раздел 3. Оркестрация в боте (raw фрагменты)
Ниже ключевые функции из handlers/career.py:
- _build_and_send_report
- _apply_route_choice_to_report
- _apply_selected_route_regeneration
- handle_route_selection_actions
- validate_final_report
- _send_final_map_bundle
- _reconcile_country_duration

```python
# --- async def _build_and_send_report ---


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
    if _route_context_missing({**data, "route_context": route_context}):
        await state.update_data(route_context_index=int(data.get("route_context_index") or 0), awaiting_route_context=True)
        await _start_route_context_intake(message, state, lang)
        return
    user_mode = str(data.get("user_mode") or "calm_steps")
    decision_layers = _build_decision_layers(data, story_analysis, answers_text)
    report_generation_id = report_generation_id or str(uuid.uuid4())
    await state.update_data(report_generation_id=report_generation_id)

    await state.set_state(CareerFlow.GENERATING_REPORT)
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

# --- def _apply_route_choice_to_report ---


def _apply_route_choice_to_report(report: dict, action: str, rows: list[dict[str, str]]) -> str:
    decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
    if not decision:
        return ""

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
        report["career_decision"] = decision
        return str(decision.get("recommended_main_path") or "").strip()

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
        decision_summary = str(decision.get("decision_summary") or "").strip()
        suffix = "Маршрут зафиксирован совместно с пользователем на этапе выбора перед финальной картой."
        if suffix not in decision_summary:
            decision["decision_summary"] = f"{decision_summary} {suffix}".strip()
        report["career_decision"] = decision
    return selected_route


def _short_conclusion_7_lines(report: dict) -> str:
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
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
    recommended_route = str(decision.get("recommended_main_path") or "").strip() or "маршрут уточняется"

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

# --- def _apply_selected_route_regeneration ---


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
    if _is_construction_estimation_domain(report):
        stable = _construction_route_stable()
        upskill = _construction_route_upskill()
        comparison = _construction_route_comparison()
        report["route_stable"] = stable
        report["route_upskill"] = upskill
        report["route_comparison"] = comparison
        return [

# --- async def handle_route_selection_actions ---
@router.message(CareerFlow.ROUTE_SELECTION, F.text.in_(ALL_ROUTE_CHOICE_ACTIONS))
@router.message(CareerFlow.FINAL_READY, F.text.in_(ALL_ROUTE_CHOICE_ACTIONS))
async def handle_route_selection_actions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _user_language(data)
    report = data.get("final_report") or {}
    rows = data.get("route_compare_rows") if isinstance(data.get("route_compare_rows"), list) else _build_route_comparison_rows(report)
    action = (message.text or "").strip()

    if action and await _maybe_switch_to_crisis_support(message, state, lang, action, source="route_selection"):
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

    if bool(data.get("awaiting_career_strategy_choice")) or action in ALL_CAREER_STRATEGY_ACTIONS:
        if action not in ALL_CAREER_STRATEGY_ACTIONS:
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

# --- def validate_final_report ---


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
        "Ваш основной маршрут — не уход в любую офисную работу, а возвращение в строительную сферу через адаптационный мост.\n\n"
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
        if len(roles) > 2:
            decision["backup_path"] = " / ".join(roles[2:4])
    decision["why_this_path"] = goal
    decision["why_not_other_paths"] = risks[:3] if risks else ["Сначала нужен маршрут с прогнозируемым входом и подтверждаемыми требованиями."]
    report["career_decision"] = decision


# --- async def _send_final_map_bundle ---


async def _send_final_map_bundle(message: Message, state: FSMContext, lang: str, report: dict) -> None:
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

    await state.set_state(CareerFlow.FINAL_READY)
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

    await state.set_state(CareerFlow.FINAL_READY)
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
    await message.answer(t(lang, "post_result_hint"), reply_markup=result_actions_keyboard())


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

# --- def _reconcile_country_duration ---


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

```

## Раздел 4. Короткая справка (человеческим языком)
1) Система сначала собирает факты и строит структурированный JSON-отчёт.
2) Затем код применяет guardrails, чтобы исключить выдумки и доменные ошибки.
3) Для construction/cost estimation действует доменная фиксация маршрутов и first-step.
4) Перед финальной отправкой работает валидатор домена; при сбое — автопересборка.
5) При выборе маршрута создаётся новая версия отчёта с пересобранными секциями.
