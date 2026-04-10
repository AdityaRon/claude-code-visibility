from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from claude_dashboard.components.filters import apply_filters
from claude_dashboard.data.loader import get_data


def render():
    st.header("Project Analytics")

    data = get_data()
    df = apply_filters(data.sessions)

    if df.empty:
        st.info("No session data found.")
        return

    # --- Project Summary Table ---
    st.subheader("Project Summary")

    df_calc = df.copy()
    df_calc["total_tokens"] = df_calc["input_tokens"] + df_calc["output_tokens"]

    project_stats = df_calc.groupby("project_name").agg(
        sessions=("session_id", "count"),
        total_tokens=("total_tokens", "sum"),
        avg_duration=("duration_minutes", "mean"),
        total_tool_calls=("total_tool_calls", "sum"),
        total_messages=("total_messages", "sum"),
        lines_added=("lines_added", "sum"),
        lines_removed=("lines_removed", "sum"),
        files_modified=("files_modified", "sum"),
        git_commits=("git_commits", "sum"),
    ).reset_index().sort_values("sessions", ascending=False)

    # Dominant language per project
    dom_langs = []
    for project in project_stats["project_name"]:
        proj_df = df[df["project_name"] == project]
        lang_counter = Counter()
        for langs in proj_df["languages"]:
            if isinstance(langs, dict):
                lang_counter.update(langs)
        dom_langs.append(lang_counter.most_common(1)[0][0] if lang_counter else "N/A")
    project_stats["dominant_language"] = dom_langs

    project_stats["avg_duration"] = project_stats["avg_duration"].round(0).astype(int)
    display = project_stats.copy()
    display.columns = [c.replace("_", " ").title() for c in display.columns]
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()

    # --- Project Comparison ---
    col1, col2 = st.columns(2)

    with col1:
        metric = st.selectbox(
            "Compare metric",
            ["sessions", "total_tokens", "total_tool_calls", "lines_added", "total_messages"],
        )
        fig = px.bar(
            project_stats.head(10), x="project_name", y=metric,
            title=f"Top Projects by {metric.replace('_', ' ').title()}",
            color="project_name",
        )
        fig.update_layout(height=400, showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Activity over time by project
        daily_project = df.groupby(["date", "project_name"]).size().reset_index(name="sessions")
        daily_project["date"] = pd.to_datetime(daily_project["date"])

        # Top 5 projects + Other
        top_projects = project_stats.head(5)["project_name"].tolist()
        daily_project["project_group"] = daily_project["project_name"].apply(
            lambda p: p if p in top_projects else "Other"
        )
        grouped = daily_project.groupby(["date", "project_group"])["sessions"].sum().reset_index()

        fig = px.area(
            grouped, x="date", y="sessions", color="project_group",
            title="Activity Over Time by Project",
            labels={"sessions": "Sessions", "project_group": "Project", "date": "Date"},
        )
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Language Sunburst ---
    st.subheader("Language Distribution by Project")
    lang_rows = []
    for _, row in df.iterrows():
        langs = row.get("languages", {})
        if isinstance(langs, dict):
            for lang, count in langs.items():
                lang_rows.append({
                    "project": row["project_name"],
                    "language": lang,
                    "count": count,
                })

    if lang_rows:
        lang_df = pd.DataFrame(lang_rows)
        lang_agg = lang_df.groupby(["project", "language"])["count"].sum().reset_index()

        fig = px.sunburst(
            lang_agg, path=["project", "language"], values="count",
            title="Languages by Project",
        )
        fig.update_layout(height=500, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No language data available.")
