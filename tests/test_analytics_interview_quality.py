from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from utils.analytics import interview_quality_metrics, log_behavior_event_sync


class AnalyticsInterviewQualityTests(unittest.TestCase):
    def test_interview_quality_metrics_aggregates_core_kpis(self) -> None:
        base = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
        rows = [
            {
                "timestamp": (base + timedelta(seconds=0)).isoformat(),
                "public_user_id": "u1",
                "event": "story_evidence_extracted",
                "state": "WAITING_STORY",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {},
            },
            {
                "timestamp": (base + timedelta(seconds=20)).isoformat(),
                "public_user_id": "u1",
                "event": "clarifying_question_asked",
                "state": "INTERVIEW",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {"signature": "g1"},
            },
            {
                "timestamp": (base + timedelta(seconds=40)).isoformat(),
                "public_user_id": "u1",
                "event": "clarifying_question_asked",
                "state": "INTERVIEW",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {"signature": "g1"},
            },
            {
                "timestamp": (base + timedelta(seconds=60)).isoformat(),
                "public_user_id": "u1",
                "event": "preliminary_map_shown",
                "state": "INTERVIEW",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {},
            },
            {
                "timestamp": (base + timedelta(seconds=70)).isoformat(),
                "public_user_id": "u1",
                "event": "profile_correction_received",
                "state": "INTERVIEW",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {},
            },
            {
                "timestamp": (base + timedelta(seconds=80)).isoformat(),
                "public_user_id": "u1",
                "event": "interview_ready_with_uncertainty",
                "state": "INTERVIEW",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {},
            },
            {
                "timestamp": (base + timedelta(seconds=90)).isoformat(),
                "public_user_id": "u1",
                "event": "report_generated",
                "state": "FINAL_READY",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {},
            },
            {
                "timestamp": (base + timedelta(seconds=100)).isoformat(),
                "public_user_id": "u1",
                "event": "route_changed",
                "state": "WAITING_ROUTE_CHANGES",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {},
            },
            {
                "timestamp": (base + timedelta(seconds=110)).isoformat(),
                "public_user_id": "u1",
                "event": "report_guardrail_failed",
                "state": "GENERATING_REPORT",
                "action": "",
                "user_mode": "calm_steps",
                "language": "ru",
                "meta": {"critical_count": 1},
            },
        ]

        with patch("utils.analytics.get_recent_events_all", return_value=rows):
            metrics = interview_quality_metrics(lookback_days=30, sample_limit=10)

        self.assertEqual(metrics["sample_users"], 1)
        self.assertGreater(metrics["average_questions_before_preliminary_map"], 0)
        self.assertGreater(metrics["duplicate_question_rate"], 0)
        self.assertGreater(metrics["user_correction_rate"], 0)
        self.assertGreater(metrics["average_time_to_first_value"], 0)
        self.assertGreater(metrics["time_to_first_useful_hypothesis"], 0)
        self.assertEqual(metrics["anti_metrics"], ["number_of_fields_completed"])

    def test_log_behavior_event_sync_normalizes_aliases(self) -> None:
        with patch("utils.analytics._append_local_event") as append_local:
            with patch("utils.analytics._append_excel_event"):
                with patch("utils.analytics.record_event") as record_event:
                    with patch("utils.analytics._send_to_google_sheets", return_value=False):
                        with patch("utils.analytics.days_since_first_seen", return_value=0):
                            log_behavior_event_sync(
                                public_user_id="u2",
                                event="question_shown",
                                state_name="INTERVIEW",
                                user_mode="calm_steps",
                                language="ru",
                                meta={"question_id": 1, "decision_that_may_change": "main_route"},
                                session_id="s2",
                            )

        payload = append_local.call_args.args[0]
        self.assertEqual(payload.get("event"), "clarifying_question_asked")
        self.assertTrue(bool((payload.get("meta") or {}).get("question_has_decision_justification")))
        self.assertEqual(record_event.call_args.kwargs.get("event"), "clarifying_question_asked")


if __name__ == "__main__":
    unittest.main()
