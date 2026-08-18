"""Provider boundary for auditable, current market evidence.

The application deliberately ships without a fake search implementation. Deployments
must configure a provider; otherwise report generation receives a concrete verification
plan and is prohibited from emitting numeric market claims.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MarketSource:
    source_url: str
    source_name: str
    country: str
    retrieved_at: str
    publication_date: str | None
    data_type: str
    confidence: str


@dataclass(slots=True)
class MarketResearchResult:
    route_title: str
    country: str
    sources: list[MarketSource] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    verification_plan: list[str] = field(default_factory=list)

    @property
    def permits_numeric_claims(self) -> bool:
        return bool(self.sources) and all(source.source_url.startswith(("https://", "http://")) for source in self.sources)


class MarketResearchProvider(Protocol):
    async def research(self, *, route_title: str, country: str, engagement_model: str) -> MarketResearchResult: ...


class UnavailableMarketResearchProvider:
    """Honest default used until a real provider is configured."""

    async def research(self, *, route_title: str, country: str, engagement_model: str) -> MarketResearchResult:
        return unavailable_market_result(route_title, country, engagement_model)


def unavailable_market_result(route_title: str, country: str, engagement_model: str) -> MarketResearchResult:
    """Synchronous safe result for deterministic report repair/rendering paths."""
    market = country or "выбранном рынке"
    plan = [
        f"Собрать 10 актуальных предложений «{route_title}» на рынке {market} из официальной службы занятости и крупного сайта вакансий.",
        "Зафиксировать URL, дату публикации, валюту, период и gross/net для каждого предложения.",
    ]
    if any(marker in engagement_model.casefold() for marker in ("самостоят", "b2b", "частн", "бизнес")):
        plan.append("Проверить 5 предложений конкурентов и рассчитать продажи × средний чек минус налоги, материалы, маркетинг, транспорт, инфраструктуру и простой.")
    else:
        plan.append("Сравнить повторяющиеся задачи, обязательные требования, язык, тип договора и формат работы у минимум трёх работодателей.")
    return MarketResearchResult(route_title=route_title, country=country, verification_plan=plan)


def retrieved_now() -> str:
    return datetime.now(timezone.utc).isoformat()
