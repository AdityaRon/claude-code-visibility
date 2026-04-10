import json
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from claude_dashboard.components.filters import apply_filters
from claude_dashboard.components.kpi_cards import render_kpi_row
from claude_dashboard.data.loader import get_data
from claude_dashboard.data.transcripts import load_all_transcript_tokens
from claude_dashboard.data.transcript_security import load_transcript_security


def render():
    st.header("Productivity & Insights")

    data = get_data()
    df = apply_filters(data.sessions)

    if df.empty:
        st.info("No session data found.")
        return

    has_facets = "outcome_score" in df.columns

    # --- KPI Row ---
    total_lines = int(df["lines_added"].sum())
    total_commits = int(df["git_commits"].sum())
    avg_outcome = df["outcome_score"].mean() if has_facets and df["outcome_score"].notna().any() else 0
    total_files = int(df["files_modified"].sum())

    render_kpi_row([
        {"label": "Lines Written", "value": f"{total_lines:,}"},
        {"label": "Git Commits", "value": f"{total_commits:,}"},
        {"label": "Files Modified", "value": f"{total_files:,}"},
        {"label": "Avg Goal Achievement", "value": f"{avg_outcome:.0%}"},
    ])

    st.divider()

    # --- Best Coding Hours & Code Efficiency ---
    col1, col2 = st.columns(2)

    with col1:
        # Best coding hours
        hour_counts = Counter()
        for hours in df["message_hours"]:
            if isinstance(hours, list):
                for h in hours:
                    hour_counts[h] = hour_counts.get(h, 0) + 1

        if hour_counts:
            hours_df = pd.DataFrame(
                [(h, c) for h, c in sorted(hour_counts.items())],
                columns=["Hour", "Messages"],
            )

            # Overlay outcome by hour if available
            if has_facets:
                hour_outcomes = {}
                for _, row in df.iterrows():
                    if pd.notna(row.get("outcome_score")) and isinstance(row.get("message_hours"), list):
                        for h in row["message_hours"]:
                            if h not in hour_outcomes:
                                hour_outcomes[h] = []
                            hour_outcomes[h].append(row["outcome_score"])

                hours_df["Avg Outcome"] = hours_df["Hour"].apply(
                    lambda h: sum(hour_outcomes.get(h, [0])) / len(hour_outcomes.get(h, [1]))
                    if h in hour_outcomes else 0
                )

            fig = px.bar(
                hours_df, x="Hour", y="Messages",
                title="Activity by Hour of Day",
                color_discrete_sequence=["#6366f1"],
            )
            # Highlight peak hours
            peak_hour = hours_df.loc[hours_df["Messages"].idxmax(), "Hour"]
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Peak hour: {peak_hour}:00")

    with col2:
        # Code output efficiency: lines per 1K tokens
        efficiency_df = df[df["lines_added"] > 0].copy()
        if not efficiency_df.empty:
            efficiency_df["tokens_total"] = efficiency_df["input_tokens"] + efficiency_df["output_tokens"]
            efficiency_df = efficiency_df[efficiency_df["tokens_total"] > 0]
            efficiency_df["lines_per_ktok"] = efficiency_df["lines_added"] / (efficiency_df["tokens_total"] / 1000)

            fig = px.scatter(
                efficiency_df, x="start_time", y="lines_per_ktok",
                title="Code Output Efficiency (Lines per 1K Tokens)",
                labels={"lines_per_ktok": "Lines / 1K Tokens", "start_time": "Date"},
                color="project_name",
                trendline="lowess",
            )
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Goal Achievement & Friction Trends ---
    col1, col2 = st.columns(2)

    with col1:
        if has_facets and df["outcome_score"].notna().any():
            trend_df = df[df["outcome_score"].notna()].sort_values("start_time").copy()
            trend_df["rolling_outcome"] = trend_df["outcome_score"].rolling(
                window=min(7, len(trend_df)), min_periods=1
            ).mean()

            fig = px.line(
                trend_df, x="start_time", y="rolling_outcome",
                title="Goal Achievement Trend (7-session rolling avg)",
                labels={"rolling_outcome": "Achievement Score", "start_time": "Date"},
                color_discrete_sequence=["#22c55e"],
            )
            fig.update_yaxes(range=[0, 1.05])
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No outcome data available for trend analysis.")

    with col2:
        # Friction trend over time
        if has_facets and "friction_counts" in df.columns:
            friction_rows = []
            for _, row in df.iterrows():
                fc = row.get("friction_counts")
                if isinstance(fc, dict) and fc:
                    for cat, count in fc.items():
                        friction_rows.append({
                            "date": row["date"],
                            "category": cat,
                            "count": count,
                        })

            if friction_rows:
                friction_df = pd.DataFrame(friction_rows)
                friction_daily = friction_df.groupby(
                    [pd.to_datetime(friction_df["date"]), "category"]
                )["count"].sum().reset_index()
                friction_daily.columns = ["date", "category", "count"]

                fig = px.area(
                    friction_daily, x="date", y="count", color="category",
                    title="Friction Points Over Time",
                    labels={"count": "Count", "category": "Type", "date": "Date"},
                )
                fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("No friction points recorded!")

    st.divider()

    # --- Git Activity ---
    col1, col2 = st.columns(2)

    with col1:
        git_df = df[df["git_commits"] > 0].copy()
        if not git_df.empty:
            daily_git = git_df.groupby("date").agg(
                commits=("git_commits", "sum"),
                pushes=("git_pushes", "sum"),
            ).reset_index()
            daily_git["date"] = pd.to_datetime(daily_git["date"])

            fig = px.bar(
                daily_git, x="date", y=["commits", "pushes"],
                title="Git Activity Over Time",
                labels={"value": "Count", "variable": "Type", "date": "Date"},
                barmode="group",
            )
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No git commit data recorded.")

    with col2:
        # User interruptions vs outcome
        if has_facets and df["outcome_score"].notna().any():
            interrupt_df = df[df["outcome_score"].notna()].copy()
            fig = px.scatter(
                interrupt_df, x="user_interruptions", y="outcome_score",
                title="Interruptions vs Goal Achievement",
                labels={"user_interruptions": "Interruptions", "outcome_score": "Achievement"},
                trendline="ols",
                color="project_name",
            )
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Recommendations Engine ---
    st.subheader("Recommendations")
    _render_recommendations(data, df)


def _render_recommendations(data, df):
    """Generate actionable recommendations based on usage patterns."""
    recommendations = []

    # --- Load supplementary data ---
    transcript_df = load_all_transcript_tokens(str(data.claude_dir))
    sec_df = load_transcript_security(str(data.claude_dir))

    # ===== CORE CHECKS (1-6) =====

    # 1. Cache efficiency
    if not transcript_df.empty:
        cache_read = transcript_df["cache_read_input_tokens"].sum()
        cache_creation = transcript_df["cache_creation_input_tokens"].sum()
        input_tok = transcript_df["input_tokens"].sum()
        total_cache_input = cache_read + input_tok + cache_creation
        if total_cache_input > 0:
            hit_rate = cache_read / total_cache_input
            if hit_rate < 0.5:
                recommendations.append((
                    "warning",
                    "Low Cache Hit Rate",
                    f"Your cache hit rate is **{hit_rate:.0%}**. To improve:\n"
                    "- Keep sessions alive longer instead of starting new ones\n"
                    "- Trim your CLAUDE.md to reduce cache churn on changes\n"
                    "- Use `/compact` less frequently to preserve cache"
                ))
            elif hit_rate > 0.8:
                recommendations.append((
                    "success",
                    "Excellent Cache Efficiency",
                    f"Cache hit rate is **{hit_rate:.0%}** - you're making great use of prompt caching!"
                ))

    # 2. Tool error rate
    total_calls = df["total_tool_calls"].sum()
    total_errors = df["tool_errors"].sum()
    if total_calls > 0:
        error_rate = total_errors / total_calls
        if error_rate > 0.1:
            error_cats = Counter()
            for ec in df["tool_error_categories"]:
                if isinstance(ec, dict):
                    error_cats.update(ec)
            top_error = error_cats.most_common(1)[0][0] if error_cats else "unknown"
            recommendations.append((
                "warning",
                "High Tool Error Rate",
                f"Tool error rate is **{error_rate:.0%}** (most common: {top_error}).\n"
                "Consider providing clearer context about your environment and file structure."
            ))

    # 3. Read vs Write ratio
    total_reads = sum(
        tc.get("Read", 0) for tc in df["tool_counts"] if isinstance(tc, dict)
    )
    total_writes = sum(
        tc.get("Write", 0) + tc.get("Edit", 0)
        for tc in df["tool_counts"] if isinstance(tc, dict)
    )
    if total_reads > 0 and total_writes / max(total_reads, 1) > 2:
        recommendations.append((
            "info",
            "High Write-to-Read Ratio",
            f"Claude is writing ({total_writes} calls) much more than reading ({total_reads} calls). "
            "You may get better results by asking Claude to read and understand existing code first."
        ))

    # 4. Short sessions
    avg_duration = df["duration_minutes"].mean()
    if avg_duration < 5 and len(df) > 3:
        recommendations.append((
            "info",
            "Very Short Sessions",
            f"Average session is **{avg_duration:.0f} minutes**. Longer sessions benefit from "
            "better cache efficiency. Consider batching related tasks into single sessions."
        ))

    # 5. Goal achievement
    if "outcome_score" in df.columns and df["outcome_score"].notna().any():
        recent = df.sort_values("start_time").tail(10)
        recent_score = recent["outcome_score"].mean()
        if recent_score < 0.5:
            recommendations.append((
                "warning",
                "Low Recent Goal Achievement",
                f"Recent sessions average **{recent_score:.0%}** goal achievement.\n"
                "- Break complex goals into smaller, focused tasks\n"
                "- Provide more context in your initial prompt\n"
                "- Use plan mode for complex changes"
            ))

    # 6. High interruptions
    avg_interrupts = df["user_interruptions"].mean()
    if avg_interrupts > 3:
        recommendations.append((
            "info",
            "Frequent Interruptions",
            f"You interrupt Claude **{avg_interrupts:.1f}x** per session on average. "
            "More specific initial prompts can reduce the need for course corrections."
        ))

    # ===== CLAUDE.md OPTIMIZATION (7-11) =====

    # 7. Heavy exploration → better CLAUDE.md project map
    if total_calls > 0:
        total_exploration = sum(
            tc.get("Glob", 0) + tc.get("Grep", 0) + tc.get("Read", 0)
            for tc in df["tool_counts"] if isinstance(tc, dict)
        )
        exploration_pct = total_exploration / total_calls * 100
        if exploration_pct > 60:
            recommendations.append((
                "info",
                "Heavy Exploration — Improve Your CLAUDE.md",
                f"Claude spends **{exploration_pct:.0f}%** of tool calls on exploration "
                "(Glob, Grep, Read). **Add a project structure section to your CLAUDE.md** "
                "describing key directories, entry points, and where important code lives. "
                "This reduces exploration tokens significantly."
            ))

    # 8. Repeated file reads → document key files in CLAUDE.md
    if not sec_df.empty:
        all_read_counts: Counter = Counter()
        for rc in sec_df["file_read_counts"]:
            if isinstance(rc, dict):
                all_read_counts.update(rc)
        # Find files read 5+ times across all sessions
        hot_files = [(fp, count) for fp, count in all_read_counts.most_common(10) if count >= 5]
        if hot_files:
            file_list = ", ".join(f"`{fp.split('/')[-1]}` ({c}x)" for fp, c in hot_files[:3])
            recommendations.append((
                "info",
                "Frequently Re-Read Files — Document in CLAUDE.md",
                f"Claude re-reads these files often: {file_list}. "
                "**Add a section to your CLAUDE.md** describing what these files do "
                "and their key patterns. This saves Claude from re-reading them every session."
            ))

    # 9. Bash instead of dedicated tools
    if not sec_df.empty:
        total_inefficient = int(sec_df["inefficient_bash_count"].sum())
        total_bash = int(sec_df["bash_command_count"].sum())
        if total_bash > 10 and total_inefficient / max(total_bash, 1) > 0.15:
            recommendations.append((
                "info",
                "Bash Used Where Tools Are Better",
                f"**{total_inefficient} Bash commands** could have used dedicated tools:\n"
                "- `find` → use **Glob**\n"
                "- `grep`/`rg` → use **Grep**\n"
                "- `cat`/`head`/`tail` → use **Read**\n"
                "- `sed`/`awk` → use **Edit**\n\n"
                "Dedicated tools are faster and use fewer tokens. "
                "**Add to your CLAUDE.md:** `Prefer Glob, Grep, Read tools over Bash equivalents.`"
            ))

    # 10. High Bash ratio → context gap in CLAUDE.md
    if total_calls > 0:
        total_bash_all = sum(
            tc.get("Bash", 0) for tc in df["tool_counts"] if isinstance(tc, dict)
        )
        bash_pct = total_bash_all / total_calls * 100
        if bash_pct > 40:
            recommendations.append((
                "info",
                "High Bash Usage — Add Context to CLAUDE.md",
                f"**{bash_pct:.0f}%** of tool calls are Bash commands. This often means Claude "
                "lacks context about your environment. **Add to your CLAUDE.md:** build commands, "
                "test commands, common scripts, and environment setup so Claude doesn't need to "
                "discover them via Bash."
            ))

    # 11. Scattered modifications → task scoping
    if len(df) > 3:
        avg_files = df["files_modified"].mean()
        avg_lines = df["lines_added"].mean()
        if avg_files > 8 and avg_lines / max(avg_files, 1) < 50:
            recommendations.append((
                "info",
                "Scattered Modifications — Scope Tasks Better",
                f"Sessions average **{avg_files:.0f} files modified** with only "
                f"**{avg_lines / max(avg_files, 1):.0f} lines per file**. "
                "Scattered edits suggest unfocused tasks. **Break complex requests into "
                "focused sub-tasks** (one component/module at a time) for better outcomes."
            ))

    # ===== WORKFLOW OPTIMIZATION (12-15) =====

    # 12. Model selection savings
    if not transcript_df.empty and "outcome_score" in df.columns:
        from claude_dashboard.config import estimate_cost
        model_data = {}
        for model_name, g in transcript_df.groupby("model"):
            cost = estimate_cost(
                input_tokens=int(g["input_tokens"].sum()),
                output_tokens=int(g["output_tokens"].sum()),
                cache_read_tokens=int(g["cache_read_input_tokens"].sum()),
                cache_creation_tokens=int(g["cache_creation_input_tokens"].sum()),
                model=model_name,
            )
            sids = g["session_id"].unique()
            outcomes = df[df["session_id"].isin(sids)]["outcome_score"].dropna()
            model_data[model_name] = {
                "cost": cost,
                "sessions": len(sids),
                "avg_outcome": outcomes.mean() if len(outcomes) > 0 else None,
            }

        # Check if Opus is heavily used but Sonnet achieves similar outcomes
        opus_models = {k: v for k, v in model_data.items() if "opus" in k.lower()}
        sonnet_models = {k: v for k, v in model_data.items() if "sonnet" in k.lower()}
        if opus_models and sonnet_models:
            opus_cost = sum(v["cost"] for v in opus_models.values())
            opus_outcomes = [v["avg_outcome"] for v in opus_models.values() if v["avg_outcome"] is not None]
            sonnet_outcomes = [v["avg_outcome"] for v in sonnet_models.values() if v["avg_outcome"] is not None]
            total_cost = sum(v["cost"] for v in model_data.values())
            if opus_outcomes and sonnet_outcomes and total_cost > 0:
                opus_avg = sum(opus_outcomes) / len(opus_outcomes)
                sonnet_avg = sum(sonnet_outcomes) / len(sonnet_outcomes)
                opus_pct = opus_cost / total_cost * 100
                if opus_pct > 50 and abs(opus_avg - sonnet_avg) < 0.15:
                    recommendations.append((
                        "info",
                        "Consider Sonnet for Routine Tasks",
                        f"Opus accounts for **{opus_pct:.0f}%** of cost but Sonnet achieves "
                        f"similar outcomes ({sonnet_avg:.0%} vs {opus_avg:.0%}). Switching "
                        "routine tasks to Sonnet could reduce costs significantly."
                    ))

    # 13. Time-of-day optimization
    if "outcome_score" in df.columns and df["outcome_score"].notna().any():
        hour_outcomes: dict[int, list] = {}
        hour_usage: Counter = Counter()
        for _, row in df.iterrows():
            hours = row.get("message_hours", [])
            if isinstance(hours, list):
                for h in hours:
                    hour_usage[h] += 1
                    if pd.notna(row.get("outcome_score")):
                        hour_outcomes.setdefault(h, []).append(row["outcome_score"])

        if hour_outcomes and hour_usage:
            best_outcome_hour = max(hour_outcomes, key=lambda h: sum(hour_outcomes[h]) / len(hour_outcomes[h]))
            peak_usage_hour = hour_usage.most_common(1)[0][0]
            best_outcome_avg = sum(hour_outcomes[best_outcome_hour]) / len(hour_outcomes[best_outcome_hour])
            if best_outcome_hour != peak_usage_hour and best_outcome_avg > 0.6:
                recommendations.append((
                    "info",
                    "Time-of-Day Optimization",
                    f"Your best outcomes happen around **{best_outcome_hour}:00** "
                    f"({best_outcome_avg:.0%} achievement), but you mostly work at "
                    f"**{peak_usage_hour}:00**. Schedule complex tasks during your "
                    "high-outcome hours."
                ))

    # 14. Plan mode underutilization
    if not sec_df.empty and len(df) > 5:
        plan_sessions = sec_df["permission_modes"].apply(
            lambda modes: "plan" in modes if isinstance(modes, list) else False
        ).sum()
        plan_pct = plan_sessions / len(sec_df) * 100
        avg_msgs = df["total_messages"].mean()
        if plan_pct < 10 and avg_msgs > 15:
            recommendations.append((
                "info",
                "Plan Mode Underutilized",
                f"Only **{plan_pct:.0f}%** of sessions use plan mode, but your sessions "
                f"average **{avg_msgs:.0f} messages**. For complex multi-file changes, "
                "starting with `/plan` improves outcomes by aligning on approach before execution."
            ))

    # 15. Task Agent for long sessions
    if len(df) > 3:
        agent_pct = df["uses_task_agent"].sum() / len(df) * 100
        avg_dur = df["duration_minutes"].mean()
        if agent_pct < 5 and avg_dur > 30:
            recommendations.append((
                "info",
                "Consider Task Agent for Long Sessions",
                f"Long sessions (**{avg_dur:.0f} min avg**) could benefit from the Agent "
                "tool for parallel sub-tasks. **Add to your CLAUDE.md:** guidance on when "
                "to use sub-agents for independent work streams."
            ))

    # ===== SECURITY (16-18) =====

    # 16. Permission hygiene
    settings_path = data.claude_dir / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            mode = settings.get("permissions", {}).get("defaultMode", "default")
            if mode == "acceptEdits":
                recommendations.append((
                    "warning",
                    "Permission Mode: acceptEdits",
                    "Your default permission mode is **acceptEdits** — Claude auto-approves "
                    "file writes without asking. Consider switching to **default** mode for "
                    "better security review. Set in `~/.claude/settings.json`."
                ))
        except (json.JSONDecodeError, OSError):
            pass

    # 17. Dangerous commands found
    if not sec_df.empty:
        danger_count = int(sec_df["dangerous_command_count"].sum())
        if danger_count > 0:
            recommendations.append((
                "warning",
                "Dangerous Commands Detected",
                f"**{danger_count} dangerous commands** detected across your sessions "
                "(e.g., `rm -rf`, `git push --force`). Review the **Security** page for details.\n\n"
                "**Add to your CLAUDE.md:** `Never run destructive commands (rm -rf, git reset --hard, "
                "force push) without explicit user confirmation.`"
            ))

    # 18. Response time → preparation
    response_times = []
    for rt in df["user_response_times"]:
        if isinstance(rt, list):
            response_times.extend(rt)
    if len(response_times) > 5:
        median_rt = sorted(response_times)[len(response_times) // 2]
        if median_rt > 120:
            recommendations.append((
                "info",
                "Slow Response Times — Prepare Before Starting",
                f"Your median response time to Claude is **{median_rt:.0f}s**. "
                "Preparing context and instructions before starting sessions improves flow. "
                "**Draft your task description before launching Claude Code.**"
            ))

    # ===== RENDER =====
    if not recommendations:
        st.success("Looking good! No specific recommendations at this time.")
        return

    for level, title, detail in recommendations:
        if level == "warning":
            st.warning(f"**{title}**\n\n{detail}")
        elif level == "info":
            st.info(f"**{title}**\n\n{detail}")
        elif level == "success":
            st.success(f"**{title}**\n\n{detail}")
