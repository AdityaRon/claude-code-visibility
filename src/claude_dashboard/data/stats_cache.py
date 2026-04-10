import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    web_search_requests: int = 0
    cost_usd: float = 0.0


@dataclass
class StatsCache:
    version: int = 0
    last_computed_date: str = ""
    daily_activity: list[dict] = field(default_factory=list)
    daily_model_tokens: list[dict] = field(default_factory=list)
    model_usage: dict[str, ModelUsage] = field(default_factory=dict)
    total_sessions: int = 0
    total_messages: int = 0
    hour_counts: dict[str, int] = field(default_factory=dict)
    total_speculation_time_saved_ms: int = 0


def load_stats_cache(claude_dir: Path) -> StatsCache:
    """Load the stats-cache.json file."""
    path = claude_dir / "stats-cache.json"
    if not path.exists():
        return StatsCache()

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return StatsCache()

    model_usage = {}
    for model, usage in data.get("modelUsage", {}).items():
        model_usage[model] = ModelUsage(
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            cache_read_input_tokens=usage.get("cacheReadInputTokens", 0),
            cache_creation_input_tokens=usage.get("cacheCreationInputTokens", 0),
            web_search_requests=usage.get("webSearchRequests", 0),
            cost_usd=usage.get("costUSD", 0.0),
        )

    return StatsCache(
        version=data.get("version", 0),
        last_computed_date=data.get("lastComputedDate", ""),
        daily_activity=data.get("dailyActivity", []),
        daily_model_tokens=data.get("dailyModelTokens", []),
        model_usage=model_usage,
        total_sessions=data.get("totalSessions", 0),
        total_messages=data.get("totalMessages", 0),
        hour_counts=data.get("hourCounts", {}),
        total_speculation_time_saved_ms=data.get("totalSpeculationTimeSavedMs", 0),
    )
