"""Country-aware market strategy contract, normalization and deterministic checks."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import re
from typing import Any, Literal

Confidence = Literal["low", "medium", "high"]

ENTRY_PATH_LABELS = {
    "direct_entry": "можно начинать проверять сейчас",
    "adjacent_transition": "переход через смежную функцию",
    "bridge_project": "сначала нужен подтверждающий проект",
    "retraining_required": "сначала требуется подтверждённое переобучение",
    "not_recommended_now": "сейчас маршрут не рекомендуется",
    "route_check_required": "нужно проверить требования выбранного маршрута",
}
TECHNICAL_TOKENS = frozenset((*ENTRY_PATH_LABELS, "assessment_id", "validation_score"))
SCENARIO_KINDS = ("safe", "main", "ambitious")

COUNTRY_RULES = {
    "LT": {"names": {"литва", "lithuania"}, "currency": "EUR", "languages": {"литовский", "lithuanian"}},
    "PL": {"names": {"польша", "poland"}, "currency": "PLN", "languages": {"польский", "polish"}},
    "DE": {"names": {"германия", "germany"}, "currency": "EUR", "languages": {"немецкий", "german"}},
    "US": {"names": {"сша", "usa", "united states"}, "currency": "USD", "languages": {"английский", "english"}, "requires_region": True},
}
CITY_COUNTRIES = {
    "vilnius": "LT", "вильнюс": "LT", "kaunas": "LT", "каунас": "LT",
    "warsaw": "PL", "варшава": "PL", "krakow": "PL", "краков": "PL",
    "berlin": "DE", "берлин": "DE", "munich": "DE", "мюнхен": "DE",
    "new york": "US", "нью-йорк": "US", "chicago": "US", "чикаго": "US",
}
AMBIGUOUS_CITIES = {"springfield", "сан-хосе", "san jose", "frankfurt", "франкфурт"}


@dataclass(slots=True)
class MarketSource:
    source_url: str
    source_name: str
    country: str
    data_type: str
    confidence: Confidence
    publication_date: str | None = None
    retrieved_at: str | None = None


@dataclass(slots=True)
class VacancyRecord:
    title: str
    country: str
    city: str | None
    work_mode: str
    language: str
    level: str
    salary: str | None
    required_skills: list[str]
    preferred_skills: list[str]
    education: str | None
    licenses: list[str]
    years_experience: str | None
    contract_type: str
    source_url: str


@dataclass(slots=True)
class CareerStrategy:
    market_context: dict[str, Any] = field(default_factory=dict)
    route_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    selected_routes: list[dict[str, Any]] = field(default_factory=list)
    market_analysis: list[dict[str, Any]] = field(default_factory=list)
    income_forecasts: list[dict[str, Any]] = field(default_factory=list)
    development_scenarios: list[dict[str, Any]] = field(default_factory=list)
    personal_insights: list[dict[str, Any]] = field(default_factory=list)
    psychological_social_conditions: list[dict[str, Any]] = field(default_factory=list)
    career_action_plan: dict[str, Any] = field(default_factory=dict)
    final_recommendation: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "CareerStrategy":
        data = payload if isinstance(payload, dict) else {}
        return cls(**{name: data.get(name, default) for name, default in (
            ("market_context", {}), ("route_hypotheses", []), ("selected_routes", []),
            ("market_analysis", []), ("income_forecasts", []), ("development_scenarios", []),
            ("personal_insights", []), ("psychological_social_conditions", []),
            ("career_action_plan", {}), ("final_recommendation", {}),
        )})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def humanize_internal_values(value: Any) -> Any:
    """Recursively remove internal ids and convert known enums for rendering."""
    if isinstance(value, dict):
        return {key: humanize_internal_values(item) for key, item in value.items() if key not in {"assessment_id", "session_id", "profile_version", "validation_score"}}
    if isinstance(value, list):
        return [humanize_internal_values(item) for item in value]
    if isinstance(value, str):
        result = value
        for token, label in ENTRY_PATH_LABELS.items():
            result = result.replace(token, label)
        return result
    return value


def country_rule(country: str | None) -> tuple[str | None, dict[str, Any] | None]:
    normalized = str(country or "").strip().casefold()
    for code, rule in COUNTRY_RULES.items():
        if normalized == code.casefold() or normalized in rule["names"]:
            return code, rule
    return None, None


def resolve_city_country(city: str | None) -> dict[str, str | bool | None]:
    """Resolve well-known unambiguous cities; explicitly flag ambiguous names."""
    normalized = str(city or "").strip().casefold()
    if not normalized:
        return {"country_code": None, "needs_clarification": False}
    if normalized in AMBIGUOUS_CITIES:
        return {"country_code": None, "needs_clarification": True}
    return {"country_code": CITY_COUNTRIES.get(normalized), "needs_clarification": normalized not in CITY_COUNTRIES}


def critical_market_gaps(profile: Any, asked: set[str] | None = None) -> list[str]:
    """Return unresolved market gaps in fixed decision-impact order."""
    asked = asked or set()
    checks = (
        ("residence_country", getattr(profile, "residence_country", None)),
        ("target_country", getattr(profile, "target_countries", [])),
        ("work_authorization", getattr(profile, "work_authorization", None)),
        ("work_languages", getattr(profile, "work_languages", [])),
        ("minimum_income", getattr(profile, "minimum_income", None)),
        ("income_deadline", getattr(profile, "income_deadline", None)),
        ("work_format", getattr(profile, "work_format_preferences", [])),
        ("desired_change", getattr(profile, "desired_change_scale", None)),
    )
    return [key for key, value in checks if key not in asked and not value]


def income_calculator(model: str, **values: float) -> dict[str, float | str]:
    model = model.casefold()
    if model == "group":
        gross = values.get("price_per_participant", 0) * values.get("participants", 0)
        return {"formula": "price_per_participant × participants", "gross_revenue": gross}
    if model == "product":
        gross = values.get("price", 0) * values.get("paying_users", 0)
        costs = sum(values.get(key, 0) for key in ("acquisition_costs", "infrastructure", "support"))
        return {"formula": "price × paying_users − acquisition_costs − infrastructure − support", "gross_revenue": gross, "forecast_income": gross - costs}
    gross = values.get("price", 0) * values.get("clients_or_sales", 0)
    costs = sum(values.get(key, 0) for key in ("taxes", "platform_costs", "marketing", "operating_costs"))
    return {"formula": "price × clients_or_sales − taxes − platform_costs − marketing − operating_costs", "gross_revenue": gross, "forecast_income": gross - costs}


def _valid_date(value: Any) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value or "")))


def _source_errors(source: Any, path: str) -> list[str]:
    if not isinstance(source, dict):
        return [f"[CRITICAL] {path} must be an object."]
    required = {"source_url", "source_name", "country", "data_type", "confidence"}
    missing = sorted(key for key in required if not source.get(key))
    errors = [f"[CRITICAL] {path} misses: {', '.join(missing)}."] if missing else []
    if not source.get("publication_date") and not source.get("retrieved_at"):
        errors.append(f"[CRITICAL] {path} requires publication_date or retrieved_at.")
    return errors


def _route_model_key(route: dict[str, Any]) -> tuple[str, str, str]:
    return tuple(str(route.get(key) or "").strip().casefold() for key in ("income_model", "buyer_type", "daily_tasks_summary"))


def validate_market_strategy(report: dict[str, Any], *, strict: bool | None = None) -> list[str]:
    """Validate complete market strategy without inventing unavailable claims."""
    errors: list[str] = []
    strict = bool(report.get("market_strategy_required")) if strict is None else strict
    context = report.get("market_context") if isinstance(report.get("market_context"), dict) else {}
    countries = context.get("target_countries") if isinstance(context.get("target_countries"), list) else []
    if not countries and context.get("target_country"):
        countries = [context["target_country"]]
    if not countries and context.get("residence_country"):
        countries = [context["residence_country"]]
    country_codes = {code for country in countries if (code := country_rule(str(country))[0])}

    hypotheses = report.get("route_hypotheses") if isinstance(report.get("route_hypotheses"), list) else []
    routes = report.get("selected_routes") if isinstance(report.get("selected_routes"), list) else []
    if strict and not 6 <= len(hypotheses) <= 12:
        errors.append("[CRITICAL] route_hypotheses must contain 6 to 12 hypotheses.")
    if strict and not 3 <= len(routes) <= 5:
        errors.append("[CRITICAL] selected_routes must contain 3 to 5 routes.")
    seen_models: set[tuple[str, str, str]] = set()
    for idx, route in enumerate(routes):
        if not isinstance(route, dict):
            continue
        required = {"route_id", "title", "income_model", "buyer_type", "daily_tasks", "risk_level", "entry_time", "requirements", "income_ceiling", "scalability", "psychological_load"}
        missing = sorted(key for key in required if not route.get(key))
        if missing:
            errors.append(f"[CRITICAL] selected_routes[{idx}] misses: {', '.join(missing)}.")
        key = _route_model_key({**route, "daily_tasks_summary": " ".join(route.get("daily_tasks") or [])})
        if key in seen_models:
            errors.append(f"[CRITICAL] selected_routes[{idx}] duplicates an earning model, buyer, and daily work.")
        seen_models.add(key)

    analyses = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
    if strict and countries and not analyses:
        errors.append("[CRITICAL] Known target country requires market_analysis.")
    analyzed_codes: set[str] = set()
    for idx, row in enumerate(analyses):
        if not isinstance(row, dict):
            continue
        row_code, _ = country_rule(str(row.get("country") or ""))
        if row_code:
            analyzed_codes.add(row_code)
        if country_codes and row_code and row_code not in country_codes:
            errors.append(f"[CRITICAL] market_analysis[{idx}] analyzes a country that is not the selected country.")
        sources = row.get("sources") if isinstance(row.get("sources"), list) else []
        for source_idx, source in enumerate(sources):
            errors += _source_errors(source, f"market_analysis[{idx}].sources[{source_idx}]")
        if row.get("market_claims") and len(sources) < 2:
            errors.append(f"[CRITICAL] market_analysis[{idx}] needs two independent sources for market claims.")
        source_hosts = {str(source.get("source_url") or "").split("/")[2] for source in sources if isinstance(source, dict) and "/" in str(source.get("source_url") or "")}
        if row.get("market_claims") and len(source_hosts) < 2:
            errors.append(f"[CRITICAL] market_analysis[{idx}] sources are not independent.")
        sample_size = row.get("vacancy_sample_size")
        narrow = bool(row.get("narrow_role"))
        minimum = 5 if narrow else 10
        if isinstance(sample_size, int) and sample_size < minimum and row.get("status") != "insufficient_data":
            errors.append(f"[CRITICAL] market_analysis[{idx}] needs at least {minimum} vacancies or an explicit insufficient-data conclusion.")
            if sample_size == 1:
                errors.append(f"[CRITICAL] market_analysis[{idx}] cannot be based on one vacancy.")
        vacancies = row.get("vacancies") if isinstance(row.get("vacancies"), list) else []
        if vacancies and sample_size != len(vacancies):
            errors.append(f"[CRITICAL] market_analysis[{idx}] vacancy_sample_size does not match vacancies.")
        vacancy_fields = {"title", "country", "work_mode", "language", "level", "required_skills", "preferred_skills", "licenses", "contract_type", "source_url"}
        for vacancy_idx, vacancy in enumerate(vacancies):
            missing = sorted(key for key in vacancy_fields if not isinstance(vacancy, dict) or vacancy.get(key) is None)
            if missing:
                errors.append(f"[CRITICAL] market_analysis[{idx}].vacancies[{vacancy_idx}] misses: {', '.join(missing)}.")
        if row.get("regulated_profession") is True and not row.get("licensing_check"):
            errors.append(f"[CRITICAL] market_analysis[{idx}] lacks a licensing check.")
        if row_code == "US" and row.get("regulated_profession") is True and not row.get("region"):
            errors.append(f"[CRITICAL] market_analysis[{idx}] requires a US state for licensing.")
        _, rule = country_rule(str(row.get("country") or ""))
        if rule and row.get("local_market") is True and not row.get("language_analysis"):
            errors.append(f"[CRITICAL] market_analysis[{idx}] lacks local-language analysis.")
    if strict and len(country_codes) > 1:
        if not country_codes.issubset(analyzed_codes):
            errors.append("[CRITICAL] Every selected country requires separate market analysis.")
        comparison = report.get("market_comparison")
        if not isinstance(comparison, dict) or not comparison.get("primary_market") or not comparison.get("reserve_market") or not comparison.get("switch_condition"):
            errors.append("[CRITICAL] Multiple countries require primary, reserve, and switch-condition comparison.")

    forecasts = report.get("income_forecasts") if isinstance(report.get("income_forecasts"), list) else []
    if strict and countries and not forecasts:
        errors.append("[CRITICAL] Known market requires income_forecasts or an explicit unavailable-data forecast.")
    required_forecast = {"route_id", "country", "currency", "amount_type", "period", "contract_type", "data_date", "confidence", "sources", "estimates", "conditions"}
    for idx, forecast in enumerate(forecasts):
        if not isinstance(forecast, dict):
            continue
        if forecast.get("status") == "data_unavailable":
            if forecast.get("estimates"):
                errors.append(f"[CRITICAL] income_forecasts[{idx}] must not invent estimates when data is unavailable.")
            continue
        missing = sorted(key for key in required_forecast if not forecast.get(key))
        if missing:
            errors.append(f"[CRITICAL] income_forecasts[{idx}] misses: {', '.join(missing)}.")
            continue
        _, rule = country_rule(str(forecast.get("country")))
        if rule and str(forecast.get("currency")).upper() != rule["currency"]:
            errors.append(f"[CRITICAL] income_forecasts[{idx}] currency does not match country.")
        if str(forecast.get("amount_type")).casefold() not in {"gross", "net", "revenue"}:
            errors.append(f"[CRITICAL] income_forecasts[{idx}] must identify gross, net, or revenue.")
        if not _valid_date(forecast.get("data_date")):
            errors.append(f"[CRITICAL] income_forecasts[{idx}] requires an ISO data date.")
        estimates = forecast.get("estimates") if isinstance(forecast.get("estimates"), dict) else {}
        if not all(estimates.get(key) is not None for key in ("conservative", "base", "optimistic")):
            errors.append(f"[CRITICAL] income_forecasts[{idx}] requires three estimates.")
        sources = forecast.get("sources") if isinstance(forecast.get("sources"), list) else []
        if len(sources) < 2:
            errors.append(f"[CRITICAL] income_forecasts[{idx}] requires two independent sources.")
        source_hosts = {str(source.get("source_url") or "").split("/")[2] for source in sources if isinstance(source, dict) and "/" in str(source.get("source_url") or "")}
        if len(source_hosts) < 2:
            errors.append(f"[CRITICAL] income_forecasts[{idx}] sources are not independent.")
        for source_idx, source in enumerate(sources):
            errors += _source_errors(source, f"income_forecasts[{idx}].sources[{source_idx}]")

    scenarios = report.get("development_scenarios") if isinstance(report.get("development_scenarios"), list) else []
    scenario_fields = {"kind", "market", "horizon", "goal", "employment_model", "preserves", "adds", "income_forecast", "investment", "hours_per_week", "actions", "checkpoints", "success_criterion", "stop_criterion", "risks", "fallback"}
    kinds = {str(item.get("kind")) for item in scenarios if isinstance(item, dict)}
    if strict and not set(SCENARIO_KINDS).issubset(kinds):
        errors.append("[CRITICAL] Development scenarios must include safe, main, and ambitious.")
    for idx, scenario in enumerate(scenarios):
        if isinstance(scenario, dict):
            missing = sorted(key for key in scenario_fields if not scenario.get(key))
            if missing:
                errors.append(f"[CRITICAL] development_scenarios[{idx}] misses: {', '.join(missing)}.")

    insights = report.get("personal_insights") if isinstance(report.get("personal_insights"), list) else []
    if strict and not 3 <= len(insights) <= 5:
        errors.append("[CRITICAL] Three to five personal insights are required.")
    valid_fact_ids = set(report.get("evidence_fact_ids") or [])
    for idx, insight in enumerate(insights):
        ids = insight.get("evidence_fact_ids") if isinstance(insight, dict) else []
        if not isinstance(insight, dict) or len(set(ids or [])) < 2 or not insight.get("practical_consequence") or not insight.get("route_impact"):
            errors.append(f"[CRITICAL] personal_insights[{idx}] needs two facts, route impact, and consequence.")
        elif valid_fact_ids and set(ids) - valid_fact_ids:
            errors.append(f"[CRITICAL] personal_insights[{idx}] references unknown evidence facts.")

    conditions = report.get("psychological_social_conditions") if isinstance(report.get("psychological_social_conditions"), list) else []
    condition_fields = {"factor_type", "evidence_fact_ids", "career_impact", "riskier_scenario", "environment_change", "behavioral_tool"}
    for idx, condition in enumerate(conditions):
        missing = sorted(key for key in condition_fields if not isinstance(condition, dict) or not condition.get(key))
        if missing:
            errors.append(f"[CRITICAL] psychological_social_conditions[{idx}] misses: {', '.join(missing)}.")

    action_plan = report.get("career_action_plan") if isinstance(report.get("career_action_plan"), dict) else {}
    action_fields = {"what", "where", "audience", "volume", "duration", "success_criterion", "change_criterion"}
    for horizon in ("48_hours", "14_days", "90_days"):
        action = action_plan.get(horizon)
        if strict and not isinstance(action, dict):
            errors.append(f"[CRITICAL] career_action_plan.{horizon} is required.")
        elif isinstance(action, dict):
            missing = sorted(key for key in action_fields if not action.get(key))
            if missing:
                errors.append(f"[CRITICAL] career_action_plan.{horizon} misses: {', '.join(missing)}.")

    recommendation = report.get("final_recommendation") if isinstance(report.get("final_recommendation"), dict) else {}
    recommendation_fields = {"recommended_route_id", "why", "why_not_competitors", "realistic_income", "first_action", "pre_investment_check", "review_date", "next_scenario_condition"}
    if strict:
        missing = sorted(key for key in recommendation_fields if not recommendation.get(key))
        if missing:
            errors.append(f"[CRITICAL] final_recommendation misses: {', '.join(missing)}.")
        route_ids = {str(route.get("route_id")) for route in routes if isinstance(route, dict)}
        if recommendation.get("recommended_route_id") and recommendation["recommended_route_id"] not in route_ids:
            errors.append("[CRITICAL] final_recommendation references an unknown route.")

    user_blob = " ".join(_all_strings(humanize_internal_values(report))).casefold()
    leaked = sorted(token for token in TECHNICAL_TOKENS if token in user_blob)
    if leaked:
        errors.append(f"[CRITICAL] User-facing strategy leaks internal values: {', '.join(leaked)}.")
    return errors


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [text for item in value.values() for text in _all_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _all_strings(item)]
    return [value] if isinstance(value, str) else []


def preliminary_market_plan(country: str | None, route: str) -> dict[str, Any]:
    return {
        "country": country or "не определена", "route": route, "status": "предварительная гипотеза",
        "limitation": "Актуальные рыночные источники не подключены; зарплата не оценивалась.",
        "research_plan": [
            "Собрать 10 актуальных вакансий (5 для узкой роли) из двух независимых каналов.",
            "Проверить повторяющиеся требования, язык, договор и опубликованные диапазоны оплаты.",
            f"Проверить лицензирование в официальном реестре страны на {date.today().isoformat()}.",
        ],
    }
