from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape, unescape
from pathlib import Path
import re
import tempfile
import textwrap
from urllib.parse import unquote, urlparse

from config import settings


@dataclass
class ReportMeta:
    user_name: str
    country: str
    mode: str
    created_at: str


def _resolve_unicode_font_path() -> Path | None:
    candidates: list[Path] = []
    if settings.report_pdf_font_path:
        candidates.append(Path(settings.report_pdf_font_path))

    candidates.extend([
        Path("fonts/DejaVuSans.ttf"),
        Path("fonts/NotoSans-Regular.ttf"),
        Path("fonts/ArialUnicodeMS.ttf"),
        Path("fonts/SegoeUI.ttf"),
        Path("C:/Windows/Fonts/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/NotoSans-Regular.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialuni.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ])
    for path in candidates:
        if path.exists() and path.is_file():
            return path.resolve()
    return None


def _safe_text(value: object, default: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else default


def _list_items(items: object, fallback: str = "-") -> list[str]:
    if not isinstance(items, list):
        return [fallback]
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return cleaned or [fallback]


def _level_label(value: object) -> str:
    normalized = str(value or "").strip().lower()
    labels = {
        "high": "высокий",
        "medium": "средний",
        "low": "низкий",
    }
    return labels.get(normalized, _safe_text(value, "не уточнено"))


def _detect_country(report: dict) -> str:
    profile = str((report.get("digital_human") or {}).get("current_state", "")).lower()
    if "польш" in profile or "poland" in profile:
        return "Poland"
    if "беларус" in profile:
        return "Belarus"
    return "Не уточнено"


def _detect_mode(report: dict) -> str:
    readiness = (report.get("digital_human") or {}).get("career_readiness", {})
    urgency = str((readiness or {}).get("urgency", "")).lower()
    if "высок" in urgency or "high" in urgency:
        return "Survival"
    if "сред" in urgency or "moder" in urgency or "medium" in urgency:
        return "Transition"
    return "Growth"


def build_meta(report: dict, user_name: str = "") -> ReportMeta:
    name = _safe_text(user_name, "Пользователь")
    country = _detect_country(report)
    mode = _detect_mode(report)
    created_at = datetime.now().strftime("%Y-%m-%d")
    return ReportMeta(user_name=name, country=country, mode=mode, created_at=created_at)


def build_telegram_summary(report: dict) -> str:
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    not_reset = report.get("what_not_reset", []) if isinstance(report.get("what_not_reset"), list) else []
    not_reset_block = "\n".join(f"- {item}" for item in _list_items(not_reset)[:4])
    energy_sources = report.get("energy_sources", []) if isinstance(report.get("energy_sources"), list) else []
    energy_block = "\n".join(f"- {item}" for item in _list_items(energy_sources)[:4])
    career_priorities = report.get("career_priorities", []) if isinstance(report.get("career_priorities"), list) else []
    priorities_block = "\n".join(f"- {item}" for item in _list_items(career_priorities)[:4])
    competency_signals = report.get("competency_signals", []) if isinstance(report.get("competency_signals"), list) else []
    competency_block = "\n".join(f"- {item}" for item in _list_items(competency_signals)[:5])
    resource_level_raw = _safe_text(report.get("resource_level"), "не уточнено")
    integration_level_raw = _safe_text(report.get("integration_level"), "не уточнено")
    resource_level = f"{resource_level_raw} ({_level_label(resource_level_raw)})" if resource_level_raw != "не уточнено" else resource_level_raw
    integration_level = f"{integration_level_raw} ({_level_label(integration_level_raw)})" if integration_level_raw != "не уточнено" else integration_level_raw

    summary = [
        "Ваш Career GPS",
        "",
        f"Кто вы сейчас:\n{_safe_text(digital_human.get('current_state'))}",
        f"Что не обнулилось:\n{not_reset_block}",
        f"Источники энергии:\n{energy_block}",
        f"Карьерные приоритеты:\n{priorities_block}",
        f"STAR-компетенции:\n{competency_block}",
        f"Уровень ресурса:\n{resource_level}",
        f"Уровень интеграции:\n{integration_level}",
        f"Главный риск:\n{_safe_text(digital_human.get('main_risk'))}",
        f"Рекомендуемый маршрут:\n{_safe_text(decision.get('recommended_main_path'))}",
        f"Запасной маршрут:\n{_safe_text(decision.get('backup_path'))}",
        f"Первый шаг сегодня:\n{_safe_text(today.get('action'))}",
        "Что хотите сделать дальше?",
    ]
    return "\n\n".join(summary)


def build_offer_text() -> str:
    return (
        "Мы можем не просто дать карту, а помочь пройти первые шаги до реальных вакансий.\n\n"
        "Что входит:\n"
        "- уточнение маршрута;\n"
        "- анализ CV;\n"
        "- подбор первых вакансий;\n"
        "- подготовка откликов;\n"
        "- разбор страхов и барьеров;\n"
        "- план действий на неделю;\n"
        "- корректировка действий.\n\n"
        "Мы уже знаем вашу ситуацию. Теперь можем помочь дойти до первых вакансий."
    )


def render_report_html(report: dict, meta: ReportMeta) -> str:
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    market = report.get("market_analysis", []) if isinstance(report.get("market_analysis"), list) else []
    recommendations = report.get("career_recommendations", []) if isinstance(report.get("career_recommendations"), list) else []
    real_solutions = report.get("real_solutions", []) if isinstance(report.get("real_solutions"), list) else []
    translation = report.get("career_translation", []) if isinstance(report.get("career_translation"), list) else []
    bridges = report.get("career_bridges", []) if isinstance(report.get("career_bridges"), list) else []
    not_reset = report.get("what_not_reset", []) if isinstance(report.get("what_not_reset"), list) else []
    experience_layers = report.get("experience_layers", []) if isinstance(report.get("experience_layers"), list) else []
    career_barriers = report.get("career_barriers", []) if isinstance(report.get("career_barriers"), list) else []
    barrier_landscape = report.get("barrier_landscape", {}) if isinstance(report.get("barrier_landscape"), dict) else {}
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    weekly = report.get("weekly_plan", []) if isinstance(report.get("weekly_plan"), list) else []
    development = report.get("development_map", {}) if isinstance(report.get("development_map"), dict) else {}
    social_integration = report.get("social_integration", {}) if isinstance(report.get("social_integration"), dict) else {}
    energy_sources = report.get("energy_sources", []) if isinstance(report.get("energy_sources"), list) else []
    career_priorities = report.get("career_priorities", []) if isinstance(report.get("career_priorities"), list) else []
    competency_signals = report.get("competency_signals", []) if isinstance(report.get("competency_signals"), list) else []
    resource_level_raw = _safe_text(report.get("resource_level"), "не уточнено")
    integration_level_raw = _safe_text(report.get("integration_level"), "не уточнено")
    resource_level = f"{resource_level_raw} ({_level_label(resource_level_raw)})" if resource_level_raw != "не уточнено" else resource_level_raw
    integration_level = f"{integration_level_raw} ({_level_label(integration_level_raw)})" if integration_level_raw != "не уточнено" else integration_level_raw
    closing_message = _safe_text(report.get("closing_message"), "Сконцентрируйтесь на ближайшем работающем шаге и проверьте его на рынке.")
    strengths_for_closing = _list_items(digital_human.get("hidden_strengths"))[:3]
    main_asset = _safe_text(digital_human.get("main_asset"), "")
    if main_asset != "-" and main_asset not in strengths_for_closing:
        strengths_for_closing = [main_asset] + strengths_for_closing
    strengths_for_closing = strengths_for_closing[:3]
    weekly_signals = [
        _safe_text(item.get("task"))
        for item in weekly[:3]
        if isinstance(item, dict)
    ]
    free_features = [
        "1-2 запуска карты в кризисной точке",
        "Базовые упражнения без глубокой обратной связи",
        "Статичная карта без еженедельной адаптации",
    ]
    paid_features = [
        "Еженедельный анализ ваших действий и узких мест",
        "Адаптивная карта: меняем маршрут по фактическому прогрессу",
        "Новый стек навыков и рабочий фокус под текущую неделю",
        "Система сопровождения, которая удерживает дисциплину до результата",
    ]

    possibilities = []
    labels = ["Возможность 1", "Возможность 2", "Возможность 3"]
    for idx, item in enumerate(market[:3]):
        if not isinstance(item, dict):
            continue
        possibilities.append(
            f"""
            <div class='card'>
              <h3>{labels[idx]}: {escape(_safe_text(item.get('profession')))}</h3>
              <ul>
                <li><b>Соответствие:</b> {escape(str(item.get('fit_percent', '-')))}%</li>
                <li><b>Скорость входа:</b> {escape(_safe_text(item.get('entry_speed')))}</li>
                <li><b>Риск:</b> {escape(_safe_text(item.get('competition')))}</li>
                <li><b>Доход:</b> {escape(_safe_text(item.get('salary_range')))}</li>
                <li><b>Что подтянуть:</b> {escape(', '.join(_list_items(item.get('requirements'))[:5]))}</li>
              </ul>
            </div>
            """
        )

    recommendations_html = []
    for item in recommendations[:4]:
        if not isinstance(item, dict):
            continue
        recommendations_html.append(
            f"""
            <div class='card'>
                <h3>{escape(_safe_text(item.get('title')))}</h3>
                <ul>
                    <li><b>Соответствие:</b> {escape(str(item.get('match_percent', '-')))}%</li>
                    <li><b>Почему подходит:</b> {escape(_safe_text(item.get('why_fit')))}</li>
                    <li><b>Риски:</b> {escape(', '.join(_list_items(item.get('risks'))[:4]))}</li>
                    <li><b>Срок входа:</b> {escape(_safe_text(item.get('entry_timeline')))}</li>
                    <li><b>Доход:</b> {escape(_safe_text(item.get('income_range')))}</li>
                </ul>
            </div>
            """
        )

    solutions_html = []
    for item in real_solutions[:3]:
        if not isinstance(item, dict):
            continue
        solutions_html.append(
            f"""
            <div class='card'>
                <h3>{escape(_safe_text(item.get('title')))}</h3>
                <ul>
                    <li><b>Уровень рекомендации:</b> {escape(_safe_text(item.get('recommendation_level')))}</li>
                    <li><b>Вероятность успеха:</b> {escape(_safe_text(item.get('success_probability')))}</li>
                    <li><b>Срок:</b> {escape(_safe_text(item.get('timeline')))}</li>
                    <li><b>Почему:</b> {escape(_safe_text(item.get('why')))}</li>
                    <li><b>Первый шаг:</b> {escape(_safe_text(item.get('first_step')))}</li>
                </ul>
            </div>
            """
        )

    translation_html = []
    for item in translation[:6]:
        if not isinstance(item, dict):
            continue
        translation_html.append(
            f"""
            <div class='card'>
                <h3>Перевод опыта</h3>
                <p><b>Было:</b> {escape(_safe_text(item.get('source_experience')))}</p>
                <p><b>На рынке называется:</b> {escape(_safe_text(item.get('market_term')))}</p>
                <p><b>Подходящие роли:</b> {escape(', '.join(_list_items(item.get('suitable_roles'))[:4]))}</p>
            </div>
            """
        )

    bridges_html = []
    for item in bridges[:5]:
        if not isinstance(item, dict):
            continue
        bridges_html.append(
            f"""
            <div class='card'>
                <h3>{escape(_safe_text(item.get('role')))}</h3>
                <p><b>Почему это мост:</b> {escape(_safe_text(item.get('why_bridge')))}</p>
                <p><b>Первый тест рынка:</b> {escape(_safe_text(item.get('first_market_test')))}</p>
            </div>
            """
        )

    barriers_html = []
    for item in career_barriers[:5]:
        if not isinstance(item, dict):
            continue
        barriers_html.append(
            f"""
            <div class='card'>
                <h3>{escape(_safe_text(item.get('barrier')))}</h3>
                <ul>
                    <li><b>Сила влияния:</b> {escape(str(item.get('severity', '-')))} / 100</li>
                    <li><b>Механизм:</b> {escape(_safe_text(item.get('mechanism')))}</li>
                    <li><b>Навык для компенсации:</b> {escape(_safe_text(item.get('recommended_skill')))}</li>
                    <li><b>Первое упражнение:</b> {escape(_safe_text(item.get('first_exercise')))}</li>
                </ul>
            </div>
            """
        )

    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    this_week = "".join(f"<li>{escape(str(step))}</li>" for step in _list_items(action_plan.get("this_week")))
    this_month = "".join(f"<li>{escape(str(step))}</li>" for step in _list_items(action_plan.get("this_month")))
    first_month = development.get("first_month", []) if isinstance(development.get("first_month"), list) else []
    month_rows = "".join(
        f"<li><b>Неделя {escape(str(row.get('week', '-')))}:</b> {escape(_safe_text(row.get('focus')))} — {escape(_safe_text(row.get('output')))}</li>"
        for row in first_month[:4]
        if isinstance(row, dict)
    )

    hypothesis_steps = [
        "Собрать 10 релевантных вакансий и выделить повторяющиеся требования.",
        "Адаптировать CV под основной маршрут и отправить 5 откликов.",
        "Провести 3 тестовых интервью-скрипта и зафиксировать обратную связь.",
    ]

    unicode_font = _resolve_unicode_font_path()
    font_face_css = ""
    if unicode_font:
        # Embed a local Unicode font for consistent Cyrillic rendering in Chromium PDF.
        font_face_css = (
            "@font-face {"
            "font-family: 'CareerUnicode';"
            f"src: url('{unicode_font.as_uri()}') format('truetype');"
            "font-weight: normal;"
            "font-style: normal;"
            "}"
        )

    html = f"""
<!DOCTYPE html>
<html lang='ru'>
<head>
  <meta charset='UTF-8' />
  <style>
        {font_face_css}
    @page {{ size: A4; margin: 18mm; }}
        body {{ font-family: CareerUnicode, DejaVu Sans, Arial, sans-serif; color: #1f2937; font-size: 12px; line-height: 1.45; }}
    h1 {{ font-size: 26px; margin: 0 0 6px 0; color: #0f172a; }}
    h2 {{ font-size: 18px; margin: 0 0 8px 0; color: #0f766e; }}
    h3 {{ font-size: 14px; margin: 0 0 6px 0; }}
    .page {{ page-break-after: always; }}
    .last {{ page-break-after: auto; }}
    .meta {{ margin-top: 10px; }}
    .meta p {{ margin: 4px 0; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }}
        .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    ul {{ margin: 6px 0 0 16px; padding: 0; }}
    li {{ margin: 2px 0; }}
    .muted {{ color: #4b5563; }}
        .brand {{ display: inline-block; font-size: 11px; color: #0f766e; border: 1px solid #99f6e4; background: #f0fdfa; border-radius: 999px; padding: 3px 10px; margin-bottom: 8px; }}
        .closing-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px; }}
        .closing-card {{ border: 1px solid #bae6fd; border-radius: 10px; padding: 12px; background: #f8fafc; }}
        .closing-title {{ font-size: 15px; color: #0f172a; margin-bottom: 6px; }}
        .offer-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px; }}
        .offer-card {{ border: 1px solid #dbeafe; border-radius: 10px; padding: 12px; background: #f8fafc; }}
        .offer-card.free {{ border-color: #d1d5db; background: #fcfcfc; }}
        .offer-card.paid {{ border-color: #93c5fd; background: #eff6ff; }}
        .offer-title {{ font-size: 15px; color: #0f172a; margin-bottom: 6px; }}
        .system-note {{ border-left: 4px solid #0f766e; padding: 10px 12px; background: #f0fdfa; border-radius: 8px; margin-top: 10px; }}
  </style>
</head>
<body>
  <section class='page'>
        <div class='brand'>NextYou</div>
        <h1>NextYou Career GPS Report</h1>
    <h2>Персональная карта карьерного перехода</h2>
    <div class='meta'>
      <p><b>Имя пользователя:</b> {escape(meta.user_name)}</p>
      <p><b>Страна:</b> {escape(meta.country)}</p>
      <p><b>Дата:</b> {escape(meta.created_at)}</p>
      <p><b>Режим:</b> {escape(meta.mode)}</p>
    </div>
  </section>

  <section class='page'>
    <h2>Профиль ситуации</h2>
    <div class='card'><h3>Кто вы сейчас</h3><p>{escape(_safe_text(digital_human.get('current_state')))}</p></div>
    <div class='card'><h3>Ваш главный актив</h3><p>{escape(_safe_text(digital_human.get('main_asset')))}</p></div>
    <div class='card'><h3>Скрытые активы</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(digital_human.get('hidden_strengths'))[:6])}</ul></div>
    <div class='card'><h3>Главный риск</h3><p>{escape(_safe_text(digital_human.get('main_risk')))}</p></div>
    <div class='card'><h3>Главный страх</h3><p>{escape(_safe_text(digital_human.get('main_fear')))}</p></div>
        <div class='card'><h3>Что не обнулилось</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(not_reset)[:8])}</ul></div>
        <div class='card'><h3>Источники энергии</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(energy_sources)[:6])}</ul></div>
        <div class='card'><h3>Карьерные приоритеты</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(career_priorities)[:6])}</ul></div>
        <div class='card'><h3>STAR-компетенции</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(competency_signals)[:6])}</ul></div>
        <div class='card'><h3>Уровень ресурса</h3><p>{escape(resource_level)}</p></div>
        <div class='card'><h3>Уровень интеграции</h3><p>{escape(integration_level)}</p></div>
        <div class='card'><h3>Слои опыта</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(experience_layers)[:6])}</ul></div>
  </section>

  <section class='page'>
    <h2>Анализ возможностей</h2>
    {''.join(possibilities) if possibilities else '<p class="muted">Данных недостаточно.</p>'}
        <h2>Рекомендованные роли</h2>
        {''.join(recommendations_html) if recommendations_html else '<p class="muted">Данных недостаточно.</p>'}
        <h2>Реальные решения</h2>
        {''.join(solutions_html) if solutions_html else '<p class="muted">Данных недостаточно.</p>'}
  </section>

    <section class='page'>
        <h2>Перевод опыта и карьерные мосты</h2>
        {''.join(translation_html) if translation_html else '<p class="muted">Данных недостаточно.</p>'}
        {''.join(bridges_html) if bridges_html else '<p class="muted">Данных недостаточно.</p>'}
    </section>

    <section class='page'>
        <h2>Барьеры и анти-цикл</h2>
        {''.join(barriers_html) if barriers_html else '<p class="muted">Данных недостаточно.</p>'}
        <div class='card'>
            <h3>Контекст застревания</h3>
            <ul>
                <li><b>Внешние барьеры:</b> {escape(', '.join(_list_items(barrier_landscape.get('external'))[:5]))}</li>
                <li><b>Внутренние барьеры:</b> {escape(', '.join(_list_items(barrier_landscape.get('internal'))[:5]))}</li>
                <li><b>Поведенческий риск:</b> {escape(_safe_text(barrier_landscape.get('behavioral_risk')))}</li>
                <li><b>Первое противодействие:</b> {escape(_safe_text(barrier_landscape.get('first_counter_action')))}</li>
            </ul>
        </div>
    </section>

    <section class='page'>
        <h2>Социальная и культурная интеграция</h2>
        <div class='card'><h3>Люди</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(social_integration.get('people'))[:6])}</ul></div>
        <div class='card'><h3>Сообщества</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(social_integration.get('communities'))[:6])}</ul></div>
        <div class='card'><h3>Возможности</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(social_integration.get('opportunities'))[:6])}</ul></div>
        <div class='card'><h3>Вклад</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(social_integration.get('contribution'))[:6])}</ul></div>
    </section>

    <section class='page'>
        <h2>Маршрут</h2>
    <div class='card'><h3>Главное решение системы</h3><p>{escape(_safe_text(decision.get('recommended_main_path')))}</p></div>
        <div class='card'><h3>Запасной маршрут</h3><p>{escape(_safe_text(decision.get('backup_path')))}</p></div>
        <div class='card'><h3>Почему именно оно</h3><p>{escape(_safe_text(decision.get('why_this_path')))}</p></div>
        <div class='card'><h3>Что не делать сейчас</h3><p>{escape(_safe_text(decision.get('avoid_for_now')))}</p></div>
        <div class='card'><h3>Как проверить гипотезу</h3><ul>{''.join(f'<li>{escape(step)}</li>' for step in hypothesis_steps)}</ul></div>

        <h2>План действий</h2>
    <div class='card'>
      <h3>Сегодня</h3>
      <p><b>Действие:</b> {escape(_safe_text(today.get('action')))}</p>
      <p><b>Время:</b> {escape(_safe_text(today.get('timebox')))}</p>
      <p><b>Результат:</b> {escape(_safe_text(today.get('result')))}</p>
    </div>
    <div class='card'><h3>Первая неделя</h3><ul>{this_week}</ul></div>
        <div class='card'><h3>Цели на месяц</h3><ul>{this_month}</ul></div>
        <div class='card'><h3>Карта 4 недель</h3><ul>{month_rows or '<li>Данных недостаточно.</li>'}</ul></div>
        <div class='card'><h3>Недельный ритм (7 дней)</h3><ul>{''.join(f"<li>День {escape(str(item.get('day', '-')))}: {escape(_safe_text(item.get('task')))}</li>" for item in weekly[:7] if isinstance(item, dict)) or '<li>Данных недостаточно.</li>'}</ul></div>
    </section>

        <section class='page last'>
        <h2>Заключение NextYou</h2>
        <div class='closing-grid'>
            <div class='closing-card'>
                <div class='closing-title'>Что уже получается у вас</div>
                <ul>{''.join(f'<li>{escape(x)}</li>' for x in strengths_for_closing) or '<li>Есть устойчивые сильные стороны, на которые можно опереться.</li>'}</ul>
            </div>
            <div class='closing-card'>
                <div class='closing-title'>Поведенческие сигналы</div>
                <ul>{''.join(f'<li>{escape(x)}</li>' for x in weekly_signals) or '<li>Вы уже можете делать короткие шаги при понятной структуре.</li>'}</ul>
            </div>
        </div>

        <div class='offer-grid'>
            <div class='offer-card free'>
                <div class='offer-title'>Бесплатная версия</div>
                <ul>{''.join(f'<li>{escape(item)}</li>' for item in free_features)}</ul>
            </div>
            <div class='offer-card paid'>
                <div class='offer-title'>Платная версия: система сопровождения</div>
                <ul>{''.join(f'<li>{escape(item)}</li>' for item in paid_features)}</ul>
            </div>
        </div>

        <div class='system-note'>
            <b>Ключевая разница:</b> мы продаем не набор навыков, который можно найти отдельно, а систему, которая исследует ваш реальный прогресс и выдает нужный навык в нужный момент.
        </div>

        <div class='card'><h3>Финальная фиксация</h3><p>{escape(closing_message)}</p></div>
  </section>
</body>
</html>
"""
    return re.sub(r"\n\s+", "\n", html).strip()


def _html_to_plain_text(html: str) -> str:
    # Keep a readable fallback when rich HTML->PDF engines are unavailable.
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</h[1-6]>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _render_plain_text_pdf(text: str, output_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError("Fallback PDF writer requires reportlab") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    font_name = "Helvetica"
    font_path = _resolve_unicode_font_path()
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont("CareerUnicode", str(font_path)))
            font_name = "CareerUnicode"
        except Exception:
            font_name = "Helvetica"

    top_margin = 48
    bottom_margin = 48
    line_height = 14
    text_width_chars = 105

    y = height - top_margin
    c.setFont(font_name, 11)

    for raw_line in text.splitlines() or [""]:
        line = raw_line.rstrip()
        wrapped = textwrap.wrap(line, width=text_width_chars) if line else [""]
        for chunk in wrapped:
            if y <= bottom_margin:
                c.showPage()
                c.setFont(font_name, 11)
                y = height - top_margin
            c.drawString(40, y, chunk)
            y -= line_height

    c.save()


def html_to_pdf(html: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    engine = (settings.report_pdf_engine or "auto").strip().lower()
    try_playwright = engine in {"auto", "playwright"}
    try_xhtml = engine in {"auto", "xhtml2pdf"}
    errors: list[str] = []

    # Primary engine: Playwright gives the best layout fidelity for modern HTML/CSS reports.
    if try_playwright:
        try:
            from playwright.sync_api import sync_playwright

            temp_html_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".html",
                    delete=False,
                    encoding="utf-8",
                    dir=str(output_path.parent),
                ) as temp_file:
                    temp_file.write(html)
                    temp_html_path = Path(temp_file.name)

                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.set_default_timeout(45000)
                    page.goto(temp_html_path.as_uri(), wait_until="networkidle")
                    page.evaluate("() => document.fonts.ready")
                    page.emulate_media(media="screen")
                    page.pdf(
                        path=str(output_path),
                        format="A4",
                        print_background=True,
                        margin={"top": "18mm", "right": "18mm", "bottom": "18mm", "left": "18mm"},
                    )
                    browser.close()
                return
            finally:
                if temp_html_path and temp_html_path.exists():
                    temp_html_path.unlink(missing_ok=True)
        except Exception as exc:
            errors.append(f"playwright: {exc}")
            if engine == "playwright":
                raise RuntimeError("Playwright PDF engine failed. Check playwright package and installed browser.")
            # Fallback engine below keeps report generation available even without Playwright browsers.
            pass

    # Fallback engine: xhtml2pdf.
    if not try_xhtml:
        raise RuntimeError(f"Unknown REPORT_PDF_ENGINE: {engine}")

    try:
        from xhtml2pdf import pisa
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception as exc:
        errors.append(f"xhtml2pdf-import: {exc}")
        if engine == "xhtml2pdf":
            raise RuntimeError("xhtml2pdf engine unavailable") from exc
        plain_text = _html_to_plain_text(html)
        _render_plain_text_pdf(plain_text, output_path)
        return

    font_path = _resolve_unicode_font_path()
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont("CareerUnicode", str(font_path)))
        except Exception:
            # Keep fallback fonts if font registration fails.
            pass

    def _link_callback(uri: str, rel: str | None = None) -> str:
        if not uri:
            return ""
        parsed = urlparse(uri)
        if parsed.scheme == "file":
            resolved = unquote(parsed.path)
            if resolved.startswith("/") and len(resolved) > 2 and resolved[2] == ":":
                resolved = resolved[1:]
            return resolved
        if parsed.scheme in {"http", "https", "data"}:
            return uri
        if rel:
            return str((Path(rel).parent / uri).resolve())
        return str(Path(uri).resolve())

    with output_path.open("wb") as fh:
        status = pisa.CreatePDF(src=html, dest=fh, encoding="utf-8", link_callback=_link_callback)
    if status.err:
        errors.append("xhtml2pdf: Failed to convert HTML to PDF")
        if engine == "xhtml2pdf":
            raise RuntimeError("Failed to convert HTML to PDF")
        plain_text = _html_to_plain_text(html)
        _render_plain_text_pdf(plain_text, output_path)


def generate_pdf_report(report: dict, output_dir: str, user_name: str = "") -> Path:
    pdf_path, _ = generate_report_files(report, output_dir=output_dir, user_name=user_name)
    if pdf_path is None:
        raise RuntimeError("PDF generation failed")
    return pdf_path


def generate_report_files(report: dict, output_dir: str, user_name: str = "") -> tuple[Path | None, Path]:
    meta = build_meta(report, user_name=user_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", meta.user_name)[:40] or "user"
    base_dir = Path(output_dir)
    html_path = base_dir / f"career_report_{safe_name}_{ts}.html"
    pdf_path = base_dir / f"career_report_{safe_name}_{ts}.pdf"

    html = render_report_html(report, meta)
    base_dir.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    try:
        html_to_pdf(html, pdf_path)
    except Exception:
        return None, html_path
    return pdf_path, html_path


def generate_report_payload(user_id: str, report: dict, base_url: str, output_dir: str, user_name: str = "") -> dict[str, str]:
    pdf_path = generate_pdf_report(report, output_dir=output_dir, user_name=user_name)
    filename = pdf_path.name
    base = base_url.rstrip("/")
    return {
        "telegram_summary": build_telegram_summary(report),
        "pdf_url": f"{base}/{filename}",
    }
