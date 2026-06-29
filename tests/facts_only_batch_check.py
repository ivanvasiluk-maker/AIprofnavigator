import asyncio
import re
import sys
from typing import Any

from config import settings
from openai_client import CareerOpenAIClient


FORBIDDEN_PATTERNS = [
    re.compile(r"\bу вас есть опыт документ", re.IGNORECASE),
    re.compile(r"\bвы умеете управлять процесс", re.IGNORECASE),
    re.compile(r"\bвы понимаете местный рынок", re.IGNORECASE),
    re.compile(r"\bу вас есть профессиональные контакты", re.IGNORECASE),
    re.compile(r"\bу вас высокий уровень интеграции", re.IGNORECASE),
    re.compile(r"\bвы готовы к переучиванию", re.IGNORECASE),
]

CAUTIOUS_PREFIXES = (
    "похоже",
    "вероятно",
    "пока не хватает данных",
    "данных недостаточно",
)

CLAIM_GROUPS: dict[str, list[str]] = {
    "documents": ["документ", "документооборот", "формальн", "процедур"],
    "processes": ["процесс", "срок", "поручен", "координа", "управлен"],
    "market": ["рынок", "рынка труда", "локальный рынок", "местный рынок"],
    "contacts": ["контакт", "нетворк", "сообществ", "профконтакт"],
    "integration": ["интеграц", "интегрир"],
    "retraining": ["переуч", "переквалиф", "обуч"],
}


def _mk_analysis(identity: str, snapshot: list[str], skills: list[str], summary: str = "") -> dict[str, Any]:
    return {
        "story_summary": summary or identity,
        "current_identity": identity,
        "experience_snapshot": snapshot,
        "skills": skills,
        "constraints": [],
        "goals": [],
        "missing_data": [],
        "follow_up_questions": [],
        "confidence_note": "",
    }


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "worker_universal_sparse",
        "story": "Работал на подработках: развоз, помощь на складе, мелкий ремонт. Сейчас в Польше ищу любой стабильный доход.",
        "analysis": _mk_analysis(
            "Мужчина, подработки и ручной труд, сейчас в Польше ищет стабильный доход",
            ["Подработки", "Развоз", "Склад", "Мелкий ремонт"],
            ["ответственность"],
        ),
        "answers": "Нужен доход быстро, могу работать 6 дней в неделю",
    },
    {
        "name": "admin_documents_confirmed",
        "story": "12 лет делала документооборот, контроль сроков и координацию задач в офисе.",
        "analysis": _mk_analysis(
            "Административный специалист",
            ["Документооборот", "Контроль сроков", "Координация задач"],
            ["Excel", "документы", "организация"],
        ),
        "answers": "Ищу офисную роль в Польше",
    },
    {
        "name": "sales_confirmed",
        "story": "7 лет в B2B продажах, переговоры, CRM, воронка, KPI.",
        "analysis": _mk_analysis(
            "Sales manager",
            ["B2B продажи", "переговоры", "CRM", "KPI"],
            ["sales", "crm", "коммуникация"],
        ),
        "answers": "Нужен быстрый доход, готов к sales support",
    },
    {
        "name": "caregiver_sparse",
        "story": "Работала сиделкой и помощницей по дому. Хочу стабильный график и доход.",
        "analysis": _mk_analysis(
            "Сиделка с опытом ухода",
            ["Уход", "Поддержка людей"],
            ["внимательность", "эмпатия"],
        ),
        "answers": "Ищу работу рядом с домом",
    },
    {
        "name": "cook_waiter",
        "story": "Работал поваром и официантом. Важно быстро выйти на доход.",
        "analysis": _mk_analysis(
            "Повар/официант",
            ["Кухня", "Сервис", "Работа в сменах"],
            ["организация", "стрессоустойчивость"],
        ),
        "answers": "Готов на сменный график",
    },
    {
        "name": "driver_logistics",
        "story": "Водитель-экспедитор 9 лет, маршруты, документы на доставку, взаимодействие с клиентами.",
        "analysis": _mk_analysis(
            "Водитель-экспедитор",
            ["Маршруты", "Доставка", "Документы на груз"],
            ["дисциплина", "навигация", "коммуникация"],
        ),
        "answers": "Нужен стабильный доход в течение месяца",
    },
    {
        "name": "warehouse_operator",
        "story": "Оператор склада, приемка и отгрузка, учет остатков.",
        "analysis": _mk_analysis(
            "Складской оператор",
            ["Приемка", "Отгрузка", "Учет"],
            ["внимательность", "скорость"],
        ),
        "answers": "Ищу склад в моем районе",
    },
    {
        "name": "seamstress",
        "story": "10 лет швея на производстве. Хочу продолжить в этой сфере.",
        "analysis": _mk_analysis(
            "Швея",
            ["Швейное производство", "Качество"],
            ["точность", "усидчивость"],
        ),
        "answers": "Готова на обучение на месте",
    },
    {
        "name": "teacher_transition",
        "story": "Была учителем, сейчас хочу перейти в координаторскую роль в образовательных проектах.",
        "analysis": _mk_analysis(
            "Педагог в переходе",
            ["Обучение", "Коммуникация", "Организация занятий"],
            ["планирование", "презентация"],
        ),
        "answers": "Хочу гибрид и стабильность",
    },
    {
        "name": "nurse",
        "story": "Работала медсестрой, хочу работу с понятным расписанием.",
        "analysis": _mk_analysis(
            "Медсестра",
            ["Уход", "Процедуры", "Командная работа"],
            ["ответственность", "внимание"],
        ),
        "answers": "Важно не ночные смены",
    },
    {
        "name": "manual_labor_no_docs",
        "story": "Работал на стройке и в сервисе. Делал физическую работу.",
        "analysis": _mk_analysis(
            "Рабочий строительного профиля",
            ["Стройка", "Физический труд"],
            ["выносливость"],
        ),
        "answers": "Нужна работа рядом",
    },
    {
        "name": "freelance_clients",
        "story": "Делала частные заказы по дизайну и договаривалась с клиентами.",
        "analysis": _mk_analysis(
            "Фриланс специалист",
            ["Частные заказы", "Переговоры с клиентами"],
            ["креатив", "коммуникация"],
        ),
        "answers": "Хочу комбинировать фриланс и работу",
    },
    {
        "name": "cleaning_service",
        "story": "Работала в клининге, хочу стабильный график и прогнозируемый доход.",
        "analysis": _mk_analysis(
            "Специалист клининга",
            ["Клининг", "Стандарты чистоты"],
            ["дисциплина", "аккуратность"],
        ),
        "answers": "Подойдет частичная занятость",
    },
    {
        "name": "it_support",
        "story": "2 года в IT support: тикеты, коммуникация с пользователями, базовая диагностика.",
        "analysis": _mk_analysis(
            "IT support",
            ["Тикеты", "Поддержка пользователей"],
            ["коммуникация", "аналитика"],
        ),
        "answers": "Хочу role с удаленкой",
    },
    {
        "name": "bookkeeper_light",
        "story": "Помогала с первичкой и таблицами, формировала отчеты в Excel.",
        "analysis": _mk_analysis(
            "Помощник бухгалтера",
            ["Первичные документы", "Отчеты", "Excel"],
            ["excel", "точность"],
        ),
        "answers": "Готова на стартовую роль",
    },
    {
        "name": "beauty_master",
        "story": "Мастер в сфере красоты, работала с клиентами и записью.",
        "analysis": _mk_analysis(
            "Мастер услуг",
            ["Работа с клиентами", "Запись", "Сервис"],
            ["коммуникация", "самоорганизация"],
        ),
        "answers": "Нужен стабильный поток клиентов",
    },
    {
        "name": "factory_operator",
        "story": "Оператор линии на производстве. Следил за качеством и нормами.",
        "analysis": _mk_analysis(
            "Оператор производственной линии",
            ["Производство", "Контроль качества"],
            ["внимательность", "дисциплина"],
        ),
        "answers": "Ищу сменный график",
    },
    {
        "name": "project_assistant",
        "story": "Ассистент проектов: встречи, таблицы, календари, коммуникация с командой.",
        "analysis": _mk_analysis(
            "Ассистент проектов",
            ["Календари", "Таблицы", "Командная координация"],
            ["организация", "коммуникация"],
        ),
        "answers": "Хочу в operations",
    },
    {
        "name": "noisy_sparse",
        "story": "Переехал недавно, делал разную работу, пока ищу направление.",
        "analysis": _mk_analysis(
            "Мигрант в переходе",
            ["Разная работа"],
            ["адаптивность"],
        ),
        "answers": "Нужен первый стабильный шаг",
    },
    {
        "name": "retail_cashier",
        "story": "Кассир и продавец, работа с клиентами и выкладкой.",
        "analysis": _mk_analysis(
            "Кассир/продавец",
            ["Клиенты", "Касса", "Выкладка"],
            ["коммуникация", "оперативность"],
        ),
        "answers": "Готова к полной занятости",
    },
]


def _iter_text_values(data: Any):
    if isinstance(data, dict):
        for value in data.values():
            yield from _iter_text_values(value)
        return
    if isinstance(data, list):
        for value in data:
            yield from _iter_text_values(value)
        return
    if isinstance(data, str):
        yield data


def _collect_user_claim_texts(report: dict[str, Any]) -> list[str]:
    texts: list[str] = []

    digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
    for key in (
        "summary",
        "previous_identity",
        "current_state",
        "main_asset",
        "main_risk",
        "main_barrier",
        "main_fear",
        "fastest_path_to_income",
        "long_term_path",
    ):
        value = digital_human.get(key)
        if isinstance(value, str):
            texts.append(value)

    for key in ("hidden_strengths",):
        for value in digital_human.get(key, []) if isinstance(digital_human.get(key), list) else []:
            if isinstance(value, str):
                texts.append(value)

    skills = digital_human.get("skills") if isinstance(digital_human.get("skills"), dict) else {}
    for key in ("professional", "transferable", "hidden"):
        for value in skills.get(key, []) if isinstance(skills.get(key), list) else []:
            if isinstance(value, str):
                texts.append(value)

    texts.extend(str(x) for x in report.get("what_not_reset", []) if isinstance(x, str))
    texts.extend(str(x) for x in report.get("experience_layers", []) if isinstance(x, str))
    texts.extend(str(x) for x in report.get("competency_signals", []) if isinstance(x, str))

    social = report.get("social_integration") if isinstance(report.get("social_integration"), dict) else {}
    for key in ("environment", "people", "communities", "opportunities", "contribution"):
        values = social.get(key)
        if isinstance(values, list):
            texts.extend(str(x) for x in values if isinstance(x, str))

    market = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
    for item in market:
        if isinstance(item, dict) and isinstance(item.get("profile_match_reason"), str):
            texts.append(item["profile_match_reason"])

    recommendations = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
    for item in recommendations:
        if isinstance(item, dict) and isinstance(item.get("why_fit"), str):
            texts.append(item["why_fit"])

    return texts


def _is_cautious(text: str) -> bool:
    line = text.strip().lower()
    return line.startswith(CAUTIOUS_PREFIXES)


def _segment_text(text: str) -> list[str]:
    parts = re.split(r"[\n\.;]+", text)
    return [part.strip() for part in parts if part.strip()]


def _validate_report(report: dict[str, Any]) -> list[str]:
    violations: list[str] = []

    facts_only = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
    explicit_facts = facts_only.get("explicit_facts") if isinstance(facts_only.get("explicit_facts"), list) else []
    explicit_blob = " ".join(str(x) for x in explicit_facts).lower()

    user_texts = _collect_user_claim_texts(report)

    # 1) Forbidden formulations in user-profile claims.
    for text in user_texts:
        if not text:
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                violations.append(f"forbidden_phrase: {text}")
                break

    # 2) Claims that have no support in explicit_facts.
    # Skip cautious phrasing and unknown placeholders.
    for text in user_texts:
        for segment in _segment_text(text):
            low = segment.lower()
            if _is_cautious(segment):
                continue
            if "данных недостаточно" in low or "пока не хватает данных" in low:
                continue

            for group_name, markers in CLAIM_GROUPS.items():
                if not any(marker in low for marker in markers):
                    continue
                if any(marker in explicit_blob for marker in markers):
                    continue
                violations.append(f"unsupported_claim[{group_name}]: {segment}")
                break

    return violations


async def _run_scenario(client: CareerOpenAIClient, scenario: dict[str, Any]) -> tuple[str, list[str]]:
    report = await client.build_report(
        story=scenario["story"],
        story_analysis=scenario["analysis"],
        answers=scenario["answers"],
        resume_analysis={},
        selected_barriers=[],
        selected_fears=[],
        selected_psych_markers=[],
        selected_energy_sources=[],
        selected_career_priorities=[],
        language="ru",
    )
    violations = _validate_report(report)
    return scenario["name"], violations


async def main() -> int:
    if len(SCENARIOS) != 20:
        print(f"ERROR: expected 20 scenarios, got {len(SCENARIOS)}")
        return 2

    client = CareerOpenAIClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        transcribe_model=settings.openai_transcribe_model,
    )

    failed = 0
    for scenario in SCENARIOS:
        name, violations = await _run_scenario(client, scenario)
        if violations:
            failed += 1
            print(f"[FAIL] {name}")
            for item in violations[:10]:
                print(f"  - {item}")
            if len(violations) > 10:
                print(f"  ... and {len(violations) - 10} more")
        else:
            print(f"[OK]   {name}")

    passed = len(SCENARIOS) - failed
    print("\nBATCH RESULT")
    print(f"Scenarios: {len(SCENARIOS)}")
    print(f"Passed:    {passed}")
    print(f"Failed:    {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
