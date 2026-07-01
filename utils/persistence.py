from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from config import settings


_DB_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    return Path(settings.app_db_path)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_storage() -> None:
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    public_user_id TEXT PRIMARY KEY,
                    telegram_user_id TEXT,
                    source_tag TEXT,
                    language TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    public_user_id TEXT NOT NULL,
                    source_tag TEXT,
                    language TEXT,
                    user_mode TEXT,
                    state_name TEXT,
                    created_at TEXT NOT NULL,
                    last_event_at TEXT NOT NULL,
                    FOREIGN KEY(public_user_id) REFERENCES users(public_user_id)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    public_user_id TEXT NOT NULL,
                    session_id TEXT,
                    event TEXT NOT NULL,
                    state_name TEXT,
                    action TEXT,
                    user_mode TEXT,
                    language TEXT,
                    meta_json TEXT NOT NULL,
                    FOREIGN KEY(public_user_id) REFERENCES users(public_user_id),
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(public_user_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);
                CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events(session_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_state_ts ON events(state_name, timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_mode_ts ON events(user_mode, timestamp);

                CREATE TABLE IF NOT EXISTS events_archive (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    public_user_id TEXT NOT NULL,
                    session_id TEXT,
                    event TEXT NOT NULL,
                    state_name TEXT,
                    action TEXT,
                    user_mode TEXT,
                    language TEXT,
                    meta_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_archive_user_ts ON events_archive(public_user_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_archive_event_ts ON events_archive(event, timestamp);

                CREATE TABLE IF NOT EXISTS profile_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    public_user_id TEXT NOT NULL,
                    session_id TEXT,
                    source TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    FOREIGN KEY(public_user_id) REFERENCES users(public_user_id),
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_profile_versions_user_ts ON profile_versions(public_user_id, timestamp);

                CREATE TABLE IF NOT EXISTS reports (
                    report_generation_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    public_user_id TEXT NOT NULL,
                    session_id TEXT,
                    html_report_path TEXT,
                    pdf_report_path TEXT,
                    report_json TEXT NOT NULL,
                    FOREIGN KEY(public_user_id) REFERENCES users(public_user_id),
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )
            conn.commit()
        finally:
            conn.close()


def upsert_user(public_user_id: str, telegram_user_id: str, source_tag: str = "", language: str = "ru") -> None:
    if not str(public_user_id or "").strip():
        return
    try:
        init_storage()
        now = _utc_now()
        with _DB_LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """
                    INSERT INTO users (public_user_id, telegram_user_id, source_tag, language, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(public_user_id) DO UPDATE SET
                        telegram_user_id=excluded.telegram_user_id,
                        source_tag=CASE WHEN users.source_tag = '' THEN excluded.source_tag ELSE users.source_tag END,
                        language=excluded.language,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        str(public_user_id).strip(),
                        str(telegram_user_id or "").strip(),
                        str(source_tag or "").strip(),
                        str(language or "ru").strip(),
                        now,
                        now,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] upsert_user failed: {exc}", flush=True)


def create_session(
    session_id: str,
    public_user_id: str,
    *,
    source_tag: str = "",
    language: str = "ru",
    user_mode: str = "",
    state_name: str = "",
) -> None:
    if not str(session_id or "").strip() or not str(public_user_id or "").strip():
        return
    try:
        init_storage()
        now = _utc_now()
        with _DB_LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, public_user_id, source_tag, language, user_mode, state_name, created_at, last_event_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        state_name=excluded.state_name,
                        user_mode=excluded.user_mode,
                        language=excluded.language,
                        last_event_at=excluded.last_event_at
                    """,
                    (
                        str(session_id).strip(),
                        str(public_user_id).strip(),
                        str(source_tag or "").strip(),
                        str(language or "ru").strip(),
                        str(user_mode or "").strip(),
                        str(state_name or "").strip(),
                        now,
                        now,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] create_session failed: {exc}", flush=True)


def touch_session(session_id: str, *, state_name: str = "", user_mode: str = "", language: str = "ru") -> None:
    if not str(session_id or "").strip():
        return
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """
                    UPDATE sessions
                    SET state_name=?, user_mode=?, language=?, last_event_at=?
                    WHERE session_id=?
                    """,
                    (
                        str(state_name or "").strip(),
                        str(user_mode or "").strip(),
                        str(language or "ru").strip(),
                        _utc_now(),
                        str(session_id).strip(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] touch_session failed: {exc}", flush=True)


def record_event(
    *,
    public_user_id: str,
    event: str,
    state_name: str = "",
    action: str = "",
    user_mode: str = "",
    language: str = "ru",
    meta: dict[str, Any] | None = None,
    session_id: str = "",
    timestamp: str = "",
) -> None:
    if not str(public_user_id or "").strip() or not str(event or "").strip():
        return
    try:
        init_storage()
        ts = str(timestamp or "").strip() or _utc_now()
        with _DB_LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """
                    INSERT INTO events (
                        timestamp, public_user_id, session_id, event, state_name, action, user_mode, language, meta_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        str(public_user_id).strip(),
                        str(session_id or "").strip() or None,
                        str(event).strip(),
                        str(state_name or "").strip(),
                        str(action or "").strip(),
                        str(user_mode or "").strip(),
                        str(language or "ru").strip(),
                        json.dumps(meta or {}, ensure_ascii=False),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] record_event failed: {exc}", flush=True)


def save_profile_version(public_user_id: str, source: str, profile: dict[str, Any], *, session_id: str = "") -> None:
    if not str(public_user_id or "").strip() or not str(source or "").strip():
        return
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """
                    INSERT INTO profile_versions (timestamp, public_user_id, session_id, source, profile_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        _utc_now(),
                        str(public_user_id).strip(),
                        str(session_id or "").strip() or None,
                        str(source).strip(),
                        json.dumps(profile or {}, ensure_ascii=False),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] save_profile_version failed: {exc}", flush=True)


def save_report_version(
    report_generation_id: str,
    public_user_id: str,
    report: dict[str, Any],
    *,
    session_id: str = "",
    html_report_path: str = "",
    pdf_report_path: str = "",
) -> None:
    if not str(report_generation_id or "").strip() or not str(public_user_id or "").strip():
        return
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """
                    INSERT INTO reports (
                        report_generation_id, timestamp, public_user_id, session_id, html_report_path, pdf_report_path, report_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(report_generation_id) DO UPDATE SET
                        html_report_path=excluded.html_report_path,
                        pdf_report_path=excluded.pdf_report_path,
                        report_json=excluded.report_json
                    """,
                    (
                        str(report_generation_id).strip(),
                        _utc_now(),
                        str(public_user_id).strip(),
                        str(session_id or "").strip() or None,
                        str(html_report_path or "").strip(),
                        str(pdf_report_path or "").strip(),
                        json.dumps(report or {}, ensure_ascii=False),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] save_report_version failed: {exc}", flush=True)


def update_report_files(report_generation_id: str, *, html_report_path: str = "", pdf_report_path: str = "") -> None:
    if not str(report_generation_id or "").strip():
        return
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """
                    UPDATE reports
                    SET html_report_path = CASE WHEN ? <> '' THEN ? ELSE html_report_path END,
                        pdf_report_path = CASE WHEN ? <> '' THEN ? ELSE pdf_report_path END
                    WHERE report_generation_id = ?
                    """,
                    (
                        str(html_report_path or "").strip(),
                        str(html_report_path or "").strip(),
                        str(pdf_report_path or "").strip(),
                        str(pdf_report_path or "").strip(),
                        str(report_generation_id).strip(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] update_report_files failed: {exc}", flush=True)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def get_user(public_user_id: str) -> dict[str, Any] | None:
    if not str(public_user_id or "").strip():
        return None
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                row = conn.execute(
                    "SELECT * FROM users WHERE public_user_id = ?",
                    (str(public_user_id).strip(),),
                ).fetchone()
                return _row_to_dict(row)
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] get_user failed: {exc}", flush=True)
        return None


def get_latest_session(public_user_id: str) -> dict[str, Any] | None:
    if not str(public_user_id or "").strip():
        return None
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                row = conn.execute(
                    """
                    SELECT *
                    FROM sessions
                    WHERE public_user_id = ?
                    ORDER BY last_event_at DESC
                    LIMIT 1
                    """,
                    (str(public_user_id).strip(),),
                ).fetchone()
                return _row_to_dict(row)
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] get_latest_session failed: {exc}", flush=True)
        return None


def get_latest_profile(public_user_id: str) -> dict[str, Any] | None:
    if not str(public_user_id or "").strip():
        return None
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                row = conn.execute(
                    """
                    SELECT *
                    FROM profile_versions
                    WHERE public_user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    (str(public_user_id).strip(),),
                ).fetchone()
                payload = _row_to_dict(row)
                if not payload:
                    return None
                raw = str(payload.get("profile_json") or "{}").strip()
                try:
                    payload["profile"] = json.loads(raw)
                except Exception:
                    payload["profile"] = {}
                return payload
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] get_latest_profile failed: {exc}", flush=True)
        return None


def get_report_by_generation_id(report_generation_id: str) -> dict[str, Any] | None:
    if not str(report_generation_id or "").strip():
        return None
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                row = conn.execute(
                    "SELECT * FROM reports WHERE report_generation_id = ? LIMIT 1",
                    (str(report_generation_id).strip(),),
                ).fetchone()
                payload = _row_to_dict(row)
                if not payload:
                    return None
                raw = str(payload.get("report_json") or "{}").strip()
                try:
                    payload["report"] = json.loads(raw)
                except Exception:
                    payload["report"] = {}
                return payload
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] get_report_by_generation_id failed: {exc}", flush=True)
        return None


def get_latest_report(public_user_id: str) -> dict[str, Any] | None:
    if not str(public_user_id or "").strip():
        return None
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                row = conn.execute(
                    """
                    SELECT *
                    FROM reports
                    WHERE public_user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    (str(public_user_id).strip(),),
                ).fetchone()
                payload = _row_to_dict(row)
                if not payload:
                    return None
                raw = str(payload.get("report_json") or "{}").strip()
                try:
                    payload["report"] = json.loads(raw)
                except Exception:
                    payload["report"] = {}
                return payload
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] get_latest_report failed: {exc}", flush=True)
        return None


def get_recent_events(public_user_id: str, *, lookback_days: int = 7, limit: int = 5000) -> list[dict[str, Any]]:
    if not str(public_user_id or "").strip():
        return []
    try:
        init_storage()
        cutoff_iso = datetime.now(timezone.utc).timestamp() - max(1, int(lookback_days)) * 24 * 3600
        rows: list[dict[str, Any]] = []
        with _DB_LOCK:
            conn = _connect()
            try:
                for row in conn.execute(
                    """
                    SELECT timestamp, public_user_id, event, state_name, action, user_mode, language, meta_json
                    FROM events
                    WHERE public_user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (str(public_user_id).strip(), max(1, int(limit))),
                ).fetchall():
                    payload = _row_to_dict(row) or {}
                    ts_raw = str(payload.get("timestamp") or "").strip()
                    try:
                        dt = datetime.fromisoformat(ts_raw)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        continue
                    if dt.timestamp() < cutoff_iso:
                        continue
                    meta_raw = str(payload.get("meta_json") or "{}").strip()
                    try:
                        meta_obj = json.loads(meta_raw)
                    except Exception:
                        meta_obj = {}
                    rows.append(
                        {
                            "timestamp": ts_raw,
                            "public_user_id": str(payload.get("public_user_id") or "").strip(),
                            "event": str(payload.get("event") or "").strip(),
                            "state": str(payload.get("state_name") or "").strip(),
                            "action": str(payload.get("action") or "").strip(),
                            "user_mode": str(payload.get("user_mode") or "").strip(),
                            "language": str(payload.get("language") or "").strip(),
                            "meta": meta_obj,
                        }
                    )
            finally:
                conn.close()
        return rows
    except Exception as exc:
        print(f"[persistence] get_recent_events failed: {exc}", flush=True)
        return []


def get_recent_events_all(*, lookback_days: int = 30, limit: int = 200000) -> list[dict[str, Any]]:
    try:
        init_storage()
        cutoff_ts = datetime.now(timezone.utc).timestamp() - max(1, int(lookback_days)) * 24 * 3600
        rows: list[dict[str, Any]] = []
        with _DB_LOCK:
            conn = _connect()
            try:
                for row in conn.execute(
                    """
                    SELECT timestamp, public_user_id, event, state_name, action, user_mode, language, meta_json
                    FROM events
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),),
                ).fetchall():
                    payload = _row_to_dict(row) or {}
                    ts_raw = str(payload.get("timestamp") or "").strip()
                    try:
                        dt = datetime.fromisoformat(ts_raw)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        continue
                    if dt.timestamp() < cutoff_ts:
                        continue
                    meta_raw = str(payload.get("meta_json") or "{}").strip()
                    try:
                        meta_obj = json.loads(meta_raw)
                    except Exception:
                        meta_obj = {}
                    rows.append(
                        {
                            "timestamp": ts_raw,
                            "public_user_id": str(payload.get("public_user_id") or "").strip(),
                            "event": str(payload.get("event") or "").strip(),
                            "state": str(payload.get("state_name") or "").strip(),
                            "action": str(payload.get("action") or "").strip(),
                            "user_mode": str(payload.get("user_mode") or "").strip(),
                            "language": str(payload.get("language") or "").strip(),
                            "meta": meta_obj,
                        }
                    )
            finally:
                conn.close()
        return rows
    except Exception as exc:
        print(f"[persistence] get_recent_events_all failed: {exc}", flush=True)
        return []


def load_recovery_bundle(public_user_id: str) -> dict[str, Any]:
    return {
        "session": get_latest_session(public_user_id),
        "profile": get_latest_profile(public_user_id),
        "report": get_latest_report(public_user_id),
    }


def archive_and_prune_events(*, ttl_days: int = 30, batch_size: int = 5000) -> dict[str, int]:
    ttl = max(1, int(ttl_days))
    chunk = max(100, int(batch_size))
    cutoff_ts = datetime.now(timezone.utc).timestamp() - ttl * 24 * 3600

    moved_total = 0
    deleted_total = 0

    try:
        init_storage()
        while True:
            with _DB_LOCK:
                conn = _connect()
                try:
                    rows = conn.execute(
                        """
                        SELECT id, timestamp, public_user_id, session_id, event, state_name, action, user_mode, language, meta_json
                        FROM events
                        ORDER BY timestamp ASC
                        LIMIT ?
                        """,
                        (chunk,),
                    ).fetchall()
                    if not rows:
                        break

                    candidate_ids: list[int] = []
                    archive_rows: list[tuple[Any, ...]] = []
                    for row in rows:
                        payload = _row_to_dict(row) or {}
                        ts_raw = str(payload.get("timestamp") or "").strip()
                        try:
                            dt = datetime.fromisoformat(ts_raw)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                        except Exception:
                            continue
                        if dt.timestamp() >= cutoff_ts:
                            continue
                        row_id = int(payload.get("id") or 0)
                        if row_id <= 0:
                            continue
                        candidate_ids.append(row_id)
                        archive_rows.append(
                            (
                                row_id,
                                ts_raw,
                                str(payload.get("public_user_id") or "").strip(),
                                str(payload.get("session_id") or "").strip() or None,
                                str(payload.get("event") or "").strip(),
                                str(payload.get("state_name") or "").strip(),
                                str(payload.get("action") or "").strip(),
                                str(payload.get("user_mode") or "").strip(),
                                str(payload.get("language") or "").strip(),
                                str(payload.get("meta_json") or "{}"),
                            )
                        )

                    if not candidate_ids:
                        break

                    conn.executemany(
                        """
                        INSERT OR IGNORE INTO events_archive (
                            id, timestamp, public_user_id, session_id, event, state_name, action, user_mode, language, meta_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        archive_rows,
                    )
                    conn.executemany(
                        "DELETE FROM events WHERE id = ?",
                        [(row_id,) for row_id in candidate_ids],
                    )
                    conn.commit()

                    moved_total += len(archive_rows)
                    deleted_total += len(candidate_ids)
                finally:
                    conn.close()

        return {
            "moved_to_archive": moved_total,
            "deleted_from_events": deleted_total,
            "ttl_days": ttl,
        }
    except Exception as exc:
        print(f"[persistence] archive_and_prune_events failed: {exc}", flush=True)
        return {
            "moved_to_archive": moved_total,
            "deleted_from_events": deleted_total,
            "ttl_days": ttl,
        }


def optimize_storage() -> None:
    try:
        init_storage()
        with _DB_LOCK:
            conn = _connect()
            try:
                conn.execute("ANALYZE")
                conn.execute("PRAGMA optimize")
                conn.execute("VACUUM")
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        print(f"[persistence] optimize_storage failed: {exc}", flush=True)
