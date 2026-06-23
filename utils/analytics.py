from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any
from urllib import error, request

from config import settings

_registry_lock = threading.Lock()


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


def _send_to_google_sheets(payload: dict[str, Any]) -> None:
    url = settings.google_sheets_webhook_url
    if not url:
        return
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=4):
            return
    except (error.URLError, TimeoutError, ValueError):
        return


def log_behavior_event_sync(
    *,
    public_user_id: str,
    event: str,
    state_name: str = "",
    action: str = "",
    user_mode: str = "",
    language: str = "ru",
    meta: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": _utc_now().isoformat(),
        "public_user_id": public_user_id,
        "event": (event or "unknown").strip(),
        "state": (state_name or "").strip(),
        "action": (action or "").strip(),
        "user_mode": (user_mode or "").strip(),
        "language": (language or "ru").strip(),
        "days_since_first_seen": days_since_first_seen(public_user_id),
        "meta": meta or {},
    }
    _append_local_event(payload)
    _send_to_google_sheets(payload)


async def log_behavior_event(
    *,
    public_user_id: str,
    event: str,
    state_name: str = "",
    action: str = "",
    user_mode: str = "",
    language: str = "ru",
    meta: dict[str, Any] | None = None,
) -> None:
    await asyncio.to_thread(
        log_behavior_event_sync,
        public_user_id=public_user_id,
        event=event,
        state_name=state_name,
        action=action,
        user_mode=user_mode,
        language=language,
        meta=meta,
    )


def behavior_insights(public_user_id: str, lookback_days: int = 7) -> list[str]:
    snapshot = behavior_offer_snapshot(public_user_id, lookback_days=lookback_days)
    return list(snapshot.get("insights", []))


def behavior_offer_snapshot(public_user_id: str, lookback_days: int = 7) -> dict[str, Any]:
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
