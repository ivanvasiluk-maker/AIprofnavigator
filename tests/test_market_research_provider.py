import asyncio

from services.market_research import UnavailableMarketResearchProvider


def test_unavailable_provider_never_invents_sources_or_numeric_claims():
    result = asyncio.run(UnavailableMarketResearchProvider().research(
        route_title="Конкретная рыночная роль", country="Литва", engagement_model="employment",
    ))
    assert result.sources == []
    assert not result.permits_numeric_claims
    assert len(result.verification_plan) == 3
    assert "10" in result.verification_plan[0]
