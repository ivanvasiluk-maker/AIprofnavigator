from __future__ import annotations

import pytest

from config import Settings


def test_default_career_assessment_budget_covers_generation_and_repair(monkeypatch) -> None:
    monkeypatch.delenv("CAREER_ASSESSMENT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OPENAI_JSON_CALL_TIMEOUT_SECONDS", raising=False)

    settings = Settings()

    assert settings.career_assessment_timeout_seconds == 180
    assert settings.openai_json_call_timeout_seconds == 70
    assert settings.openai_http_timeout_seconds == 60
    assert settings.openai_max_retries == 2
    assert settings.career_assessment_timeout_seconds > 2 * settings.openai_json_call_timeout_seconds


def test_invalid_career_assessment_budget_fails_fast(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("CAREER_ASSESSMENT_TIMEOUT_SECONDS", "100")
    monkeypatch.setenv("OPENAI_JSON_CALL_TIMEOUT_SECONDS", "70")

    with pytest.raises(ValueError, match="CAREER_ASSESSMENT_TIMEOUT_SECONDS"):
        Settings().validate()
