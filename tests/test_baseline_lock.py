import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASELINE_LOCK_PATH = ROOT / "tests" / "career_profiles" / "baseline" / "baseline_lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class BaselineLockTests(unittest.TestCase):
    def test_baseline_lock_is_present_and_locked(self) -> None:
        self.assertTrue(BASELINE_LOCK_PATH.exists(), f"Missing baseline lock: {BASELINE_LOCK_PATH}")
        payload = json.loads(BASELINE_LOCK_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload.get("baseline_id"), "career_baseline_v1")
        self.assertEqual(payload.get("baseline_status"), "locked")
        self.assertFalse(bool(payload.get("production_logic_changes_allowed")))
        self.assertTrue(str(payload.get("git_commit") or "").strip())
        self.assertTrue(str(payload.get("prompt_version") or "").strip())
        self.assertTrue(str(payload.get("model") or "").strip())
        self.assertIsInstance(payload.get("patches_included"), list)
        self.assertTrue(bool(payload.get("patches_included")))
        self.assertIsInstance(payload.get("locked_files"), dict)
        self.assertTrue(bool(payload.get("locked_files")))

    def test_locked_file_hashes_match_current_workspace(self) -> None:
        payload = json.loads(BASELINE_LOCK_PATH.read_text(encoding="utf-8"))
        locked_files = payload.get("locked_files") or {}

        for rel_path, expected_hash in locked_files.items():
            file_path = ROOT / str(rel_path)
            self.assertTrue(file_path.exists(), f"Locked file is missing: {rel_path}")
            self.assertEqual(
                _sha256(file_path),
                str(expected_hash or "").strip().upper(),
                f"Baseline drift detected for {rel_path}",
            )


if __name__ == "__main__":
    unittest.main()