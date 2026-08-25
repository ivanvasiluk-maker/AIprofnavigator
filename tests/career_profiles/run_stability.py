from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from handlers.career import _build_profile_snapshot
from openai_client import CareerOpenAIClient


BASE_DIR = ROOT / "tests" / "career_profiles"
EMPTY_ROUTE_TITLES = {"", "не уточнено", "возможный маршрут", "проверка выполняемых функций"}


def _load_profiles(path: Path) -> list[dict[str, Any]]:
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    return [json.loads(item.read_text(encoding="utf-8")) for item in files]


def _state_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    answers = profile.get("answers") if isinstance(profile.get("answers"), dict) else {}
    resume_facts = profile.get("resume_facts") if isinstance(profile.get("resume_facts"), list) else []
    return {
        "assessment_id": str(profile.get("profile_id") or "stability-profile"),
        "story_text": str(profile.get("story") or ""),
        "story_analysis": {
            "confirmed_functions": [str(item) for item in resume_facts],
            "target_roles": [str(item) for item in answers.get("preferred_experiments", [])] if isinstance(answers.get("preferred_experiments"), list) else [],
        },
        "resume_analysis": {"achievements": [str(item) for item in resume_facts]},
        "route_context": {
            "city": str(answers.get("city") or ""),
            "country": str(answers.get("country") or ""),
            "minimum_monthly_income": str(answers.get("minimum_income") or ""),
        },
        "career_goal": str(answers.get("desired_change") or ""),
        "selected_career_priorities": list(answers.get("priorities") or []),
    }


def _signature(assessment) -> dict[str, Any]:
    route = assessment.routes.by_id(assessment.routes.recommended_route_id) or assessment.routes.primary_routes[0]
    return {
        "professional_core": list(assessment.identity.professional_core),
        "recommended_route_id": route.route_id,
        "recommended_route_title": route.title,
        "seniority_current": assessment.identity.seniority_current,
        "recovered_by": str(assessment.metadata.get("recovered_by") or ""),
    }


def _same_count(values: list[Any]) -> int:
    encoded = [json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values]
    return Counter(encoded).most_common(1)[0][1] if encoded else 0


async def _run(args: argparse.Namespace) -> int:
    profiles_path = Path(args.profiles)
    if not profiles_path.is_absolute():
        profiles_path = BASE_DIR / profiles_path
    profiles = _load_profiles(profiles_path)
    estimated_calls = len(profiles) * args.runs
    print(f"Планируется вызовов модели: {estimated_calls} ({len(profiles)} профилей x {args.runs} прогона)")
    if not args.confirm:
        print("Добавьте --confirm, чтобы действительно запустить модель и сохранить результат.")
        return 0

    client = CareerOpenAIClient(settings.openai_api_key, settings.openai_model, settings.openai_transcribe_model)
    rows: list[dict[str, Any]] = []
    stable_routes = 0
    empty_route_runs = 0
    for profile in profiles:
        profile_id = str(profile.get("profile_id") or profile.get("title") or "profile")
        signatures = []
        state = _state_from_profile(profile)
        snapshot = _build_profile_snapshot(state)
        for run_index in range(args.runs):
            assessment = await client.build_career_assessment(
                snapshot,
                assessment_id=f"{profile_id}-{run_index + 1}",
                session_id=f"stability-{profile_id}",
                profile_version="stability",
                story_analysis=state["story_analysis"],
                resume_analysis=state["resume_analysis"],
            )
            signature = _signature(assessment)
            signatures.append(signature)
            if signature["recommended_route_title"].strip().casefold() in EMPTY_ROUTE_TITLES:
                empty_route_runs += 1
        route_titles = [item["recommended_route_title"] for item in signatures]
        if len(set(route_titles)) == 1:
            stable_routes += 1
        row = {
            "profile": profile_id,
            "professional_core_match": _same_count([item["professional_core"] for item in signatures]),
            "recommended_route_match": _same_count(route_titles),
            "seniority_match": _same_count([item["seniority_current"] for item in signatures]),
            "recovered_by": [item["recovered_by"] for item in signatures],
            "runs": signatures,
        }
        rows.append(row)
        print(
            f"{profile_id} | core {row['professional_core_match']}/{args.runs} | "
            f"route {row['recommended_route_match']}/{args.runs} | "
            f"seniority {row['seniority_match']}/{args.runs} | recovered_by={', '.join(row['recovered_by'])}"
        )
    summary = f"стабильность основного маршрута: {stable_routes} из {len(profiles)} профилей ({args.runs} прогона)"
    print(summary)
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runs": args.runs,
        "profile_count": len(profiles),
        "estimated_model_calls": estimated_calls,
        "stable_route_profiles": stable_routes,
        "empty_route_run_share": empty_route_runs / max(1, estimated_calls),
        "summary": summary,
        "profiles": rows,
    }
    results_dir = BASE_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"stability_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON сохранён: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure CareerAssessment stability across repeated model runs")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--profiles", default="inputs")
    parser.add_argument("--confirm", action="store_true")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
