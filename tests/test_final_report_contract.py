import unittest

from prompts import FINAL_REPORT_PROMPT
from handlers.career import _build_execution_steps
from keyboards import CTA_CAREER_CONSULTANT, CTA_JOB_SEARCH_SUPPORT, next_step_cta_keyboard
from openai_client import EXECUTION_RESULT_SCHEMA
from utils.reporting import _guidance_text, build_meta, render_report_html


class FinalReportContractTests(unittest.TestCase):
    def test_selected_cta_is_first_keyboard_action(self) -> None:
        report = {"next_step_guidance": {"primary_cta": {"type": "job_search_support"}}}

        keyboard = next_step_cta_keyboard(report)

        self.assertEqual(CTA_JOB_SEARCH_SUPPORT, keyboard.keyboard[0][0].text)
        self.assertEqual(CTA_CAREER_CONSULTANT, keyboard.keyboard[1][0].text)

    def test_execution_result_contract_updates_facts_and_next_step(self) -> None:
        self.assertIn("confirmed_facts", EXECUTION_RESULT_SCHEMA["properties"])
        self.assertIn("hypothesis_update", EXECUTION_RESULT_SCHEMA["properties"])
        self.assertIn("next_step", EXECUTION_RESULT_SCHEMA["properties"])
        self.assertIn("human_escalation_recommended", EXECUTION_RESULT_SCHEMA["properties"])

    def test_legacy_report_gets_complete_guidance_and_chat_task(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Operations Coordinator"},
            "facts_only": {"unknowns": ["Уровень языка не подтверждён"]},
            "action_plan": {"today": {"action": "Собрать вакансии", "result": "Список требований"}},
        }

        guidance = _guidance_text(report)

        self.assertIn("Продолжить разбор в карьерном чате", guidance)
        self.assertGreaterEqual(guidance.count("—"), 2)
        self.assertIn("Когда особенно полезен живой консультант", guidance)

    def test_first_chat_task_becomes_first_execution_step(self) -> None:
        report = {
            "next_step_guidance": {"first_chat_task": {
                "action": "Найдите вакансии CAD/CAM",
                "volume": "5 вакансий",
                "result_to_send": "ссылки",
                "assistant_response": "Сравню повторяющиеся требования",
            }},
            "weekly_plan": [{"task": "Обновить CV"}],
        }

        steps = _build_execution_steps(report)

        self.assertIn("5 вакансий", steps[0]["task"])
        self.assertIn("ссылки", steps[0]["result"])
        self.assertEqual("Обновить CV", steps[1]["task"])

    def test_prompt_contains_patch31_required_contract(self) -> None:
        self.assertIn("Новый обязательный порядок финального контракта", FINAL_REPORT_PROMPT)
        self.assertIn("1. Как мы поняли вашу ситуацию", FINAL_REPORT_PROMPT)
        self.assertIn("15. План на неделю и месяц", FINAL_REPORT_PROMPT)
        self.assertIn("route_evidence_blocks", FINAL_REPORT_PROMPT)
        self.assertIn('"income_role": "primary|transition|quick|emergency"', FINAL_REPORT_PROMPT)
        self.assertIn("Запрет категоричности", FINAL_REPORT_PROMPT)
        self.assertIn("Возможный маршрут", FINAL_REPORT_PROMPT)
        self.assertIn("Вы точно должны стать", FINAL_REPORT_PROMPT)
        self.assertIn('"next_step_guidance"', FINAL_REPORT_PROMPT)
        self.assertIn('"type": "career_chat|career_consultant|job_search_support"', FINAL_REPORT_PROMPT)
        self.assertIn("не запускает диагностику заново", FINAL_REPORT_PROMPT)

    def test_html_contains_contract_and_route_evidence_block(self) -> None:
        report = {
            "digital_human": {
                "current_state": "Переходный этап",
                "main_asset": "Системная работа",
                "hidden_strengths": ["Дисциплина"],
                "main_risk": "Недостаток данных",
                "main_fear": "Ошибиться",
                "barriers": {"internal": ["Неуверенность"], "external": ["Язык"]},
                "career_readiness": {"urgency": "средняя"},
                "fastest_path_to_income": "Back-office Assistant",
            },
            "career_decision": {
                "recommended_main_path": "Back-office Specialist",
                "backup_path": "Operations Coordinator",
                "why_this_path": "Опирается на проверяемый опыт",
                "why_not_other_paths": [],
                "avoid_for_now": "Долгая смена трека",
                "decision_summary": "Гипотеза",
            },
            "route_evidence_blocks": [
                {
                    "route": "Back-office Specialist",
                    "why_it_fits": ["Есть опыт документов"],
                    "evidence_from_user": ["Работа с документооборотом"],
                    "missing_competencies": ["Польский B1"],
                    "entry_level": "junior-middle",
                    "income_role": "primary",
                    "risks": ["Конкуренция"],
                    "what_may_disprove_this_route": ["Появится прямой отказ"],
                }
            ],
            "facts_only": {
                "explicit_facts": ["Опыт координации"],
                "inferences": ["Похоже, есть устойчивый административный опыт."],
                "unknowns": ["Пока недостаточно данных, чтобы это оценить."],
                "contradictions": [],
            },
            "energy_sources": ["Планирование"],
            "career_priorities": ["Быстрый доход"],
            "competency_signals": ["Документооборот"],
            "resource_level": "medium",
            "integration_level": "medium",
            "action_plan": {"today": {"action": "Собрать 10 вакансий", "timebox": "15 минут", "result": "Требования"}},
            "weekly_plan": [{"day": 1, "task": "Обновить CV"}],
            "development_map": {"first_month": [{"week": 1, "focus": "Старт", "output": "Черновик"}]},
            "what_not_reset": ["Организация"],
            "experience_layers": ["Административный"],
            "social_integration": {},
            "market_analysis": [],
            "next_step_guidance": {
                "main_risks": [{"risk": "Оплатить курс до проверки вакансий", "consequence": "Можно выбрать невостребованный стек"}],
                "checks_before_decision": [{"check": "Право на работу", "why_it_matters": "Меняет доступность маршрута"}],
                "self_service_actions": [{"action": "Собрать 10 вакансий", "result": "Таблица требований"}],
                "support_accelerators": [{"task": "Сравнить вакансии", "result": "Список обязательных навыков", "format": "ai"}],
                "decision_level": {"known": "Основной маршрут выбран.", "next_confirmation": "Рынок и деньги.", "decision_after": "Затем решать об обучении."},
                "primary_cta": {"type": "career_chat", "title": "Продолжить разбор в карьерном чате", "why_now": "Нужно проверить рынок", "outcomes": ["Разобрать вакансии"]},
                "first_chat_task": {"action": "Найти вакансии", "volume": "5", "result_to_send": "ссылки", "assistant_response": "Сравню требования"},
            },
        }
        html = render_report_html(report, build_meta(report, user_name="Ivan"))

        self.assertIn("Подробный анализ по 15 блокам", html)
        self.assertNotIn("Контракт финального отчёта", html)
        self.assertIn("1. Как мы поняли вашу ситуацию", html)
        self.assertIn("15. План на неделю и месяц", html)
        self.assertIn("Маршруты с обязательным блоком доказательств", html)
        self.assertIn("Доказательства пользователя", html)
        self.assertIn("Что может опровергнуть маршрут", html)
        self.assertIn("Персональный следующий шаг", html)
        self.assertIn("Где сейчас главный риск ошибиться", html)
        self.assertIn("Что вы можете сделать самостоятельно", html)
        self.assertIn("Продолжить разбор в карьерном чате", html)


if __name__ == "__main__":
    unittest.main()
