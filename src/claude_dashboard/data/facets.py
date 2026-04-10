import json
from pathlib import Path

import pandas as pd

OUTCOME_SCORES = {
    "not_achieved": 0.0,
    "partially_achieved": 0.33,
    "mostly_achieved": 0.67,
    "achieved": 1.0,
    "fully_achieved": 1.0,
}

HELPFULNESS_SCORES = {
    "unhelpful": 0.0,
    "slightly_helpful": 0.33,
    "somewhat_helpful": 0.5,
    "moderately_helpful": 0.67,
    "very_helpful": 1.0,
}


def load_facets(claude_dir: Path) -> pd.DataFrame:
    """Load all session facets files into a DataFrame."""
    facets_dir = claude_dir / "usage-data" / "facets"
    if not facets_dir.exists():
        return _empty_df()

    records = []
    for f in facets_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            records.append(_parse_facet(data))
        except (json.JSONDecodeError, KeyError):
            continue

    if not records:
        return _empty_df()

    df = pd.DataFrame(records)
    df["outcome_score"] = df["outcome"].map(OUTCOME_SCORES).fillna(0.0)
    df["helpfulness_score"] = df["helpfulness"].map(HELPFULNESS_SCORES).fillna(0.0)
    df["satisfaction_score"] = df["user_satisfaction_counts"].apply(_compute_satisfaction)
    return df


SATISFACTION_WEIGHTS = {
    "likely_satisfied": 1.0,
    "neutral": 0.0,
    "likely_dissatisfied": -1.0,
    "dissatisfied": -1.0,
    "frustrated": -2.0,
}


def _parse_facet(data: dict) -> dict:
    return {
        "session_id": data.get("session_id", ""),
        "underlying_goal": data.get("underlying_goal", ""),
        "goal_categories": data.get("goal_categories", {}),
        "outcome": data.get("outcome", ""),
        "helpfulness": data.get("claude_helpfulness", ""),
        "session_type": data.get("session_type", ""),
        "friction_counts": data.get("friction_counts", {}),
        "friction_detail": data.get("friction_detail", ""),
        "primary_success": data.get("primary_success", ""),
        "brief_summary": data.get("brief_summary", ""),
        "user_satisfaction_counts": data.get("user_satisfaction_counts", {}),
    }


def _compute_satisfaction(counts: dict) -> float:
    if not isinstance(counts, dict) or not counts:
        return float("nan")
    total_weight = 0.0
    total_count = 0
    for key, count in counts.items():
        weight = SATISFACTION_WEIGHTS.get(key, 0.0)
        total_weight += weight * count
        total_count += count
    if total_count == 0:
        return float("nan")
    return max(-1.0, min(1.0, total_weight / total_count))


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "session_id", "underlying_goal", "goal_categories", "outcome",
            "helpfulness", "session_type", "friction_counts", "friction_detail",
            "primary_success", "brief_summary", "outcome_score",
            "helpfulness_score", "user_satisfaction_counts", "satisfaction_score",
        ]
    )
