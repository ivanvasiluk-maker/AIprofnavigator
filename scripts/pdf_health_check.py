from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import settings
from utils.reporting import (
    generate_html_report_file,
    generate_pdf_from_html_file_with_error,
    generate_plain_pdf_from_html_file_with_error,
)


def _sample_report() -> dict:
    return {
        "digital_human": {
            "current_state": "Тестовый профиль для проверки PDF",
            "main_asset": "Сильный прикладной опыт",
            "main_risk": "Нестабильная генерация PDF",
            "main_barrier": "Техническая несовместимость движка",
            "main_fear": "Потеря форматирования",
            "hidden_strengths": ["Системность", "Упорство"],
        },
        "career_decision": {
            "recommended_main_path": "Тестовый маршрут",
            "why_this_path": "Проверить стабильность рендера",
            "backup_path": "Plain fallback",
            "avoid_for_now": "Слепой запуск без диагностики",
        },
        "action_plan": {
            "today": {
                "action": "Сгенерировать health-check PDF",
                "timebox": "10 минут",
                "result": "Понятно, какой движок стабилен",
            }
        },
        "market_analysis": [],
        "career_recommendations": [],
        "real_solutions": [],
        "career_translation": [],
        "career_bridges": [],
        "what_not_reset": ["Проверочный pipeline", "HTML-first подход"],
        "experience_layers": ["Диагностика инфраструктуры"],
        "career_barriers": [],
        "barrier_landscape": {},
        "weekly_plan": [],
        "development_map": {},
        "social_integration": {},
        "resource_level": "medium",
        "integration_level": "medium",
        "energy_sources": ["Структура", "Контроль качества"],
        "career_priorities": ["Стабильность", "Прозрачная диагностика"],
        "competency_signals": ["Debugging", "Процессный подход"],
        "closing_message": "Health-check завершен",
    }


def _row(engine: str, pdf_path: Path | None, error: str) -> list[str]:
    ok = pdf_path is not None and not error
    status = "OK" if ok else "FAIL"
    path_text = str(pdf_path) if pdf_path else "-"
    details = error or "-"
    return [engine, status, path_text, details]


def _print_table(rows: list[list[str]]) -> None:
    headers = ["Engine", "Status", "PDF", "Details"]
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        safe = [cell.replace("|", "/") for cell in row]
        print("| " + " | ".join(safe) + " |")


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF engine health-check for release readiness.")
    parser.add_argument("--output-dir", default=settings.report_output_dir, help="Directory for generated files.")
    args = parser.parse_args()

    output_dir = str(args.output_dir)
    html_path = generate_html_report_file(_sample_report(), output_dir=output_dir, user_name="PDF_Health_Check")

    original_engine = settings.report_pdf_engine
    rows: list[list[str]] = []

    try:
        settings.report_pdf_engine = "playwright"
        pdf_path, error = generate_pdf_from_html_file_with_error(html_path)
        rows.append(_row("playwright", pdf_path, error))

        settings.report_pdf_engine = "xhtml2pdf"
        pdf_path, error = generate_pdf_from_html_file_with_error(html_path)
        rows.append(_row("xhtml2pdf", pdf_path, error))

        pdf_path, error = generate_plain_pdf_from_html_file_with_error(html_path)
        rows.append(_row("plain-fallback", pdf_path, error))
    finally:
        settings.report_pdf_engine = original_engine

    print(f"HTML: {html_path}")
    _print_table(rows)


if __name__ == "__main__":
    main()
