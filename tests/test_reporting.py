import unittest

from utils.reporting import build_meta, build_offer_text, build_telegram_summary, render_report_html


class ReportingUtilsTests(unittest.TestCase):
    def test_build_telegram_summary_contains_core_fields(self) -> None:
        report = {
            "digital_human": {
                "current_state": "Административный специалист в Польше",
                "main_asset": "Документооборот и координация",
                "main_risk": "Финансовое давление",
            },
            "career_decision": {
                "recommended_main_path": "Administrative Assistant",
                "why_this_path": "Быстрый вход с текущими навыками",
            },
            "action_plan": {"today": {"action": "Открыть 5 вакансий"}},
        }

        summary = build_telegram_summary(report)
        self.assertIn("Ваш Career GPS", summary)
        self.assertIn("Кто вы сейчас", summary)
        self.assertIn("Что не обнулилось", summary)
        self.assertIn("Рекомендуемый маршрут", summary)
        self.assertIn("Открыть 5 вакансий", summary)

    def test_render_report_html_contains_key_sections(self) -> None:
        report = {
            "digital_human": {
                "current_state": "Переходный этап",
                "main_asset": "Сильная координация",
                "hidden_strengths": ["Системность"],
                "main_risk": "Тревога",
                "main_fear": "Ошибиться",
                "career_readiness": {"urgency": "высокая"},
            },
            "career_decision": {
                "recommended_main_path": "Back-office Specialist",
                "why_this_path": "Минимальный разрыв",
                "avoid_for_now": "Долгая смена профессии",
            },
            "market_analysis": [
                {
                    "profession": "Back-office Specialist",
                    "fit_percent": 85,
                    "entry_speed": "средняя",
                    "competition": "средняя",
                    "salary_range": "5500-8000 PLN brutto",
                    "requirements": ["Excel", "Документы", "Польский B1"],
                }
            ],
            "action_plan": {
                "today": {"action": "Собрать 10 вакансий", "timebox": "15 минут", "result": "Список требований"},
                "this_week": ["5 откликов"],
            },
            "weekly_plan": [{"day": 1, "task": "Обновить CV"}],
            "development_map": {"first_month": [{"week": 1, "focus": "Старт", "output": "Черновик CV"}]},
        }
        meta = build_meta(report, user_name="Ivan")
        html = render_report_html(report, meta)

        self.assertIn("Career GPS Report", html)
        self.assertIn("Профиль ситуации", html)
        self.assertIn("Анализ возможностей", html)
        self.assertIn("План действий", html)

    def test_offer_text_contains_zero_price(self) -> None:
        offer = build_offer_text()
        self.assertIn("Что входит", offer)
        self.assertIn("первых вакансий", offer)


if __name__ == "__main__":
    unittest.main()
