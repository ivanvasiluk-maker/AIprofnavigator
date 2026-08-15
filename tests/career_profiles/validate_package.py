from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PACKAGE_COMPLETE = "PACKAGE_COMPLETE"
PACKAGE_INCOMPLETE = "PACKAGE_INCOMPLETE"
PACKAGE_VERSION_MISMATCH = "PACKAGE_VERSION_MISMATCH"
INPUT_EXPECTED_ID_MISMATCH = "INPUT_EXPECTED_ID_MISMATCH"
EXPECTED_DATA_IN_INPUT = "EXPECTED_DATA_IN_INPUT"
INVALID_MANIFEST = "INVALID_MANIFEST"

_EXPECTED_ONLY_FIELDS = {
    "expected_routes",
    "route_expectations",
    "expected_professional_core",
    "professional_core",
    "seniority_expectations",
    "direct_refusals",
    "must_show_uncertainty",
    "evidence_fragments",
    "forbidden_recommendations",
    "critical_errors",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _normalize_manifest_file_entry(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return {
            "path": raw,
            "required": True,
            "sha256": "",
            "alternatives": [],
        }
    if isinstance(raw, dict):
        return {
            "path": str(raw.get("path") or "").strip(),
            "required": bool(raw.get("required", True)),
            "sha256": str(raw.get("sha256") or "").strip().upper(),
            "alternatives": [str(item).strip() for item in raw.get("alternatives") or [] if str(item).strip()],
        }
    raise ValueError(f"Invalid manifest file entry: {raw!r}")


def _iter_json_files(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.json") if path.is_file())


def _find_expected_field_paths(payload: Any, *, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_str = str(key)
            current_path = f"{path}.{key_str}" if path else key_str
            normalized = key_str.strip().lower()
            if normalized.startswith("expected") or normalized in _EXPECTED_ONLY_FIELDS:
                findings.append(current_path)
            findings.extend(_find_expected_field_paths(value, path=current_path))
    elif isinstance(payload, list):
        for idx, item in enumerate(payload):
            findings.extend(_find_expected_field_paths(item, path=f"{path}[{idx}]"))
    return findings


def _determine_primary_status(statuses: set[str]) -> str:
    if INVALID_MANIFEST in statuses:
        return INVALID_MANIFEST
    if PACKAGE_VERSION_MISMATCH in statuses:
        return PACKAGE_VERSION_MISMATCH
    if PACKAGE_INCOMPLETE in statuses:
        return PACKAGE_INCOMPLETE
    if INPUT_EXPECTED_ID_MISMATCH in statuses:
        return INPUT_EXPECTED_ID_MISMATCH
    if EXPECTED_DATA_IN_INPUT in statuses:
        return EXPECTED_DATA_IN_INPUT
    return PACKAGE_COMPLETE


def validate_test_package(
    *,
    manifest_path: Path,
    inputs_dir: Path,
    expected_dir: Path,
    expected_package_version: str = "",
) -> dict[str, Any]:
    statuses: set[str] = set()
    findings: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}

    if not manifest_path.exists():
        statuses.add(INVALID_MANIFEST)
        findings.append({"issue": "manifest_missing", "path": str(manifest_path)})
        return {
            "status": INVALID_MANIFEST,
            "statuses": [INVALID_MANIFEST],
            "manifest_path": str(manifest_path),
            "manifest": {},
            "findings": findings,
            "baseline_ready": False,
            "baseline_blockers": [INVALID_MANIFEST],
        }

    try:
        manifest = _load_json(manifest_path)
    except Exception as exc:
        statuses.add(INVALID_MANIFEST)
        findings.append({"issue": "manifest_invalid_json", "error": str(exc), "path": str(manifest_path)})
        return {
            "status": INVALID_MANIFEST,
            "statuses": [INVALID_MANIFEST],
            "manifest_path": str(manifest_path),
            "manifest": {},
            "findings": findings,
            "baseline_ready": False,
            "baseline_blockers": [INVALID_MANIFEST],
        }

    package_version = str(manifest.get("package_version") or "").strip()
    profile_count_declared = int(manifest.get("profile_count") or 0)
    manifest_files_raw = manifest.get("files")
    if not package_version or not isinstance(manifest_files_raw, list):
        statuses.add(INVALID_MANIFEST)
        findings.append(
            {
                "issue": "manifest_missing_required_keys",
                "required_keys": ["package_version", "profile_count", "files"],
            }
        )

    manifest_file_entries: list[dict[str, Any]] = []
    for entry in manifest_files_raw or []:
        try:
            normalized = _normalize_manifest_file_entry(entry)
            if not normalized["path"]:
                raise ValueError("file path is empty")
            manifest_file_entries.append(normalized)
        except Exception as exc:
            statuses.add(INVALID_MANIFEST)
            findings.append({"issue": "manifest_invalid_file_entry", "entry": entry, "error": str(exc)})

    manifest_root = manifest_path.parent
    for entry in manifest_file_entries:
        target = (manifest_root / entry["path"]).resolve()
        alternatives = [((manifest_root / alt).resolve(), alt) for alt in entry["alternatives"]]
        target_exists = target.exists()
        alternative_exists = any(path.exists() for path, _ in alternatives)
        if entry["required"] and not target_exists and not alternative_exists:
            statuses.add(PACKAGE_INCOMPLETE)
            findings.append(
                {
                    "issue": "required_file_missing",
                    "path": entry["path"],
                    "alternatives": entry["alternatives"],
                }
            )
        elif target_exists and entry["sha256"]:
            if target.is_file():
                actual_hash = _sha256(target)
                if actual_hash != entry["sha256"]:
                    statuses.add(INVALID_MANIFEST)
                    findings.append(
                        {
                            "issue": "checksum_mismatch",
                            "path": entry["path"],
                            "expected": entry["sha256"],
                            "actual": actual_hash,
                        }
                    )
            else:
                statuses.add(INVALID_MANIFEST)
                findings.append(
                    {
                        "issue": "checksum_target_not_file",
                        "path": entry["path"],
                    }
                )

    if expected_package_version and package_version and package_version != expected_package_version:
        statuses.add(PACKAGE_VERSION_MISMATCH)
        findings.append(
            {
                "issue": "package_version_mismatch",
                "expected": expected_package_version,
                "actual": package_version,
            }
        )

    input_files = _iter_json_files(inputs_dir)
    expected_files = _iter_json_files(expected_dir)

    input_profiles: dict[str, Path] = {}
    expected_profiles: dict[str, Path] = {}

    for path in input_files:
        try:
            payload = _load_json(path)
        except Exception as exc:
            statuses.add(INVALID_MANIFEST)
            findings.append({"issue": "input_invalid_json", "path": str(path), "error": str(exc)})
            continue

        profile_id = str(payload.get("profile_id") or "").strip()
        if not profile_id:
            statuses.add(INPUT_EXPECTED_ID_MISMATCH)
            findings.append({"issue": "input_missing_profile_id", "path": str(path)})
            continue
        if profile_id in input_profiles:
            statuses.add(INPUT_EXPECTED_ID_MISMATCH)
            findings.append(
                {
                    "issue": "input_duplicate_profile_id",
                    "profile_id": profile_id,
                    "path": str(path),
                    "original_path": str(input_profiles[profile_id]),
                }
            )
        input_profiles[profile_id] = path

        expected_like_paths = _find_expected_field_paths(payload)
        if expected_like_paths:
            statuses.add(EXPECTED_DATA_IN_INPUT)
            findings.append(
                {
                    "issue": "expected_data_found_in_input",
                    "profile_id": profile_id,
                    "path": str(path),
                    "fields": expected_like_paths,
                }
            )

    for path in expected_files:
        try:
            payload = _load_json(path)
        except Exception as exc:
            statuses.add(INVALID_MANIFEST)
            findings.append({"issue": "expected_invalid_json", "path": str(path), "error": str(exc)})
            continue

        profile_id = str(payload.get("profile_id") or payload.get("id") or "").strip()
        if not profile_id:
            statuses.add(INPUT_EXPECTED_ID_MISMATCH)
            findings.append({"issue": "expected_missing_id", "path": str(path)})
            continue
        if profile_id in expected_profiles:
            statuses.add(INPUT_EXPECTED_ID_MISMATCH)
            findings.append(
                {
                    "issue": "expected_duplicate_profile_id",
                    "profile_id": profile_id,
                    "path": str(path),
                    "original_path": str(expected_profiles[profile_id]),
                }
            )
        expected_profiles[profile_id] = path

    input_ids = set(input_profiles)
    expected_ids = set(expected_profiles)
    if input_ids != expected_ids:
        statuses.add(INPUT_EXPECTED_ID_MISMATCH)
        findings.append(
            {
                "issue": "profile_id_set_mismatch",
                "input_only": sorted(input_ids - expected_ids),
                "expected_only": sorted(expected_ids - input_ids),
            }
        )

    if profile_count_declared > 0:
        if len(input_ids) != profile_count_declared or len(expected_ids) != profile_count_declared:
            statuses.add(PACKAGE_INCOMPLETE)
            findings.append(
                {
                    "issue": "profile_count_mismatch",
                    "declared": profile_count_declared,
                    "inputs_found": len(input_ids),
                    "expected_found": len(expected_ids),
                }
            )

    if not statuses:
        statuses.add(PACKAGE_COMPLETE)

    status = _determine_primary_status(statuses)
    status_list = sorted(statuses)
    baseline_ready = status == PACKAGE_COMPLETE and status_list == [PACKAGE_COMPLETE]
    blockers = [item for item in status_list if item != PACKAGE_COMPLETE]

    return {
        "status": status,
        "statuses": status_list,
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "findings": findings,
        "profile_counts": {
            "declared": profile_count_declared,
            "inputs_found": len(input_ids),
            "expected_found": len(expected_ids),
        },
        "baseline_ready": baseline_ready,
        "baseline_blockers": blockers,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="Validate career profile package integrity")
    parser.add_argument("--manifest", required=True, help="Path to package_manifest.json")
    parser.add_argument("--inputs-dir", required=True, help="Directory with input profiles")
    parser.add_argument("--expected-dir", required=True, help="Directory with expected profiles")
    parser.add_argument("--expected-package-version", default="", help="Expected package version")
    args = parser.parse_args()

    report = validate_test_package(
        manifest_path=Path(args.manifest),
        inputs_dir=Path(args.inputs_dir),
        expected_dir=Path(args.expected_dir),
        expected_package_version=str(args.expected_package_version or ""),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == PACKAGE_COMPLETE else 2


if __name__ == "__main__":
    raise SystemExit(_main())
