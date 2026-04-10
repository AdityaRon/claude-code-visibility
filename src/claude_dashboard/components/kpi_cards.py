import streamlit as st


def render_kpi_row(metrics: list[dict]):
    """Render a row of KPI metric cards.

    Each dict: {"label": str, "value": str|int|float, "delta": str|None}
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        col.metric(
            label=m["label"],
            value=m["value"],
            delta=m.get("delta"),
        )
