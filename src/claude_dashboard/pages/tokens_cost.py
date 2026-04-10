import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from claude_dashboard.components.charts import gauge_chart
from claude_dashboard.components.filters import apply_filters
from claude_dashboard.components.kpi_cards import render_kpi_row
from claude_dashboard.config import estimate_cost
from claude_dashboard.data.loader import get_data
from claude_dashboard.data.transcripts import load_all_transcript_tokens


def render():
    st.header("Tokens & Cost Analytics")

    data = get_data()
    df = apply_filters(data.sessions)

    if df.empty:
        st.info("No session data found.")
        return

    # --- Load transcript-level token data for cache analysis ---
    transcript_df = load_all_transcript_tokens(str(data.claude_dir))

    # --- KPI Row ---
    total_input = int(df["input_tokens"].sum())
    total_output = int(df["output_tokens"].sum())

    cache_read = 0
    cache_creation = 0
    if not transcript_df.empty:
        cache_read = int(transcript_df["cache_read_input_tokens"].sum())
        cache_creation = int(transcript_df["cache_creation_input_tokens"].sum())
    else:
        for usage in data.stats.model_usage.values():
            cache_read += usage.cache_read_input_tokens
            cache_creation += usage.cache_creation_input_tokens

    total_all = total_input + total_output + cache_read + cache_creation
    cache_hit_rate = (cache_read / (cache_read + total_input + cache_creation) * 100) if (cache_read + total_input + cache_creation) > 0 else 0

    render_kpi_row([
        {"label": "Input Tokens", "value": _fmt(total_input)},
        {"label": "Output Tokens", "value": _fmt(total_output)},
        {"label": "Cache Read", "value": _fmt(cache_read)},
        {"label": "Cache Creation", "value": _fmt(cache_creation)},
    ])

    st.divider()

    # --- Token Breakdown & Cache Hit Rate ---
    col1, col2 = st.columns(2)

    with col1:
        # Token type breakdown pie chart
        token_data = pd.DataFrame({
            "Type": ["Input", "Output", "Cache Read", "Cache Creation"],
            "Tokens": [total_input, total_output, cache_read, cache_creation],
        })
        token_data = token_data[token_data["Tokens"] > 0]

        fig = px.pie(
            token_data, names="Type", values="Tokens",
            title="Token Type Distribution",
            color_discrete_sequence=["#3b82f6", "#22c55e", "#06b6d4", "#f59e0b"],
        )
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = gauge_chart(cache_hit_rate, "Cache Hit Rate")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Token usage over time from transcripts ---
    if not transcript_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            daily_tokens = transcript_df.groupby("date").agg(
                input_tokens=("input_tokens", "sum"),
                output_tokens=("output_tokens", "sum"),
                cache_read=("cache_read_input_tokens", "sum"),
                cache_creation=("cache_creation_input_tokens", "sum"),
            ).reset_index()
            daily_tokens["date"] = pd.to_datetime(daily_tokens["date"])

            fig = px.bar(
                daily_tokens, x="date",
                y=["input_tokens", "output_tokens", "cache_read", "cache_creation"],
                title="Daily Token Breakdown",
                labels={"value": "Tokens", "variable": "Type", "date": "Date"},
                color_discrete_sequence=["#3b82f6", "#22c55e", "#06b6d4", "#f59e0b"],
            )
            fig.update_layout(height=400, barmode="stack", margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Cache hit rate over time
            daily_tokens["cache_hit_rate"] = (
                daily_tokens["cache_read"]
                / (daily_tokens["cache_read"] + daily_tokens["input_tokens"] + daily_tokens["cache_creation"])
                * 100
            ).fillna(0)

            fig = px.line(
                daily_tokens, x="date", y="cache_hit_rate",
                title="Cache Hit Rate Over Time",
                labels={"cache_hit_rate": "Hit Rate (%)", "date": "Date"},
            )
            fig.add_hline(y=70, line_dash="dash", line_color="#22c55e",
                         annotation_text="Good (70%)")
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Cost by Model ---
    col1, col2 = st.columns(2)

    with col1:
        if not transcript_df.empty:
            model_cost_rows = []
            for model_name, g in transcript_df.groupby("model"):
                cost = estimate_cost(
                    input_tokens=int(g["input_tokens"].sum()),
                    output_tokens=int(g["output_tokens"].sum()),
                    cache_read_tokens=int(g["cache_read_input_tokens"].sum()),
                    cache_creation_tokens=int(g["cache_creation_input_tokens"].sum()),
                    model=model_name,
                )
                model_cost_rows.append({"model": model_name, "cost_usd": cost})
            model_costs = pd.DataFrame(model_cost_rows)

            fig = px.bar(
                model_costs, x="model", y="cost_usd",
                title="Estimated Cost by Model (API Equiv.)",
                labels={"cost_usd": "Cost (USD)", "model": "Model"},
                color="model",
            )
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Cost per session distribution
        if not transcript_df.empty:
            session_cost_rows = []
            for sid, g in transcript_df.groupby("session_id"):
                cost = estimate_cost(
                    input_tokens=int(g["input_tokens"].sum()),
                    output_tokens=int(g["output_tokens"].sum()),
                    cache_read_tokens=int(g["cache_read_input_tokens"].sum()),
                    cache_creation_tokens=int(g["cache_creation_input_tokens"].sum()),
                    model=g["model"].iloc[0] if len(g) > 0 else "claude-sonnet-4-6",
                )
                session_cost_rows.append({"session_id": sid, "cost_usd": cost})
            session_costs = pd.DataFrame(session_cost_rows)

            fig = px.histogram(
                session_costs, x="cost_usd",
                title="Cost Per Session Distribution",
                labels={"cost_usd": "Cost (USD)"},
                nbins=20,
            )
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Cost per Successful Session ---
    has_facets = "outcome" in df.columns and df["outcome"].notna().any()
    if not transcript_df.empty and has_facets:
        st.subheader("Cost vs Outcome")
        col1, col2 = st.columns(2)

        # Build session cost lookup
        session_cost_map = {}
        for sid, g in transcript_df.groupby("session_id"):
            session_cost_map[sid] = estimate_cost(
                input_tokens=int(g["input_tokens"].sum()),
                output_tokens=int(g["output_tokens"].sum()),
                cache_read_tokens=int(g["cache_read_input_tokens"].sum()),
                cache_creation_tokens=int(g["cache_creation_input_tokens"].sum()),
                model=g["model"].iloc[0] if len(g) > 0 else "claude-sonnet-4-6",
            )

        df_cost = df[df["outcome"].notna()].copy()
        df_cost["session_cost"] = df_cost["session_id"].map(session_cost_map)
        df_cost = df_cost.dropna(subset=["session_cost"])

        if not df_cost.empty:
            with col1:
                fig = px.box(
                    df_cost, x="outcome", y="session_cost",
                    title="Cost by Session Outcome",
                    labels={"session_cost": "Cost (USD)", "outcome": "Outcome"},
                    color="outcome",
                    color_discrete_map={
                        "achieved": "#22c55e", "fully_achieved": "#22c55e",
                        "mostly_achieved": "#86efac",
                        "partially_achieved": "#f59e0b",
                        "not_achieved": "#ef4444",
                    },
                )
                fig.update_layout(height=400, showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.scatter(
                    df_cost, x="session_cost", y="outcome_score",
                    title="Cost vs Goal Achievement",
                    labels={"session_cost": "Cost (USD)", "outcome_score": "Achievement"},
                    trendline="ols",
                    color="project_name",
                )
                fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

    # --- Weekly Cost Trends ---
    if not transcript_df.empty:
        st.subheader("Weekly Cost Trends")
        col1, col2 = st.columns(2)

        # Compute daily costs
        daily_cost_rows = []
        for date, g in transcript_df.groupby("date"):
            cost = estimate_cost(
                input_tokens=int(g["input_tokens"].sum()),
                output_tokens=int(g["output_tokens"].sum()),
                cache_read_tokens=int(g["cache_read_input_tokens"].sum()),
                cache_creation_tokens=int(g["cache_creation_input_tokens"].sum()),
                model=g["model"].iloc[0] if len(g) > 0 else "claude-sonnet-4-6",
            )
            daily_cost_rows.append({"date": date, "cost_usd": cost})

        if daily_cost_rows:
            daily_cost_df = pd.DataFrame(daily_cost_rows)
            daily_cost_df["date"] = pd.to_datetime(daily_cost_df["date"])
            daily_cost_df = daily_cost_df.sort_values("date")

            with col1:
                # Weekly aggregation
                weekly = daily_cost_df.set_index("date").resample("W")["cost_usd"].sum().reset_index()
                weekly["rolling_avg"] = weekly["cost_usd"].rolling(window=4, min_periods=1).mean()

                fig = px.bar(
                    weekly, x="date", y="cost_usd",
                    title="Weekly Cost (API Equiv.)",
                    labels={"cost_usd": "Cost (USD)", "date": "Week"},
                )
                fig.add_scatter(
                    x=weekly["date"], y=weekly["rolling_avg"],
                    mode="lines", name="4-week avg",
                    line=dict(color="#f59e0b", dash="dash"),
                )
                fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Anomaly detection
                mean_cost = daily_cost_df["cost_usd"].mean()
                std_cost = daily_cost_df["cost_usd"].std()
                if std_cost > 0:
                    daily_cost_df["is_anomaly"] = daily_cost_df["cost_usd"] > (mean_cost + 2 * std_cost)
                else:
                    daily_cost_df["is_anomaly"] = False

                fig = px.scatter(
                    daily_cost_df, x="date", y="cost_usd",
                    title="Daily Cost (anomalies highlighted)",
                    labels={"cost_usd": "Cost (USD)", "date": "Date"},
                    color="is_anomaly",
                    color_discrete_map={True: "#ef4444", False: "#6366f1"},
                )
                fig.add_hline(
                    y=mean_cost, line_dash="dash", line_color="#94a3b8",
                    annotation_text=f"Avg: ${mean_cost:.2f}",
                )
                if std_cost > 0:
                    fig.add_hline(
                        y=mean_cost + 2 * std_cost, line_dash="dot", line_color="#ef4444",
                        annotation_text="Anomaly threshold",
                    )
                fig.update_layout(height=400, showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

                anomaly_count = daily_cost_df["is_anomaly"].sum()
                if anomaly_count > 0:
                    st.warning(f"**{anomaly_count} high-cost days** detected above the anomaly threshold.")

        st.divider()

    # --- Model ROI Comparison ---
    if not transcript_df.empty and has_facets:
        st.subheader("Model ROI Comparison")

        model_roi_rows = []
        for model_name, g in transcript_df.groupby("model"):
            cost = estimate_cost(
                input_tokens=int(g["input_tokens"].sum()),
                output_tokens=int(g["output_tokens"].sum()),
                cache_read_tokens=int(g["cache_read_input_tokens"].sum()),
                cache_creation_tokens=int(g["cache_creation_input_tokens"].sum()),
                model=model_name,
            )
            session_ids = g["session_id"].unique()
            model_sessions = df[df["session_id"].isin(session_ids)]
            avg_outcome = model_sessions["outcome_score"].mean() if "outcome_score" in model_sessions.columns else 0
            total_lines = model_sessions["lines_added"].sum()
            total_messages = model_sessions["total_messages"].sum()

            model_roi_rows.append({
                "Model": model_name,
                "Total Cost": f"${cost:.2f}",
                "Sessions": len(session_ids),
                "Avg Outcome": f"{avg_outcome:.0%}" if pd.notna(avg_outcome) else "N/A",
                "Lines / Dollar": f"{total_lines / max(cost, 0.01):.0f}" if cost > 0 else "N/A",
                "Cost / Message": f"${cost / max(total_messages, 1):.4f}",
            })

        if model_roi_rows:
            st.dataframe(
                pd.DataFrame(model_roi_rows),
                use_container_width=True,
                hide_index=True,
            )

    st.caption("Costs are estimated API-equivalent rates. Actual billing depends on your plan (Pro/Max).")


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
