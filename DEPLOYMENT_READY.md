# 🚀 DEPLOYMENT READY - Финальный чеклист

## ✅ Статус: ГОТОВ К ВЫКАТКЕ

Дата: 2026-07-01  
Статус тестов: **37/37 PASSED**  
Pre-deploy check: **ALL PASSED**  
PDF health check: **3/3 engines OK**

---

## 📋 Обязательные переменные окружения для Railway

```env
# Необходимые (без них бот не запустится)
BOT_TOKEN=<ваш Telegram Bot Token>
OPENAI_API_KEY=<ваш OpenAI API key>

# Опциональные (рекомендуется установить)
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/d/{ID}/userweb
ANALYTICS_REGISTRY_PATH=/data/reports/user_registry.json
ANALYTICS_EVENTS_LOG_PATH=/data/reports/behavior_events.jsonl

# Если не установить GOOGLE_SHEETS_WEBHOOK_URL - просто не будет облачной синхронизации,
# но бот продолжит работать (события остаются локально в SQLite).
```

---

## 🔧 Инструкция для Google Sheets

Смотрите полную инструкцию: [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)

Быстро:
1. Создать Google Apps Script с функцией `doPost(e)`
2. Deploy как Web app
3. Скопировать URL в `GOOGLE_SHEETS_WEBHOOK_URL`

---

## ✨ Что включено в релиз

### Секция 1-11: Функциональность
- ✅ Интервьюирование (8 вопросов для calm_steps, FACTS_ONLY)
- ✅ CV анализ (загрузка, парсинг, синхронизация)
- ✅ Дерево предпосылок и психо-модель
- ✅ 3 маршрута с rich comparison
- ✅ Post-report actions (6 новых кнопок)
- ✅ Overload protection (если "слишком сложно" → 5-минутный шаг)

### Секция 12-14: Надёжность
- ✅ SQLite persistence (primary DB)
- ✅ Recovery by report_generation_id (idempotency)
- ✅ Conflict detection при stale button answers
- ✅ HTML mandatory + PDF fallback (3 engine: Playwright, xhtml2pdf, plain)

### Секция 15-16: Production-ready
- ✅ No syntax errors
- ✅ Full test coverage (37 tests)
- ✅ Pre-deploy checks pass
- ✅ Analytics metrics ready
- ✅ Error handling и graceful degradation

---

## 🎯 Ручной smoke-тест в Telegram (обязательный)

**Сценарий 1: Базовый путь**
```
/start → Выбрать "Нормальный разбор" → 
Написать историю → 
Ответить на 2 вопроса → 
Выбрать маршрут →
✅ Должен вывести финальную карту + PDF
```

**Сценарий 2: CV + PDF fallback**
```
При выборе резюме → загрузить PDF →
✅ Должен распарсить и включить в отчёт →
✅ Если PDF не генерится → fallback на HTML (всё равно работает)
```

**Сценарий 3: Overload protection**
```
На финальной карте → Клик "Начать первый шаг" →
Если в шаге текст содержит "не знаю / страшно / слишком сложно" →
✅ Шаг должен переписаться на "Открыть 3 вакансии и выбрать 1" (5 минут)
```

**Сценарий 4: Route disagreement**
```
На экране маршрутов → Клик "Я не согласен с маршрутом" →
✅ Должен показать форму для ввода причины →
✅ При сохранении → вернуться в меню с новым маршрутом
```

---

## 🔍 Мониторинг первые 30 минут

Смотреть логи на предмет:
- `report_generated` — должны появиться
- `conflict_detected` — нормально, если 0
- `pdf_failed` — если > 5%, откатить
- `first_step_too_hard` — нормально, если есть

---

## 📦 Файлы для деплоя

```
bot.py                       # Главный бот
handlers/career.py          # Основная логика (3900+ строк)
keyboards.py                # Кнопки и UI
states.py                   # FSM состояния
config.py                   # Конфиг (уже включает GOOGLE_SHEETS_WEBHOOK_URL)
openai_client.py            # LLM интеграция
prompts.py                  # Системные промпты
report_api.py               # FastAPI для отчётов
utils/
  ├─ reporting.py          # HTML + PDF генерация
  ├─ analytics.py          # События + Google Sheets
  ├─ persistence.py        # SQLite DB
  ├─ localization.py       # Тексты на русском/белорусском
requirements.txt            # Dependencies (включая aiohttp)
tests/                      # 37 unit tests (все проходят)
```

---

## ⚡ Быстрый start на Railway

```bash
# 1. Fork репо (если не уже)
# 2. Connect Railway
# 3. Set environment variables (см. выше)
# 4. Deploy
# 5. Проверить logs: tail -f logs
# 6. Запустить smoke-тест в Telegram
```

---

## 🚨 Откат (если что-то не так)

Если что-то сломалось:
1. Откатить коммит на Railway
2. SQLite DB останется в `/data/reports/app_data.sqlite3`
3. HTML/PDF отчёты останутся в `/data/reports/`
4. Пользователи смогут восстановиться через `/start` → recovery flow

---

## 📞 Контакты / Поддержка

При ошибках:
1. Проверить логи на Railway
2. Проверить `GOOGLE_SHEETS_WEBHOOK_URL` формат
3. Убедиться что `BOT_TOKEN` и `OPENAI_API_KEY` установлены
4. Перезапустить бота

---

**Status: READY TO DEPLOY ✅**

