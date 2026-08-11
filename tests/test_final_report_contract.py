import unittest

from prompts import FINAL_REPORT_PROMPT
from utils.reporting import build_meta, render_report_html


class FinalReportContractTests(unittest.TestCase):
    def test_prompt_contains_patch31_required_contract(self) -> None:
        self.assertIn("Новый обязательный порядок финального контракта", FINAL_REPORT_PROMPT)
        self.assertIn("1. Как мы поняли вашу ситуацию", FINAL_REPORT_PROMPT)
        self.assertIn("15. План на неделю и месяц", FINAL_REPORT_PROMPT)
        self.assertIn("route_evidence_blocks", FINAL_REPORT_PROMPT)
        self.assertIn('"income_role": "primary|transition|quick|emergency"', FINAL_REPORT_PROMPT)
        self.assertIn("Запрет категоричности", FINAL_REPORT_PROMPT)
        self.assertIn("Возможный маршрут", FINAL_REPORT_PROMPT)
        self.assertIn("Вы точно должны стать", FINAL_REPORT_PROMPT)

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
        }
        html = render_report_html(report, build_meta(report, user_name="Ivan"))

        self.assertIn("Подробный анализ по 15 блокам", html)
        self.assertNotIn("Контракт финального отчёта", html)
        self.assertIn("1. Как мы поняли вашу ситуацию", html)
        self.assertIn("15. План на неделю и месяц", html)
        self.assertIn("Маршруты с обязательным блоком доказательств", html)
        self.assertIn("Доказательства пользователя", html)
        self.assertIn("Что может опровергнуть маршрут", html)


if __name__ == "__main__":
    unittest.main()
