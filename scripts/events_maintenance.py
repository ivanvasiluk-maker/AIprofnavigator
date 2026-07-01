from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.persistence import archive_and_prune_events, optimize_storage


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive and prune old analytics events in SQLite storage.",
    )
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=30,
        help="Keep events newer than this number of days in primary events table (default: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Max events to process per batch (default: 5000)",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Run ANALYZE/PRAGMA optimize/VACUUM after archival",
    )
    args = parser.parse_args()

    result = archive_and_prune_events(ttl_days=max(1, int(args.ttl_days)), batch_size=max(100, int(args.batch_size)))
    print("Events maintenance result:")
    print(f"- ttl_days: {result.get('ttl_days', 0)}")
    print(f"- moved_to_archive: {result.get('moved_to_archive', 0)}")
    print(f"- deleted_from_events: {result.get('deleted_from_events', 0)}")

    if args.vacuum:
        optimize_storage()
        print("- storage_optimized: yes")


if __name__ == "__main__":
    main()
