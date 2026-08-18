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
            # The deterministic fallback must not manufacture a second profession
            # from a task when no researched target role was supplied.
            self.assertGreaterEqual(len(assessment.routes.all_routes()), 1)
            self.assertLessEqual(len(assessment.routes.all_routes()), 4)
            self.assertEqual(len({route.title for route in assessment.routes.all_routes()}), len(assessment.routes.all_routes()))
            self.assertEqual(len({step.type for step in assessment.first_steps}), len(assessment.first_steps))
            self.assertEqual(assessment.context.country_code, "EE")
            self.assertEqual(assessment.context.preferred_currency, "EUR")
            self.assertEqual([item.language for item in assessment.context.current_languages], ["русский"])
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

    def test_current_and_target_roles_are_never_conflated(self) -> None:
        assessment = build_deterministic_assessment(
            {"current_role": "Координатор лаборатории", "career_goal": "перейти в смежную роль"},
            {"confirmed_functions": ["ведёт реестр образцов", "координирует график"]},
            {"target_roles": ["Специалист по качеству"]},
            assessment_id="role-separation", session_id="role-separation-session", profile_version="1",
        )
        self.assertEqual(assessment.routes.primary_routes[0].title, "Координатор лаборатории")
        target = next(route for route in assessment.routes.all_routes() if route.title == "Специалист по качеству")
        self.assertEqual(assessment.metadata["route_evaluations"][target.route_id]["kind"], "transition")
        self.assertNotIn("Специалист по качеству", assessment.identity.professional_core)

    def test_full_pool_is_evaluated_before_explicit_experiment_is_selected(self) -> None:
        assessment = build_deterministic_assessment(
            {"current_role": "Куратор фонда", "career_goal": "проверить частную практику"},
            {"confirmed_functions": ["описывает предметы", "готовит экспозиции", "проводит экскурсии"]},
            {"target_roles": ["Методист экспозиций", "Исследователь фонда"]},
            assessment_id="full-pool", session_id="full-pool-session", profile_version="1",
        )
        self.assertGreaterEqual(assessment.metadata["candidate_count_before_selection"], 4)
        self.assertEqual(len(assessment.routes.all_routes()), 4)
        self.assertEqual(sum(route.title.startswith("Самостоятельная практика:") for route in assessment.routes.all_routes()), 1)
        self.assertFalse(assessment.routes.primary_routes[0].title.startswith("Самостоятельная практика:"))

    def test_criteria_detect_conflicts_and_do_not_invent_market_or_income_fit(self) -> None:
        assessment = build_deterministic_assessment(
            {"minimum_income": "2400", "currency": "EUR", "care_constraints": "только дневной график"},
            {
                "confirmed_functions": ["проводит ночные дежурства", "оформляет журнал"],
                "functions_to_avoid": ["ночные дежурства"],
            },
            {}, assessment_id="criteria", session_id="criteria-session", profile_version="1",
        )
        self.assertTrue(all("ночные дежурства" not in route.title for route in assessment.routes.all_routes()))
        route = assessment.routes.primary_routes[0]
        criteria = assessment.metadata["route_evaluations"][route.route_id]["criteria"]
        self.assertEqual(criteria["confirmed_function_fit"], "conflict")
        self.assertEqual(criteria["life_constraints_fit"], "conflict")
        self.assertEqual(criteria["target_country_access"], "unknown_country")
        self.assertEqual(criteria["income_minimum_fit"], "salary_data_required")

    def test_constraint_points_to_its_own_evidence(self) -> None:
        constraint = "Можно работать только четыре часа подряд"
        assessment = build_deterministic_assessment(
            {"care_constraints": constraint},
            {"confirmed_functions": ["проверяет документы", "ведёт реестр"]},
            {}, assessment_id="constraint", session_id="constraint-session", profile_version="1",
        )
        evidence_by_id = {item.evidence_id: item.fact for item in assessment.evidence}
        self.assertEqual(len(assessment.constraints), 1)
        self.assertEqual(
            [evidence_by_id[item] for item in assessment.constraints[0].evidence_ids],
            [constraint],
        )

    def test_next_question_uses_first_unanswered_gap_without_repetition(self) -> None:
        assessment = build_deterministic_assessment(
            {},
            {
                "confirmed_functions": ["сверяет документы"],
                "answered_critical_questions": ["Какие функции и задачи вы выполняли?"],
            },
            {}, assessment_id="questions", session_id="questions-session", profile_version="1",
        )
        self.assertEqual(assessment.questions.answered_critical_questions, ["Какие функции и задачи вы выполняли?"])
        self.assertEqual(assessment.questions.unanswered_critical_questions, ["В какой стране вы планируете искать работу?"])

    def test_insufficient_data_uses_functional_directions_and_still_has_steps(self) -> None:
        assessment = build_deterministic_assessment(
            {}, {"confirmed_functions": ["систематизирует обращения"]}, {},
            assessment_id="insufficient", session_id="insufficient-session", profile_version="1",
        )
        self.assertEqual(assessment.metadata["fallback_mode"], "insufficient_data")
        self.assertEqual(len(assessment.routes.all_routes()), 1)
        self.assertTrue(all("систематизирует обращения" not in route.title for route in assessment.routes.all_routes()))
        self.assertEqual(len(assessment.first_steps), 3)
        self.assertEqual(len(assessment.questions.unanswered_critical_questions), 1)

    def test_unknown_fields_only_block_related_conclusions(self) -> None:
        assessment = build_deterministic_assessment(
            {}, {"confirmed_functions": ["анализирует заявки", "готовит заключения"]}, {},
            assessment_id="unknowns", session_id="unknowns-session", profile_version="1",
        )
        self.assertEqual(len(assessment.routes.all_routes()), 1)
        for route in assessment.routes.all_routes():
            criteria = assessment.metadata["route_evaluations"][route.route_id]["criteria"]
            self.assertEqual(criteria["target_country_access"], "unknown_country")
            self.assertEqual(criteria["language_fit"], "unknown_language")
            self.assertEqual(criteria["income_minimum_fit"], "unknown_income")
            self.assertIn("Юридическая доступность требует проверки", route.missing)

    def test_empty_profile_is_honest_and_does_not_block_document(self) -> None:
        assessment = build_deterministic_assessment(
            {}, {}, {}, assessment_id="empty", session_id="empty-session", profile_version="1",
        )
        self.assertEqual(assessment.identity.professional_core, ["Подтверждённые функции отсутствуют"])
        self.assertEqual(assessment.routes.primary_routes[0].title, "Проверка выполняемых функций")
        self.assertEqual(assessment.metadata["fallback_mode"], "insufficient_data")
        self.assertEqual(len(assessment.first_steps), 3)
        self.assertTrue(assessment.conclusions.main_conclusion)

    def test_technical_profile_preserves_license_and_physical_constraint(self) -> None:
        constraint = "Нельзя поднимать груз тяжелее десяти килограммов"
        assessment = build_deterministic_assessment(
            {"country_name": "Латвия", "currency": "EUR", "care_constraints": constraint},
            {"current_role": "Техник измерительного оборудования", "confirmed_functions": ["калибрует приборы", "ведёт журнал допусков"]},
            {"licenses": ["Допуск к электроустановкам"], "languages": ["латышский B1"]},
            assessment_id="technical", session_id="technical-session", profile_version="1",
        )
        text = str(assessment.to_dict())
        self.assertIn("Допуск к электроустановкам", assessment.identity.professional_capital)
        self.assertIn(constraint, text)
        self.assertNotIn("управление офисной командой", text.casefold())

    def test_answered_gaps_are_not_reasked_and_conclusion_is_always_built(self) -> None:
        answered = [
            "Какие функции и задачи вы выполняли?",
            "Какая страна и рынок вам нужны?",
            "Какой язык вы знаете?",
            "Есть ли право и документы на работу?",
            "Какой минимальный доход нужен?",
            "Какой масштаб смены профессии нужен?",
        ]
        assessment = build_deterministic_assessment(
            {}, {"confirmed_functions": ["проверяет записи"], "answered_critical_questions": answered}, {},
            assessment_id="question-limit", session_id="question-limit-session", profile_version="1",
        )
        self.assertEqual(assessment.questions.unanswered_critical_questions, [])
        self.assertTrue(assessment.conclusions.main_conclusion)
        self.assertEqual(len(assessment.first_steps), 3)


if __name__ == "__main__":
    unittest.main()
