from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.analytics import pilot_quality_metrics


def _format_percent(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return "0.00%"


def _dropoff_summary(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    chunks: list[str] = []
    for item in value[:3]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        state = str(item[0]).strip() or "unknown"
        count = item[1]
        chunks.append(f"{state}: {count}")
    return "; ".join(chunks) if chunks else "-"


def _build_table(samples: list[int]) -> str:
    snapshots = {sample: pilot_quality_metrics(sample_limit=sample) for sample in samples}

    headers = ["Метрика"] + [str(sample) for sample in samples]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    metrics = [
        ("sample_users", "Размер выборки", lambda v: str(int(v) if str(v).strip() else 0)),
        ("reached_map_percent", "Процент дошедших до карты", _format_percent),
        ("conflict_percent", "Процент конфликтов", _format_percent),
        ("disagreed_percent", "Процент не согласен", _format_percent),
        ("first_step_too_hard_percent", "Процент слишком сложно", _format_percent),
        ("specialist_click_percent", "Процент перехода к специалисту", _format_percent),
        ("pdf_or_report_error_percent", "Ошибки PDF/отчета", _format_percent),
        ("dropoff_stages", "Топ точки выхода", _dropoff_summary),
    ]

    for key, label, formatter in metrics:
        values = [formatter(snapshots[sample].get(key)) for sample in samples]
        lines.append("| " + " | ".join([label] + values) + " |")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Печатает daily review таблицу по pilot_quality_metrics для выбранных выборок пользователей.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        nargs="+",
        default=[50, 100],
        help="Список размеров выборки (по умолчанию: 50 100)",
    )
    args = parser.parse_args()

    samples = [max(1, int(item)) for item in args.samples]
    print(_build_table(samples))


if __name__ == "__main__":
    main()
