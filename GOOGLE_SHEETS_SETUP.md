# Google Sheets Интеграция

## Что передаётся в Google Sheets

Каждое событие пользователя в боте автоматически логируется в Google Sheets через webhook:

```json
{
  "timestamp": "2026-07-01T20:15:30+00:00",
  "public_user_id": "20260701-0001",
  "event": "report_generated",
  "state": "FINAL_READY",
  "action": "",
  "user_mode": "calm_steps",
  "language": "ru",
  "days_since_first_seen": 0,
  "meta": {
    "has_income_signal": true
  }
}
```

## Как настроить

### Шаг 1: Создать Google Apps Script

1. Зайти в [Google Apps Script](https://script.google.com/)
2. Создать новый проект
3. Вставить этот код:

```javascript
function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    
    // Открыть вашу Google Sheet (замените на реальный ID)
    const sheet = SpreadsheetApp.openById("YOUR_SPREADSHEET_ID")
                                .getSheetByName("events");
    
    // Преобразовать объект в строку
    const row = [
      payload.timestamp,
      payload.public_user_id,
      payload.event,
      payload.state,
      payload.user_mode,
      JSON.stringify(payload.meta || {})
    ];
    
    sheet.appendRow(row);
    
    return ContentService
      .createTextOutput(JSON.stringify({status: "ok"}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (e) {
    return ContentService
      .createTextOutput(JSON.stringify({error: e.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
```

### Шаг 2: Развернуть как веб-приложение

1. Нажать "Deploy" → "New deployment"
2. Тип: "Web app"
3. Выполнить как: ваш Google аккаунт
4. Кто имеет доступ: "Anyone"
5. Скопировать URL (выглядит как `https://script.google.com/macros/d/{ID}/userweb`)

### Шаг 3: Подставить в Railway

В переменных окружения на Railway добавить:

```
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/d/{ID}/userweb
```

Где `{ID}` - это ID из URL развёрнутого скрипта.

### Шаг 4 (опционально): Выставить переменные аналитики

```
ANALYTICS_REGISTRY_PATH=/data/reports/user_registry.json
ANALYTICS_EVENTS_LOG_PATH=/data/reports/behavior_events.jsonl
```

## Готовые события

Интеграция отправляет все события:
- `report_generated` - отчёт выгенерирован
- `conflict_detected` - обнаружен конфликт при ответе
- `route_selected` - пользователь выбрал маршрут
- `first_step_too_hard` - первый шаг слишком сложный
- `html_ready` - HTML готов
- `pdf_ready` - PDF готов
- `pdf_fallback_html` - PDF fallback на HTML
- `specialist_clicked` - клик на специалиста
- и другие...

## Если webhook не установлен

Если переменная `GOOGLE_SHEETS_WEBHOOK_URL` не установлена или пустая:
- События **продолжат логироваться** локально в SQLite и JSONL
- Google Sheets просто не будет получать данные
- Всё работает как раньше, но без облачной синхронизации

## Локальное тестирование

```bash
GOOGLE_SHEETS_WEBHOOK_URL="" python test_deploy_check.py
# без webhook
```

```bash
GOOGLE_SHEETS_WEBHOOK_URL="https://..." python test_deploy_check.py
# с webhook - если сработает, увидите событие в Google Sheets
```
