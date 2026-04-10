from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from claude_dashboard.components.filters import apply_filters
from claude_dashboard.components.kpi_cards import render_kpi_row
from claude_dashboard.data.loader import get_data


def render():
    st.header("Session Deep Dive")

    data = get_data()
    df = apply_filters(data.sessions)

    if df.empty:
        st.info("No session data found.")
        return

    has_facets = "outcome" in df.columns and df["outcome"].notna().any()
    facets_df = df[df["outcome"].notna()] if has_facets else pd.DataFrame()
    facets_pct = f"{len(facets_df)}/{len(df)}" if has_facets else "0/0"

    # --- KPI Row ---
    avg_duration = df["duration_minutes"].mean()
    median_duration = df["duration_minutes"].median()
    avg_messages = df["total_messages"].mean()
    avg_interruptions = df["user_interruptions"].mean()

    render_kpi_row([
        {"label": "Avg Duration", "value": f"{avg_duration:.0f} min"},
        {"label": "Median Duration", "value": f"{median_duration:.0f} min"},
        {"label": "Avg Messages/Session", "value": f"{avg_messages:.0f}"},
        {"label": "Avg Interruptions", "value": f"{avg_interruptions:.1f}"},
    ])

    st.divider()

    # --- Duration Distribution & Outcome ---
    col1, col2 = st.columns(2)

    with col1:
        fig = px.histogram(
            df, x="duration_minutes",
            title="Session Duration Distribution",
            labels={"duration_minutes": "Duration (minutes)"},
            nbins=25,
        )
        fig.add_vline(x=avg_duration, line_dash="dash", line_color="#3b82f6",
                      annotation_text=f"Mean: {avg_duration:.0f}")
        fig.add_vline(x=median_duration, line_dash="dot", line_color="#22c55e",
                      annotation_text=f"Median: {median_duration:.0f}")
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if has_facets and not facets_df.empty:
            outcome_counts = facets_df["outcome"].value_counts().reset_index()
            outcome_counts.columns = ["Outcome", "Count"]

            color_map = {
                "achieved": "#22c55e", "fully_achieved": "#22c55e",
                "mostly_achieved": "#86efac",
                "partially_achieved": "#f59e0b",
                "not_achieved": "#ef4444",
            }
            fig = px.pie(
                outcome_counts, names="Outcome", values="Count",
                title=f"Session Outcomes ({facets_pct} sessions with data)",
                color="Outcome",
                color_discrete_map=color_map,
            )
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No outcome data available (facets not generated for these sessions).")

    st.divider()

    # --- Helpfulness & Session Type ---
    col1, col2 = st.columns(2)

    with col1:
        if has_facets and "helpfulness_score" in facets_df.columns:
            facets_sorted = facets_df.sort_values("start_time")
            fig = px.scatter(
                facets_sorted, x="start_time", y="helpfulness_score",
                title="Claude Helpfulness Over Time",
                labels={"helpfulness_score": "Helpfulness Score", "start_time": "Date"},
                trendline="lowess",
                color_discrete_sequence=["#6366f1"],
            )
            fig.update_yaxes(range=[-0.1, 1.1])
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if has_facets and "session_type" in facets_df.columns:
            type_counts = facets_df["session_type"].value_counts().reset_index()
            type_counts.columns = ["Type", "Count"]
            fig = px.bar(
                type_counts, x="Type", y="Count",
                title="Session Type Distribution",
                color="Type",
            )
            fig.update_layout(height=400, showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Friction Analysis ---
    if has_facets:
        st.subheader("Friction Analysis")
        friction_totals = Counter()
        for fc in facets_df["friction_counts"]:
            if isinstance(fc, dict):
                friction_totals.update(fc)

        if friction_totals:
            friction_df = pd.DataFrame(
                sorted(friction_totals.items(), key=lambda x: x[1], reverse=True),
                columns=["Category", "Count"],
            )
            fig = px.bar(
                friction_df, x="Count", y="Category", orientation="h",
                title="Friction Points Across Sessions",
                color_discrete_sequence=["#f59e0b"],
            )
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No friction points recorded!")

    st.divider()

    # --- Session Table ---
    st.subheader("All Sessions")
    table_cols = ["start_time", "project_name", "duration_minutes", "total_messages",
                  "total_tool_calls", "input_tokens", "output_tokens",
                  "lines_added", "files_modified"]

    if has_facets:
        table_cols.extend(["outcome", "helpfulness", "brief_summary"])

    available_cols = [c for c in table_cols if c in df.columns]
    table_df = df[available_cols].copy()
    table_df["start_time"] = table_df["start_time"].dt.strftime("%Y-%m-%d %H:%M")
    table_df.columns = [c.replace("_", " ").title() for c in table_df.columns]

    st.dataframe(table_df, use_container_width=True, hide_index=True, height=500)

    # --- Session Detail Expanders ---
    if has_facets:
        st.subheader("Session Details")
        for _, row in facets_df.head(10).iterrows():
            label = f"{row['start_time'].strftime('%Y-%m-%d')} - {row.get('project_name', 'Unknown')}"
            with st.expander(label):
                if pd.notna(row.get("underlying_goal")):
                    st.markdown(f"**Goal:** {row['underlying_goal']}")
                if pd.notna(row.get("outcome")):
                    st.markdown(f"**Outcome:** {row['outcome']}")
                if pd.notna(row.get("helpfulness")):
                    st.markdown(f"**Helpfulness:** {row['helpfulness']}")
                if pd.notna(row.get("primary_success")) and row.get("primary_success") not in ("", "none"):
                    st.markdown(f"**What Worked:** {row['primary_success']}")
                if pd.notna(row.get("friction_detail")):
                    st.markdown(f"**Friction:** {row['friction_detail']}")
                if pd.notna(row.get("brief_summary")):
                    st.markdown(f"**Summary:** {row['brief_summary']}")
                if pd.notna(row.get("first_prompt")):
                    st.markdown(f"**First Prompt:** {row['first_prompt']}")
