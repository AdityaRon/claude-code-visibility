from datetime import timedelta

import pandas as pd
import streamlit as st


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render sidebar filters and return filtered DataFrame."""
    if df.empty:
        return df

    with st.sidebar:
        st.markdown("### Filters")

        # Date range presets
        min_date = df["date"].min()
        max_date = df["date"].max()

        preset = st.radio(
            "Time range",
            ["Last 7 days", "Last 30 days", "All time", "Custom"],
            index=2,
            horizontal=True,
        )

        if preset == "Last 7 days":
            start = max_date - timedelta(days=7)
            end = max_date
        elif preset == "Last 30 days":
            start = max_date - timedelta(days=30)
            end = max_date
        elif preset == "All time":
            start = min_date
            end = max_date
        else:
            date_range = st.date_input(
                "Date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start, end = date_range
            else:
                start, end = min_date, max_date

        # Project filter
        projects = sorted(df["project_name"].unique())
        selected_projects = st.multiselect("Projects", options=projects)

        # Apply filters
        filtered = df[(df["date"] >= start) & (df["date"] <= end)]
        if selected_projects:
            filtered = filtered[filtered["project_name"].isin(selected_projects)]

        st.caption(f"Showing {len(filtered)} of {len(df)} sessions")

        if st.button("Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    return filtered
