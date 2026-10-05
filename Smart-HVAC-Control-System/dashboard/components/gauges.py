"""
Dashboard Gauge Components
===========================

Plotly-based gauge indicators for temperature, humidity, and HVAC state.
"""

import plotly.graph_objects as go
from dashboard.styles.theme import COLORS


def temperature_gauge(temp: float, title: str = "Indoor Temperature",
                      min_val: float = 10, max_val: float = 45) -> go.Figure:
    """
    Create a temperature gauge with comfort zone coloring.

    Args:
        temp:    Current temperature (°C)
        title:   Gauge title
        min_val: Minimum scale value
        max_val: Maximum scale value

    Returns:
        Plotly Figure
    """
    # Determine color based on comfort zone
    if temp < 20:
        bar_color = COLORS["zone_cold"]
    elif temp > 26:
        bar_color = COLORS["zone_hot"]
    else:
        bar_color = COLORS["zone_comfort"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=temp,
        title={"text": title, "font": {"size": 14, "color": COLORS["text_secondary"]}},
        number={"suffix": "°C", "font": {"size": 36, "color": COLORS["text_primary"]}},
        gauge={
            "axis": {
                "range": [min_val, max_val],
                "tickwidth": 1,
                "tickcolor": COLORS["text_muted"],
                "tickfont": {"color": COLORS["text_muted"]},
            },
            "bar": {"color": bar_color, "thickness": 0.75},
            "bgcolor": COLORS["bg_card"],
            "borderwidth": 0,
            "steps": [
                {"range": [min_val, 20], "color": "rgba(59,130,246,0.15)"},
                {"range": [20, 26], "color": "rgba(16,185,129,0.15)"},
                {"range": [26, max_val], "color": "rgba(239,68,68,0.15)"},
            ],
            "threshold": {
                "line": {"color": COLORS["accent_amber"], "width": 3},
                "thickness": 0.8,
                "value": 23  # Optimal setpoint
            },
        }
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif"},
        height=250,
        margin={"l": 20, "r": 20, "t": 50, "b": 10},
    )

    return fig


def humidity_gauge(humidity: float, title: str = "Indoor Humidity") -> go.Figure:
    """
    Create a humidity gauge with comfort zone coloring.

    Comfortable range: 30-60% RH
    """
    if humidity < 30:
        bar_color = COLORS["accent_amber"]  # Too dry
    elif humidity > 60:
        bar_color = COLORS["accent_red"]    # Too humid
    else:
        bar_color = COLORS["accent_cyan"]   # Comfortable

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=humidity,
        title={"text": title, "font": {"size": 14, "color": COLORS["text_secondary"]}},
        number={"suffix": "%", "font": {"size": 36, "color": COLORS["text_primary"]}},
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": COLORS["text_muted"],
                "tickfont": {"color": COLORS["text_muted"]},
            },
            "bar": {"color": bar_color, "thickness": 0.75},
            "bgcolor": COLORS["bg_card"],
            "borderwidth": 0,
            "steps": [
                {"range": [0, 30], "color": "rgba(245,158,11,0.1)"},
                {"range": [30, 60], "color": "rgba(6,182,212,0.1)"},
                {"range": [60, 100], "color": "rgba(239,68,68,0.1)"},
            ],
        }
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif"},
        height=250,
        margin={"l": 20, "r": 20, "t": 50, "b": 10},
    )

    return fig


def hvac_status_indicator(mode: str, stage: str, power_w: float) -> go.Figure:
    """
    Create an HVAC status indicator.

    Shows current mode (cooling/heating/idle), stage, and power consumption.
    """
    mode_colors = {
        "cooling": COLORS["hvac_cooling"],
        "heating": COLORS["hvac_heating"],
        "idle": COLORS["hvac_idle"],
    }
    mode_icons = {
        "cooling": "❄️",
        "heating": "🔥",
        "idle": "⏸️",
    }

    color = mode_colors.get(mode, COLORS["hvac_off"])
    icon = mode_icons.get(mode, "⏹️")

    fig = go.Figure(go.Indicator(
        mode="number",
        value=power_w,
        title={
            "text": f"{icon} HVAC: {mode.upper()} ({stage})",
            "font": {"size": 14, "color": color}
        },
        number={
            "suffix": " W",
            "font": {"size": 32, "color": color}
        },
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif"},
        height=160,
        margin={"l": 20, "r": 20, "t": 60, "b": 10},
    )

    return fig
