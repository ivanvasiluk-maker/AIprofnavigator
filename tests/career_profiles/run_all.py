from __future__ import annotations

import asyncio

from tests.career_profiles.run_baseline_profiles import _main


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
