import asyncio
import unittest
from types import SimpleNamespace

from handlers import career


class FakeMessage:
    def __init__(self):
        self.chat = SimpleNamespace(id=123)
        self.sent = []

    async def answer(self, text, **kwargs):
        self.sent.append(str(text))
        return None


class FakeState:
    def __init__(self):
        self.data = {
            "story_text": "Есть опыт в маркетинге и продуктовых исследованиях.",
            "answers_text": "Пользователь готов сменить сферу, есть 5 лет опыта.",
            "story_analysis": {"follow_up_questions": []},
            "selected_barriers": ["страх неуспеха"],
            "selected_fears": ["потеря дохода"],
            "selected_psych_markers": ["тревожность"],
            "selected_career_priorities": ["product marketing"],
            "selected_energy_sources": ["анализ данных"],
            "user_mode": "calm_steps",
            "session_id": "test-session",
            "public_user_id": "user-42",
            "language": "ru",
            "route_context": {
                "country": "Польша",
                "city": "Варшава",
                "current_language_level": "B1",
                "target_language": "B2",
                "income_urgency": "стабильно",
                "minimum_monthly_income": "2000 PLN",
                "desired_monthly_income": "3000 PLN",
                "training_budget": "500 PLN",
                "available_time_for_study": "3 часа",
                "career_goal_type": "сменить сферу",
                "work_preferences": "удалённо",
                "health_or_schedule_limits": "нет",
                "documents_and_work_rights": "есть",
                "diploma_status": "есть",
                "portfolio_or_references": "есть",
            },
            "profile_snapshot": {
                "country_code": "PL",
                "ready_for_report": True,
                "route_context": {"country": "Польша"},
            },
            "report_generation_in_progress": False,
            "report_already_generated": False,
            "report_generation_status": "",
            "short_report_sent": False,
            "html_report_generated": False,
            "final_report": {},
        }
        self.state = None

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, state):
        self.state = state


class FinalizationHotfixTest(unittest.TestCase):
    def test_finalize_career_flow_exits_with_short_report_and_flag(self):
        async def run_test():
            fake_state = FakeState()
            fake_message = FakeMessage()
            career.SESSION_FSM_CACHE[("user-42", "test-session")] = fake_state
            career.SESSION_MESSAGE_CACHE[("user-42", "test-session")] = fake_message

            await career.finalize_career_flow("user-42", "test-session", "last_required_answer")

            self.assertTrue(fake_state.data.get("report_already_generated"))
            self.assertIn("Собираю заключение", "\n".join(fake_message.sent))
            self.assertIn("Маршрут на основе подтверждённых функций", "\n".join(fake_message.sent))
            self.assertFalse(fake_state.data.get("report_generation_in_progress"))

        asyncio.run(run_test())

    def test_canonical_career_decision_exposes_main_route_and_route_id(self):
        report = {
            "career_decision": {
                "recommended_main_path": "Product Marketing Manager",
                "backup_path": "Product Discovery",
                "country_name": "Литва",
                "city": "Вильнюс",
                "professional_core": "Вы умеете исследовать рынок и вести продуктовые решения.",
                "market_value": "High for PMM",
            },
            "profile_snapshot": {"country_name": "Литва", "city": "Вильнюс"},
            "action_plan": {"today": {"action": "Собрать 10 вакансий"}},
        }

        decision = career._ensure_canonical_career_decision(report, route_id="route-main")

        self.assertEqual(decision["main_route"]["title"], "Product Marketing Manager")
        self.assertEqual(decision["selected_route_id"], "route-main")
        self.assertEqual(decision["country_name"], "Литва")
        self.assertEqual(decision["city"], "Вильнюс")
        self.assertIn("Product Discovery", [route["title"] for route in decision["alternative_routes"]])
        self.assertEqual(report["career_decision"]["recommended_main_path"], "Product Marketing Manager")


if __name__ == "__main__":
    unittest.main()
