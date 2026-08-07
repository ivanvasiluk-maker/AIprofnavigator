from __future__ import annotations

import unittest

from tests.career_profiles.evaluators.baseline_evaluator import BaselineCareerEvaluator


class ExplainableEvaluatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_forbidden_route_in_temporary_bridge_is_not_primary_violation(self) -> None:
        evaluator = BaselineCareerEvaluator()
        generated_result = {
            "career_decision": {"recommended_main_path": "Operations Specialist", "backup_path": "Customer Support"},
            "route_evidence_blocks": [
                {
                    "route": "Operations Specialist",
                    "income_role": "primary",
                    "why_it_fits": ["операционный опыт"],
                    "evidence_from_user": ["операционный опыт"],
                    "missing_competencies": ["польский"],
                    "entry_level": "transition",
                    "risks": ["конкуренция"],
                    "what_may_disprove_this_route": ["изменение ограничений"],
                },
                {
                    "route": "Бухгалтер",
                    "income_role": "quick",
                    "why_it_fits": ["временный денежный мост"],
                    "evidence_from_user": ["нужен быстрый доход"],
                    "missing_competencies": [],
                    "entry_level": "entry",
                    "risks": ["не как основной путь"],
                    "what_may_disprove_this_route": ["если спадет финансовый стресс"],
                },
            ],
            "facts_only": {
                "explicit_facts": ["операционный опыт"],
                "resume_facts": [],
                "inferences": [],
                "unknowns": ["точный уровень языка"],
                "contradictions": [],
            },
            "career_recommendations": [{"title": "Operations Specialist"}],
        }
        expected_profile = {
            "profile_id": "p1",
            "direct_refusals": ["Бухгалтер"],
            "forbidden_recommendations": ["Бухгалтер"],
            "route_expectations": {"main_route": "Operations Specialist", "quick_route": "Бухгалтер"},
            "professional_core": ["операционный опыт"],
            "evidence_fragments": ["операционный опыт"],
        }

        result = await evaluator.evaluate({"profile_id": "p1"}, generated_result, expected_profile)
        forbidden_result = result["score_breakdown"]["forbidden_recommendations"]
        self.assertGreaterEqual(forbidden_result["score"], 8)
        self.assertFalse(result["critical_error_detected"])

    async def test_primary_forbidden_route_triggers_critical_failure(self) -> None:
        evaluator = BaselineCareerEvaluator()
        generated_result = {
            "career_decision": {"recommended_main_path": "Бухгалтер"},
            "route_evidence_blocks": [
                {
                    "route": "Бухгалтер",
                    "income_role": "primary",
                    "why_it_fits": ["старый путь"],
                    "evidence_from_user": ["прошлый опыт"],
                    "missing_competencies": [],
                    "entry_level": "mid",
                    "risks": ["отказ пользователя"],
                    "what_may_disprove_this_route": ["прямой отказ"],
                }
            ],
            "facts_only": {
                "explicit_facts": ["прошлый опыт"],
                "resume_facts": [],
                "inferences": [],
                "unknowns": ["альтернативный маршрут"],
                "contradictions": [],
            },
            "career_recommendations": [{"title": "Бухгалтер"}],
        }
        expected_profile = {
            "profile_id": "p2",
            "direct_refusals": ["Бухгалтер"],
            "forbidden_recommendations": ["Бухгалтер"],
            "route_expectations": {"main_route": "Operations Specialist"},
            "professional_core": ["операционный опыт"],
        }

        result = await evaluator.evaluate({"profile_id": "p2"}, generated_result, expected_profile)
        self.assertTrue(result["critical_error_detected"])
        self.assertEqual(result["evaluation_status"], "failed")
        self.assertIn("FORBIDDEN_ROLE_RECOMMENDED", result["reason_codes"])