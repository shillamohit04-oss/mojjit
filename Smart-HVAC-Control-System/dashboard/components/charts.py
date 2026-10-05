"""
Dashboard Chart Components
===========================

Interactive Plotly time-series charts for the HVAC monitoring dashboard.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from dashboard.styles.theme import COLORS, PLOTLY_LAYOUT


def temperature_timeseries(df: pd.DataFrame, title: str = "Temperature Over Time") -> go.Figure:
    """
    Create a temperature time-series chart with indoor, outdoor, and comfort zone.

    Args:
        df:    DataFrame with columns: hour, day, temp_indoor, temp_outdoor
        title: Chart title

    Returns:
        Plotly Figure
    """
    # Create time axis (hours from start)
    if "minute" in df.columns:
        time_hours = df["minute"] / 60.0
    else:
        time_hours = np.arange(len(df)) / 60.0

    fig = go.Figure()

    # Comfort zone band
    fig.add_trace(go.Scatter(
        x=time_hours, y=[26] * len(time_hours),
        mode="lines", line={"width": 0}, showlegend=False,
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=time_hours, y=[20] * len(time_hours),
        mode="lines", line={"width": 0},
        fill="tonexty", fillcolor="rgba(16,185,129,0.08)",
        name="Comfort Zone (20-26°C)",
    ))

    # Outdoor temperature
    fig.add_trace(go.Scatter(
        x=time_hours, y=df["temp_outdoor"],
        mode="lines",
        name="Outdoor",
        line={"color": COLORS["accent_amber"], "width": 1.5, "dash": "dot"},
        opacity=0.7,
    ))

    # Indoor temperature
    fig.add_trace(go.Scatter(
        x=time_hours, y=df["temp_indoor"],
        mode="lines",
        name="Indoor",
        line={"color": COLORS["accent_cyan"], "width": 2.5},
    ))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title={"text": title, "font": {"size": 16}},
        xaxis_title="Time (hours)",
        yaxis_title="Temperature (°C)",
        height=400,
        hovermode="x unified",
    )

    return fig


def energy_consumption_chart(df: pd.DataFrame, title: str = "Energy Consumption") -> go.Figure:
    """
    Create an energy consumption chart with power and cumulative energy.

    Shows instantaneous power (W) and cumulative energy (kWh) on dual axes.
    """
    if "minute" in df.columns:
        time_hours = df["minute"] / 60.0
    else:
        time_hours = np.arange(len(df)) / 60.0

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Power (left axis) — area chart
    fig.add_trace(
        go.Scatter(
            x=time_hours, y=df["hvac_power_w"],
            mode="lines",
            name="Power (W)",
            line={"color": COLORS["accent_purple"], "width": 1},
            fill="tozeroy",
            fillcolor="rgba(139,92,246,0.15)",
        ),
        secondary_y=False,
    )

    # Cumulative energy (right axis)
    fig.add_trace(
        go.Scatter(
            x=time_hours, y=df["energy_consumed_kwh"],
            mode="lines",
            name="Cumulative Energy (kWh)",
            line={"color": COLORS["accent_emerald"], "width": 2.5},
        ),
        secondary_y=True,
    )

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title={"text": title, "font": {"size": 16}},
        height=350,
        hovermode="x unified",
    )

    fig.update_xaxes(title_text="Time (hours)")
    fig.update_yaxes(title_text="Power (W)", secondary_y=False,
                     gridcolor="#1e293b")
    fig.update_yaxes(title_text="Energy (kWh)", secondary_y=True,
                     gridcolor="#1e293b")

    return fig


def hvac_state_timeline(df: pd.DataFrame, title: str = "HVAC Operating States") -> go.Figure:
    """
    Create a timeline showing HVAC operating states over time.

    Color-coded by mode: cooling (cyan), heating (orange), idle (gray).
    """
    if "minute" in df.columns:
        time_hours = df["minute"] / 60.0
    else:
        time_hours = np.arange(len(df)) / 60.0

    # Map modes to numeric for coloring
    mode_map = {"cooling": -1, "idle": 0, "heating": 1}
    mode_numeric = df["hvac_mode"].map(mode_map).fillna(0)

    fig = go.Figure()

    # Add colored bars for each mode
    for mode, color, label in [
        ("cooling", COLORS["hvac_cooling"], "❄️ Cooling"),
        ("heating", COLORS["hvac_heating"], "🔥 Heating"),
        ("idle", COLORS["hvac_idle"], "⏸️ Idle"),
    ]:
        mask = df["hvac_mode"] == mode
        if mask.any():
            fig.add_trace(go.Scatter(
                x=time_hours[mask],
                y=[1] * mask.sum(),
                mode="markers",
                name=label,
                marker={
                    "color": color,
                    "size": 3,
                    "symbol": "square",
                },
            ))

    layout_kwargs = {k: v for k, v in PLOTLY_LAYOUT.items() if k not in ("xaxis", "yaxis")}
    fig.update_layout(
        **layout_kwargs,
        title={"text": title, "font": {"size": 16}},
        xaxis_title="Time (hours)",
        xaxis=PLOTLY_LAYOUT.get("xaxis", {}),
        yaxis={"visible": False},
        height=150,
        showlegend=True,
    )

    return fig


def comfort_heatmap(df: pd.DataFrame, title: str = "Daily Temperature Pattern") -> go.Figure:
    """
    Create a heatmap showing temperature patterns by day and hour.

    Rows = days, Columns = hours, Color = indoor temperature.
    """
    if "day" not in df.columns or "hour" not in df.columns:
        return go.Figure()

    # Pivot to day × hour matrix
    df["hour_bin"] = df["hour"].apply(lambda h: int(h))
    pivot = df.pivot_table(values="temp_indoor", index="day", columns="hour_bin",
                            aggfunc="mean")

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=[f"{h}:00" for h in range(24)],
        y=[f"Day {d+1}" for d in range(len(pivot))],
        colorscale=[
            [0.0, COLORS["zone_cold"]],
            [0.4, COLORS["accent_cyan"]],
            [0.5, COLORS["zone_comfort"]],
            [0.7, COLORS["accent_amber"]],
            [1.0, COLORS["zone_hot"]],
        ],
        colorbar={"title": "°C", "tickfont": {"color": COLORS["text_muted"]}},
    ))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title={"text": title, "font": {"size": 16}},
        xaxis_title="Hour of Day",
        yaxis_title="",
        height=300,
    )

    return fig


def comparison_bar_chart(metrics: dict, title: str = "Controller Comparison") -> go.Figure:
    """
    Create a grouped bar chart comparing two controllers.

    Args:
        metrics: Dictionary with 'baseline' and 'optimized' sub-dicts.
        title:   Chart title

    Returns:
        Plotly Figure
    """
    categories = list(metrics.get("baseline", {}).keys())
    baseline_vals = list(metrics.get("baseline", {}).values())
    optimized_vals = list(metrics.get("optimized", {}).values())

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Rule-Based",
        x=categories, y=baseline_vals,
        marker_color=COLORS["accent_amber"],
        opacity=0.8,
    ))

    fig.add_trace(go.Bar(
        name="Adaptive Q-Learning",
        x=categories, y=optimized_vals,
        marker_color=COLORS["accent_emerald"],
        opacity=0.8,
    ))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title={"text": title, "font": {"size": 16}},
        barmode="group",
        height=350,
    )

    return fig
