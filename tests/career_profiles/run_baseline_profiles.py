from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from openai_client import CareerOpenAIClient
from tests.career_profiles.evaluators.baseline_evaluator import BaselineCareerEvaluator
from tests.career_profiles.fixtures.baseline_runner import run_baseline_profiles
from tests.career_profiles.fixtures.generator_boundary import OpenAICareerGenerator


BASE_DIR = ROOT / "tests" / "career_profiles"


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated baseline career profiles")
    parser.add_argument("--run-id", default="", help="Immutable run identifier; if omitted, a new one is generated")
    parser.add_argument("--required-count", type=int, default=9, help="Expected number of input profiles")
    parser.add_argument("--inputs-dir", default=str(BASE_DIR / "inputs"), help="Directory with input profile JSON files")
    parser.add_argument("--expected-dir", default=str(BASE_DIR / "expected"), help="Directory with expected profile JSON files")
    parser.add_argument("--results-dir", default=str(BASE_DIR / "results"), help="Directory for generated and evaluation outputs")
    parser.add_argument("--baseline-lock", default=str(BASE_DIR / "baseline" / "baseline_lock.json"), help="Baseline lock manifest path")
    parser.add_argument(
        "--package-manifest",
        default=str(BASE_DIR / "package_manifest.json"),
        help="Path to test package manifest",
    )
    parser.add_argument(
        "--skip-package-integrity-check",
        action="store_true",
        help="Skip package integrity gate (infrastructure-only runs)",
    )
    parser.add_argument("--change-proposal", default="", help="Path to change proposal JSON")
    parser.add_argument(
        "--enforce-change-proposal-gate",
        action="store_true",
        help="Require accepted change proposal before running",
    )
    parser.add_argument(
        "--baseline-reference-dir",
        default="",
        help="Path to baseline profile_results dir or run dir for regression comparison",
    )
    parser.add_argument(
        "--enforce-regression-gate",
        action="store_true",
        help="Fail run if regression matrix detects regressions",
    )
    parser.add_argument("--application-version", default="manual", help="Application version label for reproducibility metadata")
    parser.add_argument("--git-commit", default="unknown", help="Git commit used for the run")
    parser.add_argument("--prompt-version", default="unknown", help="Prompt version hash or label")
    parser.add_argument("--environment", default="local", help="Execution environment label")
    args = parser.parse_args()

    from tests.career_profiles.fixtures.baseline_runner import generate_run_id

    client = CareerOpenAIClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        transcribe_model=settings.openai_transcribe_model,
    )
    generator = OpenAICareerGenerator(client)
    evaluator = BaselineCareerEvaluator()

    summary = await run_baseline_profiles(
        generator=generator,
        evaluator=evaluator,
        inputs_dir=Path(args.inputs_dir),
        expected_dir=Path(args.expected_dir),
        results_dir=Path(args.results_dir),
        baseline_lock_path=Path(args.baseline_lock),
        required_profile_count=args.required_count,
        run_id=args.run_id.strip() or generate_run_id(),
        application_version=str(args.application_version or "manual"),
        git_commit=str(args.git_commit or "unknown"),
        prompt_version=str(args.prompt_version or "unknown"),
        model=settings.openai_model,
        model_parameters={
            "temperature": 0.2,
            "response_format": "json_schema.strict",
            "transcribe_model": settings.openai_transcribe_model,
        },
        environment=str(args.environment or "local"),
        package_manifest_path=Path(args.package_manifest) if str(args.package_manifest or "").strip() else None,
        enforce_package_integrity=not bool(args.skip_package_integrity_check),
        change_proposal_path=Path(args.change_proposal) if str(args.change_proposal or "").strip() else None,
        enforce_change_proposal_gate=bool(args.enforce_change_proposal_gate),
        baseline_reference_dir=Path(args.baseline_reference_dir) if str(args.baseline_reference_dir or "").strip() else None,
        enforce_regression_gate=bool(args.enforce_regression_gate),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))