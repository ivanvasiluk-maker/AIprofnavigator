from __future__ import annotations

from aiogram.fsm.storage.memory import MemoryStorage

import bot


def test_memory_storage_is_default(monkeypatch) -> None:
    monkeypatch.setattr(bot.settings, "redis_url", "")

    assert isinstance(bot.build_fsm_storage(), MemoryStorage)


def test_redis_storage_is_selected_when_url_is_configured(monkeypatch) -> None:
    class FakeRedisStorage:
        @classmethod
        def from_url(cls, url: str):
            return {"storage": "redis", "url": url}

    monkeypatch.setattr(bot.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setitem(__import__("sys").modules, "aiogram.fsm.storage.redis", type("M", (), {"RedisStorage": FakeRedisStorage}))

    assert bot.build_fsm_storage() == {"storage": "redis", "url": "redis://localhost:6379/0"}
