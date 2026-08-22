import copy
import unittest

from services.career_guardrails import (
    validate_career_break_logic,
    validate_explicit_refusals,
    validate_function_evidence,
    validate_management_assumption,
    validate_regulated_professions,
    validate_seniority_transfer,
)
from services.evidence_profile import CareerEvidenceProfile, EvidenceItem, FunctionEvidence, LegalAccess, next_question_from_profile
from services.interview_policy import evaluate_report_readiness, get_route_specific_gaps, is_ready_for_conclusion


def _ev(text: str) -> EvidenceItem:
    return EvidenceItem(statement=text, source="user_story", confidence="confirmed")


def _base_report() -> dict:
    return {
        "career_decision": {
            "recommended_main_path": "-",
            "backup_path": "-",
            "why_this_path": "-",
            "why_not_other_paths": [],
            "avoid_for_now": "-",
            "decision_summary": "-",
        },
        "career_recommendations": [],
        "real_solutions": [],
    }


class ConversationalInterviewAcceptanceTests(unittest.TestCase):
    def test_no_questionnaire_when_core_facts_already_known(self) -> None:
        profile = CareerEvidenceProfile(
            explicit_goal=[_ev("Стабильный доход в ближайшие 2 месяца")],
            explicit_refusals=[_ev("Не хочу уходить в продажи")],
            work_history_facts=[_ev("7 лет опыта в административной координации")],
            functions=[
                FunctionEvidence(
                    function_name="Административная координация",
                    evidence=[_ev("Вел(а) процессы и документы")],
                    frequency="daily",
                    autonomy="performed_independently",
                )
            ],
            minimum_income=_ev("5000 PLN"),
            income_deadline=_ev("2-4 недели"),
            acceptable_transition_level=_ev("Да, временно ниже уровня"),
            location_and_language=[_ev("Польский A2, работаю в Польше")],
            legal_access=LegalAccess(profession_is_regulated=False, current_permission="n/a"),
            unresolved_gaps=[],
        )

        next_q = next_question_from_profile(profile, language="ru", user_mode="calm_steps")
        self.assertIsNotNone(next_q)
        self.assertTrue(bool(next_q.get("critical_gap")))
        self.assertIn(str(next_q.get("gap_key") or ""), {"personal_contribution", "autonomy", "responsibility_scale", "demonstrated_result"})

        with_one_gap = copy.deepcopy(profile)
        with_one_gap.legal_access = LegalAccess(profession_is_regulated=True, current_permission=None)
        one_gap_question = next_question_from_profile(with_one_gap, language="ru", user_mode="calm_steps")
        self.assertIsNotNone(one_gap_question)
        self.assertIn(str(one_gap_question.get("gap_key") or ""), {"regulated_profession_access", "legal_access"})

    def test_single_episode_not_promoted_to_professional_core(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[
                FunctionEvidence(
                    function_name="project manager",
                    evidence=[_ev("Один раз помог(ла) провести мероприятие")],
                    frequency="single_episode",
                )
            ]
        )

        report_pm = _base_report()
        report_pm["career_decision"]["recommended_main_path"] = "Project Manager"
        report_pm["real_solutions"] = [{"title": "Project Manager"}]
        errors_pm = validate_function_evidence(profile, report_pm)
        self.assertTrue(any(err.startswith("[CRITICAL]") for err in errors_pm))

        report_assistant = _base_report()
        report_assistant["career_decision"]["recommended_main_path"] = "Event Assistant (hypothesis)"
        report_assistant["real_solutions"] = [{"title": "Event Assistant (hypothesis)"}]
        errors_assistant = validate_function_evidence(profile, report_assistant)
        self.assertFalse(any(err.startswith("[CRITICAL]") for err in errors_assistant))

    def test_single_event_episode_is_blocked_through_role_synonym(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[
                FunctionEvidence(
                    function_name="организация мероприятия",
                    evidence=[_ev("Один раз помог(ла) провести мероприятие")],
                    frequency="single_episode",
                )
            ]
        )
        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "Event Project Coordinator"

        errors = validate_function_evidence(profile, report)

        self.assertTrue(any(err.startswith("[CRITICAL]") for err in errors))

    def test_different_seniority_per_function_is_preserved(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[
                FunctionEvidence(
                    function_name="Accounting",
                    evidence=[_ev("8 лет самостоятельного ведения бухгалтерии")],
                    frequency="daily",
                    autonomy="owned_full_process",
                    inferred_seniority="senior",
                    seniority_confidence="confirmed",
                ),
                FunctionEvidence(
                    function_name="ERP analysis",
                    evidence=[_ev("Участвовал(а) в поддержке ERP")],
                    frequency="periodic",
                    autonomy="assisted",
                    inferred_seniority="junior",
                    seniority_confidence="probable",
                ),
            ]
        )
        seniority_map = {f.function_name: f.inferred_seniority for f in profile.functions}
        self.assertEqual(seniority_map.get("Accounting"), "senior")
        self.assertIn(seniority_map.get("ERP analysis"), {"junior", "strong_junior", "middle", "probable", "junior"})

        route_gaps = get_route_specific_gaps("ERP Business Analyst", profile)
        gap_keys = {g.gap_key for g in route_gaps}
        self.assertIn("erp_requirements", gap_keys)
        self.assertIn("erp_testing", gap_keys)

    def test_migration_and_licensing_for_doctor(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[FunctionEvidence(function_name="doctor", evidence=[_ev("10 лет врачом")], inferred_seniority="senior")],
            legal_access=LegalAccess(profession_is_regulated=True, current_permission=None),
        )

        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "Самостоятельная медицинская практика"
        errors = validate_regulated_professions(profile, report)
        self.assertTrue(any(err.startswith("[CRITICAL]") for err in errors))

        route_gaps = get_route_specific_gaps("doctor return", profile)
        keys = {item.gap_key for item in route_gaps}
        self.assertIn("doctor_diploma_recognition_stage", keys)
        self.assertIn("doctor_allowed_activities", keys)

    def test_career_break_does_not_auto_restore_seniority(self) -> None:
        profile = CareerEvidenceProfile(
            work_history_facts=[_ev("Опыт HR 9 лет назад")],
            functions=[FunctionEvidence(function_name="HR specialist", evidence=[_ev("Подбор и адаптация")])],
            career_breaks=[_ev("Перерыв 9 лет")],
        )

        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "Senior HR Manager"
        errors = validate_career_break_logic(profile, report)
        self.assertTrue(any("career break" in err.lower() or "перерыв" in err.lower() for err in errors))

    def test_burnout_does_not_force_exit_from_it(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[FunctionEvidence(function_name="software engineering", evidence=[_ev("Senior разработчик")])],
            management_preference=_ev("без управления людьми"),
        )
        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "Engineering Manager"
        errors = validate_management_assumption(profile, report)
        self.assertTrue(any(err.startswith("[CRITICAL]") for err in errors))

        route_gaps = get_route_specific_gaps("senior developer route", profile)
        self.assertTrue(any(item.gap_key == "dev_oncall_tolerance" for item in route_gaps))

    def test_beginner_psychologist_requires_safety_checks(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[FunctionEvidence(function_name="psychology", evidence=[_ev("Есть диплом")])],
            legal_access=LegalAccess(profession_is_regulated=True, current_permission=None),
        )
        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "Clinical Psychologist"
        errors = validate_regulated_professions(profile, report)
        self.assertTrue(any(err.startswith("[CRITICAL]") for err in errors))

        route_gaps = get_route_specific_gaps("beginner psychologist", profile)
        keys = {item.gap_key for item in route_gaps}
        self.assertIn("psych_legal_status", keys)
        self.assertIn("psych_supervision", keys)
        self.assertIn("psych_referral", keys)

    def test_entrepreneur_not_auto_upgraded_to_ceo(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[
                FunctionEvidence(
                    function_name="предприниматель",
                    evidence=[_ev("12 лет небольшой розничный бизнес")],
                    frequency="daily",
                )
            ]
        )
        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "CEO of retail corporation"
        errors = validate_management_assumption(profile, report)
        self.assertTrue(any(err.startswith("[CRITICAL]") for err in errors))

    def test_entrepreneur_ceo_requires_executive_scale_evidence(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[
                FunctionEvidence(
                    function_name="business owner",
                    evidence=[_ev("Отвечал за P&L и корпоративную стратегию")],
                    frequency="daily",
                )
            ]
        )
        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "CEO"

        errors = validate_management_assumption(profile, report)

        self.assertFalse(any(err.startswith("[CRITICAL]") for err in errors))

    def test_direct_refusal_blocks_refused_routes(self) -> None:
        profile = CareerEvidenceProfile(
            explicit_refusals=[_ev("бухгалтер")]
        )
        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "Главный бухгалтер"
        report["career_recommendations"] = [
            {"title": "Аудитор"},
            {"title": "Налоговый консультант"},
        ]
        errors = validate_explicit_refusals(profile, report)
        self.assertTrue(any(err.startswith("[CRITICAL]") for err in errors))

    def test_broad_accounting_refusal_blocks_related_routes_and_english_synonyms(self) -> None:
        profile = CareerEvidenceProfile(
            explicit_refusals=[_ev("Не хочу больше работать в бухгалтерии вообще")]
        )
        for role in ("Auditor", "Налоговый консультант", "Accountant"):
            with self.subTest(role=role):
                report = _base_report()
                report["career_decision"]["recommended_main_path"] = role
                errors = validate_explicit_refusals(profile, report)
                self.assertTrue(any(err.startswith("[CRITICAL]") for err in errors))

    def test_narrow_accountant_refusal_does_not_block_auditor(self) -> None:
        profile = CareerEvidenceProfile(explicit_refusals=[_ev("Не хочу должность бухгалтера")])
        report = _base_report()
        report["career_decision"]["recommended_main_path"] = "Аудитор"

        errors = validate_explicit_refusals(profile, report)

        self.assertFalse(any(err.startswith("[CRITICAL]") for err in errors))

    def test_seniority_is_not_transferred_between_role_families(self) -> None:
        profile = CareerEvidenceProfile(
            functions=[
                FunctionEvidence(
                    function_name="Accounting",
                    evidence=[_ev("8 лет самостоятельно вел(а) бухгалтерию")],
                    frequency="daily",
                    inferred_seniority="senior",
                )
            ]
        )
        senior_report = _base_report()
        senior_report["career_decision"]["recommended_main_path"] = "Senior ERP Business Analyst"
        transition_report = _base_report()
        transition_report["career_decision"]["recommended_main_path"] = "ERP Business Analyst (transition)"

        senior_errors = validate_seniority_transfer(profile, senior_report)
        transition_errors = validate_seniority_transfer(profile, transition_report)

        self.assertTrue(any(err.startswith("[CRITICAL]") for err in senior_errors))
        self.assertFalse(any(err.startswith("[CRITICAL]") for err in transition_errors))

    def test_stop_when_enough_data_is_known(self) -> None:
        profile = CareerEvidenceProfile(
            explicit_goal=[_ev("Стабильный доход")],
            explicit_refusals=[_ev("Без бухгалтерии")],
            work_history_facts=[_ev("Профессиональное ядро подтверждено")],
            functions=[FunctionEvidence(function_name="Operations", evidence=[_ev("Регулярные функции")], frequency="daily")],
            minimum_income=_ev("5000 PLN"),
            income_deadline=_ev("1-3 месяца"),
            acceptable_transition_level=_ev("Да"),
            location_and_language=[_ev("Польский B1")],
            legal_access=LegalAccess(profession_is_regulated=False, current_permission="n/a"),
            unresolved_gaps=[],
        )
        readiness = evaluate_report_readiness(profile, route_hypotheses=[{"route": "Operations"}])
        self.assertIn(readiness.status, {"ready", "ready_with_uncertainty"})
        self.assertTrue(is_ready_for_conclusion(profile, user_mode="calm_steps"))


if __name__ == "__main__":
    unittest.main()
