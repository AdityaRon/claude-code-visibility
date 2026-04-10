import pandas as pd
import plotly.express as px
import streamlit as st

from claude_dashboard.components.charts import activity_heatmap
from claude_dashboard.components.filters import apply_filters
from claude_dashboard.components.kpi_cards import render_kpi_row
from claude_dashboard.config import estimate_cost
from claude_dashboard.data.loader import get_data
from claude_dashboard.data.transcripts import load_all_transcript_tokens


def render():
    st.header("Overview")

    data = get_data()
    df = apply_filters(data.sessions)

    if df.empty:
        st.info("No session data found. Use Claude Code to generate usage data.")
        return

    # --- KPI Row ---
    total_sessions = len(df)

    # Compute cost from transcript data (includes cache tokens for accurate pricing)
    transcript_df = load_all_transcript_tokens(str(data.claude_dir))
    if not transcript_df.empty:
        total_input = int(transcript_df["input_tokens"].sum())
        total_output = int(transcript_df["output_tokens"].sum())
        total_cache_read = int(transcript_df["cache_read_input_tokens"].sum())
        total_cache_create = int(transcript_df["cache_creation_input_tokens"].sum())

        total_cost = 0.0
        for model_name, g in transcript_df.groupby("model"):
            total_cost += estimate_cost(
                input_tokens=int(g["input_tokens"].sum()),
                output_tokens=int(g["output_tokens"].sum()),
                cache_read_tokens=int(g["cache_read_input_tokens"].sum()),
                cache_creation_tokens=int(g["cache_creation_input_tokens"].sum()),
                model=model_name,
            )
    else:
        total_input = int(df["input_tokens"].sum())
        total_output = int(df["output_tokens"].sum())
        total_cache_read = 0
        total_cache_create = 0
        total_cost = 0.0

    avg_duration = df["duration_minutes"].mean()

    render_kpi_row([
        {"label": "Total Sessions", "value": f"{total_sessions:,}"},
        {"label": "Input Tokens", "value": _fmt_tokens(total_input)},
        {"label": "Output Tokens", "value": _fmt_tokens(total_output)},
        {"label": "Est. Cost (API equiv.)", "value": f"${total_cost:,.2f}"},
    ])

    render_kpi_row([
        {"label": "Cache Read Tokens", "value": _fmt_tokens(total_cache_read)},
        {"label": "Cache Creation Tokens", "value": _fmt_tokens(total_cache_create)},
        {"label": "Avg Duration", "value": f"{avg_duration:.0f} min"},
        {"label": "Total Tool Calls", "value": f"{int(df['total_tool_calls'].sum()):,}"},
    ])

    st.divider()

    # --- Daily Usage Trend ---
    col1, col2 = st.columns(2)

    with col1:
        daily = df.groupby("date").agg(
            sessions=("session_id", "count"),
            messages=("total_messages", "sum"),
        ).reset_index()
        daily["date"] = pd.to_datetime(daily["date"])

        fig = px.line(
            daily, x="date", y=["sessions", "messages"],
            title="Daily Usage",
            labels={"value": "Count", "variable": "Metric", "date": "Date"},
        )
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    # --- Activity Heatmap ---
    with col2:
        fig = activity_heatmap(
            df["message_hours"].tolist(),
            df["date"].tolist(),
            title="Activity by Hour & Day",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Recent Sessions ---
    st.subheader("Recent Sessions")
    display_cols = ["start_time", "project_name", "duration_minutes", "total_messages",
                    "total_tool_calls", "input_tokens", "output_tokens"]

    if "outcome" in df.columns:
        display_cols.append("outcome")
    if "brief_summary" in df.columns:
        display_cols.append("brief_summary")

    recent = df.head(15)[display_cols].copy()
    recent["start_time"] = recent["start_time"].dt.strftime("%Y-%m-%d %H:%M")
    recent.columns = [c.replace("_", " ").title() for c in recent.columns]
    st.dataframe(recent, use_container_width=True, hide_index=True)


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
