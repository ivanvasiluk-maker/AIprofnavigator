from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from pydantic import BaseModel

from tests.career_profiles.evaluators.protocols import CareerEvaluatorProtocol, CareerGeneratorProtocol
from tests.career_profiles.fixtures.career_analysis_adapter import (
    CareerAnalysisAdapter,
    CareerTestInput,
    RunContext,
)
from tests.career_profiles.fixtures.change_governance import load_change_proposal, validate_change_proposal
from tests.career_profiles.fixtures.generator_boundary import assert_no_generator_leakage
from tests.career_profiles.fixtures.regression_matrix import (
    build_regression_matrix,
    evaluate_regression_acceptance,
    load_profile_payloads,
)
from tests.career_profiles.validate_package import PACKAGE_COMPLETE, validate_test_package


@dataclass(slots=True)
class BaselineProfileCase:
    profile_id: str
    input_path: Path
    expected_path: Path


class CareerTestRunMetadata(BaseModel):
    model_config = {"protected_namespaces": ()}

    run_id: str
    baseline_id: str | None
    application_version: str
    git_commit: str
    prompt_version: str
    model: str
    model_parameters: dict[str, Any]
    test_package_version: str
    input_manifest_hash: str
    expected_manifest_hash: str
    started_at: datetime
    completed_at: datetime | None
    environment: str


def load_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def discover_profile_cases(inputs_dir: Path, expected_dir: Path) -> list[BaselineProfileCase]:
    input_files = sorted(path for path in inputs_dir.glob("*.json") if path.is_file())
    cases: list[BaselineProfileCase] = []
    for input_path in input_files:
        profile_id = input_path.stem
        expected_path = expected_dir / f"{profile_id}.json"
        if not expected_path.exists():
            raise FileNotFoundError(f"Missing expected profile for {profile_id}: {expected_path}")
        cases.append(BaselineProfileCase(profile_id=profile_id, input_path=input_path, expected_path=expected_path))
    return cases


def build_runtime_context(input_profile: dict[str, Any]) -> dict[str, Any]:
    runtime_context = {
        "decision_layers": dict(input_profile.get("decision_layers") or {}),
        "selected_barriers": list(input_profile.get("selected_barriers") or []),
        "selected_fears": list(input_profile.get("selected_fears") or []),
        "selected_psych_markers": list(input_profile.get("selected_psych_markers") or []),
        "selected_energy_sources": list(input_profile.get("selected_energy_sources") or []),
        "selected_career_priorities": list(input_profile.get("selected_career_priorities") or []),
        "user_segment": str(input_profile.get("user_segment") or ""),
        "user_segment_label": str(input_profile.get("user_segment_label") or ""),
        "language": str(input_profile.get("language") or "ru"),
    }
    assert_no_generator_leakage(runtime_context, "runtime_context")
    return runtime_context


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def generate_run_id(*, prefix: str = "career-test-run") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _manifest_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name.lower()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest().upper()


def _comparison_flags(
    *,
    baseline_lock: dict[str, Any],
    input_manifest_hash: str,
    expected_manifest_hash: str,
    model: str,
    model_parameters: dict[str, Any],
) -> dict[str, Any]:
    changed_code = str(baseline_lock.get("git_commit") or "").strip() == "" or bool(baseline_lock.get("git_worktree_dirty"))
    changed_prompt = str(baseline_lock.get("prompt_version") or "").strip() == ""
    changed_model = str(baseline_lock.get("model") or "").strip() != str(model or "").strip()
    changed_parameters = (baseline_lock.get("model_parameters") or {}) != model_parameters
    changed_test_data = bool(input_manifest_hash) or bool(expected_manifest_hash)
    reliability = "full"
    if changed_code or changed_prompt or changed_model or changed_parameters or changed_test_data:
        reliability = "limited"
    return {
        "baseline_id": baseline_lock.get("baseline_id"),
        "changed_code": changed_code,
        "changed_prompt": changed_prompt,
        "changed_model": changed_model,
        "changed_parameters": changed_parameters,
        "changed_test_data": changed_test_data,
        "comparison_reliability": reliability,
    }


def _is_technical_retryable(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    text = str(exc or "").strip().lower()
    retryable_markers = [
        "timeout",
        "timed out",
        "rate limit",
        "429",
        "network",
        "transport",
        "connection reset",
        "temporarily unavailable",
    ]
    return any(marker in text for marker in retryable_markers)


async def _generate_with_retry(
    *,
    generator: CareerGeneratorProtocol,
    input_profile: dict[str, Any],
    runtime_context: dict[str, Any],
    max_attempts: int = 3,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    retry_log: list[dict[str, Any]] = []
    attempt = 1
    while True:
        try:
            generated = await generator.generate(input_profile, runtime_context)
            if retry_log:
                retry_log.append({"attempt": attempt, "result": "success"})
            return generated, retry_log
        except Exception as exc:
            retryable = _is_technical_retryable(exc)
            retry_log.append(
                {
                    "attempt": attempt,
                    "result": "error",
                    "retryable": retryable,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            if not retryable or attempt >= max_attempts:
                raise
            attempt += 1


async def _run_profile_with_retry(
    *,
    adapter: CareerAnalysisAdapter,
    profile: CareerTestInput,
    run_context: RunContext,
    max_attempts: int = 3,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    retry_log: list[dict[str, Any]] = []
    attempt = 1
    while True:
        try:
            run_result = await adapter.run_profile(profile, run_context)
            if retry_log:
                retry_log.append({"attempt": attempt, "result": "success"})
            return run_result.generated_result, run_result.conversation_trace, retry_log
        except Exception as exc:
            retryable = _is_technical_retryable(exc)
            retry_log.append(
                {
                    "attempt": attempt,
                    "result": "error",
                    "retryable": retryable,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            if not retryable or attempt >= max_attempts:
                raise
            attempt += 1


def _summarize_systemic_errors(profile_payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, set[str]] = {}
    for payload in profile_payloads:
        profile_id = str(payload.get("profile_id") or "").strip()
        evaluation_result = payload.get("evaluation_result") if isinstance(payload.get("evaluation_result"), dict) else {}
        for finding in evaluation_result.get("critical_findings") or []:
            if not isinstance(finding, dict):
                continue
            error_code = str(finding.get("error_code") or "").strip()
            if not error_code:
                continue
            buckets.setdefault(error_code, set()).add(profile_id)

    result: list[dict[str, Any]] = []
    for error_code, profiles in sorted(buckets.items()):
        if len(profiles) < 2:
            continue
        result.append(
            {
                "error_code": error_code,
                "affected_profiles": sorted(profiles),
                "frequency": len(profiles),
                "likely_shared_cause": "Repeated evaluator signal across multiple profiles.",
                "recommended_investigation": "Inspect shared route construction, refusals handling, and evidence framing for this error code.",
            }
        )
    return result


def _render_baseline_summary_md(summary: dict[str, Any], systemic_errors: list[dict[str, Any]]) -> str:
    lines = [
        f"# Baseline Summary: {summary.get('run_id', '')}",
        "",
        f"- Baseline: {summary.get('baseline_id', '-')}",
        f"- Profiles: {summary.get('profile_count', 0)}",
        f"- Started: {summary.get('started_at', '-')}",
        f"- Completed: {summary.get('completed_at', '-')}",
        f"- Comparison reliability: {((summary.get('comparison') or {}).get('comparison_reliability') or '-')}",
        f"- Production logic unchanged during run: {str(not bool((summary.get('comparison') or {}).get('changed_code'))).lower()}",
        "",
        "## Profile Results",
        "",
    ]
    for row in summary.get("profiles") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"- {row.get('profile_id', '-')}: {row.get('evaluation_status', 'unknown')}")
    lines.extend(["", "## Systemic Errors", ""])
    if not systemic_errors:
        lines.append("- No systemic errors detected in two or more profiles.")
    else:
        for error in systemic_errors:
            lines.append(f"- {error.get('error_code', '-')}: {error.get('frequency', 0)} profiles")
    return "\n".join(lines)


async def run_baseline_profiles(
    *,
    generator: CareerGeneratorProtocol,
    evaluator: CareerEvaluatorProtocol,
    inputs_dir: Path,
    expected_dir: Path,
    results_dir: Path,
    baseline_lock_path: Path,
    required_profile_count: int | None = 9,
    run_id: str,
    application_version: str,
    git_commit: str,
    prompt_version: str,
    model: str,
    model_parameters: dict[str, Any],
    test_package_version: str = "career_profiles_v1",
    environment: str = "local",
    package_manifest_path: Path | None = None,
    enforce_package_integrity: bool = False,
    change_proposal_path: Path | None = None,
    enforce_change_proposal_gate: bool = False,
    baseline_reference_dir: Path | None = None,
    enforce_regression_gate: bool = False,
) -> dict[str, Any]:
    baseline_lock = load_json_file(baseline_lock_path)

    package_validation: dict[str, Any] | None = None
    if package_manifest_path is not None:
        package_validation = validate_test_package(
            manifest_path=package_manifest_path,
            inputs_dir=inputs_dir,
            expected_dir=expected_dir,
            expected_package_version=test_package_version,
        )
        if enforce_package_integrity and package_validation.get("status") != PACKAGE_COMPLETE:
            raise RuntimeError(
                f"Package integrity gate blocked run: {package_validation.get('status')}"
            )

    change_proposal_gate: dict[str, Any] | None = None
    proposal = None
    if change_proposal_path is not None:
        proposal = load_change_proposal(change_proposal_path)
        change_proposal_gate = validate_change_proposal(
            proposal=proposal,
            systemic_errors=[],
            production_root=Path.cwd(),
            inputs_dir=inputs_dir,
        )
        if enforce_change_proposal_gate and not bool(change_proposal_gate.get("allowed")):
            raise RuntimeError("Change proposal gate blocked run: proposal is not accepted")

    cases = discover_profile_cases(inputs_dir, expected_dir)
    if required_profile_count is not None and len(cases) != required_profile_count:
        raise ValueError(f"Expected {required_profile_count} input profiles, found {len(cases)}")

    run_dir = results_dir / run_id
    if run_dir.exists():
        raise FileExistsError(f"Run directory already exists and is immutable: {run_dir}")

    input_paths = [case.input_path for case in cases]
    expected_paths = [case.expected_path for case in cases]
    input_manifest_hash = _manifest_hash(input_paths)
    expected_manifest_hash = _manifest_hash(expected_paths)
    started_at = _utc_now_dt()
    comparison = _comparison_flags(
        baseline_lock=baseline_lock,
        input_manifest_hash=input_manifest_hash,
        expected_manifest_hash=expected_manifest_hash,
        model=model,
        model_parameters=model_parameters,
    )

    metadata = CareerTestRunMetadata(
        run_id=run_id,
        baseline_id=baseline_lock.get("baseline_id"),
        application_version=application_version,
        git_commit=git_commit,
        prompt_version=prompt_version,
        model=model,
        model_parameters=model_parameters,
        test_package_version=test_package_version,
        input_manifest_hash=input_manifest_hash,
        expected_manifest_hash=expected_manifest_hash,
        started_at=started_at,
        completed_at=None,
        environment=environment,
    )

    run_dir.mkdir(parents=True, exist_ok=False)
    profiles_dir = run_dir / "profiles"
    profile_results_dir = run_dir / "profile_results"
    judge_logs_dir = run_dir / "judge_logs"
    raw_responses_dir = run_dir / "raw_responses"
    profiles_dir.mkdir(parents=True, exist_ok=False)
    profile_results_dir.mkdir(parents=True, exist_ok=False)
    judge_logs_dir.mkdir(parents=True, exist_ok=False)
    raw_responses_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "run_metadata.json").write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    if package_validation is not None:
        (run_dir / "package_validation.json").write_text(
            json.dumps(package_validation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if change_proposal_gate is not None:
        (run_dir / "change_proposal_gate.json").write_text(
            json.dumps(change_proposal_gate, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary_rows: list[dict[str, Any]] = []
    profile_payloads: list[dict[str, Any]] = []
    adapter = CareerAnalysisAdapter(generator)
    for case in cases:
        input_profile = load_json_file(case.input_path)
        expected_profile = load_json_file(case.expected_path)
        assert_no_generator_leakage(input_profile, "input_profile")

        runtime_context = build_runtime_context(input_profile)
        generated_result, conversation_trace, retry_log = await _run_profile_with_retry(
            adapter=adapter,
            profile=CareerTestInput(profile_id=case.profile_id, payload=input_profile),
            run_context=RunContext(run_id=run_id, profile_id=case.profile_id, runtime_context=runtime_context),
        )
        evaluation_result = await evaluator.evaluate(input_profile, generated_result, expected_profile)

        raw_response_payload = {
            "profile_id": case.profile_id,
            "baseline_id": baseline_lock.get("baseline_id"),
            "run_id": run_id,
            "generated_at": _utc_now(),
            "input_source": str(case.input_path),
            "retry_log": retry_log,
            "conversation_trace": conversation_trace,
            "generated_result": generated_result,
        }
        judge_log_payload = {
            "profile_id": case.profile_id,
            "baseline_id": baseline_lock.get("baseline_id"),
            "run_id": run_id,
            "evaluated_at": _utc_now(),
            "expected_source": str(case.expected_path),
            "retry_log": retry_log,
            "evaluation_result": evaluation_result,
        }
        profile_payload = {
            "profile_id": case.profile_id,
            "baseline_id": baseline_lock.get("baseline_id"),
            "run_id": run_id,
            "comparison": comparison,
            "input_source": str(case.input_path),
            "expected_source": str(case.expected_path),
            "retry_log": retry_log,
            "conversation_trace": conversation_trace,
            "generated_result": generated_result,
            "evaluation_result": evaluation_result,
        }

        (raw_responses_dir / f"{case.profile_id}.raw.json").write_text(
            json.dumps(raw_response_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (judge_logs_dir / f"{case.profile_id}.judge.json").write_text(
            json.dumps(judge_log_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (profiles_dir / f"{case.profile_id}.json").write_text(
            json.dumps(profile_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (profile_results_dir / f"{case.profile_id}.json").write_text(
            json.dumps(profile_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        profile_payloads.append(profile_payload)

        summary_rows.append(
            {
                "profile_id": case.profile_id,
                "profile_path": str(profiles_dir / f"{case.profile_id}.json"),
                "profile_result_path": str(profile_results_dir / f"{case.profile_id}.json"),
                "judge_log_path": str(judge_logs_dir / f"{case.profile_id}.judge.json"),
                "raw_response_path": str(raw_responses_dir / f"{case.profile_id}.raw.json"),
                "evaluation_status": str(evaluation_result.get("evaluation_status") or "unknown"),
                "comparison_reliability": comparison["comparison_reliability"],
            }
        )

    completed_at = _utc_now_dt()
    metadata.completed_at = completed_at
    (run_dir / "run_metadata.json").write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    summary = {
        "baseline_id": baseline_lock.get("baseline_id"),
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "profile_count": len(cases),
        "comparison": comparison,
        "baseline_immutable": True,
        "no_fix_rule_applied": True,
        "profiles": summary_rows,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "baseline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    systemic_errors = _summarize_systemic_errors(profile_payloads)
    (run_dir / "systemic_errors.json").write_text(json.dumps(systemic_errors, ensure_ascii=False, indent=2), encoding="utf-8")

    profile_payload_map = {
        str(payload.get("profile_id") or "").strip(): payload
        for payload in profile_payloads
        if str(payload.get("profile_id") or "").strip()
    }

    if change_proposal_gate is not None and proposal is not None:
        change_proposal_gate = validate_change_proposal(
            proposal=proposal,
            systemic_errors=systemic_errors,
            production_root=Path.cwd(),
            inputs_dir=inputs_dir,
        )
        (run_dir / "change_proposal_gate.json").write_text(
            json.dumps(change_proposal_gate, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if enforce_change_proposal_gate and not bool(change_proposal_gate.get("allowed")):
            raise RuntimeError("Change proposal gate blocked run: proposal is not accepted")

    regression_matrix: dict[str, Any] | None = None
    regression_gate: dict[str, Any] | None = None
    if baseline_reference_dir is not None:
        reference_profile_dir = baseline_reference_dir
        if (baseline_reference_dir / "profile_results").exists():
            reference_profile_dir = baseline_reference_dir / "profile_results"
        baseline_payloads = load_profile_payloads(reference_profile_dir)
        regression_matrix = build_regression_matrix(
            baseline_payloads=baseline_payloads,
            current_payloads=profile_payload_map,
        )
        required_codes = proposal.source_error_codes if proposal is not None else []
        regression_gate = evaluate_regression_acceptance(
            matrix=regression_matrix,
            required_error_codes=required_codes,
        )
        (run_dir / "regression_matrix.json").write_text(
            json.dumps(regression_matrix, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "regression_gate.json").write_text(
            json.dumps(regression_gate, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if enforce_regression_gate and not bool(regression_gate.get("accepted")):
            raise RuntimeError("Regression gate blocked run: regressions detected")

    summary["package_validation"] = package_validation
    summary["change_proposal_gate"] = change_proposal_gate
    summary["regression_gate"] = regression_gate
    summary["baseline_complete"] = bool(package_validation and package_validation.get("status") == PACKAGE_COMPLETE)
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "baseline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    (run_dir / "baseline_summary.md").write_text(_render_baseline_summary_md(summary, systemic_errors), encoding="utf-8")
    return summary