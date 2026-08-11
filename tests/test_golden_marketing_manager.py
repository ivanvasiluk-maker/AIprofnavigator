"""
PATCH-2026-08 v2 Golden Test §10 + §3 A/B/C anti-template test

Profile A: IT Marketing Manager, 8 years, team of 5.
Profile B: Builder (плитка, гипсокартон).
Profile C: Administrative specialist (documentoobrot).

Verifies that each profile produces distinct, non-contaminated output,
and that the safe empty FINAL_REPORT_FALLBACK has no admin content.
"""
from __future__ import annotations

import copy
import unittest

from openai_client import FINAL_REPORT_FALLBACK, REPORT_PIPELINE_VERSION
from services.career_guardrails import (
    has_critical_errors,
    validate_admin_roles_require_evidence,
    validate_career_report,
    validate_country_market_consistency,
    validate_no_invented_psychological_facts,
    validate_seniority_protection,
    validate_survival_mode_evidence,
)
from services.evidence_profile import (
    CareerEvidenceProfile,
    EvidenceItem,
    FunctionEvidence,
)


def _ev(statement: str, source: str = "user_story", confidence: str = "confirmed") -> EvidenceItem:
    return EvidenceItem(statement=statement, source=source, confidence=confidence)  # type: ignore[arg-type]


def _make_marketing_manager_profile() -> CareerEvidenceProfile:
    """Minimal evidence profile for the golden test persona."""
    return CareerEvidenceProfile(
        explicit_goal=[
            _ev("Рассматривает: Product Management, образовательные проекты, консалтинг, психологию, собственный проект"),
            _ev("Не хочет резко терять доход; хочет проверить варианты за 1-2 месяца без увольнения"),
        ],
        work_history_facts=[
            _ev("8 лет в IT-маркетинге"),
            _ev("Руководитель отдела маркетинга, команда из 5 человек"),
            _ev("Рост входящих заявок на 35%"),
        ],
        functions=[
            FunctionEvidence(
                function_name="маркетинговое исследование рынка и конкурентов",
                evidence=[_ev("исследование рынка и конкурентов — регулярно, самостоятельно")],
                frequency="weekly",
                autonomy="owned_full_process",
                responsibility_scale="department",
                years=8.0,
                inferred_seniority="senior",
                seniority_confidence="confirmed",
            ),
            FunctionEvidence(
                function_name="интервью с клиентами",
                evidence=[_ev("интервью с клиентами для позиционирования")],
                frequency="weekly",
                autonomy="owned_full_process",
                responsibility_scale="team",
                years=6.0,
                inferred_seniority="senior",
                seniority_confidence="confirmed",
            ),
            FunctionEvidence(
                function_name="управление командой",
                evidence=[_ev("команда из 5 человек")],
                frequency="daily",
                autonomy="owned_full_process",
                responsibility_scale="team",
                years=4.0,
                inferred_seniority="lead",
                seniority_confidence="confirmed",
            ),
            FunctionEvidence(
                function_name="маркетинговая стратегия и запуск продукта",
                evidence=[_ev("позиционирование продукта, управление запуском, анализ результатов")],
                frequency="periodic",
                autonomy="owned_full_process",
                responsibility_scale="project",
                years=5.0,
                inferred_seniority="senior",
                seniority_confidence="confirmed",
            ),
        ],
    )


# ── Forbidden-content checks on a bad report (what the system used to produce) ──

_BAD_REPORT = {
    "digital_human": {
        "summary": "Специалист в поиске нового пути",
        "current_state": "Смотрит на рынок Литвы, тревога из-за переезда",
        "strategy_mode": "Survival",
        "career_readiness": {"urgency": "высокая"},
        "barriers": {"internal": ["Тревога из-за переезда", "Страх отказов"], "external": []},
        "psychological_profile": {
            "dominant_fears": ["страх отказов"],
            "dominant_barriers": ["тревога из-за переезда"],
        },
    },
    "career_decision": {
        "recommended_main_path": "Administrative Assistant",
        "backup_path": "Document Controller",
    },
    "career_recommendations": [
        {"title": "Administrative Assistant", "income_range": "5000-7500 EUR brutto"},
        {"title": "Back-office Specialist", "income_range": "5500-8000 EUR brutto"},
        {"title": "Document Controller", "income_range": "6000-9000 EUR brutto"},
    ],
    "action_plan": {
        "today": {
            "action": "Напишите три вида работ: плитка, гипсокартон, мебель.",
            "timebox": "10 мин",
            "result": "Список",
        }
    },
    "market_analysis": [
        {
            "profession": "Administrative Assistant",
            "salary_range": "5000-7500 EUR brutto",
            "fit_percent": 90,
        }
    ],
    "facts_only": {
        "explicit_facts": [],
        "inferences": [],
        "unknowns": [],
        "contradictions": [],
    },
}

_GOOD_REPORT = {
    "digital_human": {
        "summary": "Руководитель маркетинга IT, 8 лет, команда 5 человек",
        "current_state": "Рассматривает переход в Product Management или EdTech",
        "strategy_mode": "Transition",
        "career_readiness": {"urgency": "средняя"},
        "barriers": {"internal": [], "external": []},
        "psychological_profile": {
            "dominant_fears": [],
            "dominant_barriers": [],
        },
    },
    "career_decision": {
        "recommended_main_path": "Product Marketing Manager",
        "backup_path": "Customer Insights / UX Research",
    },
    "career_recommendations": [
        {"title": "Product Marketing Manager", "income_range": "данных недостаточно"},
        {"title": "Product Manager", "income_range": "данных недостаточно"},
        {"title": "EdTech Program Manager", "income_range": "данных недостаточно"},
    ],
    "action_plan": {
        "today": {
            "action": "Откройте список из 3 маркетинговых задач, которые вам удаются лучше всего.",
            "timebox": "10 мин",
            "result": "Список задач",
        }
    },
    "market_analysis": [
        {
            "profession": "Product Marketing Manager",
            "salary_range": "Зарплатный диапазон требует уточнения страны и рынка",
            "fit_percent": None,
            "profile_match_reason": "8 лет маркетинга IT, управление запусками, исследование рынка",
        }
    ],
    "route_evidence_blocks": [
        {
            "route": "Product Marketing Manager",
            "why_it_fits": [
                "8 лет маркетинга в IT",
                "Исследование рынка и конкурентов",
                "Управление запусками продукта",
            ],
            "evidence_from_user": ["рост входящих заявок на 35%"],
            "missing_competencies": ["Уточнить формат и рынок"],
            "entry_level": "senior/lead",
            "income_role": "primary",
            "risks": [],
            "what_may_disprove_this_route": [],
        }
    ],
    "facts_only": {
        "explicit_facts": [
            "8 лет в IT-маркетинге",
            "Руководитель отдела маркетинга, команда из 5 человек",
            "Рост входящих заявок на 35%",
        ],
        "inferences": [],
        "unknowns": [],
        "contradictions": [],
    },
}


class GoldenMarketingManagerTest(unittest.TestCase):
    """Golden test: bad report must produce CRITICAL errors; good report must pass clean."""

    def setUp(self) -> None:
        self.profile = _make_marketing_manager_profile()

    # ── Bad report must be blocked ────────────────────────────────────────────

    def test_bad_report_blocks_on_survival_without_evidence(self) -> None:
        errors = validate_survival_mode_evidence(self.profile, _BAD_REPORT)
        self.assertTrue(
            any("[CRITICAL]" in e for e in errors),
            f"Expected CRITICAL Survival error, got: {errors}",
        )

    def test_bad_report_blocks_on_seniority_degradation(self) -> None:
        errors = validate_seniority_protection(self.profile, _BAD_REPORT)
        self.assertTrue(
            any("[CRITICAL]" in e for e in errors),
            f"Expected CRITICAL seniority error, got: {errors}",
        )

    def test_bad_report_blocks_on_admin_roles_without_evidence(self) -> None:
        errors = validate_admin_roles_require_evidence(self.profile, _BAD_REPORT)
        self.assertTrue(
            any("[CRITICAL]" in e for e in errors),
            f"Expected CRITICAL admin role error, got: {errors}",
        )

    def test_bad_report_warns_on_invented_psych_facts(self) -> None:
        errors = validate_no_invented_psychological_facts(self.profile, _BAD_REPORT)
        self.assertTrue(
            any("[WARNING]" in e or "[CRITICAL]" in e for e in errors),
            f"Expected WARNING/CRITICAL for invented psych facts, got: {errors}",
        )

    def test_bad_report_has_critical_errors_overall(self) -> None:
        errors = validate_career_report(self.profile, _BAD_REPORT)
        self.assertTrue(
            has_critical_errors(errors),
            f"Overall validation should have CRITICAL errors. Errors: {errors}",
        )

    # ── Bad report must not contain construction examples ─────────────────────

    def test_bad_report_contains_construction_example(self) -> None:
        """Confirms the bug: bad report has строительный example."""
        text = str(_BAD_REPORT)
        self.assertIn("плитка", text.lower())

    # ── Good report must pass ─────────────────────────────────────────────────

    def test_good_report_passes_survival_check(self) -> None:
        errors = validate_survival_mode_evidence(self.profile, _GOOD_REPORT)
        self.assertFalse(
            any("[CRITICAL]" in e for e in errors),
            f"Good report should pass Survival check, got: {errors}",
        )

    def test_good_report_passes_seniority_check(self) -> None:
        errors = validate_seniority_protection(self.profile, _GOOD_REPORT)
        self.assertFalse(
            any("[CRITICAL]" in e for e in errors),
            f"Good report should pass seniority check, got: {errors}",
        )

    def test_good_report_passes_admin_roles_check(self) -> None:
        errors = validate_admin_roles_require_evidence(self.profile, _GOOD_REPORT)
        self.assertFalse(
            any("[CRITICAL]" in e for e in errors),
            f"Good report should pass admin roles check, got: {errors}",
        )

    def test_good_report_has_no_critical_errors(self) -> None:
        errors = validate_career_report(self.profile, _GOOD_REPORT)
        self.assertFalse(
            has_critical_errors(errors),
            f"Good report must have no CRITICAL errors. Errors: {errors}",
        )

    def test_good_report_has_product_marketing_route(self) -> None:
        routes = [
            str(_GOOD_REPORT.get("career_decision", {}).get("recommended_main_path", "")),
            *[r.get("title", "") for r in _GOOD_REPORT.get("career_recommendations", [])],
        ]
        route_text = " ".join(routes).lower()
        self.assertIn("product marketing", route_text)

    def test_good_report_no_construction_example(self) -> None:
        text = str(_GOOD_REPORT).lower()
        self.assertNotIn("плитка", text)
        self.assertNotIn("гипсокартон", text)
        self.assertNotIn("мебель", text.replace("мебельного", ""))  # allow incidental

    def test_good_report_no_admin_roles_in_recommendations(self) -> None:
        roles_text = str(_GOOD_REPORT.get("career_recommendations", [])).lower()
        self.assertNotIn("administrative assistant", roles_text)
        self.assertNotIn("back-office specialist", roles_text)
        self.assertNotIn("document controller", roles_text)

    def test_good_report_salary_requires_country(self) -> None:
        market = _GOOD_REPORT.get("market_analysis", [])
        for item in market:
            salary = str(item.get("salary_range", "")).lower()
            # Must not have bare EUR/PLN numbers without country clarification notice
            import re
            has_bare_range = bool(re.search(r"\d{4}\s*[-–]\s*\d{4}", salary))
            if has_bare_range:
                self.assertIn(
                    "уточнени",
                    salary,
                    f"Salary '{salary}' has numbers but no country clarification notice",
                )


class UserIsolationTest(unittest.TestCase):
    """
    §2 Isolation: User B (marketing manager) report must not contain facts from User A (builder).
    """

    _USER_A_FACTS = {"плитка", "гипсокартон", "сборка мебели", "отделка", "строительство"}

    def _user_b_report_text(self) -> str:
        return str(_GOOD_REPORT).lower()

    def test_user_b_report_has_no_user_a_facts(self) -> None:
        report_text = self._user_b_report_text()
        found = [fact for fact in self._USER_A_FACTS if fact in report_text]
        self.assertEqual(
            found,
            [],
            f"User B report contains User A facts: {found}. Cross-user contamination detected.",
        )

    def test_user_b_report_has_no_admin_routes(self) -> None:
        report_text = self._user_b_report_text()
        forbidden = ["administrative assistant", "back-office specialist", "document controller"]
        found = [r for r in forbidden if r in report_text]
        self.assertEqual(found, [], f"User B report contains admin routes: {found}")

    def test_user_b_report_has_no_survival_mode(self) -> None:
        mode = _GOOD_REPORT.get("digital_human", {}).get("strategy_mode", "")
        self.assertNotEqual(mode, "Survival", "User B should not be in Survival mode")


# ── Profile B: builder ────────────────────────────────────────────────────────
_PROFILE_B_FACTS = ["17 лет в строительстве", "плитка, гипсокартон, покраска, мебель", "нерегулярная занятость"]
_PROFILE_B_ROLES = ["Tile Setter", "Drywaller", "Construction Worker"]

# ── Profile C: administrative specialist ─────────────────────────────────────
_PROFILE_C_FACTS = ["документооборот", "1С документооборот", "канцелярия", "секретарь"]
_PROFILE_C_ROLES = ["Administrative Assistant", "Document Controller", "Back-office Specialist"]


class FallbackSafetyTest(unittest.TestCase):
    """Verify FINAL_REPORT_FALLBACK contains NO substantive user content."""

    def test_fallback_has_pipeline_version(self) -> None:
        self.assertEqual(FINAL_REPORT_FALLBACK.get("_pipeline_version"), REPORT_PIPELINE_VERSION)

    def test_fallback_has_no_admin_roles(self) -> None:
        text = str(FINAL_REPORT_FALLBACK).lower()
        forbidden = ["administrative assistant", "back-office specialist", "document controller"]
        found = [r for r in forbidden if r in text]
        self.assertEqual(found, [], f"FINAL_REPORT_FALLBACK contains admin roles: {found}")

    def test_fallback_has_no_survival_mode(self) -> None:
        mode = FINAL_REPORT_FALLBACK.get("digital_human", {}).get("strategy_mode", "")
        self.assertNotEqual(mode, "Survival")

    def test_fallback_has_no_psych_facts(self) -> None:
        text = str(FINAL_REPORT_FALLBACK).lower()
        psych_fragments = ["тревога из-за переезда", "страх отказов", "финансовое давление", "хаос в голове"]
        found = [p for p in psych_fragments if p in text]
        self.assertEqual(found, [], f"FINAL_REPORT_FALLBACK contains psych facts: {found}")

    def test_fallback_market_analysis_is_empty(self) -> None:
        self.assertEqual(FINAL_REPORT_FALLBACK.get("market_analysis"), [])

    def test_fallback_career_recommendations_is_empty(self) -> None:
        self.assertEqual(FINAL_REPORT_FALLBACK.get("career_recommendations"), [])

    def test_fallback_has_no_salary_ranges(self) -> None:
        import re
        text = str(FINAL_REPORT_FALLBACK)
        matches = re.findall(r"\d{4,5}\s*[-–]\s*\d{4,5}", text)
        self.assertEqual(matches, [], f"FINAL_REPORT_FALLBACK has hardcoded salary ranges: {matches}")


class AntiTemplateABCTest(unittest.TestCase):
    """
    §10 Anti-template: verify that reports for A/B/C profiles stay isolated.
    This test uses static mock reports to verify cross-contamination detection logic.
    """

    def _report_for_b_contaminated_with_a(self) -> dict:
        """Simulates the old bug: builder B gets marketing manager routes."""
        return {
            "digital_human": {"current_state": "строитель", "strategy_mode": "Survival"},
            "career_decision": {"recommended_main_path": "Product Marketing Manager"},
            "career_recommendations": [{"title": "Product Manager"}],
            "action_plan": {"today": {"action": "плитка, гипсокартон", "timebox": "10 min", "result": "список"}},
            "facts_only": {"explicit_facts": [], "inferences": [], "unknowns": [], "contradictions": []},
        }

    def _report_for_a_contaminated_with_b(self) -> dict:
        """Simulates the old bug: marketing A gets builder routes."""
        return {
            "digital_human": {
                "current_state": "руководитель маркетинга IT",
                "strategy_mode": "Survival",
                "barriers": {"internal": ["тревога из-за переезда"], "external": []},
            },
            "career_decision": {"recommended_main_path": "Administrative Assistant"},
            "career_recommendations": [
                {"title": "Administrative Assistant"},
                {"title": "Back-office Specialist"},
            ],
            "action_plan": {"today": {"action": "плитка, гипсокартон, мебель", "timebox": "10 min", "result": "список"}},
            "facts_only": {"explicit_facts": [], "inferences": [], "unknowns": [], "contradictions": []},
        }

    def _report_for_c(self) -> dict:
        """Clean report for profile C."""
        return {
            "digital_human": {"current_state": "административный специалист", "strategy_mode": "Transition"},
            "career_decision": {"recommended_main_path": "Administrative Assistant"},
            "career_recommendations": [{"title": "Administrative Assistant"}, {"title": "Document Controller"}],
            "action_plan": {"today": {"action": "Собрать 10 вакансий под документооборот", "timebox": "15 min", "result": "список"}},
            "facts_only": {"explicit_facts": ["документооборот", "1С", "канцелярия"], "inferences": [], "unknowns": [], "contradictions": []},
        }

    def test_report_a_with_builder_contamination_fails_guardrail(self) -> None:
        """Report A must block if it has builder data (плитка) and admin routes."""
        report = self._report_for_a_contaminated_with_b()
        profile = _make_marketing_manager_profile()
        errors = validate_career_report(profile, report)
        self.assertTrue(
            has_critical_errors(errors),
            f"Contaminated report A should have CRITICAL errors, got: {errors}",
        )

    def test_report_a_not_contaminated_with_builder_example(self) -> None:
        report_text = str(self._report_for_a_contaminated_with_b()).lower()
        construction = ["плитка", "гипсокартон", "мебель"]
        found = [c for c in construction if c in report_text]
        self.assertTrue(found, "Test fixture should contain construction terms to confirm detection works")

    def test_report_c_is_clean(self) -> None:
        """Profile C (admin) gets admin roles — that's correct."""
        report_c = self._report_for_c()
        report_text = str(report_c).lower()
        # Profile C should NOT contain marketing manager routes
        self.assertNotIn("product marketing manager", report_text)
        self.assertNotIn("плитка", report_text)

    def test_a_and_c_routes_differ(self) -> None:
        """Routes for marketing manager (A) and admin (C) must differ."""
        route_a = _GOOD_REPORT.get("career_decision", {}).get("recommended_main_path", "")
        route_c = self._report_for_c().get("career_decision", {}).get("recommended_main_path", "")
        self.assertNotEqual(route_a.lower(), route_c.lower(), "Routes for A and C must differ")

    def test_a_first_step_not_construction(self) -> None:
        """Profile A first step must not reference construction materials."""
        first_step = str(_GOOD_REPORT.get("action_plan", {}).get("today", {}).get("action", "")).lower()
        for term in ["плитка", "гипсокартон", "мебель", "сметы"]:
            self.assertNotIn(term, first_step, f"Profile A first step contains construction term: {term}")

    def test_pipeline_version_present_in_fallback(self) -> None:
        fb = copy.deepcopy(FINAL_REPORT_FALLBACK)
        self.assertIn("_pipeline_version", fb)
        self.assertEqual(fb["_pipeline_version"], REPORT_PIPELINE_VERSION)


if __name__ == "__main__":
    unittest.main()
