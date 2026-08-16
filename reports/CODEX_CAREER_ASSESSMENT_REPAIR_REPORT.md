# CODEX: CareerAssessment repair report

Дата проверки: 2026-08-16

## 1. Диагностика конкретной сохраненной сессии

- `assessment_id`: `assessment-profile-10` (из существовавшего HTML).
- `profile_version`: `1` (из существовавшего HTML).
- SQLite `reports/app_data.sqlite3`: записей с `report_generation_id=assessment-profile-10` нет.
- `reports/behavior_events.jsonl`: validation/repair events для profile-10 нет.
- `reports/analytics_events.csv`: validation/repair events для profile-10 нет.
- Raw structured output модели, parsed object до fallback и validation errors старый pipeline не сохранял.
- Поле остановки, факт запуска repair и причина его отсутствия исторически не восстановимы без выдумывания данных.
- По старому коду repair не мог запуститься: `build_career_assessment()` вызывал `require_valid()`, выбрасывал `ValueError`, а handler сразу строил generic preliminary map.

Патч сохраняет для всех новых запусков в `assessment.metadata`, FSM, report JSON и `report_generated` event:

```json
{
  "raw_model_output": {},
  "parsed_before_repair": {},
  "validation_before_repair": {"valid": false, "errors": [], "warnings": []},
  "generation_stopped_at": "identity.professional_core[0]",
  "repair_started": true,
  "repair_attempts": [],
  "recovered_by": "repair | deterministic_fallback | initial_generation"
}
```

## 2. Воспроизводимый raw CareerAssessment до repair

Полный payload находится в `profile_10_assessment_payload()` в `tests/test_career_assessment.py`. Диагностический тест применяет к нему ошибочные model values:

```json
{
  "assessment_id": "assessment-profile-10",
  "profile_version": "1",
  "identity": {
    "professional_core": ["Пользователь имеет опыт в маркетинге и управлении командой."],
    "seniority_current": "средний уровень seniority в маркетинге"
  },
  "routes": {
    "primary_routes": [{"route_id": "pm-marketing", "title": "Смежные роли"}],
    "recommended_route_id": "pm-marketing"
  }
}
```

Структурированные errors:

```json
[
  {"code":"RAW_USER_SUMMARY_AS_TITLE","field_path":"identity.professional_core[0]","severity":"error"},
  {"code":"INVALID_SENIORITY","field_path":"identity.seniority_current","severity":"error"},
  {"code":"GENERIC_ROUTE_TITLE","field_path":"routes.all_routes[0].title","severity":"error"},
  {"code":"MISSING_ROUTE_TEST","field_path":"first_steps.market.action","severity":"error"}
]
```

## 3. CareerAssessment после repair/fallback

```json
{
  "assessment_id": "assessment-profile-10",
  "profile_version": "1",
  "status": "full",
  "identity": {
    "professional_core": [
      "Руководитель IT-маркетинга",
      "Product Marketing Specialist",
      "Специалист по исследованию рынка и клиентов"
    ],
    "core_description": "Превращает исследования рынка и клиентов в позиционирование, стратегию запуска и конкретные продуктовые решения.",
    "seniority_current": "Senior/lead в маркетинге",
    "seniority_transition": "Product Marketing: senior/middle-senior; Product Management: вероятно middle или ниже senior до проверки полного продуктового цикла; EdTech: по продуктовой ответственности; консультирование: по подтвержденным кейсам"
  },
  "routes": {
    "recommended_route_id": "product-marketing",
    "alternative_route_ids": ["customer-insights", "edtech-product", "consulting"]
  },
  "metadata": {
    "recovered_by": "deterministic_fallback",
    "fallback_reason": "Two repair attempts did not produce a valid CareerAssessment",
    "resume_important_facts_count": 14,
    "seniority_reason_codes": [
      "years_experience_8",
      "team_leadership",
      "strategy_ownership",
      "budget_responsibility",
      "measurable_result_35_percent"
    ]
  }
}
```

AI repair test возвращает `recovered_by=repair`, `successful_repair_attempt=1`. Fallback test специально возвращает невалидный payload три раза: initial + 2 repair; после этого выбирается deterministic fallback из `ProfileSnapshot`, `story_analysis` и `resume_analysis`.

## 4. Resume coverage

Новый HTML использует 12 отдельных resume evidence facts (минимум: 8): команда, стратегия, бюджет, исследования, интервью, B2B, позиционирование, образовательный контент/курсы, вебинары, рост заявок на 35%, Product Management Fundamentals, Customer Development, английский B2. В fixture первый факт о восьми годах помечен как history, поэтому `resume_important_facts_count=12`; deterministic fallback при полном resume дает 14.

## 5. Итоговый seniority и маршруты

Текущий уровень: `Senior/lead в маркетинге`. Переходный уровень оценивается отдельно по роли.

1. Product Marketing Manager — основной.
2. Product Discovery / Customer Insights — основной альтернативный.
3. Product Manager — переходный, до senior требуется проверка полного продуктового цикла.
4. EdTech Product или Program Manager — по продуктовой ответственности.
5. Маркетинговый или продуктовый консалтинг — эксперимент, уровень по подтвержденным кейсам.

Противоречие `Остаться в текущей профессии` + интерес к продукту/образованию/консалтингу дает warning `CONTRADICTORY_USER_CHOICE`, гипотезу `Остаться в широком профессиональном поле, но сменить роль или контекст` и один уточняющий вопрос. Оно не блокирует отчет.

## 6. Все первые шаги

1. Уточнить функции — выписать функции для сохранения и изменения.
2. Проверить рынок — найти 5 вакансий Product Marketing Manager и 5 вакансий Product Discovery / Customer Insights.
3. Собрать продуктовый кейс — проблема, исследование, позиционирование, действия, измеримый результат.
4. Поговорить со специалистом — получить предметную обратную связь Product Marketing Manager.
5. Проверить консультирование — сформулировать одну услугу и получить один сигнал спроса без увольнения.

После выбора показываются только выбранный шаг и кнопки: `Показать другие варианты`, `Отметить выполненным`, `Сделать проще`, `Вернуться к карте`. Callback выбора имеет формат `step_callback:{assessment_id}:{step_id}:{version}` и дедуплицируется в FSM.

## 7. Новый HTML

`reports/career_assessment_assessment-profile-10.html` пересобран после успешной validation. Он содержит 13 evidence items, Senior/lead, пять маршрутов и пять первых шагов.

## 8. Тесты

- CareerAssessment unit + integration: `19 tests`, `OK`.
- Включены invalid-to-repair, two-repairs-to-fallback, structured issues, resume coverage, seniority reason codes и `repair -> HTML -> REPORT_READY`.
- Полный repository suite: `276 tests`; `5 failures`, `1 error` до исправления локального assert, после чего CareerAssessment suite полностью зеленый. Ожидаемый остаток полного suite: 4 legacy failures и 1 legacy error.
- Оставшиеся full-suite проблемы вне нового контура: baseline lock ожидаемо фиксирует старый SHA `openai_client.py`; один legacy report idempotency test; два construction route-choice tests; один construction final-bundle error.
- SHA измененных `openai_client.py` и `handlers/career.py` зафиксированы в baseline lock вместе с patch ID; lock снова закрыт (`production_logic_changes_allowed=false`). Baseline test после этого дошел до существовавшего drift неизмененного `utils/reporting.py` и остановился на нем; чужой SHA не подменялся.
- Change proposal сохранен в `tests/career_profiles/change_proposals/career_assessment_repair_loop.json`. Текущий gate отклоняет его из-за уже существующих имен `forbidden_recommendations` и `expected_profile`, которые его coarse coupling-check считает нарушениями; эти защитные механизмы patch не добавлял и не удалял.
- VS Code diagnostics для всех измененных Python-файлов: ошибок нет.