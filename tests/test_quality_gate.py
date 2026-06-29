import json
import unittest
from pathlib import Path


REQUIRED_CHECKLIST_KEYS = {
    "facts_not_invented",
    "contradictions_detected",
    "route_explained",
    "first_step_realistic",
    "next_action_clear",
    "no_loop",
    "report_delivered_html_or_pdf",
}


class QualityGateCasesTests(unittest.TestCase):
    def test_quality_gate_has_exactly_20_mandatory_cases(self) -> None:
        path = Path("tests/quality_gate_cases.json")
        self.assertTrue(path.exists(), "Missing tests/quality_gate_cases.json")

        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 20)

        ids = [int(item.get("id", 0)) for item in rows if isinstance(item, dict)]
        self.assertEqual(sorted(ids), list(range(1, 21)))

    def test_each_case_has_required_checklist(self) -> None:
        rows = json.loads(Path("tests/quality_gate_cases.json").read_text(encoding="utf-8"))
        for item in rows:
            self.assertIsInstance(item, dict)
            self.assertTrue(str(item.get("name", "")).strip())
            self.assertTrue(str(item.get("profile", "")).strip())
            checklist = item.get("checklist")
            self.assertIsInstance(checklist, dict)
            self.assertEqual(set(checklist.keys()), REQUIRED_CHECKLIST_KEYS)
            for key in REQUIRED_CHECKLIST_KEYS:
                self.assertIsInstance(checklist[key], bool)


if __name__ == "__main__":
    unittest.main()
