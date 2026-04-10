from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from claude_dashboard.components.filters import apply_filters
from claude_dashboard.components.kpi_cards import render_kpi_row
from claude_dashboard.config import TOOL_COLORS
from claude_dashboard.data.loader import get_data
from claude_dashboard.data.transcript_security import load_transcript_security


def render():
    st.header("Tool Usage Analytics")

    data = get_data()
    df = apply_filters(data.sessions)

    if df.empty:
        st.info("No session data found.")
        return

    # --- Aggregate tool counts ---
    tool_totals = Counter()
    for tc in df["tool_counts"]:
        if isinstance(tc, dict):
            tool_totals.update(tc)

    total_calls = sum(tool_totals.values())
    total_errors = int(df["tool_errors"].sum())
    error_rate = (total_errors / total_calls * 100) if total_calls > 0 else 0
    unique_tools = len(tool_totals)

    render_kpi_row([
        {"label": "Total Tool Calls", "value": f"{total_calls:,}"},
        {"label": "Unique Tools Used", "value": unique_tools},
        {"label": "Total Tool Errors", "value": f"{total_errors:,}"},
        {"label": "Error Rate", "value": f"{error_rate:.1f}%"},
    ])

    st.divider()

    # --- Tool Distribution ---
    col1, col2 = st.columns(2)

    with col1:
        tool_df = pd.DataFrame(
            sorted(tool_totals.items(), key=lambda x: x[1], reverse=True),
            columns=["Tool", "Calls"],
        )
        colors = [TOOL_COLORS.get(t, "#94a3b8") for t in tool_df["Tool"]]

        fig = px.bar(
            tool_df, x="Calls", y="Tool", orientation="h",
            title="Tool Call Distribution",
            color="Tool",
            color_discrete_map=TOOL_COLORS,
        )
        fig.update_layout(height=400, showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.pie(
            tool_df, names="Tool", values="Calls",
            title="Tool Usage Share",
            color="Tool",
            color_discrete_map=TOOL_COLORS,
        )
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Tool Usage Over Time ---
    col1, col2 = st.columns(2)

    with col1:
        # Expand tool_counts per session into rows
        tool_rows = []
        for _, row in df.iterrows():
            tc = row.get("tool_counts", {})
            if isinstance(tc, dict):
                for tool, count in tc.items():
                    tool_rows.append({"date": row["date"], "tool": tool, "count": count})

        if tool_rows:
            tool_time_df = pd.DataFrame(tool_rows)
            daily_tools = tool_time_df.groupby(["date", "tool"])["count"].sum().reset_index()
            daily_tools["date"] = pd.to_datetime(daily_tools["date"])

            fig = px.area(
                daily_tools, x="date", y="count", color="tool",
                title="Tool Usage Over Time",
                labels={"count": "Calls", "tool": "Tool", "date": "Date"},
                color_discrete_map=TOOL_COLORS,
            )
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Tool calls per session box plot
        fig = px.box(
            df, y="total_tool_calls",
            title="Tool Calls Per Session",
            labels={"total_tool_calls": "Tool Calls"},
        )
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Error Categories & Read/Write Ratio ---
    col1, col2 = st.columns(2)

    with col1:
        # Tool error categories
        error_totals = Counter()
        for ec in df["tool_error_categories"]:
            if isinstance(ec, dict):
                error_totals.update(ec)

        if error_totals:
            error_df = pd.DataFrame(
                sorted(error_totals.items(), key=lambda x: x[1], reverse=True),
                columns=["Category", "Count"],
            )
            fig = px.bar(
                error_df, x="Count", y="Category", orientation="h",
                title="Tool Error Categories",
                color_discrete_sequence=["#ef4444"],
            )
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No tool errors recorded!")

    with col2:
        # Feature adoption
        features = {
            "Task Agent": df["uses_task_agent"].sum(),
            "MCP": df["uses_mcp"].sum(),
            "Web Search": df["uses_web_search"].sum(),
            "Web Fetch": df["uses_web_fetch"].sum(),
        }
        feat_df = pd.DataFrame(
            [(k, v, v / len(df) * 100) for k, v in features.items()],
            columns=["Feature", "Sessions", "Adoption %"],
        )
        fig = px.bar(
            feat_df, x="Feature", y="Adoption %",
            title="Feature Adoption (% of sessions)",
            color="Feature",
            text="Sessions",
        )
        fig.update_layout(height=350, showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Read vs Write Ratio ---
    st.subheader("Read vs Write+Edit Ratio")
    ratio_data = []
    for _, row in df.iterrows():
        tc = row.get("tool_counts", {})
        if isinstance(tc, dict):
            reads = tc.get("Read", 0)
            writes = tc.get("Write", 0) + tc.get("Edit", 0)
            if reads > 0 or writes > 0:
                ratio_data.append({
                    "Read": reads,
                    "Write+Edit": writes,
                    "project": row.get("project_name", ""),
                    "session": row.get("session_id", "")[:8],
                })

    if ratio_data:
        ratio_df = pd.DataFrame(ratio_data)
        fig = px.scatter(
            ratio_df, x="Read", y="Write+Edit",
            color="project", hover_data=["session"],
            title="Read vs Write+Edit Per Session",
        )
        fig.add_shape(type="line", x0=0, y0=0, x1=ratio_df[["Read", "Write+Edit"]].max().max(),
                      y1=ratio_df[["Read", "Write+Edit"]].max().max(),
                      line=dict(dash="dash", color="#94a3b8"))
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Bash Efficiency Analysis ---
    st.subheader("Bash Efficiency")
    st.caption(
        "Bash commands that could use dedicated tools (Glob, Grep, Read, Edit) — "
        "dedicated tools are faster and use fewer tokens."
    )

    sec_df = load_transcript_security(str(data.claude_dir))
    if not sec_df.empty:
        total_inefficient = int(sec_df["inefficient_bash_count"].sum())
        total_bash = int(sec_df["bash_command_count"].sum())

        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Bash Commands", f"{total_bash:,}")
            st.metric("Could Use Tools", f"{total_inefficient:,}")
            if total_bash > 0:
                st.metric(
                    "Efficiency Rate",
                    f"{(1 - total_inefficient / total_bash) * 100:.0f}%",
                )

        with col2:
            # Aggregate inefficient bash by recommended tool
            tool_counts_map: dict[str, int] = {}
            for cmds in sec_df["inefficient_bash_commands"]:
                if isinstance(cmds, list):
                    for cmd in cmds:
                        tool = cmd.get("tool", "Unknown")
                        tool_counts_map[tool] = tool_counts_map.get(tool, 0) + 1

            if tool_counts_map:
                ineff_df = pd.DataFrame([
                    {"Recommended Tool": tool, "Count": count}
                    for tool, count in sorted(tool_counts_map.items(), key=lambda x: x[1], reverse=True)
                ])
                fig = px.bar(
                    ineff_df, x="Count", y="Recommended Tool", orientation="h",
                    title="Bash Commands by Recommended Tool",
                    color="Recommended Tool",
                    color_discrete_map=TOOL_COLORS,
                )
                fig.update_layout(height=250, showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("All Bash commands are being used appropriately!")
    else:
        st.info("No transcript data available for Bash analysis.")
