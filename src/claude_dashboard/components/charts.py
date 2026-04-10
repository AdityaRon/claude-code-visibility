import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def activity_heatmap(message_hours: list[list[int]], dates: list, title: str = "Activity Heatmap"):
    """Create hour-of-day x day-of-week heatmap from message_hours and session dates."""
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    matrix = np.zeros((7, 24))

    for hours, date in zip(message_hours, dates):
        if not hours or date is None:
            continue
        try:
            day_of_week = pd.Timestamp(date).dayofweek
        except Exception:
            continue
        for h in hours:
            if 0 <= h < 24:
                matrix[day_of_week][h] += 1

    fig = px.imshow(
        matrix,
        labels=dict(x="Hour of Day", y="Day of Week", color="Messages"),
        x=[str(h) for h in range(24)],
        y=day_names,
        color_continuous_scale="Blues",
        aspect="auto",
    )
    fig.update_layout(title=title, height=300, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def gauge_chart(value: float, title: str, max_val: float = 100):
    """Create a gauge chart for a percentage metric."""
    color = "#22c55e" if value >= 70 else "#f59e0b" if value >= 40 else "#ef4444"
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={"text": title},
        number={"suffix": "%"},
        gauge={
            "axis": {"range": [0, max_val]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 40], "color": "#fef2f2"},
                {"range": [40, 70], "color": "#fefce8"},
                {"range": [70, 100], "color": "#f0fdf4"},
            ],
        },
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=60, b=20))
    return fig
