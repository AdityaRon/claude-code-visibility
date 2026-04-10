from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from claude_dashboard.config import CLAUDE_DIR
from claude_dashboard.data.session_meta import load_session_meta
from claude_dashboard.data.facets import load_facets
from claude_dashboard.data.stats_cache import load_stats_cache, StatsCache
from claude_dashboard.data.history import load_history


@dataclass
class DashboardData:
    sessions: pd.DataFrame
    stats: StatsCache
    history: pd.DataFrame
    claude_dir: Path


@st.cache_data(ttl=300)
def load_all_data(_claude_dir: Path = None) -> dict:
    """Load all data sources and merge sessions with facets.

    Returns a dict (for Streamlit cache serialization) with keys:
    sessions, stats, history, claude_dir.
    """
    claude_dir = _claude_dir or CLAUDE_DIR

    sessions_df = load_session_meta(claude_dir)
    facets_df = load_facets(claude_dir)
    stats = load_stats_cache(claude_dir)
    history_df = load_history(claude_dir)

    # Left join: not all sessions have facets
    if not facets_df.empty and not sessions_df.empty:
        facet_cols = [
            "session_id", "underlying_goal", "goal_categories", "outcome",
            "helpfulness", "session_type", "friction_counts", "friction_detail",
            "primary_success", "brief_summary", "outcome_score",
            "helpfulness_score", "user_satisfaction_counts", "satisfaction_score",
        ]
        existing = [c for c in facet_cols if c in facets_df.columns]
        sessions_df = sessions_df.merge(
            facets_df[existing], on="session_id", how="left"
        )

    return {
        "sessions": sessions_df,
        "stats": stats,
        "history": history_df,
        "claude_dir": str(claude_dir),
    }


def get_data() -> DashboardData:
    """Convenience wrapper that returns a typed DashboardData."""
    raw = load_all_data()
    return DashboardData(
        sessions=raw["sessions"],
        stats=raw["stats"],
        history=raw["history"],
        claude_dir=Path(raw["claude_dir"]),
    )
