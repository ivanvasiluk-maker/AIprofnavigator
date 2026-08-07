# Results

Каждый baseline-run сохраняется в отдельной immutable папке `<run_id>/`.

Единая команда запуска всех профилей:

- `python -m tests.career_profiles.run_all`

Внутри прогона:

- `run_metadata.json` — воспроизводимые параметры запуска
- `summary.json` — агрегированная сводка
- `baseline_summary.json` — baseline-ориентированная сводка в JSON
- `baseline_summary.md` — human-readable baseline summary
- `package_validation.json` — отчёт валидатора комплектности пакета (если включен)
- `change_proposal_gate.json` — результат валидации change proposal gate (если передан proposal)
- `regression_matrix.json` — покейсное сравнение baseline vs current (если передан baseline reference)
- `regression_gate.json` — итоговый статус acceptance после матрицы регрессий (если передан baseline reference)
- `systemic_errors.json` — ошибки, повторившиеся минимум в двух профилях
- `profiles/PROFILE_ID.json` — объединенный профильный результат
- `profile_results/PROFILE_ID.json` — дублируемый профильный export для baseline review
- `judge_logs/PROFILE_ID.judge.json` — детальные результаты оценщиков
- `raw_responses/PROFILE_ID.raw.json` — сырые ответы генератора и retry log

Expected-профили не копируются в payload генератора и доступны только внешнему evaluator layer.