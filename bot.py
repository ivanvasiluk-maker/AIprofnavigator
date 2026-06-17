import asyncio
import hashlib
import socket
import sys
from contextlib import suppress

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import Update

from config import settings
from handlers import career, start, voice


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


async def main() -> None:
    settings.validate()

    guard = SingleInstanceGuard(settings.bot_token)
    if not guard.acquire():
        print("Local instance is already running. Stop other local bot.py process and retry.")
        sys.exit(1)

    print("Starting bot polling...", flush=True)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    dp.update.outer_middleware(DedupMiddleware())

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
