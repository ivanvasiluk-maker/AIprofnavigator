import asyncio
import json

from config import settings
from openai_client import CareerOpenAIClient


BASE_STORY_ANALYSIS = {
    "current_identity": "Женщина, 41 год, из Беларуси, 12 лет админ-опыта в госструктуре, сейчас живет в Польше, хочет стабильную работу без резкой смены профессии",
    "experience_snapshot": [
        "Документооборот, контроль сроков и поручений",
        "Координация 4 сотрудников",
        "Работа с формальными процедурами и отчетностью",
    ],
    "transferable_strengths": [
        "системность",
        "внимание к деталям",
        "дисциплина процессов",
    ],
    "constraints": [
        "польский язык A2",
        "высокий финансовый стресс",
        "нужен доход в ближайшие 4-8 недель",
    ],
    "missing_data": [],
    "follow_up_questions": [
        {
            "question": "Какой минимальный доход нужен в месяц?",
            "why_it_matters": "определяет стратегии входа",
            "answer_type": "number",
            "options": [],
        },
        {
            "question": "Сколько часов в неделю готовы уделять поиску?",
            "why_it_matters": "реалистичность плана",
            "answer_type": "number",
            "options": [],
        },
        {
            "question": "Готовы ли начать с временной/частичной занятости?",
            "why_it_matters": "ускорение первого дохода",
            "answer_type": "single_choice",
            "options": ["да", "нет"],
        },
        {
            "question": "Какие города Польши рассматриваете?",
            "why_it_matters": "локальный рынок вакансий",
            "answer_type": "text",
            "options": [],
        },
        {
            "question": "Есть ли опыт CRM/Excel/Google Sheets?",
            "why_it_matters": "matching к office/back-office вакансиям",
            "answer_type": "text",
            "options": [],
        },
        {
            "question": "Нужна ли полностью удаленная работа?",
            "why_it_matters": "ограничения вакансий",
            "answer_type": "single_choice",
            "options": ["да", "нет", "гибрид"],
        },
        {
            "question": "Какие задачи из прошлого нравились больше всего?",
            "why_it_matters": "стабильная мотивация",
            "answer_type": "text",
            "options": [],
        },
        {
            "question": "Какие задачи вызывают наибольший стресс?",
            "why_it_matters": "профилактика выгорания",
            "answer_type": "text",
            "options": [],
        },
    ],
}

BASE_RESUME_ANALYSIS = {
    "hard_skills": ["Документооборот", "MS Excel", "Организация процессов"],
    "soft_skills": ["Ответственность", "Коммуникация", "Стрессоустойчивость"],
    "gaps": ["Польский язык", "Лексика под вакансии Польши"],
    "cv_fixes": ["Усилить блок достижений", "Добавить KPI-формулировки"],
}

BASE_BARRIERS = "Боюсь ошибиться, тревога, откладываю отклики"
BASE_QA_ANSWERS = (
    "Минимум 6000 PLN netto в месяц; 12 часов в неделю; готова на гибрид и временную занятость; "
    "Варшава и Лодзь; Excel уверенно"
)
BASE_STORY_TEXT = (
    "Мне 41 год, я из Беларуси, последние 12 лет работала в административной роли в госструктуре. "
    "Сейчас живу в Польше, польский пока на уровне A2. Мне нужна стабильная работа без резкой смены профессии, "
    "потому что есть финансовое давление и нужен доход в ближайшие 4-8 недель. "
    "Лучше всего у меня получались документооборот, контроль сроков и координация людей."
)


SCENARIOS = [
    {
        "name": "admin_pl",
        "story": BASE_STORY_TEXT,
        "story_analysis": BASE_STORY_ANALYSIS,
        "resume_analysis": BASE_RESUME_ANALYSIS,
        "answers": BASE_QA_ANSWERS,
        "selected_barriers": ["Боюсь ошибиться", "Откладываю"],
        "selected_psych_markers": ["Тревога"],
    },
    {
        "name": "ops_ngo",
        "story": "Я из Беларуси, 38 лет, в Польше. Работала координатором проектов и вела документы, расписания, отчеты и коммуникацию с участниками. Нужна стабильная работа в NGO, education admin или operations.",
        "story_analysis": {
            "current_identity": "Женщина, 38 лет, координатор проектов и админ-процессов, живет в Польше, ищет стабильную operations/NGO роль",
            "experience_snapshot": ["Координация проектов", "Отчеты и документы", "Коммуникация с участниками"],
            "skills": ["координация", "документы", "таблицы"],
        },
        "resume_analysis": BASE_RESUME_ANALYSIS,
        "answers": "Готова на гибрид, нужен стабильный доход, интересны NGO и education projects",
        "selected_barriers": ["Боюсь ошибиться"],
        "selected_psych_markers": ["Тревога"],
    },
    {
        "name": "sales_profile",
        "story": "Я 33-летний sales manager, переехал в Польшу и 7 лет работал в B2B продажах, вел клиентов и переговоры. Хочу быстро выйти в доход.",
        "story_analysis": {
            "current_identity": "Мужчина, 33 года, sales manager с 7 годами B2B продаж, живет в Польше и хочет быстро вернуться в доход",
            "experience_snapshot": ["B2B продажи", "переговоры", "ведение клиентов"],
            "skills": ["sales", "CRM", "переговоры"],
        },
        "resume_analysis": {"hard_skills": ["CRM", "Sales pipeline"], "soft_skills": ["переговоры"], "gaps": [], "cv_fixes": []},
        "answers": "Нужен быстрый доход, готов к sales support или account roles",
        "selected_barriers": ["Боюсь потерять деньги"],
        "selected_psych_markers": ["Тревога"],
    },
]


async def main() -> None:
    client = CareerOpenAIClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        transcribe_model=settings.openai_transcribe_model,
    )
    for scenario in SCENARIOS:
        report = await client.build_report(
            story=scenario["story"],
            story_analysis=scenario["story_analysis"],
            answers=scenario["answers"],
            resume_analysis=scenario["resume_analysis"],
            selected_barriers=scenario["selected_barriers"],
            selected_psych_markers=scenario["selected_psych_markers"],
            language="ru",
        )

        checks = {
            "current_state_matches_story": report.get("digital_human", {}).get("current_state")
            == scenario["story_analysis"]["current_identity"],
            "has_career_translation": isinstance(report.get("career_translation"), list)
            and len(report.get("career_translation", [])) > 0,
            "has_barrier_landscape": isinstance(report.get("barrier_landscape"), dict),
            "has_recommendations": isinstance(report.get("career_recommendations"), list)
            and len(report.get("career_recommendations", [])) > 0,
        }

        print("SCENARIO=" + scenario["name"])
        print("SMOKE_CHECKS=" + json.dumps(checks, ensure_ascii=False))
        print("CURRENT_STATE=" + report.get("digital_human", {}).get("current_state", ""))
        if report.get("career_recommendations"):
            first_reco = report["career_recommendations"][0]
            print("TOP_RECO_1=" + first_reco.get("title", first_reco.get("role", "")))
        if report.get("career_translation"):
            first_translation = report["career_translation"][0]
            if isinstance(first_translation, dict):
                print("TRANSLATION_1=" + str(first_translation.get("market_term", "")))
            else:
                print("TRANSLATION_1=")


if __name__ == "__main__":
    asyncio.run(main())