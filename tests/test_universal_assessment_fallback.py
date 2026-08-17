from __future__ import annotations

import unittest

from services.career_assessment import build_deterministic_assessment, validate_career_assessment


class UniversalAssessmentFallbackTest(unittest.TestCase):
    PROFILES = (
        ("Клинический логопед", ["проводит диагностику речи", "ведёт коррекционные занятия"], "сохранить квалификацию"),
        ("Наладчик станков", ["настраивает оборудование", "контролирует допуски"], "сменить график"),
        ("Руководитель закупок", ["ведёт переговоры", "отвечает за бюджет"], "сохранить уровень ответственности"),
        ("Администратор площадки", ["принимает посетителей", "координирует расписание"], "понять сильные функции"),
        ("Организатор сообщества", ["координирует волонтёров", "проводит мероприятия"], "сменить профессию полностью"),
    )

    def build(self, index: int):
        role, functions, goal = self.PROFILES[index]
        return build_deterministic_assessment(
            {"country_code": "EE", "country_name": "Эстония", "currency": "EUR", "career_goal": goal},
            {"professional_core_hypotheses": [role], "confirmed_functions": functions},
            {"achievements": [f"Подтверждённый результат профиля {index}"], "languages": ["русский"]},
            assessment_id=f"assessment-{index}", session_id=f"session-{index}", profile_version="1",
        )

    def test_five_distinct_profiles_are_fact_bound_and_complete(self) -> None:
        assessments = [self.build(index) for index in range(len(self.PROFILES))]
        for index, assessment in enumerate(assessments):
            role, functions, _ = self.PROFILES[index]
            validation = validate_career_assessment(assessment, snapshot_country_code="EE", snapshot_currency="EUR")
            self.assertTrue(validation.valid, validation.errors)
            self.assertEqual(assessment.identity.professional_core, functions)
            self.assertEqual(assessment.routes.primary_routes[0].title, role)
            self.assertGreaterEqual(len(assessment.first_steps), 3)
            self.assertEqual(len({step.type for step in assessment.first_steps}), len(assessment.first_steps))
            rendered = str(assessment.to_dict())
            self.assertTrue(all(function in rendered for function in functions))
            for other_index, (other_role, _, _) in enumerate(self.PROFILES):
                if other_index != index:
                    self.assertNotIn(other_role, rendered)

    def test_unknown_market_fields_limit_only_related_claims(self) -> None:
        assessment = build_deterministic_assessment(
            {},
            {"professional_core_hypotheses": ["Редактор научных текстов"], "confirmed_functions": ["проверяет аргументацию"]},
            {},
            assessment_id="unknown-market", session_id="unknown-market-session", profile_version="1",
        )
        self.assertIsNone(assessment.context.country_name)
        self.assertIsNone(assessment.context.preferred_currency)
        self.assertEqual(len(assessment.first_steps), 3)
        self.assertIn("Целевая страна", assessment.routes.primary_routes[0].missing)
        self.assertNotIn("зарплат", str(assessment.to_dict()).casefold())

    def test_fallback_contains_no_forbidden_generic_route_labels(self) -> None:
        text = str(self.build(0).to_dict())
        for forbidden in (
            "Текущая профессиональная специализация",
            "Смежная роль",
            "Возможная новая профессия",
            "Маршрут требует повторной сборки",
        ):
            self.assertNotIn(forbidden, text)

    def test_every_hypothesis_has_all_ten_evaluation_criteria(self) -> None:
        assessment = self.build(2)
        expected = {
            "confirmed_function_fit",
            "professional_capital_preserved",
            "entry_level_realistic",
            "target_country_access",
            "language_fit",
            "income_minimum_fit",
            "life_constraints_fit",
            "learning_volume",
            "safe_test_speed",
            "income_status_loss_risk",
        }
        evaluations = assessment.metadata["route_evaluations"]
        self.assertEqual(set(evaluations), {route.route_id for route in assessment.routes.all_routes()})
        for evaluation in evaluations.values():
            self.assertEqual(set(evaluation["criteria"]), expected)

    def test_self_employment_and_retraining_require_user_signals(self) -> None:
        ordinary = build_deterministic_assessment(
            {"career_goal": "сменить график"},
            {"professional_core_hypotheses": ["Архивист"], "confirmed_functions": ["описывает документы"], "career_hypotheses": ["Исследователь коллекций"]},
            {}, assessment_id="ordinary", session_id="ordinary-session", profile_version="1",
        )
        ordinary_text = str(ordinary.to_dict()).casefold()
        self.assertNotIn("самостоятельная практика", ordinary_text)
        self.assertNotIn("retraining_required", [route.entry_path for route in ordinary.routes.all_routes()])

        substantial = build_deterministic_assessment(
            {"career_goal": "полностью сменить профессию и попробовать частную практику"},
            {"professional_core_hypotheses": ["Архивист"], "confirmed_functions": ["описывает документы"], "career_hypotheses": ["Исследователь коллекций"]},
            {}, assessment_id="substantial", session_id="substantial-session", profile_version="1",
        )
        self.assertEqual(sum("Самостоятельная практика" in route.title for route in substantial.routes.all_routes()), 1)
        self.assertIn("retraining_required", [route.entry_path for route in substantial.routes.all_routes()])

    def test_technical_log_records_supplied_fallback_reason(self) -> None:
        with self.assertLogs("services.career_assessment", level="WARNING") as captured:
            build_deterministic_assessment(
                {}, {"confirmed_functions": ["сверяет реестры", "проверяет записи"]}, {},
                assessment_id="logged", session_id="logged-session", profile_version="1",
                fallback_reason="schema_repair_exhausted",
            )
        self.assertIn("reason=schema_repair_exhausted", " ".join(captured.output))


if __name__ == "__main__":
    unittest.main()
