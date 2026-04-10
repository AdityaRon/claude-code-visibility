import json
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from claude_dashboard.components.filters import apply_filters
from claude_dashboard.components.kpi_cards import render_kpi_row
from claude_dashboard.config import PERMISSION_MODE_COLORS, PERMISSION_MODE_LABELS
from claude_dashboard.data.loader import get_data
from claude_dashboard.data.transcript_security import load_transcript_security


def render():
    st.header("Security & Permissions")

    data = get_data()
    df = apply_filters(data.sessions)

    if df.empty:
        st.info("No session data found.")
        return

    # Load security data from transcripts
    sec_df = load_transcript_security(str(data.claude_dir))

    # --- KPI Row ---
    total_tool_calls = int(df["total_tool_calls"].sum())
    total_errors = int(df["tool_errors"].sum())
    error_rate = (total_errors / total_tool_calls * 100) if total_tool_calls > 0 else 0

    total_dangerous = 0
    default_mode_pct = 0.0
    if not sec_df.empty:
        total_dangerous = int(sec_df["dangerous_command_count"].sum())
        # Count sessions where "default" is in permission_modes
        default_count = sec_df["permission_modes"].apply(
            lambda modes: "default" in modes if isinstance(modes, list) else False
        ).sum()
        default_mode_pct = default_count / len(sec_df) * 100 if len(sec_df) > 0 else 0

    render_kpi_row([
        {"label": "Sessions Analyzed", "value": f"{len(sec_df):,}" if not sec_df.empty else "0"},
        {"label": "Dangerous Commands", "value": f"{total_dangerous:,}"},
        {"label": "Default Mode %", "value": f"{default_mode_pct:.0f}%"},
        {"label": "Tool Error Rate", "value": f"{error_rate:.1f}%"},
    ])

    st.divider()

    # --- Permission Mode Distribution ---
    if not sec_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            # Explode permission modes for aggregate counting
            mode_counts = Counter()
            for modes in sec_df["permission_modes"]:
                if isinstance(modes, list):
                    for m in modes:
                        mode_counts[m] += 1

            if mode_counts:
                mode_df = pd.DataFrame(
                    [(PERMISSION_MODE_LABELS.get(m, m), c) for m, c in mode_counts.items()],
                    columns=["Mode", "Sessions"],
                )
                fig = px.pie(
                    mode_df, names="Mode", values="Sessions",
                    title="Permission Mode Distribution",
                    color="Mode",
                    color_discrete_map={
                        PERMISSION_MODE_LABELS.get(k, k): v
                        for k, v in PERMISSION_MODE_COLORS.items()
                    },
                )
                fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Permission mode over time (join with sessions for dates)
            sec_with_dates = sec_df.merge(
                df[["session_id", "date"]].drop_duplicates(),
                on="session_id", how="inner",
            )
            if not sec_with_dates.empty:
                mode_time_rows = []
                for _, row in sec_with_dates.iterrows():
                    modes = row.get("permission_modes", [])
                    if isinstance(modes, list):
                        for m in modes:
                            mode_time_rows.append({
                                "date": row["date"],
                                "mode": PERMISSION_MODE_LABELS.get(m, m),
                            })

                if mode_time_rows:
                    mode_time_df = pd.DataFrame(mode_time_rows)
                    daily_modes = mode_time_df.groupby(
                        [pd.to_datetime(mode_time_df["date"]), "mode"]
                    ).size().reset_index(name="count")
                    daily_modes.columns = ["date", "mode", "count"]

                    fig = px.bar(
                        daily_modes, x="date", y="count", color="mode",
                        title="Permission Modes Over Time",
                        labels={"count": "Sessions", "mode": "Mode", "date": "Date"},
                        barmode="stack",
                    )
                    fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig, use_container_width=True)

        st.divider()

    # --- Dangerous Command Audit ---
    st.subheader("Dangerous Command Audit")

    if not sec_df.empty and total_dangerous > 0:
        danger_rows = []
        sec_with_dates = sec_df.merge(
            df[["session_id", "date", "project_name"]].drop_duplicates(),
            on="session_id", how="inner",
        )
        for _, row in sec_with_dates.iterrows():
            cmds = row.get("dangerous_commands", [])
            if isinstance(cmds, list):
                for cmd in cmds:
                    danger_rows.append({
                        "Date": row.get("date", ""),
                        "Project": row.get("project_name", ""),
                        "Command": cmd.get("command", "")[:100],
                        "Risk": cmd.get("risk", ""),
                        "Pattern": cmd.get("label", ""),
                    })

        if danger_rows:
            danger_df = pd.DataFrame(danger_rows)
            # Color-code risk column
            st.dataframe(
                danger_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Risk": st.column_config.TextColumn(width="small"),
                    "Command": st.column_config.TextColumn(width="large"),
                },
            )
            st.caption(
                "Risk levels: **high** = data loss or security risk, "
                "**medium** = potentially unsafe, **low** = worth reviewing"
            )
    else:
        st.success("No dangerous commands detected across your sessions!")

    st.divider()

    # --- Tool Error Audit ---
    st.subheader("Tool Error Audit")
    col1, col2 = st.columns(2)

    with col1:
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
                title="Error Categories",
                color_discrete_sequence=["#ef4444"],
            )
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No tool errors recorded!")

    with col2:
        # Errors vs outcome
        has_facets = "outcome_score" in df.columns and df["outcome_score"].notna().any()
        if has_facets:
            fig = px.scatter(
                df[df["outcome_score"].notna()],
                x="tool_errors", y="outcome_score",
                title="Tool Errors vs Goal Achievement",
                labels={"tool_errors": "Errors", "outcome_score": "Achievement"},
                trendline="ols",
                color="project_name",
            )
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No outcome data available for correlation analysis.")

    st.divider()

    # --- Auto-Approval Candidates ---
    st.subheader("Auto-Approval Candidates")
    st.caption(
        "Tools with zero errors are safe candidates for auto-approval. "
        "Configure in `~/.claude/settings.json` under `permissions.allow`."
    )

    tool_stats = Counter()
    tool_errors_by_name: dict[str, int] = {}
    for _, row in df.iterrows():
        tc = row.get("tool_counts", {})
        if isinstance(tc, dict):
            for tool, count in tc.items():
                tool_stats[tool] += count

    # Approximate errors by tool (we don't have per-tool errors, so use categories)
    # Tools with known safe categories
    safe_tools = {"Read", "Glob", "Grep", "LSP"}
    approval_rows = []
    for tool, calls in sorted(tool_stats.items(), key=lambda x: x[1], reverse=True):
        is_safe = tool in safe_tools
        approval_rows.append({
            "Tool": tool,
            "Total Calls": calls,
            "Category": "Read-only" if is_safe else "Modifying",
            "Recommendation": "Safe to auto-approve" if is_safe else "Requires review",
        })

    if approval_rows:
        st.dataframe(
            pd.DataFrame(approval_rows),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # --- Settings Audit ---
    st.subheader("Settings Audit")
    settings_path = data.claude_dir / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            col1, col2, col3 = st.columns(3)

            with col1:
                perm = settings.get("permissions", {})
                mode = perm.get("defaultMode", "default")
                label = PERMISSION_MODE_LABELS.get(mode, mode)
                st.metric("Permission Mode", label)
                if mode == "acceptEdits":
                    st.warning(
                        "**acceptEdits** auto-approves file writes. "
                        "Consider **default** mode for better security."
                    )

            with col2:
                plugins = settings.get("enabledPlugins", {})
                enabled = [k for k, v in plugins.items() if v]
                st.metric("Enabled Plugins", len(enabled))
                if enabled:
                    for p in enabled:
                        st.caption(f"- {p}")

            with col3:
                effort = settings.get("effortLevel", "not set")
                st.metric("Effort Level", effort)

        except (json.JSONDecodeError, OSError):
            st.info("Could not read settings.json")
    else:
        st.info("No settings.json found — using default configuration.")
