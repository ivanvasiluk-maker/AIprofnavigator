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
    profile_version: str = ""


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


def _resource_human_message(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "low":
        return (
            "Сейчас ресурс ограничен.\n"
            "Вам важнее не брать на себя большой карьерный разворот, а выбрать путь, который дает доход "
            "и не требует резко учиться всему с нуля."
        )
    if normalized == "medium":
        return (
            "Сейчас ресурс частично ограничен.\n"
            "Лучше двигаться короткими шагами: сначала стабильный доход и понятный ритм, затем расширять траекторию."
        )
    if normalized == "high":
        return (
            "Сейчас ресурс устойчивый.\n"
            "Вы можете брать более амбициозные шаги, но сохранять контроль: измеримые действия и проверка гипотез на рынке."
        )
    return (
        "Ресурс пока нельзя оценить точно.\n"
        "Нужно уточнить, насколько стабильно у вас хватает времени, сил и темпа на регулярные карьерные действия."
    )


def _integration_human_message(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "low":
        return (
            "Интеграция пока начальная.\n"
            "Нужен щадящий маршрут: меньше зависимости от широких контактов и сложных локальных процессов на старте."
        )
    if normalized == "medium":
        return (
            "Интеграция пока частичная.\n"
            "Вы уже живете и работаете в стране, но язык, местные контакты и понимание рынка еще требуют укрепления."
        )
    if normalized == "high":
        return (
            "Интеграция уже устойчивая.\n"
            "Можно делать ставку на роли с более высокой планкой входа и активнее использовать локальный нетворк."
        )
    return (
        "Интеграцию пока нельзя оценить точно.\n"
        "Мы знаем, что вы уже живете в стране, но пока не понимаем, насколько уверенно вы используете язык, "
        "контакты и местные сервисы."
    )


def _professional_core_summary(report: dict) -> str:
    digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
    not_reset = report.get("what_not_reset") if isinstance(report.get("what_not_reset"), list) else []
    snapshot = " ".join(str(item) for item in not_reset[:6]).lower().replace("ё", "е")
    state_blob = " ".join(
        [
            str(digital_human.get("current_state", "")),
            str(digital_human.get("main_asset", "")),
            snapshot,
        ]
    ).lower().replace("ё", "е")

    worker_markers = ["плитк", "гипсокарт", "ремонт", "строит", "мебел", "рукам", "отделк"]
    if any(marker in state_blob for marker in worker_markers):
        return (
            "Вы не начинаете с нуля. Ваш основной капитал — практический опыт, способность работать руками, "
            "доводить задачу до результата и общаться с заказчиком. "
            "Сейчас вам нужен не абстрактный «новый старт», а перевод уже имеющегося опыта в понятный доход в новой стране."
        )

    return (
        "Вы не начинаете с нуля. У вас уже есть профессиональный капитал: практический опыт, рабочая дисциплина, "
        "умение доводить задачи до результата и взаимодействовать с людьми. "
        "Сейчас нужен не «новый старт с пустого места», а точная упаковка и перевод вашего опыта в понятный доход в новой стране."
    )


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


def build_meta(report: dict, user_name: str = "", profile_version: str = "") -> ReportMeta:
    name = _safe_text(user_name, "Пользователь")
    country = _detect_country(report)
    mode = _detect_mode(report)
    created_at = datetime.now().strftime("%Y-%m-%d")
    return ReportMeta(
        user_name=name,
        country=country,
        mode=mode,
        created_at=created_at,
        profile_version=_safe_text(profile_version, "-") if str(profile_version or "").strip() else "-",
    )


def _clean_fact_line(text: object) -> str:
    value = str(text or "").strip()
    if value.lower().startswith("ответ пользователя:"):
        value = value.split(":", 1)[1].strip()
    return value


def _build_story_echo(report: dict) -> str:
    facts_only = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
    explicit_facts = [_clean_fact_line(item) for item in (facts_only.get("explicit_facts") or [])]
    explicit_facts = [item for item in explicit_facts if item]
    inferences = [str(item).strip() for item in (facts_only.get("inferences") or []) if str(item).strip()]
    unknowns = [str(item).strip() for item in (facts_only.get("unknowns") or []) if str(item).strip()]

    facts: list[str] = []
    for item in explicit_facts:
        if item not in facts:
            facts.append(item)
        if len(facts) >= 4:
            break
    for item in inferences:
        if len(facts) >= 2:
            break
        if item not in facts:
            facts.append(item)
    if not facts:
        facts = ["Пока не хватает подтвержденных фактов из вашей истории. Это можно уточнить позже."]

    digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
    barriers = digital_human.get("barriers") if isinstance(digital_human.get("barriers"), dict) else {}

    problem = _safe_text(digital_human.get("main_barrier"), "данных недостаточно")
    if problem == "-":
        problem = "данных недостаточно"

    resource = _safe_text(digital_human.get("main_asset"), "данных недостаточно")
    if resource == "-":
        resource = "данных недостаточно"

    constraint_candidates = _list_items(barriers.get("external"))
    constraint = next((item for item in constraint_candidates if item != "-"), "")
    if not constraint and unknowns:
        constraint = unknowns[0]
    if not constraint:
        constraint = "данных недостаточно"

    facts_block = "\n".join(f"- {item}" for item in facts[:4])
    return (
        "Что я услышал в вашей истории\n\n"
        f"{facts_block}\n\n"
        f"Главная проблема:\n{problem}\n\n"
        f"Ресурс:\n{resource}\n\n"
        f"Ограничение:\n{constraint}"
    )


def _unknowns_list(report: dict) -> list[str]:
    facts_only = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
    unknowns = [str(item).strip() for item in (facts_only.get("unknowns") or []) if str(item).strip()]
    return unknowns[:6]


def _psych_social_recommendation(report: dict) -> tuple[list[str], list[str]]:
    digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
    barriers = digital_human.get("barriers") if isinstance(digital_human.get("barriers"), dict) else {}
    social_integration = report.get("social_integration") if isinstance(report.get("social_integration"), dict) else {}

    internal = _list_items(barriers.get("internal"))[:3]
    external = _list_items(barriers.get("external"))[:3]
    fears = _list_items((digital_human.get("psychological_profile") or {}).get("dominant_fears"))[:3]
    communities = _list_items(social_integration.get("communities"))[:3]

    self_help: list[str] = []
    if any(item != "-" for item in internal):
        self_help.append("Действовать через микрошаг 5-15 минут в день, без попытки решить всё сразу.")
    if any(item != "-" for item in external):
        self_help.append("Разделить барьеры на управляемые (сегодня) и внешние (план на неделю).")
    if any(item != "-" for item in communities):
        self_help.append("Добавить один социальный контакт в неделю: сообщество, чат или профильный канал.")
    if not self_help:
        self_help.append("Пока данных мало: начните с одного короткого действия и зафиксируйте результат.")

    specialist: list[str] = []
    signal_blob = " ".join([" ".join(fears), " ".join(internal)]).lower().replace("ё", "е")
    if any(token in signal_blob for token in ["страх", "пан", "стыд", "не могу", "нет сил", "хаос", "трев"]):
        specialist.append("Если перегруз и тревога держатся неделями, полезно разобрать это с психологом/консультантом по адаптации.")
    specialist.append("Если маршрут понятен, но нет движения, полезен разбор со специалистом: барьер, темп, корректировка шага.")
    specialist.append("Это не медицинское заключение: рекомендация нужна только для опоры и ускорения адаптации.")

    return self_help[:3], specialist[:3]


def build_telegram_summary(report: dict) -> str:
    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    weekly = report.get("weekly_plan", []) if isinstance(report.get("weekly_plan"), list) else []
    development = report.get("development_map", {}) if isinstance(report.get("development_map"), dict) else {}
    not_reset = report.get("what_not_reset", []) if isinstance(report.get("what_not_reset"), list) else []
    not_reset_block = "\n".join(f"- {item}" for item in _list_items(not_reset)[:4])
    energy_sources = report.get("energy_sources", []) if isinstance(report.get("energy_sources"), list) else []
    energy_block = "\n".join(f"- {item}" for item in _list_items(energy_sources)[:4])
    career_priorities = report.get("career_priorities", []) if isinstance(report.get("career_priorities"), list) else []
    priorities_block = "\n".join(f"- {item}" for item in _list_items(career_priorities)[:4])
    competency_signals = report.get("competency_signals", []) if isinstance(report.get("competency_signals"), list) else []
    competency_block = "\n".join(f"- {item}" for item in _list_items(competency_signals)[:5])
    weaknesses = []
    barriers = (digital_human.get("barriers") or {}) if isinstance(digital_human.get("barriers"), dict) else {}
    weaknesses.extend(_list_items(barriers.get("internal"))[:2])
    weaknesses.extend(_list_items(barriers.get("external"))[:2])
    weaknesses_block = "\n".join(f"- {item}" for item in weaknesses[:4]) if weaknesses else "- данных недостаточно"
    facts_only = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
    unknowns = [str(item).strip() for item in (facts_only.get("unknowns") or []) if str(item).strip()]
    unknowns_block = "\n".join(f"- {item}" for item in unknowns[:3]) if unknowns else "- критичных неизвестных сейчас нет"
    resource_level = _resource_human_message(report.get("resource_level"))
    integration_level = _integration_human_message(report.get("integration_level"))
    story_echo = _build_story_echo(report)
    professional_core = _professional_core_summary(report)
    market = report.get("market_analysis", []) if isinstance(report.get("market_analysis"), list) else []
    resume_analysis = report.get("resume_analysis", {}) if isinstance(report.get("resume_analysis"), dict) else {}
    resume_status = "есть" if resume_analysis else "нет"
    route_lines: list[str] = []
    for idx, item in enumerate(market[:3], start=1):
        if not isinstance(item, dict):
            continue
        route_lines.append(
            f"{idx}. {_safe_text(item.get('profession'))}: {_safe_text(item.get('salary_range'))}; {_safe_text(item.get('fit_percent'))}%"
        )
    route_block = "\n".join(f"- {item}" for item in route_lines) if route_lines else "- данных недостаточно"
    weekly_block = "\n".join(f"- День {item.get('day', '-')}: {_safe_text(item.get('task'))}" for item in weekly[:4] if isinstance(item, dict)) or "- данных недостаточно"
    first_month = development.get("first_month", []) if isinstance(development.get("first_month"), list) else []
    month_block = "\n".join(
        f"- Неделя {row.get('week', '-')}: {_safe_text(row.get('focus'))} — {_safe_text(row.get('output'))}"
        for row in first_month[:4]
        if isinstance(row, dict)
    ) or "- данных недостаточно"

    summary = [
        story_echo,
        "",
        "Ваш NextYou отчёт",
        "",
        f"1. Что я услышал:\n{story_echo}",
        f"2. Профессиональное ядро:\n{professional_core}",
        f"Кто вы сейчас:\n{_safe_text(digital_human.get('current_state'))}",
        f"Что не обнулилось:\n{not_reset_block}",
        f"Ваше профессиональное ядро:\n{professional_core}",
        f"3. Сильные стороны и опоры:\n{energy_block}",
        f"4. Ограничения и неизвестные:\n{weaknesses_block}\n\nЧто уточнить:\n{unknowns_block}",
        f"5. Устойчивость в период изменений:\n{resource_level}",
        f"Ресурс и рабочий темп:\n{resource_level}",
        f"6. Интеграция в новой стране:\n{integration_level}",
        f"Состояние интеграции:\n{integration_level}",
        f"7. Сравнение маршрутов:\n{route_block}",
        f"8. Выбранный маршрут и первый шаг:\n{_safe_text(decision.get('recommended_main_path'))}\n{_safe_text(today.get('action'))}",
        f"9. План на 30 дней:\n{weekly_block}\n{month_block}",
        f"10. Анализ резюме:\nАнализ CV: {resume_status}",
        f"11. Что может быть не так:\n{weaknesses_block}",
        f"Источники энергии:\n{energy_block}",
        f"Карьерные приоритеты:\n{priorities_block}",
        f"STAR-компетенции:\n{competency_block}",
        f"Что делать самому:\n{_safe_text(today.get('action'))}",
        f"Что подумать со специалистом:\n{_safe_text(decision.get('why_this_path'))}",
        f"Главный риск:\n{_safe_text(digital_human.get('main_risk'))}",
        f"Рекомендуемый маршрут:\n{_safe_text(decision.get('recommended_main_path'))}",
        f"Почему он предложен:\n{_safe_text(decision.get('why_this_path'))}",
        f"Запасной маршрут:\n{_safe_text(decision.get('backup_path'))}",
        f"Маленький первый шаг:\n{_safe_text(today.get('action'))}",
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
    resume_analysis = report.get("resume_analysis", {}) if isinstance(report.get("resume_analysis"), dict) else {}
    resource_level = _resource_human_message(report.get("resource_level"))
    integration_level = _integration_human_message(report.get("integration_level"))
    closing_message = _safe_text(
        report.get("closing_message"),
        "Это работа, а не испытание. Один проверяемый шаг — и карта начнёт двигаться.",
    )
    strengths_for_closing = list(dict.fromkeys(
        [item for item in _list_items(not_reset)[:3] if item != "-"] +
        [item for item in _list_items(digital_human.get("hidden_strengths"))[:3] if item != "-"]
    ))[:4]
    first_step_today = _safe_text(
        (report.get("action_plan") or {}).get("today", {}).get("action") if isinstance((report.get("action_plan") or {}).get("today"), dict) else None,
        "Собрать 10 вакансий по выбранному маршруту и выписать повторяющиеся требования.",
    )
    next_step_week = _safe_text(
        ((report.get("action_plan") or {}).get("this_week") or [""])[0] if isinstance((report.get("action_plan") or {}).get("this_week"), list) else "",
        "Подготовить CV под выбранный маршрут и отправить 3-5 тестовых отклика.",
    )
    specialist_hints, _ = _psych_social_recommendation(report)
    weekly_signals = [
        _safe_text(item.get("task"))
        for item in weekly[:3]
        if isinstance(item, dict)
    ]
    strengths_items = list(dict.fromkeys(_list_items(not_reset)[:4] + _list_items(digital_human.get("hidden_strengths"))[:4]))[:6]
    barriers_obj = digital_human.get("barriers") if isinstance(digital_human.get("barriers"), dict) else {}
    weaknesses_items = list(dict.fromkeys(_list_items(barriers_obj.get("internal"))[:3] + _list_items(barriers_obj.get("external"))[:3]))[:6]
    blind_spots = [
        _safe_text(digital_human.get("main_risk"), ""),
        _safe_text(digital_human.get("main_barrier"), ""),
        _safe_text((decision or {}).get("avoid_for_now"), ""),
        _safe_text((barrier_landscape or {}).get("behavioral_risk"), ""),
    ]
    blind_spots = [item for item in blind_spots if item and item != "-"][:4]
    important_consider = [
        f"Ресурс: {resource_level.splitlines()[0]}",
        f"Интеграция: {integration_level.splitlines()[0]}",
        f"Приоритеты: {', '.join(_list_items(career_priorities)[:3])}",
    ]
    market_questions = []
    for item in market[:6]:
        if not isinstance(item, dict):
            continue
        for req in _list_items(item.get("requirements"))[:4]:
            if req not in market_questions and req != "-":
                market_questions.append(req)
    unknowns = _unknowns_list(report)
    self_help_points, specialist_points = _psych_social_recommendation(report)
    scenario_labels = ["Пессимистичный", "Базовый", "Оптимистичный"]

    possibilities = []
    labels = ["Быстрый доход", "Основной маршрут", "Долгосрочное развитие"]
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
    for idx, item in enumerate(real_solutions[:3]):
        if not isinstance(item, dict):
            continue
        solutions_html.append(
            f"""
            <div class='card'>
                <h3>{escape(scenario_labels[idx])}: {escape(_safe_text(item.get('title')))}</h3>
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
                    <li><b>Что это значит:</b> {escape(_safe_text(item.get('mechanism')))}</li>
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

    resume_good = _list_items(resume_analysis.get("what_is_good"))[:6]
    resume_missing = _list_items(resume_analysis.get("what_is_missing"))[:6]
    resume_conflicts = _list_items(resume_analysis.get("inconsistencies"))[:6]
    resume_professions = _list_items(resume_analysis.get("professions"))[:6]
    resume_periods = _list_items(resume_analysis.get("periods"))[:6]
    resume_tasks = _list_items(resume_analysis.get("tasks"))[:6]
    resume_education = _list_items(resume_analysis.get("education"))[:6]
    resume_languages = _list_items(resume_analysis.get("languages"))[:6]
    resume_certificates = _list_items(resume_analysis.get("certificates"))[:6]
    resume_questions = _list_items(resume_analysis.get("clarifying_questions"))[:6]
    has_resume_module = bool(resume_analysis)
    story_echo = _build_story_echo(report)

    unicode_font = _resolve_unicode_font_path()
    font_face_css = ""
    body_font_stack = "'Arial', 'Helvetica', 'DejaVu Sans', sans-serif"
    if unicode_font:
        # Use an absolute file path to keep compatibility with both Chromium and xhtml2pdf.
        font_src = str(unicode_font.resolve()).replace("\\", "/")
        font_face_css = (
            "@font-face {"
            "font-family: 'CareerUnicode';"
            f"src: url('{font_src}') format('truetype');"
            "font-weight: normal;"
            "font-style: normal;"
            "}"
        )
        body_font_stack = "'CareerUnicode', 'Arial', 'Helvetica', 'DejaVu Sans', sans-serif"

    html = f"""
<!DOCTYPE html>
<html lang='ru'>
<head>
  <meta charset='UTF-8' />
  <style>
        {font_face_css}
    :root {{
      --paper: #ffffff;
      --ink: #1f2937;
      --muted: #4b5563;
      --accent: #0f766e;
      --line: #d1d5db;
    }}
    @page {{ size: A4; margin: 16mm; }}
        body {{ font-family: {body_font_stack}; color: var(--ink); font-size: 12px; line-height: 1.5; }}
    h1 {{ font-size: 28px; margin: 0 0 4px 0; color: #0f172a; letter-spacing: 0.2px; }}
    h2 {{ font-size: 18px; margin: 0 0 8px 0; color: var(--accent); border-left: 4px solid #8fd9cb; padding-left: 10px; }}
    h3 {{ font-size: 14px; margin: 0 0 6px 0; }}
    .page {{ page-break-after: always; }}
    .last {{ page-break-after: auto; }}
    .hero {{ border: 1px solid #cbe8e0; border-radius: 14px; background: linear-gradient(135deg, #f5fffc 0%, #eef7ff 100%); padding: 14px 16px; margin-bottom: 10px; }}
    .subtitle {{ margin: 0; color: var(--muted); font-size: 13px; }}
    .meta {{ margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; border-top: 1px dashed #b8d9d1; padding-top: 8px; }}
    .meta p {{ margin: 2px 0; }}
    .card {{ border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; background: var(--paper); }}
        .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    ul {{ margin: 6px 0 0 16px; padding: 0; }}
    li {{ margin: 2px 0; }}
    .muted {{ color: var(--muted); }}
        .brand {{ display: inline-block; font-size: 11px; font-weight: bold; color: var(--accent); border: 1px solid #99f6e4; background: #f0fdfa; border-radius: 999px; padding: 3px 10px; margin-bottom: 8px; }}
        .closing-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px; }}
        .closing-card {{ border: 1px solid #bae6fd; border-radius: 10px; padding: 12px; background: #f8fafc; }}
        .closing-title {{ font-size: 15px; color: #0f172a; margin-bottom: 6px; }}
        .swot-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px; }}
        .system-note {{ border-left: 4px solid #0f766e; padding: 10px 12px; background: #f0fdfa; border-radius: 8px; margin-top: 10px; }}
        .final-conclusion {{ background: linear-gradient(135deg, #f0fdfa 0%, #eff6ff 100%); border: 2px solid #0f766e; border-radius: 14px; padding: 20px 22px; margin-top: 16px; page-break-inside: avoid; }}
        .final-conclusion-title {{ font-size: 17px; font-weight: bold; color: #0f172a; margin-bottom: 10px; border-bottom: 1px solid #99f6e4; padding-bottom: 6px; }}
        .final-conclusion-text {{ font-size: 13px; line-height: 1.7; color: #1f2937; white-space: pre-line; }}
        .action-box {{ border: 1px solid #bbf7d0; background: #f0fdf4; border-radius: 10px; padding: 14px 16px; margin-top: 12px; }}
        .action-box-title {{ font-size: 13px; font-weight: bold; color: #166534; margin-bottom: 6px; }}
        .honest-note {{ border-left: 4px solid #f59e0b; padding: 10px 14px; background: #fffbeb; border-radius: 8px; margin-top: 12px; font-size: 12px; color: #78350f; }}
  </style>
</head>
<body>
  <section class='page'>
                <div class='hero'>
                    <div class='brand'>NextYou</div>
                    <h1>NextYou Report</h1>
                    <p class='subtitle'>Персональная карта карьерного перехода</p>
                    <div class='meta'>
                        <p><b>Имя пользователя:</b> {escape(meta.user_name)}</p>
                        <p><b>Страна:</b> {escape(meta.country)}</p>
                        <p><b>Дата:</b> {escape(meta.created_at)}</p>
                        <p><b>Режим:</b> {escape(meta.mode)}</p>
                        <p><b>Версия профиля:</b> {escape(meta.profile_version)}</p>
                    </div>
                </div>
  </section>

    <section class='page'>
        <h2>1. Что я услышал</h2>
        <div class='card'><h3>Кто вы сейчас</h3><p>{escape(_safe_text(digital_human.get('current_state')))}</p></div>
        <div class='card'><h3>Ключевые факты из истории и резюме</h3><p>{escape(story_echo)}</p></div>

        <h2>2. Профессиональное ядро</h2>
        <div class='card'><h3>Ваш профессиональный капитал</h3><p>{escape(_professional_core_summary(report))}</p></div>
        <div class='card'><h3>Что не обнулилось после миграции</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(not_reset)[:8])}</ul></div>
        <div class='card'><h3>Слои опыта</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(experience_layers)[:6])}</ul></div>

        <h2>3. Сильные стороны и опоры</h2>
        <div class='card'><h3>Подтверждённые сильные стороны</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in strengths_items) or '<li>Данных недостаточно.</li>'}</ul></div>
        <div class='card'><h3>Источники энергии</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(energy_sources)[:6])}</ul></div>
        <div class='card'><h3>Карьерные приоритеты</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(career_priorities)[:6])}</ul></div>
        <div class='card'><h3>Подтверждённые компетенции</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(competency_signals)[:6])}</ul></div>

        <h2>4. Ограничения и неизвестные</h2>
        <div class='card'><h3>Ограничения</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in weaknesses_items) or '<li>Данных недостаточно.</li>'}</ul></div>
        <div class='card'><h3>Что нужно уточнить</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in unknowns) or '<li>Критичных неизвестных сейчас нет.</li>'}</ul></div>
        <div class='swot-grid'>
            <div class='card'><h3>SWOT: Strengths</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in strengths_items) or '<li>Данных недостаточно.</li>'}</ul></div>
            <div class='card'><h3>SWOT: Weaknesses</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in weaknesses_items) or '<li>Данных недостаточно.</li>'}</ul></div>
            <div class='card'><h3>SWOT: Blind Spots</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in blind_spots) or '<li>Данных недостаточно.</li>'}</ul></div>
            <div class='card'><h3>SWOT: Important to Consider</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in important_consider) or '<li>Данных недостаточно.</li>'}</ul></div>
        </div>
        <div class='card'>
            <h3>Психологический и социальный анализ (без медицинских выводов)</h3>
            <p><b>Что можно делать самому:</b></p>
            <ul>{''.join(f'<li>{escape(x)}</li>' for x in self_help_points)}</ul>
            <p><b>Когда полезен специалист:</b></p>
            <ul>{''.join(f'<li>{escape(x)}</li>' for x in specialist_points)}</ul>
        </div>

        <h2>5. Устойчивость в период изменений</h2>
        <div class='card'><h3>Ресурс и рабочий темп</h3><p>{escape(resource_level).replace('\n', '<br/>')}</p></div>
        <div class='card'><h3>Главный риск</h3><p>{escape(_safe_text(digital_human.get('main_risk')))}</p></div>
        <div class='card'><h3>Главный страх</h3><p>{escape(_safe_text(digital_human.get('main_fear')))}</p></div>

        <h2>6. Интеграция в новой стране</h2>
        <div class='card'><h3>Состояние интеграции</h3><p>{escape(integration_level).replace('\n', '<br/>')}</p></div>
        <div class='card'><h3>Ваш главный актив</h3><p>{escape(_safe_text(digital_human.get('main_asset')))}</p></div>
        <div class='card'><h3>Скрытые активы</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in _list_items(digital_human.get('hidden_strengths'))[:6])}</ul></div>
  </section>

    <section class='page'>
        <h2>7. Сравнение маршрутов</h2>
          <div class='muted'>Анализ возможностей</div>
    {''.join(possibilities) if possibilities else '<p class="muted">Данных недостаточно.</p>'}
        <div class='card'><h3>Что рынок будет проверять</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in market_questions[:10]) or '<li>Данных недостаточно.</li>'}</ul></div>
        <h2>Рекомендованные роли</h2>
        {''.join(recommendations_html) if recommendations_html else '<p class="muted">Данных недостаточно.</p>'}
        <h2>Три сценария: пессимистичный, базовый, оптимистичный</h2>
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
        <h2>8. Выбранный маршрут и первый шаг</h2>
          <div class='muted'>План действий</div>
    <div class='card'><h3>Главное решение системы</h3><p>{escape(_safe_text(decision.get('recommended_main_path')))}</p></div>
        <div class='card'><h3>Запасной маршрут</h3><p>{escape(_safe_text(decision.get('backup_path')))}</p></div>
        <div class='card'><h3>Почему именно оно</h3><p>{escape(_safe_text(decision.get('why_this_path')))}</p></div>
        <div class='card'><h3>Что не делать сейчас</h3><p>{escape(_safe_text(decision.get('avoid_for_now')))}</p></div>
        <div class='card'><h3>Как проверить гипотезу</h3><ul>{''.join(f'<li>{escape(step)}</li>' for step in hypothesis_steps)}</ul></div>
        <div class='card'><h3>Кнопки после отчёта</h3><ul><li>🧭 Начать первый шаг</li><li>✍️ Исправить факт или приоритет</li><li>📄 Загрузить / доработать резюме</li><li>🔎 Разобрать рынок и вакансии</li><li>👤 Разобрать со специалистом</li><li>👥 Найти группу / сообщество</li></ul></div>

        <h2>9. План на 30 дней</h2>
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

    <section class='page'>
        <h2>10. Анализ резюме</h2>
        {
            (
                "<div class='card'><h3>Профессии и периоды</h3><ul>"
                + ''.join(f"<li>{escape(x)}</li>" for x in resume_professions + resume_periods)
                + "</ul></div>"
                + "<div class='card'><h3>Задачи и достижения</h3><ul>"
                + ''.join(f"<li>{escape(x)}</li>" for x in resume_tasks + resume_good)
                + "</ul></div>"
                + "<div class='card'><h3>Образование, языки, сертификаты</h3><ul>"
                + ''.join(f"<li>{escape(x)}</li>" for x in resume_education + resume_languages + resume_certificates)
                + "</ul></div>"
                "<div class='card'><h3>Сильные стороны CV</h3><ul>"
                + ''.join(f"<li>{escape(x)}</li>" for x in resume_good)
                + "</ul></div>"
                + "<div class='card'><h3>Что недосказано для маршрута</h3><ul>"
                + ''.join(f"<li>{escape(x)}</li>" for x in resume_missing)
                + "</ul></div>"
                + "<div class='card'><h3>Несостыковки для уточнения</h3><ul>"
                + ''.join(f"<li>{escape(x)}</li>" for x in resume_conflicts)
                + "</ul></div>"
                + "<div class='card'><h3>Вопросы для уточнения</h3><ul>"
                + ''.join(f"<li>{escape(x)}</li>" for x in resume_questions)
                + "</ul></div>"
            )
            if has_resume_module
            else "<div class='card'><h3>Резюме не загружено</h3><p>Загрузите CV для отдельного анализа и адаптации под выбранный маршрут.</p><p><b>Кнопка:</b> «Загрузить резюме для анализа»</p></div>"
        }
    </section>

        <section class='page last'>
        <h2>11. Что может быть не так в моём выводе</h2>

        <div class='system-note'>
            <b>На чём основан этот вывод:</b> история, ответы на вопросы и данные резюме (если загружено).
            Карта меняется при новых фактах о языке, документах, приоритетах, контактах или рынке.
            Если что-то не совпадает — исправьте через кнопки ниже.
        </div>

        <div class='closing-grid' style='margin-top:12px;'>
            <div class='closing-card'>
                <div class='closing-title'>✅ Что не обнулилось — ваша опора</div>
                <ul>{''.join(f'<li>{escape(x)}</li>' for x in strengths_for_closing) or '<li>Есть устойчивые сильные стороны. Уточните в беседе со специалистом.</li>'}</ul>
            </div>
            <div class='closing-card'>
                <div class='closing-title'>⚠️ Что может изменить карту</div>
                <ul>{''.join(f'<li>{escape(x)}</li>' for x in unknowns) or '<li>Критичных неизвестных сейчас нет.</li>'}</ul>
            </div>
        </div>

        <div class='action-box' style='margin-top:14px;'>
            <div class='action-box-title'>🎯 Первый шаг — сделайте сегодня (до 15 минут)</div>
            <p style='margin:4px 0;'>{escape(first_step_today)}</p>
            <div class='action-box-title' style='margin-top:8px;'>📅 На эту неделю</div>
            <p style='margin:4px 0;'>{escape(next_step_week)}</p>
        </div>

        <div class='honest-note'>
            <b>Честно о рекомендациях специалиста:</b>
            {''.join(f' {escape(x)}' for x in specialist_hints[:2]) or ' Если маршрут понятен, но нет движения — разбор со специалистом ускоряет выход.'}
            Это не медицинская рекомендация — только карьерная и адаптационная опора.
        </div>

        <div class='card' style='margin-top:14px;'>
            <h3>🔎 Проверьте карту</h3>
            <ul>
                <li>✅ Всё похоже на правду → продолжайте по шагам</li>
                <li>✍️ Исправить факт → карта обновится</li>
                <li>🧭 Изменить приоритет → маршрут перестроится</li>
                <li>❓ Не согласен с маршрутом → объясните, что не так</li>
            </ul>
        </div>

        <div class='final-conclusion' style='margin-top:18px;'>
            <div class='final-conclusion-title'>💬 Заключение</div>
            <div class='final-conclusion-text'>{escape(closing_message)}</div>
        </div>

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
                    page = browser.new_page(viewport={"width": 1280, "height": 1800})
                    page.set_default_timeout(45000)
                    page.goto(temp_html_path.as_uri(), wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle")
                    page.wait_for_function(
                        "() => !document.fonts || document.fonts.status === 'loaded'",
                        timeout=12000,
                    )
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
                raise RuntimeError(f"Playwright PDF engine failed. Details: {exc}")
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
            raise RuntimeError(f"xhtml2pdf engine unavailable: {exc}") from exc
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

    # xhtml2pdf is sensitive to custom @font-face declarations in some Windows envs.
    html_for_xhtml = re.sub(r"@font-face\s*\{[^}]*\}", "", html, flags=re.IGNORECASE | re.DOTALL)
    html_for_xhtml = html_for_xhtml.replace("'CareerUnicode', ", "")

    with output_path.open("wb") as fh:
        status = pisa.CreatePDF(src=html_for_xhtml, dest=fh, encoding="utf-8", link_callback=_link_callback)
    if status.err:
        errors.append("xhtml2pdf: Failed to convert HTML to PDF")
        if engine == "xhtml2pdf":
            joined = " | ".join(errors) if errors else "unknown"
            raise RuntimeError(f"Failed to convert HTML to PDF: {joined}")
        plain_text = _html_to_plain_text(html)
        _render_plain_text_pdf(plain_text, output_path)


def generate_pdf_from_html_file_with_error(html_path: Path) -> tuple[Path | None, str]:
    try:
        html = html_path.read_text(encoding="utf-8")
    except Exception as exc:
        return None, f"html_read_error: {exc}"
    pdf_path = html_path.with_suffix(".pdf")
    try:
        html_to_pdf(html, pdf_path)
    except Exception as exc:
        return None, f"pdf_render_error: {exc}"
    return pdf_path, ""


def generate_plain_pdf_from_html_file_with_error(html_path: Path) -> tuple[Path | None, str]:
    """Force plain-text PDF generation path for diagnostics.

    This bypasses HTML engines and renders readable text PDF via reportlab.
    """
    try:
        html = html_path.read_text(encoding="utf-8")
    except Exception as exc:
        return None, f"html_read_error: {exc}"
    pdf_path = html_path.with_name(f"{html_path.stem}.plain.pdf")
    try:
        plain_text = _html_to_plain_text(html)
        _render_plain_text_pdf(plain_text, pdf_path)
    except Exception as exc:
        return None, f"plain_pdf_render_error: {exc}"
    return pdf_path, ""


def generate_pdf_report(report: dict, output_dir: str, user_name: str = "") -> Path:
    pdf_path, _, _ = generate_report_files(report, output_dir=output_dir, user_name=user_name)
    if pdf_path is None:
        raise RuntimeError("PDF generation failed")
    return pdf_path


def generate_html_report_file(report: dict, output_dir: str, user_name: str = "", profile_version: str = "") -> Path:
    meta = build_meta(report, user_name=user_name, profile_version=profile_version)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", meta.user_name)[:40] or "user"
    base_dir = Path(output_dir)
    html_path = base_dir / f"career_report_{safe_name}_{ts}.html"
    html = render_report_html(report, meta)
    base_dir.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return html_path


def generate_docx_report_file(report: dict, output_dir: str, user_name: str = "") -> tuple[Path | None, str]:
    """Generate a DOCX version of the report. Returns (path, error_string)."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except Exception as exc:
        return None, f"python-docx unavailable: {exc}"

    meta = build_meta(report, user_name=user_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", meta.user_name)[:40] or "user"
    base_dir = Path(output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    docx_path = base_dir / f"career_report_{safe_name}_{ts}.docx"

    digital_human = report.get("digital_human", {}) if isinstance(report.get("digital_human"), dict) else {}
    decision = report.get("career_decision", {}) if isinstance(report.get("career_decision"), dict) else {}
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan"), dict) else {}
    today = action_plan.get("today", {}) if isinstance(action_plan.get("today"), dict) else {}
    market = report.get("market_analysis", []) if isinstance(report.get("market_analysis"), list) else []
    not_reset = report.get("what_not_reset", []) if isinstance(report.get("what_not_reset"), list) else []
    resume_analysis = report.get("resume_analysis", {}) if isinstance(report.get("resume_analysis"), dict) else {}
    development = report.get("development_map", {}) if isinstance(report.get("development_map"), dict) else {}
    first_month = development.get("first_month", []) if isinstance(development.get("first_month"), list) else []
    closing_message = _safe_text(
        report.get("closing_message"),
        "Это работа, а не испытание. Один проверяемый шаг — и карта начнёт двигаться.",
    )
    self_help_pts, specialist_pts = _psych_social_recommendation(report)
    unknowns = _unknowns_list(report)

    def _teal(r: int = 15, g: int = 118, b: int = 110) -> RGBColor:
        return RGBColor(r, g, b)

    def _add_heading(doc: "Document", text: str, level: int = 1) -> None:
        p = doc.add_heading(text, level=level)
        run = p.runs[0] if p.runs else p.add_run(text)
        run.font.color.rgb = _teal()

    def _add_bullet(doc: "Document", text: str, bold_prefix: str = "") -> None:
        p = doc.add_paragraph(style="List Bullet")
        if bold_prefix:
            run = p.add_run(bold_prefix)
            run.bold = True
        p.add_run(_safe_text(text))

    def _add_kv(doc: "Document", key: str, value: str) -> None:
        p = doc.add_paragraph()
        run = p.add_run(f"{key}: ")
        run.bold = True
        p.add_run(_safe_text(value))

    try:
        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "Arial"
        style.font.size = Pt(11)

        # Cover
        title = doc.add_heading("NextYou Report", 0)
        title.runs[0].font.color.rgb = _teal()
        doc.add_paragraph(f"Имя: {meta.user_name}  |  Страна: {meta.country}  |  Дата: {meta.created_at}  |  Режим: {meta.mode}")
        doc.add_paragraph("")

        # 1. Что я услышал
        _add_heading(doc, "1. Что я услышал", 1)
        _add_kv(doc, "Кто вы сейчас", _safe_text(digital_human.get("current_state")))
        _add_kv(doc, "Главный актив", _safe_text(digital_human.get("main_asset")))
        doc.add_paragraph("")

        # 2. Профессиональное ядро
        _add_heading(doc, "2. Профессиональное ядро", 1)
        doc.add_paragraph(_professional_core_summary(report))
        _add_heading(doc, "Что не обнулилось", 2)
        for item in _list_items(not_reset)[:8]:
            _add_bullet(doc, item)
        doc.add_paragraph("")

        # 3. Сравнение маршрутов
        _add_heading(doc, "3. Сравнение маршрутов", 1)
        labels = ["Пессимистичный", "Базовый", "Оптимистичный"]
        for idx, item in enumerate(market[:3]):
            if not isinstance(item, dict):
                continue
            label = labels[idx] if idx < len(labels) else f"Вариант {idx+1}"
            _add_heading(doc, f"{label}: {_safe_text(item.get('profession'))}", 2)
            _add_kv(doc, "Соответствие", f"{item.get('fit_percent', '-')}%")
            _add_kv(doc, "Доход", _safe_text(item.get("salary_range")))
            _add_kv(doc, "Скорость входа", _safe_text(item.get("entry_speed")))
            _add_kv(doc, "Требования", ", ".join(_list_items(item.get("requirements"))[:5]))
        doc.add_paragraph("")

        # 4. Выбранный маршрут и первый шаг
        _add_heading(doc, "4. Выбранный маршрут и первый шаг", 1)
        _add_kv(doc, "Маршрут", _safe_text(decision.get("recommended_main_path")))
        _add_kv(doc, "Почему", _safe_text(decision.get("why_this_path")))
        _add_kv(doc, "Запасной", _safe_text(decision.get("backup_path")))
        _add_kv(doc, "Первый шаг", _safe_text(today.get("action")))
        _add_kv(doc, "Время", _safe_text(today.get("timebox")))
        doc.add_paragraph("")

        # 5. План на 30 дней
        _add_heading(doc, "5. План на 30 дней", 1)
        for week in first_month[:4]:
            if not isinstance(week, dict):
                continue
            _add_heading(doc, f"Неделя {week.get('week', '-')}: {_safe_text(week.get('focus'))}", 2)
            for task in _list_items(week.get("tasks", []))[:4]:
                _add_bullet(doc, task)
            doc.add_paragraph(f"Результат недели: {_safe_text(week.get('output'))}")
        doc.add_paragraph("")

        # 6. Анализ резюме
        _add_heading(doc, "6. Анализ резюме", 1)
        if resume_analysis:
            for item in _list_items(resume_analysis.get("what_is_good"))[:5]:
                _add_bullet(doc, item, "✅ ")
            for item in _list_items(resume_analysis.get("what_is_missing"))[:5]:
                _add_bullet(doc, item, "⚠️ ")
        else:
            doc.add_paragraph("Резюме не загружено. Загрузите CV для отдельного анализа под маршрут.")
        doc.add_paragraph("")

        # 7. Заключение (STAR section)
        _add_heading(doc, "7. Что может быть не так. Заключение", 1)
        doc.add_paragraph(
            "Карта меняется при новых данных о языке, документах, резюме, приоритетах или рынке."
        )
        if unknowns:
            _add_heading(doc, "Что нужно уточнить:", 2)
            for u in unknowns:
                _add_bullet(doc, u)
        _add_heading(doc, "Что делать самому:", 2)
        for pt in self_help_pts:
            _add_bullet(doc, pt)
        _add_heading(doc, "Когда полезен специалист:", 2)
        for pt in specialist_pts:
            _add_bullet(doc, pt)
        doc.add_paragraph("")

        # Closing
        closing_p = doc.add_paragraph()
        closing_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = closing_p.add_run("💬 Заключение")
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = _teal()
        doc.add_paragraph(closing_message)

        doc.save(str(docx_path))
        return docx_path, ""
    except Exception as exc:
        return None, f"docx_render_error: {exc}"


def generate_pdf_from_html_file(html_path: Path) -> Path | None:
    pdf_path, _error = generate_pdf_from_html_file_with_error(html_path)
    return pdf_path


def generate_report_files(report: dict, output_dir: str, user_name: str = "") -> tuple[Path | None, Path, Path | None]:
    html_path = generate_html_report_file(report, output_dir=output_dir, user_name=user_name)
    pdf_path = generate_pdf_from_html_file(html_path)
    docx_path, _ = generate_docx_report_file(report, output_dir=output_dir, user_name=user_name)
    return pdf_path, html_path, docx_path


def generate_report_payload(user_id: str, report: dict, base_url: str, output_dir: str, user_name: str = "") -> dict[str, str]:
    pdf_path = generate_pdf_report(report, output_dir=output_dir, user_name=user_name)
    filename = pdf_path.name
    base = base_url.rstrip("/")
    return {
        "telegram_summary": build_telegram_summary(report),
        "pdf_url": f"{base}/{filename}",
    }
