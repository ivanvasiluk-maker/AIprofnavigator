"""
PATCH-37: Country-aware questionnaire tests.

Verifies:
- _resolve_country_config returns correct config for LT/PL/DE
- _income_options_for_currency returns EUR for LT, PLN for PL, EUR for DE
- _language_options_for_country returns Lithuanian for LT, Polish for PL, German for DE
- _route_context_question returns country-aware options after Q1 answer
- _report_draft_is_empty correctly detects empty/placeholder reports
"""
from __future__ import annotations

import unittest
from pathlib import Path

from services.evidence_profile import CareerEvidenceProfile, EvidenceItem, FunctionEvidence
from services.interview_policy import evaluate_report_readiness

from handlers.career import (
    _build_profile_snapshot,
    _income_options_for_currency,
    _is_route_context_stale_input,
    _language_options_for_country,
    _normalize_route_context,
    _report_draft_is_empty,
    _resolve_country_config,
    _route_context_answer_is_valid,
    _route_context_question,
    _snapshot_is_ready_for_report,
)


class CountryConfigResolutionTest(unittest.TestCase):
    def test_lt_by_name(self) -> None:
        cfg = _resolve_country_config("Литва")
        self.assertEqual(cfg["country_code"], "LT")
        self.assertEqual(cfg["currency"], "EUR")
        self.assertEqual(cfg["local_language"], "Литовский")
        self.assertEqual(cfg["market_locale"], "lt-LT")

    def test_lt_by_city(self) -> None:
        cfg = _resolve_country_config("Вильнюс")
        self.assertEqual(cfg["country_code"], "LT")

    def test_pl_by_name(self) -> None:
        cfg = _resolve_country_config("Польша")
        self.assertEqual(cfg["country_code"], "PL")
        self.assertEqual(cfg["currency"], "PLN")
        self.assertEqual(cfg["local_language"], "Польский")

    def test_pl_by_city(self) -> None:
        cfg = _resolve_country_config("Варшава")
        self.assertEqual(cfg["country_code"], "PL")

    def test_de_by_name(self) -> None:
        cfg = _resolve_country_config("Германия")
        self.assertEqual(cfg["country_code"], "DE")
        self.assertEqual(cfg["currency"], "EUR")
        self.assertEqual(cfg["local_language"], "Немецкий")

    def test_de_by_city(self) -> None:
        cfg = _resolve_country_config("Берлин")
        self.assertEqual(cfg["country_code"], "DE")

    def test_remote(self) -> None:
        cfg = _resolve_country_config("Удалённо")
        self.assertEqual(cfg["country_code"], "REMOTE")

    def test_unknown_returns_eur(self) -> None:
        cfg = _resolve_country_config("Нарния")
        self.assertEqual(cfg["currency"], "EUR")
        self.assertEqual(cfg["country_code"], "UNKNOWN")


class CurrencyOptionsTest(unittest.TestCase):
    def test_lt_uses_eur(self) -> None:
        min_opts, desired_opts, budget_opts = _income_options_for_currency("EUR")
        self.assertTrue(all("EUR" in o for o in min_opts))
        self.assertTrue(all("EUR" in o for o in desired_opts))
        self.assertTrue(all("EUR" in o for o in budget_opts))
        self.assertFalse(any("PLN" in o for o in min_opts))

    def test_pl_uses_pln(self) -> None:
        min_opts, desired_opts, budget_opts = _income_options_for_currency("PLN")
        self.assertTrue(all("PLN" in o for o in min_opts))
        self.assertFalse(any("EUR" in o for o in min_opts))

    def test_de_uses_eur(self) -> None:
        min_opts, _, _ = _income_options_for_currency("EUR")
        self.assertTrue(any("EUR" in o for o in min_opts))

    def test_gb_uses_gbp(self) -> None:
        min_opts, _, _ = _income_options_for_currency("GBP")
        self.assertTrue(all("GBP" in o for o in min_opts))


class LanguageOptionsTest(unittest.TestCase):
    def test_lt_shows_lithuanian(self) -> None:
        current, target = _language_options_for_country("LT")
        self.assertTrue(any("Литовский" in o for o in current))
        self.assertFalse(any("Польский" in o for o in current))

    def test_pl_shows_polish(self) -> None:
        current, target = _language_options_for_country("PL")
        self.assertTrue(any("Польский" in o for o in current))
        self.assertFalse(any("Литовский" in o for o in current))

    def test_de_shows_german(self) -> None:
        current, target = _language_options_for_country("DE")
        self.assertTrue(any("Немецкий" in o for o in current))

    def test_gb_shows_english(self) -> None:
        current, target = _language_options_for_country("GB")
        self.assertTrue(any("Английский" in o for o in current))

    def test_unknown_shows_local_placeholder(self) -> None:
        current, _ = _language_options_for_country("UNKNOWN")
        self.assertTrue(any("Местный язык" in o or "язык" in o.lower() for o in current))


class DynamicQuestionOptionsTest(unittest.TestCase):
    """After country=LT, income/language questions must use EUR/Lithuanian."""

    def _make_lt_context(self) -> dict:
        return {
            "country": "Литва",
            "country_config": {
                "country_code": "LT",
                "currency": "EUR",
                "local_language": "Литовский",
                "market_locale": "lt-LT",
            },
        }

    def _make_pl_context(self) -> dict:
        return {
            "country": "Польша",
            "country_config": {
                "country_code": "PL",
                "currency": "PLN",
                "local_language": "Польский",
                "market_locale": "pl-PL",
            },
        }

    def _find_question_index(self, q_id: str) -> int:
        from handlers.career import _ROUTE_CONTEXT_FIELDS
        for i, q in enumerate(_ROUTE_CONTEXT_FIELDS):
            if q.get("id") == q_id:
                return i
        raise ValueError(f"Question id {q_id!r} not found")

    def test_lt_income_question_uses_eur(self) -> None:
        idx = self._find_question_index("minimum_monthly_income")
        q = _route_context_question(idx, self._make_lt_context())
        options = q.get("options", [])
        self.assertTrue(any("EUR" in o for o in options), f"Expected EUR options, got: {options}")
        self.assertFalse(any("PLN" in o for o in options), f"Unexpected PLN in options: {options}")

    def test_pl_income_question_uses_pln(self) -> None:
        idx = self._find_question_index("minimum_monthly_income")
        q = _route_context_question(idx, self._make_pl_context())
        options = q.get("options", [])
        self.assertTrue(any("PLN" in o for o in options))

    def test_lt_language_question_uses_lithuanian(self) -> None:
        idx = self._find_question_index("current_language_level")
        q = _route_context_question(idx, self._make_lt_context())
        options = q.get("options", [])
        self.assertTrue(any("Литовский" in o for o in options), f"Expected Lithuanian, got: {options}")
        self.assertFalse(any("Польский" in o for o in options))

    def test_pl_language_question_uses_polish(self) -> None:
        idx = self._find_question_index("current_language_level")
        q = _route_context_question(idx, self._make_pl_context())
        options = q.get("options", [])
        self.assertTrue(any("Польский" in o for o in options))

    def test_lt_training_budget_uses_eur(self) -> None:
        idx = self._find_question_index("training_budget")
        q = _route_context_question(idx, self._make_lt_context())
        options = q.get("options", [])
        self.assertTrue(any("EUR" in o for o in options))

    def test_no_context_returns_default_polish(self) -> None:
        idx = self._find_question_index("current_language_level")
        q = _route_context_question(idx)
        options = q.get("options", [])
        self.assertTrue(any("Польский" in o for o in options))


class SnapshotReadinessGateTest(unittest.TestCase):
    def test_snapshot_has_country_and_route_context(self) -> None:
        snapshot = _build_profile_snapshot(
            {
                "country_config": {"country_code": "LT", "currency": "EUR", "local_language": "Литовский"},
                "route_context": {
                    "country": "Литва",
                    "city": "Вильнюс",
                    "current_language_level": "A2",
                    "target_language": "B1",
                    "income_urgency": "1-2 месяца",
                    "minimum_monthly_income": "1000 EUR/мес",
                    "desired_monthly_income": "2000 EUR/мес",
                    "training_budget": "200 EUR",
                    "available_time_for_study": "6 часов/неделю",
                    "career_goal_type": "Полностью сменить сферу",
                    "work_preferences": "Лучше без активных продаж",
                    "health_or_schedule_limits": "Есть ограничения по графику",
                    "documents_and_work_rights": "Право на работу нужно уточнить",
                    "diploma_status": "Диплом подтверждён",
                    "portfolio_or_references": "Есть портфолио",
                },
                "selected_psych_markers": ["страх неуспеха", "переделать себя"],
                "selected_barriers": ["без активных продаж"],
                "selected_fears": ["потеря дохода"],
                "answers_text": "Пользователь готов менять направление",
                "story_text": "Есть опыт в маркетинге",
            }
        )
        self.assertEqual(snapshot["country_code"], "LT")
        self.assertEqual(snapshot["currency"], "EUR")
        self.assertEqual(snapshot["city"], "Вильнюс")
        self.assertEqual(snapshot["income_urgency"], "1-2 месяца")
        self.assertEqual(snapshot["minimum_income"], "1000 EUR/мес")
        self.assertEqual(snapshot["target_income"], "2000 EUR/мес")
        self.assertEqual(snapshot["career_goal"], "Полностью сменить сферу")
        self.assertIn("без активных продаж", snapshot["work_preferences"])
        self.assertTrue(snapshot["ready_for_report"])
        self.assertIn("route_context", snapshot)

    def test_snapshot_keeps_non_empty_values_only(self) -> None:
        snapshot = _build_profile_snapshot(
            {
                "route_context": {
                    "country": "Литва",
                    "city": "Вильнюс",
                    "income_urgency": "1-2 месяца",
                    "minimum_monthly_income": "1500 EUR/мес",
                    "desired_monthly_income": "2200 EUR/мес",
                    "training_budget": "300 EUR",
                    "available_time_for_study": "10+ часов",
                    "career_goal_type": "Полностью сменить сферу",
                    "work_preferences": "Лучше без активных продаж",
                    "health_or_schedule_limits": "Есть ограничения по графику",
                    "documents_and_work_rights": "Право на работу нужно уточнить",
                    "diploma_status": "Диплом подтверждён",
                    "portfolio_or_references": "Есть портфолио",
                    "country_config": {"country_code": "LT", "currency": "EUR"},
                },
                "selected_psych_markers": ["страх неуспеха"],
                "selected_barriers": ["без активных продаж"],
                "selected_fears": [],
            }
        )
        self.assertEqual(snapshot["country_code"], "LT")
        self.assertEqual(snapshot["currency"], "EUR")
        self.assertNotIn("-", str(snapshot.get("minimum_income", "")))
        self.assertNotIn("None", str(snapshot.get("work_preferences", "")))
        self.assertIsInstance(snapshot.get("psychological_barriers", []), list)
        self.assertTrue(len(snapshot.get("psychological_barriers", [])) >= 1)

    def test_incomplete_snapshot_is_not_ready(self) -> None:
        snapshot = _build_profile_snapshot({"route_context": {"country": "Литва"}})
        self.assertFalse(_snapshot_is_ready_for_report(snapshot))

    def test_internal_gap_ledger_is_not_rendered(self) -> None:
        source = Path("handlers/career.py").read_text(encoding="utf-8")
        self.assertNotIn("Для более точного заключения пока не хватает данных:", source)
        self.assertNotIn("Я не буду блокировать результат", source)

    def test_readiness_levels_distinguish_preliminary_and_full(self) -> None:
        profile = CareerEvidenceProfile(
            work_history_facts=[EvidenceItem(statement="8 лет в IT-маркетинге", source="user_story", confidence="confirmed")],
            functions=[FunctionEvidence(function_name="исследования рынка", evidence=[EvidenceItem(statement="исследования рынка", source="user_story", confidence="confirmed")])],
        )
        readiness = evaluate_report_readiness(profile)
        self.assertEqual(readiness.readiness_level, "PRELIMINARY_REPORT_READY")

class RouteContextStaleInputTest(unittest.TestCase):
    def test_stale_text_is_rejected(self) -> None:
        self.assertTrue(_is_route_context_stale_input("✍️ Написать историю"))
        self.assertTrue(_is_route_context_stale_input("📄 Загрузить резюме"))
        self.assertTrue(_is_route_context_stale_input("➡️ Продолжить без резюме"))
        self.assertTrue(_is_route_context_stale_input("✅ Отметил(а), что мешает"))
        self.assertFalse(_is_route_context_stale_input("Литва"))


class RouteContextNormalizationTest(unittest.TestCase):
    def test_partial_country_payload_is_normalized_before_report_gate(self) -> None:
        route_context = {
            "country": "Литва",
            "city": "Вильнюс",
            "goal": "Product marketing",
            "work": "Remote",
            "documents": "Есть право на работу",
            "proof": "Есть портфолио",
        }
        normalized = _normalize_route_context(route_context)
        self.assertEqual(normalized["career_goal_type"], "Product marketing")
        self.assertEqual(normalized["work_preferences"], "Remote")
        self.assertEqual(normalized["documents_and_work_rights"], "Есть право на работу")
        self.assertEqual(normalized["portfolio_or_references"], "Есть портфолио")
        self.assertEqual(normalized["country_config"]["country_code"], "LT")

    def test_country_language_answers_allow_multiple_values(self) -> None:
        current_idx = next(i for i, q in enumerate(__import__("handlers.career", fromlist=["_ROUTE_CONTEXT_FIELDS"])._ROUTE_CONTEXT_FIELDS) if q.get("id") == "current_language_level")
        current_q = _route_context_question(current_idx, {"country": "Литва", "country_config": {"country_code": "LT", "currency": "EUR"}})
        self.assertTrue(_route_context_answer_is_valid("Литовский: B1+, Английский: B1 и выше", current_q.get("options", []), "current_language_level"))

        health_idx = next(i for i, q in enumerate(__import__("handlers.career", fromlist=["_ROUTE_CONTEXT_FIELDS"])._ROUTE_CONTEXT_FIELDS) if q.get("id") == "health_or_schedule_limits")
        health_q = _route_context_question(health_idx, {"country": "Литва", "country_config": {"country_code": "LT", "currency": "EUR"}})
        self.assertTrue(_route_context_answer_is_valid("Есть ограничения по графику, Есть ограничения по здоровью", health_q.get("options", []), "health_or_schedule_limits"))


class ReportDraftGateTest(unittest.TestCase):
    def test_empty_dict_is_empty(self) -> None:
        self.assertTrue(_report_draft_is_empty({}))

    def test_placeholder_main_path_is_empty(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Возможный маршрут"},
            "market_analysis": [{"profession": "Something"}],
            "action_plan": {"today": {"action": "Do something"}},
        }
        self.assertTrue(_report_draft_is_empty(report))

    def test_dash_main_path_is_empty(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "-"},
            "market_analysis": [{"profession": "Something"}],
            "action_plan": {"today": {"action": "Do something"}},
        }
        self.assertTrue(_report_draft_is_empty(report))

    def test_no_market_analysis_is_empty(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Product Marketing Manager"},
            "market_analysis": [],
            "career_recommendations": [],
            "action_plan": {"today": {"action": "Find 10 vacancies"}},
        }
        self.assertTrue(_report_draft_is_empty(report))

    def test_good_report_is_not_empty(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Product Marketing Manager"},
            "market_analysis": [{"profession": "Product Marketing Manager"}],
            "action_plan": {"today": {"action": "Find 10 vacancies in product marketing"}},
        }
        self.assertFalse(_report_draft_is_empty(report))

    def test_predvaritelno_gipoteza_is_empty(self) -> None:
        report = {
            "career_decision": {"recommended_main_path": "Предварительная гипотеза"},
            "market_analysis": [{"profession": "Something"}],
            "action_plan": {"today": {"action": "Do something"}},
        }
        self.assertTrue(_report_draft_is_empty(report))


if __name__ == "__main__":
    unittest.main()
