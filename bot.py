import asyncio
import hashlib
import json
import os
import socket
import sys
from contextlib import suppress

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from config import settings
from handlers import career, start, voice
from services.career_assessment import (
    CAREER_HTML_RENDERER_VERSION,
    CAREER_PIPELINE_VERSION,
    CAREER_TELEGRAM_RENDERER_VERSION,
)
from utils.persistence import save_profile_version, touch_session


class SingleInstanceGuard:
    """Keep one local bot process per machine by reserving a TCP port."""

    def __init__(self, key: str) -> None:
        self._key = key
        self._sock: socket.socket | None = None

    @staticmethod
    def _port_from_key(key: str) -> int:
        # Stable user-space port in a safe range across all Python processes.
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return 42000 + (int(digest[:8], 16) % 1500)

    def acquire(self) -> bool:
        port = self._port_from_key(self._key)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            sock.listen(1)
            self._sock = sock
            return True
        except OSError:
            with suppress(Exception):
                sock.close()
            return False

    def release(self) -> None:
        if self._sock is not None:
            with suppress(Exception):
                self._sock.close()
            self._sock = None


class DedupMiddleware(BaseMiddleware):
    """Discard exact-duplicate Telegram updates by update_id."""

    def __init__(self) -> None:
        self._seen: set[int] = set()

    async def __call__(self, handler, event: Update, data: dict):  # type: ignore[override]
        uid = event.update_id
        if uid in self._seen:
            return
        self._seen.add(uid)
        if len(self._seen) > 2000:
            self._seen = set(list(self._seen)[1000:])
        return await handler(event, data)


class SessionCheckpointMiddleware(BaseMiddleware):
    """Persist FSM progress so a Railway restart does not reset an active interview."""

    async def __call__(self, handler, event: Update, data: dict):  # type: ignore[override]
        result = await handler(event, data)
        fsm_state = data.get("state")
        if fsm_state is None:
            return result
        try:
            state_name = str(await fsm_state.get_state() or "").strip()
            snapshot = await fsm_state.get_data()
            session_id = str(snapshot.get("session_id") or "").strip()
            public_user_id = str(snapshot.get("public_user_id") or "").strip()
            if not session_id or not public_user_id:
                return result
            touch_session(
                session_id,
                state_name=state_name,
                user_mode=str(snapshot.get("user_mode") or ""),
                language=str(snapshot.get("language") or "ru"),
            )
            if state_name.endswith((":INTERVIEW", ":ROUTE_CONTEXT", ":REPORT_NEEDS_CLARIFICATION")):
                save_profile_version(
                    public_user_id,
                    "fsm_checkpoint",
                    {
                        "session_id": session_id,
                        "language": snapshot.get("language", "ru"),
                        "user_mode": snapshot.get("user_mode", "calm_steps"),
                        "story_text": snapshot.get("story_text", ""),
                        "story_analysis": snapshot.get("story_analysis", {}),
                        "qa_answers": snapshot.get("qa_answers", []),
                        "qa_index": snapshot.get("qa_index", 0),
                        "question_count": snapshot.get("question_count", 0),
                        "answers_text": snapshot.get("answers_text", ""),
                        "evidence_profile": snapshot.get("evidence_profile", {}),
                        "interview_context": snapshot.get("interview_context", {}),
                        "asked_question_signatures": snapshot.get("asked_question_signatures", []),
                        "active_canonical_question": snapshot.get("active_canonical_question", {}),
                        "question_state": snapshot.get("question_state", {}),
                        "route_context": snapshot.get("route_context", {}),
                        "route_context_index": snapshot.get("route_context_index", 0),
                        "route_context_question_id": snapshot.get("route_context_question_id", ""),
                        "interaction_profile": snapshot.get("interaction_profile", {}),
                    },
                    session_id=session_id,
                )
        except Exception as exc:
            print(f"[checkpoint] failed: {exc}", flush=True)
        return result


def build_fsm_storage():
    if settings.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage

        return RedisStorage.from_url(settings.redis_url)
    return MemoryStorage()


async def main() -> None:
    settings.validate()

    guard = SingleInstanceGuard(settings.bot_token)
    if not guard.acquire():
        print("Local instance is already running. Stop other local bot.py process and retry.")
        sys.exit(1)

    print(
        json.dumps(
            {
                "event": "career_pipeline_started",
                "commit_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA") or "unknown",
                "build_commit": os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA") or "unknown",
                "build_time": os.getenv("BUILD_TIME") or "see .build_time",
                "environment": settings.environment,
                "pipeline_version": CAREER_PIPELINE_VERSION,
                "telegram_renderer_version": CAREER_TELEGRAM_RENDERER_VERSION,
                "html_renderer_version": CAREER_HTML_RENDERER_VERSION,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print("Starting bot polling...", flush=True)
    webhook_configured = bool(str(settings.google_sheets_webhook_url or "").strip())
    print(
        "Analytics status: "
        + ("Google Sheets connected" if webhook_configured else "Google Sheets not configured")
        + f", CSV={settings.analytics_excel_log_path}",
        flush=True,
    )

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=build_fsm_storage())

    dp.update.outer_middleware(DedupMiddleware())
    dp.update.outer_middleware(SessionCheckpointMiddleware())

    dp.include_router(start.router)
    dp.include_router(career.router)
    dp.include_router(voice.router)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        print("Bot is running and waiting for Telegram updates.", flush=True)
        await dp.start_polling(bot)
    finally:
        guard.release()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Bot startup failed: {exc}", flush=True)
        raise
