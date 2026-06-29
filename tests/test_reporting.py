import unittest

from utils.reporting import build_meta, build_offer_text, build_telegram_summary, render_report_html


class ReportingUtilsTests(unittest.TestCase):
    def test_build_telegram_summary_contains_core_fields(self) -> None:
        report = {
            "digital_human": {
                "current_state": "Административный специалист в Польше",
                "main_asset": "Документооборот и координация",
                "main_risk": "Финансовое давление",
                "main_barrier": "Нестабильная занятость",
                "barriers": {"external": ["Язык", "Нет локального резюме"]},
            },
            "resource_level": "medium",
            "integration_level": "low",
            "energy_sources": ["Организация процессов", "Анализ"],
            "career_priorities": ["Быстро выйти на доход", "Найти устойчивость и баланс"],
            "competency_signals": ["Коммуникация", "Организация процессов"],
            "facts_only": {
                "explicit_facts": [
                    "17 лет работали в строительстве",
                    "Умеете делать отделку и собирать мебель",
                    "Есть опыт ведения небольших объектов",
                ],
                "inferences": [],
                "unknowns": [],
                "contradictions": [],
            },
            "career_decision": {
                "recommended_main_path": "Administrative Assistant",
                "why_this_path": "Быстрый вход с текущими навыками",
            },
            "action_plan": {"today": {"action": "Открыть 5 вакансий"}},
        }

        summary = build_telegram_summary(report)
        self.assertIn("Что я услышал в вашей истории", summary)
        self.assertLess(summary.index("Что я услышал в вашей истории"), summary.index("Ваш Career GPS"))
        self.assertIn("Главная проблема", summary)
        self.assertIn("Ресурс", summary)
        self.assertIn("Ограничение", summary)
        self.assertIn("Ваш Career GPS", summary)
        self.assertIn("Ваше профессиональное ядро", summary)
        self.assertIn("Вы не начинаете с нуля", summary)
        self.assertIn("Кто вы сейчас", summary)
        self.assertIn("Что не обнулилось", summary)
        self.assertIn("Источники энергии", summary)
        self.assertIn("Карьерные приоритеты", summary)
        self.assertIn("STAR-компетенции", summary)
        self.assertIn("Ресурс и рабочий темп", summary)
        self.assertIn("Сейчас ресурс частично ограничен", summary)
        self.assertIn("Состояние интеграции", summary)
        self.assertIn("Интеграция пока начальная", summary)
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
            "resource_level": "high",
            "integration_level": "medium",
            "energy_sources": ["Организация процессов", "Работа с людьми"],
            "career_priorities": ["Быстро выйти на доход", "Работать по специальности"],
            "competency_signals": ["Лидерство", "Коммуникация"],
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
        self.assertIn("Ваше профессиональное ядро", html)
        self.assertIn("Анализ возможностей", html)
        self.assertIn("План действий", html)
        self.assertIn("Источники энергии", html)
        self.assertIn("Карьерные приоритеты", html)
        self.assertIn("STAR-компетенции", html)
        self.assertIn("Ресурс и рабочий темп", html)
        self.assertIn("Сейчас ресурс устойчивый", html)
        self.assertIn("Состояние интеграции", html)
        self.assertIn("Интеграция пока частичная", html)

    def test_offer_text_contains_zero_price(self) -> None:
        offer = build_offer_text()
        self.assertIn("Что входит", offer)
        self.assertIn("первых вакансий", offer)


if __name__ == "__main__":
    unittest.main()
