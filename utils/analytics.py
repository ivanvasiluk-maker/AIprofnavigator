from __future__ import annotations

import asyncio
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any
from urllib import error, request

from config import settings
from utils.persistence import get_recent_events, get_recent_events_all, get_user, record_event, upsert_user

_registry_lock = threading.Lock()
_ASYNC_EVENT_TASKS: set[asyncio.Task] = set()

_INTERVIEW_QUALITY_EVENTS: set[str] = {
    "story_evidence_extracted",
    "career_hypothesis_created",
    "career_hypothesis_confirmed",
    "career_hypothesis_rejected",
    "critical_gap_detected",
    "clarifying_question_asked",
    "clarifying_question_skipped_existing_answer",
    "interview_ready",
    "interview_ready_with_uncertainty",
    "preliminary_map_shown",
    "profile_correction_received",
    "report_guardrail_failed",
    "report_regenerated",
}

_EVENT_ALIASES: dict[str, str] = {
    # Existing runtime events -> PATCH-33 canonical events
    "story_submitted": "story_evidence_extracted",
    "question_shown": "clarifying_question_asked",
    "conflict_detected": "clarifying_question_skipped_existing_answer",
    "interview_ready_early": "interview_ready_with_uncertainty",
    "prelim_map_error_flagged": "profile_correction_received",
    "guardrail_violations": "report_guardrail_failed",
    "guardrail_regen_triggered": "report_regenerated",
}

_FIRST_VALUE_EVENTS: set[str] = {
    "interview_ready",
    "interview_ready_with_uncertainty",
    "preliminary_map_shown",
    "report_generated",
}


def _canonical_event_name(event: str, meta: dict[str, Any] | None = None) -> str:
    raw = str(event or "unknown").strip()
    if not raw:
        return "unknown"
    if raw in _INTERVIEW_QUALITY_EVENTS:
        return raw
    normalized = _EVENT_ALIASES.get(raw, raw)
    if normalized == "interview_ready_with_uncertainty":
        status = str((meta or {}).get("status") or "").strip().lower()
        if status == "ready":
            return "interview_ready"
    return normalized


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat((value or "").strip())
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _registry_path() -> Path:
    return Path(settings.analytics_registry_path)


def _events_log_path() -> Path:
    return Path(settings.analytics_events_log_path)


def _excel_log_path() -> Path:
    return Path(settings.analytics_excel_log_path)


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _public_id_for_new_user(registry: dict[str, Any]) -> str:
    today = _utc_now().strftime("%Y%m%d")
    daily = registry.setdefault("daily_counters", {})
    counter = int(daily.get(today, 0)) + 1
    daily[today] = counter
    return f"{today}-{counter:04d}"


def ensure_public_user_id(telegram_user_id: int | str, source_tag: str = "") -> str:
    key = str(telegram_user_id)
    source_clean = str(source_tag or "").strip()[:120]
    with _registry_lock:
        registry = _read_json(_registry_path(), default={"users": {}, "daily_counters": {}})
        users = registry.setdefault("users", {})
        row = users.get(key)
        if isinstance(row, dict) and str(row.get("public_user_id", "")).strip():
            upsert_user(
                str(row["public_user_id"]),
                key,
                source_tag=source_clean,
                language="ru",
            )
            if source_clean and not str(row.get("first_source", "")).strip():
                row["first_source"] = source_clean
                row["updated_at"] = _utc_now().isoformat()
                _write_json(_registry_path(), registry)
            return str(row["public_user_id"])

        public_user_id = _public_id_for_new_user(registry)
        users[key] = {
            "public_user_id": public_user_id,
            "created_at": _utc_now().isoformat(),
            "first_source": source_clean,
        }
        _write_json(_registry_path(), registry)
        upsert_user(
            public_user_id,
            key,
            source_tag=source_clean,
            language="ru",
        )
        return public_user_id


def _user_row_by_public_id(public_user_id: str) -> dict[str, Any] | None:
    registry = _read_json(_registry_path(), default={"users": {}, "daily_counters": {}})
    users = registry.get("users", {})
    if not isinstance(users, dict):
        return None
    for row in users.values():
        if isinstance(row, dict) and str(row.get("public_user_id")) == public_user_id:
            return row
    return None


def days_since_first_seen(public_user_id: str) -> int:
    db_user = get_user(public_user_id)
    created_raw_db = str((db_user or {}).get("first_seen_at", "")).strip()
    if created_raw_db:
        try:
            created_db = datetime.fromisoformat(created_raw_db)
            if created_db.tzinfo is None:
                created_db = created_db.replace(tzinfo=timezone.utc)
            return max(0, (_utc_now().date() - created_db.date()).days)
        except Exception:
            pass

    row = _user_row_by_public_id(public_user_id)
    created_raw = str((row or {}).get("created_at", "")).strip()
    if not created_raw:
        return 0
    try:
        created = datetime.fromisoformat(created_raw)
    except Exception:
        return 0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0, (_utc_now().date() - created.date()).days)


def _append_local_event(payload: dict[str, Any]) -> None:
    log_path = _events_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _append_excel_event(payload: dict[str, Any]) -> None:
    path = _excel_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    headers = [
        "timestamp",
        "public_user_id",
        "event",
        "state",
        "action",
        "user_mode",
        "language",
        "days_since_first_seen",
        "session_id",
        "meta_json",
        "sheets_delivery",
    ]
    row = {
        "timestamp": str(payload.get("timestamp") or ""),
        "public_user_id": str(payload.get("public_user_id") or ""),
        "event": str(payload.get("event") or ""),
        "state": str(payload.get("state") or ""),
        "action": str(payload.get("action") or ""),
        "user_mode": str(payload.get("user_mode") or ""),
        "language": str(payload.get("language") or ""),
        "days_since_first_seen": str(payload.get("days_since_first_seen") or ""),
        "session_id": str(payload.get("session_id") or ""),
        "meta_json": json.dumps(payload.get("meta") or {}, ensure_ascii=False),
        "sheets_delivery": str(payload.get("sheets_delivery") or ""),
    }
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _send_to_google_sheets(payload: dict[str, Any]) -> bool:
    url = settings.google_sheets_webhook_url
    if not url:
        return False
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=1.5):
            return True
    except (error.URLError, TimeoutError, ValueError):
        return False


def log_behavior_event_sync(
    *,
    public_user_id: str,
    event: str,
    state_name: str = "",
    action: str = "",
    user_mode: str = "",
    language: str = "ru",
    meta: dict[str, Any] | None = None,
    session_id: str = "",
) -> None:
    meta_payload = meta or {}
    canonical_event = _canonical_event_name(event, meta_payload)
    payload: dict[str, Any] = {
        "timestamp": _utc_now().isoformat(),
        "public_user_id": public_user_id,
        "event": canonical_event,
        "state": (state_name or "").strip(),
        "action": (action or "").strip(),
        "user_mode": (user_mode or "").strip(),
        "language": (language or "ru").strip(),
        "days_since_first_seen": days_since_first_seen(public_user_id),
        "session_id": (session_id or "").strip(),
        "meta": meta_payload,
    }
    if canonical_event == "clarifying_question_asked":
        # PATCH-34 rule: each question must map to a decision that can change.
        decision_change = str(meta_payload.get("decision_that_may_change") or meta_payload.get("decision_impact") or "").strip()
        payload["meta"]["question_has_decision_justification"] = bool(decision_change)

    _append_local_event(payload)
    sheets_delivery = _send_to_google_sheets(payload)
    payload["sheets_delivery"] = "ok" if sheets_delivery else "failed_or_disabled"
    _append_excel_event(payload)
    record_event(
        public_user_id=public_user_id,
        event=canonical_event,
        state_name=(state_name or "").strip(),
        action=(action or "").strip(),
        user_mode=(user_mode or "").strip(),
        language=(language or "ru").strip(),
        meta=meta_payload,
        session_id=(session_id or "").strip(),
        timestamp=str(payload.get("timestamp") or ""),
    )


def interview_quality_metrics(*, lookback_days: int = 30, sample_limit: int = 3000) -> dict[str, Any]:
    """Aggregate quality metrics for conversational interview flow (PATCH-33)."""
    rows = get_recent_events_all(lookback_days=max(1, int(lookback_days)), limit=250000)
    if not rows:
        return {
            "sample_users": 0,
            "average_questions_before_preliminary_map": 0.0,
            "percentage_reports_without_extra_questions": 0.0,
            "duplicate_question_rate": 0.0,
            "user_correction_rate": 0.0,
            "critical_guardrail_failure_rate": 0.0,
            "average_time_to_first_value": 0.0,
            "preliminary_map_acceptance_rate": 0.0,
            "route_change_after_report_rate": 0.0,
            "time_to_first_useful_hypothesis": 0.0,
            "anti_metrics": ["number_of_fields_completed"],
        }

    by_user: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        uid = str(row.get("public_user_id") or "").strip()
        if not uid:
            continue
        by_user.setdefault(uid, []).append(row)
        if len(by_user) > max(1, int(sample_limit)):
            break

    def _to_dt(value: str) -> datetime | None:
        return _parse_iso(value)

    users = list(by_user.keys())
    if not users:
        return {
            "sample_users": 0,
            "average_questions_before_preliminary_map": 0.0,
            "percentage_reports_without_extra_questions": 0.0,
            "duplicate_question_rate": 0.0,
            "user_correction_rate": 0.0,
            "critical_guardrail_failure_rate": 0.0,
            "average_time_to_first_value": 0.0,
            "preliminary_map_acceptance_rate": 0.0,
            "route_change_after_report_rate": 0.0,
            "time_to_first_useful_hypothesis": 0.0,
            "anti_metrics": ["number_of_fields_completed"],
        }

    total_questions = 0
    duplicate_questions = 0
    users_with_reports = 0
    users_reports_without_extra_questions = 0
    prelim_shown_count = 0
    prelim_accepted_count = 0
    route_changed_after_report = 0
    user_corrections = 0
    critical_guardrail_failures = 0
    report_generations = 0
    q_before_prelim_samples: list[int] = []
    ttfv_samples: list[float] = []
    useful_hypothesis_samples: list[float] = []

    for uid in users:
        user_rows = by_user.get(uid, [])
        user_rows.sort(key=lambda r: str(r.get("timestamp") or ""))
        seen_signatures: set[str] = set()
        questions_before_prelim = 0
        prelim_shown_at: datetime | None = None
        report_generated_at: datetime | None = None
        story_start_at: datetime | None = None
        first_value_at: datetime | None = None
        first_useful_hypothesis_at: datetime | None = None
        interview_ready_at: datetime | None = None
        report_has_extra_q_after_ready = False
        report_has_route_change_after = False

        for row in user_rows:
            ts = _to_dt(str(row.get("timestamp") or ""))
            if ts is None:
                continue
            event_name = _canonical_event_name(str(row.get("event") or ""), row.get("meta") if isinstance(row.get("meta"), dict) else None)
            meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}

            if story_start_at is None and event_name == "story_evidence_extracted":
                story_start_at = ts

            if first_value_at is None and event_name in _FIRST_VALUE_EVENTS:
                first_value_at = ts

            if event_name in {"career_hypothesis_confirmed", "interview_ready", "interview_ready_with_uncertainty"} and first_useful_hypothesis_at is None:
                first_useful_hypothesis_at = ts

            if event_name == "clarifying_question_asked":
                total_questions += 1
                signature = str(meta.get("signature") or meta.get("question_signature") or meta.get("question_id") or "").strip()
                if signature:
                    if signature in seen_signatures:
                        duplicate_questions += 1
                    seen_signatures.add(signature)
                if prelim_shown_at is None:
                    questions_before_prelim += 1
                if interview_ready_at is not None and report_generated_at is None:
                    report_has_extra_q_after_ready = True

            if event_name == "preliminary_map_shown":
                prelim_shown_count += 1
                if prelim_shown_at is None:
                    prelim_shown_at = ts

            if event_name in {"prelim_map_confirmed", "career_hypothesis_confirmed"}:
                prelim_accepted_count += 1

            if event_name in {"interview_ready", "interview_ready_with_uncertainty"} and interview_ready_at is None:
                interview_ready_at = ts

            if event_name == "profile_correction_received":
                user_corrections += 1

            if event_name == "report_guardrail_failed":
                report_generations += 1
                errors = meta.get("errors") if isinstance(meta.get("errors"), list) else []
                critical_count = int(meta.get("critical_count") or 0)
                if critical_count > 0 or any(str(item).startswith("[CRITICAL]") for item in errors):
                    critical_guardrail_failures += 1

            if event_name == "report_generated" and report_generated_at is None:
                report_generated_at = ts
                users_with_reports += 1

            if event_name == "route_changed" and report_generated_at is not None:
                report_has_route_change_after = True

        if prelim_shown_at is not None:
            q_before_prelim_samples.append(questions_before_prelim)

        if story_start_at is not None and first_value_at is not None:
            ttfv_samples.append(max(0.0, (first_value_at - story_start_at).total_seconds()))

        if story_start_at is not None and first_useful_hypothesis_at is not None:
            useful_hypothesis_samples.append(max(0.0, (first_useful_hypothesis_at - story_start_at).total_seconds()))

        if report_generated_at is not None and not report_has_extra_q_after_ready:
            users_reports_without_extra_questions += 1

        if report_has_route_change_after:
            route_changed_after_report += 1

    def _avg(values: list[float]) -> float:
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    def _pct(num: int, den: int) -> float:
        if den <= 0:
            return 0.0
        return round((100.0 * num) / den, 2)

    return {
        "sample_users": len(users),
        "average_questions_before_preliminary_map": _avg([float(v) for v in q_before_prelim_samples]),
        "percentage_reports_without_extra_questions": _pct(users_reports_without_extra_questions, users_with_reports),
        "duplicate_question_rate": _pct(duplicate_questions, total_questions),
        "user_correction_rate": _pct(user_corrections, prelim_shown_count),
        "critical_guardrail_failure_rate": _pct(critical_guardrail_failures, max(report_generations, 1)),
        "average_time_to_first_value": _avg(ttfv_samples),
        "preliminary_map_acceptance_rate": _pct(prelim_accepted_count, prelim_shown_count),
        "route_change_after_report_rate": _pct(route_changed_after_report, users_with_reports),
        "time_to_first_useful_hypothesis": _avg(useful_hypothesis_samples),
        "anti_metrics": ["number_of_fields_completed"],
    }


async def log_behavior_event(
    *,
    public_user_id: str,
    event: str,
    state_name: str = "",
    action: str = "",
    user_mode: str = "",
    language: str = "ru",
    meta: dict[str, Any] | None = None,
    session_id: str = "",
) -> None:
    async def _runner() -> None:
        try:
            await asyncio.to_thread(
                log_behavior_event_sync,
                public_user_id=public_user_id,
                event=event,
                state_name=state_name,
                action=action,
                user_mode=user_mode,
                language=language,
                meta=meta,
                session_id=session_id,
            )
        except Exception:
            # Telemetry must never block user flow.
            return

    task = asyncio.create_task(_runner())
    _ASYNC_EVENT_TASKS.add(task)
    task.add_done_callback(lambda t: _ASYNC_EVENT_TASKS.discard(t))


def behavior_insights(public_user_id: str, lookback_days: int = 7) -> list[str]:
    snapshot = behavior_offer_snapshot(public_user_id, lookback_days=lookback_days)
    return list(snapshot.get("insights", []))


def behavior_offer_snapshot(public_user_id: str, lookback_days: int = 7) -> dict[str, Any]:
    rows = get_recent_events(public_user_id, lookback_days=lookback_days)
    if rows:
        action_counters = Counter()
        event_counters = Counter()
        state_counters = Counter()
        total_events = 0

        for row in rows:
            total_events += 1
            action = str(row.get("action", "")).strip()
            event = str(row.get("event", "")).strip()
            state_name = str(row.get("state", "")).strip()
            if action:
                action_counters[action] += 1
            if event:
                event_counters[event] += 1
            if state_name:
                state_counters[state_name] += 1

        insights: list[str] = []
        for action, count in action_counters.most_common(3):
            insights.append(f"Вы чаще всего выбирали: {action} ({count} раз).")

        reports = int(event_counters.get("report_generated", 0))
        today_steps = int(event_counters.get("today_step_opened", 0))
        details = int(event_counters.get("details_opened", 0))

        if reports:
            insights.append("Вы уже доходили до полной карты и это хороший признак устойчивого действия.")
        if today_steps:
            insights.append("Вы регулярно возвращаетесь к первому шагу, значит умеете запускать движение без перегруза.")
        if details:
            insights.append("Вы открываете подробный разбор, значит принимаете решения на фактах, а не на эмоции момента.")
        if total_events >= 6:
            insights.append("У вас уже сформирован рабочий ритм: вы не просто читаете карту, а взаимодействуете с ней по шагам.")

        top_states = [state for state, _count in state_counters.most_common(3)]

        return {
            "insights": insights[:5],
            "top_actions": action_counters.most_common(3),
            "top_states": top_states,
            "stats": {
                "total_events": total_events,
                "report_generated": reports,
                "today_step_opened": today_steps,
                "details_opened": details,
            },
        }

    # Legacy fallback path: local jsonl file.
    path = _events_log_path()
    if not path.exists():
        return {
            "insights": [],
            "top_actions": [],
            "stats": {},
        }
    cutoff = _utc_now().timestamp() - lookback_days * 24 * 3600
    action_counters = Counter()
    event_counters = Counter()
    state_counters = Counter()
    total_events = 0

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if str(row.get("public_user_id", "")).strip() != public_user_id:
            continue
        ts = str(row.get("timestamp", "")).strip()
        dt = _parse_iso(ts)
        if dt is None:
            continue
        if dt.timestamp() < cutoff:
            continue

        total_events += 1
        action = str(row.get("action", "")).strip()
        event = str(row.get("event", "")).strip()
        state_name = str(row.get("state", "")).strip()
        if action:
            action_counters[action] += 1
        if event:
            event_counters[event] += 1
        if state_name:
            state_counters[state_name] += 1

    insights: list[str] = []
    for action, count in action_counters.most_common(3):
        insights.append(f"Вы чаще всего выбирали: {action} ({count} раз).")

    reports = int(event_counters.get("report_generated", 0))
    today_steps = int(event_counters.get("today_step_opened", 0))
    details = int(event_counters.get("details_opened", 0))

    if reports:
        insights.append("Вы уже доходили до полной карты и это хороший признак устойчивого действия.")
    if today_steps:
        insights.append("Вы регулярно возвращаетесь к первому шагу, значит умеете запускать движение без перегруза.")
    if details:
        insights.append("Вы открываете подробный разбор, значит принимаете решения на фактах, а не на эмоции момента.")
    if total_events >= 6:
        insights.append("У вас уже сформирован рабочий ритм: вы не просто читаете карту, а взаимодействуете с ней по шагам.")

    top_states = [state for state, _count in state_counters.most_common(3)]

    return {
        "insights": insights[:5],
        "top_actions": action_counters.most_common(3),
        "top_states": top_states,
        "stats": {
            "total_events": total_events,
            "report_generated": reports,
            "today_step_opened": today_steps,
            "details_opened": details,
        },
    }


def pilot_quality_metrics(sample_limit: int = 100) -> dict[str, Any]:
    """Aggregate early-pilot quality metrics from local analytics events log.

    The function focuses on canonical events used in PATCH 17 and returns
    percentages for the first `sample_limit` unique users.
    """
    rows = get_recent_events_all(lookback_days=60, limit=250000)
    if not rows:
        interview_quality = interview_quality_metrics(lookback_days=60, sample_limit=sample_limit)
        return {
            "sample_users": 0,
            "reached_map_percent": 0.0,
            "conflict_percent": 0.0,
            "disagreed_percent": 0.0,
            "first_step_too_hard_percent": 0.0,
            "specialist_click_percent": 0.0,
            "pdf_or_report_error_percent": 0.0,
            "dropoff_stages": [],
            "interview_quality": interview_quality,
        }

    user_order: list[str] = []
    by_user: dict[str, dict[str, Any]] = {}

    for row in rows:
        uid = str(row.get("public_user_id", "")).strip()
        if not uid:
            continue
        if uid not in by_user:
            if len(user_order) >= max(1, int(sample_limit)):
                continue
            user_order.append(uid)
            by_user[uid] = {
                "events": Counter(),
                "states": Counter(),
                "last_state": "",
            }

        profile = by_user[uid]
        event = str(row.get("event", "")).strip()
        state_name = str(row.get("state", "")).strip()
        if event:
            profile["events"][event] += 1
        if state_name:
            profile["states"][state_name] += 1
            profile["last_state"] = state_name

    sample_size = len(user_order)
    if sample_size == 0:
        interview_quality = interview_quality_metrics(lookback_days=60, sample_limit=sample_limit)
        return {
            "sample_users": 0,
            "reached_map_percent": 0.0,
            "conflict_percent": 0.0,
            "disagreed_percent": 0.0,
            "first_step_too_hard_percent": 0.0,
            "specialist_click_percent": 0.0,
            "pdf_or_report_error_percent": 0.0,
            "dropoff_stages": [],
            "interview_quality": interview_quality,
        }

    reached_map = 0
    with_conflict = 0
    disagreed = 0
    too_hard = 0
    specialist = 0
    errors = 0
    dropoff_counter: Counter[str] = Counter()

    for uid in user_order:
        events: Counter = by_user[uid]["events"]
        last_state = str(by_user[uid].get("last_state", "")).strip() or "unknown"

        if events.get("report_generated", 0) > 0:
            reached_map += 1
        else:
            dropoff_counter[last_state] += 1

        if events.get("conflict_detected", 0) > 0:
            with_conflict += 1
        if events.get("user_disagreed", 0) > 0:
            disagreed += 1
        if events.get("first_step_too_hard", 0) > 0:
            too_hard += 1
        if events.get("specialist_clicked", 0) > 0:
            specialist += 1
        if events.get("pdf_failed", 0) > 0 or events.get("report_failed", 0) > 0:
            errors += 1

    def _pct(value: int) -> float:
        return round((100.0 * value) / sample_size, 2)

    interview_quality = interview_quality_metrics(lookback_days=60, sample_limit=sample_limit)

    return {
        "sample_users": sample_size,
        "reached_map_percent": _pct(reached_map),
        "conflict_percent": _pct(with_conflict),
        "disagreed_percent": _pct(disagreed),
        "first_step_too_hard_percent": _pct(too_hard),
        "specialist_click_percent": _pct(specialist),
        "pdf_or_report_error_percent": _pct(errors),
        "dropoff_stages": dropoff_counter.most_common(5),
        "interview_quality": interview_quality,
    }
