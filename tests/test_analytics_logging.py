import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils import analytics


class AnalyticsLoggingTests(unittest.TestCase):
    def test_log_behavior_event_writes_excel_csv_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            events_path = Path(tmp_dir) / "events.jsonl"
            excel_path = Path(tmp_dir) / "events.csv"

            old_events = analytics.settings.analytics_events_log_path
            old_excel = analytics.settings.analytics_excel_log_path
            try:
                analytics.settings.analytics_events_log_path = str(events_path)
                analytics.settings.analytics_excel_log_path = str(excel_path)

                with patch("utils.analytics.record_event"):
                    with patch("utils.analytics._send_to_google_sheets", return_value=False):
                        analytics.log_behavior_event_sync(
                            public_user_id="20260704-0001",
                            event="report_profile_snapshot",
                            state_name="final_ready",
                            action="",
                            user_mode="fast",
                            language="ru",
                            meta={"resource_level": "medium", "integration_level": "low"},
                            session_id="session-1",
                        )

                self.assertTrue(excel_path.exists())
                with excel_path.open("r", encoding="utf-8", newline="") as fh:
                    rows = list(csv.DictReader(fh))

                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].get("event"), "report_profile_snapshot")
                self.assertEqual(rows[0].get("public_user_id"), "20260704-0001")
                self.assertEqual(rows[0].get("session_id"), "session-1")
                self.assertEqual(rows[0].get("sheets_delivery"), "failed_or_disabled")
            finally:
                analytics.settings.analytics_events_log_path = old_events
                analytics.settings.analytics_excel_log_path = old_excel


if __name__ == "__main__":
    unittest.main()
