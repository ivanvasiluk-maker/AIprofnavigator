# Career GPS MVP

Telegram-бот для карьерной и социальной диагностики человека с последующей персональной картой развития.

## Базовый сценарий MVP

1. Пользователь рассказывает историю текстом или голосом.
2. Бот выделяет профиль, навыки, ограничения и цели.
3. Бот задаёт 5-7 уточняющих вопросов.
4. После ответов бот собирает Digital Human профиль.
5. Бот предлагает 3-5 карьерных направлений.
6. Бот строит персональную карту развития.
7. Бот выдаёт 5-7 действий на ближайшую неделю.

## Дополнения к техническому заданию

### Обновлённая логика диагностики

Система анализирует человека по четырём направлениям:

1. Профессиональный профиль:
   - опыт работы;
   - образование;
   - навыки;
   - компетенции;
   - достижения;
   - жизненный опыт;
   - предпринимательский опыт;
   - интересы и карьерные цели.

   Формат сбора: текст, голос, кнопки для ускорения прохождения.

2. Психоэмоциональное состояние:
   - страхи;
   - сопротивление изменениям;
   - прокрастинация;
   - тревога;
   - неуверенность;
   - выгорание;
   - ограничения, которые мешают профессиональной реализации.

   Используются структурированные вопросы и уточнения.

3. Социальная поддержка:
   - наличие семьи;
   - наличие друзей;
   - наличие профессиональных контактов;
   - наличие поддержки в новой стране;
   - уровень социальной изоляции;
   - особенности ситуации пользователя, включая single parent, миграцию, политическое преследование и другие кейсы.

   Формат: кнопки, текст, голосовой ответ.

4. Социальная интеграция:
   - участие в сообществах;
   - владение языком;
   - взаимодействие с местным населением;
   - опыт адаптации;
   - барьеры интеграции.

   Дополнительно пользователь рассказывает свою историю в свободной форме, чтобы учесть факторы, которые не видны стандартным опросником.

### Заключение

Итоговое заключение строится на основе четырёх направлений:

1. профессиональная ситуация;
2. психоэмоциональное состояние;
3. социальная поддержка;
4. социальная интеграция.

Система формирует персональную карту развития человека.

### Персональный план

После диагностики создаются три независимых трека развития.

1. Трек 1. Профессиональное развитие:
   - карьерные рекомендации;
   - навыки для освоения;
   - языки для изучения;
   - шаги поиска работы;
   - рекомендации по обучению.

2. Трек 2. Психологическая устойчивость:
   - КПТ;
   - ДБТ;
   - ACT;
   - другие направления третьей волны;
   - работа с тревогой;
   - эмоциональная регуляция;
   - преодоление прокрастинации;
   - толерантность к неопределённости;
   - навыки кризисной устойчивости.

3. Трек 3. Социальная интеграция:
   - расширение круга общения;
   - поиск сообществ;
   - развитие языка;
   - участие в мероприятиях;
   - интеграционные активности.

### Ежедневное сопровождение

Каждый день пользователь получает задания по трём направлениям:

1. профессиональное развитие;
2. психологическая устойчивость;
3. социальная интеграция.

После выполнения пользователь отмечает результат:

- получилось;
- частично получилось;
- не получилось.

Система адаптирует дальнейший маршрут.

### Еженедельный чекпоинт

Раз в неделю пользователь проходит короткий обзор.

Вопросы:

- Что сделано по профессии?
- Что сделано по интеграции?
- Какие психологические навыки использовались?
- Что помогло?
- Что не получилось?
- Какие появились препятствия?

На основе ответов система корректирует план.

### Монетизация

1. Уровень 1:
   самостоятельное сопровождение через бота.

2. Уровень 2:
   персонализированное сопровождение специалистом.

   В зависимости от запроса это может быть карьерный консультант, коуч, психолог, специалист по социальной интеграции или волонтёр.

3. Уровень 3:
   группы поддержки.

   Форматы: карьерные группы, группы психологической поддержки, интеграционные группы.

### Геймификация

За выполнение задач пользователь получает баллы:

- выполнение ежедневных заданий;
- прохождение недельных чекпоинтов;
- удержание серии активности;
- достижение целей.

Баллы могут конвертироваться в скидку на подписку до 50%.

Цель геймификации — повышение удержания и вовлечённости пользователя.

## Features

- text input
- voice input
- transcription
- structured JSON responses from OpenAI
- no database
- no long questionnaires
- FSM context only

## Run

## Environment variables

Create `.env` from `.env.example` and set values locally:

```bash
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_TRANSCRIBE_MODEL=whisper-1
```

For deployment, set these variables in your hosting platform secrets manager.
Do not store real keys in repository files.

Behavior analytics to Google Sheets (anonymized):

```bash
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/<deployment-id>/exec
ANALYTICS_REGISTRY_PATH=reports/user_registry.json
ANALYTICS_EVENTS_LOG_PATH=reports/behavior_events.jsonl
```

- `user_registry.json` stores mapping `telegram_user_id -> public_user_id` locally.
- `public_user_id` format is `YYYYMMDD-XXXX` (example: `20260619-0007`).
- Google Sheets receives only anonymized behavior events by `public_user_id`.

### Google Sheets quick setup

1. Create a Google Sheet, for example `NextYou Behavior`.
2. In Google Sheets open `Extensions -> Apps Script`.
3. Paste and deploy a simple webhook script:

```javascript
function doPost(e) {
   const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('events')
      || SpreadsheetApp.getActiveSpreadsheet().insertSheet('events');
   const row = JSON.parse(e.postData.contents || '{}');

   if (sheet.getLastRow() === 0) {
      sheet.appendRow([
         'timestamp',
         'public_user_id',
         'event',
         'state',
         'action',
         'user_mode',
         'language',
         'days_since_first_seen',
         'meta_json'
      ]);
   }

   sheet.appendRow([
      row.timestamp || '',
      row.public_user_id || '',
      row.event || '',
      row.state || '',
      row.action || '',
      row.user_mode || '',
      row.language || '',
      row.days_since_first_seen || 0,
      JSON.stringify(row.meta || {})
   ]);

   return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
}
```

4. Deploy as Web App and copy the URL to `GOOGLE_SHEETS_WEBHOOK_URL`.
5. Restart bot and verify that events are appended to `events` sheet.

Notes:
- For behavior analysis per user, use `public_user_id` (stable, pseudonymous identifier).
- `source_tag` from Telegram deep link `/start <tag>` is saved in local registry and can be sent in event meta.
- If legal policy requires, do not push raw Telegram identifiers to external sheets.

### Daily review metrics

To print pilot quality metrics as a table for team daily review:

.\.venv\Scripts\python.exe scripts\pilot_metrics_report.py --samples 50 100

The script uses analytics events and prints:

- percent reached map;
- conflict percent;
- disagree percent;
- first step too hard percent;
- specialist click percent;
- PDF/report error percent;
- top drop-off stages.

### PDF health-check before release

Run a one-command diagnostics report for PDF generation engines:

.\.venv\Scripts\python.exe scripts\pdf_health_check.py

It generates a test HTML report and prints a table with status/details for:

- `playwright`
- `xhtml2pdf`
- `plain-fallback` (readable text PDF via reportlab)

Use this check before deploy to quickly see which engine is stable in the current environment.

PDF font quality (Cyrillic):

```bash
REPORT_PDF_ENGINE=auto
REPORT_PDF_FONT_PATH=C:/Windows/Fonts/arial.ttf
```

If you keep a project font in `fonts/DejaVuSans.ttf`, it will be used automatically.

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```
