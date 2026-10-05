"""
Dashboard Control Panel
========================

Sidebar controls for the HVAC monitoring dashboard.
"""

import streamlit as st
from simulation.weather import Season


def render_sidebar_controls() -> dict:
    """
    Render the sidebar control panel and return user selections.

    Returns:
        Dictionary with user-selected parameters.
    """
    st.sidebar.markdown("## 🎛️ Control Panel")
    st.sidebar.markdown("---")

    # Simulation controls
    st.sidebar.markdown("### ⚙️ Simulation")

    season = st.sidebar.selectbox(
        "Season Profile",
        ["summer", "winter", "spring", "fall"],
        index=0,
        help="Select the outdoor weather profile"
    )

    days = st.sidebar.slider(
        "Duration (days)",
        min_value=1, max_value=14, value=7,
        help="Simulation duration"
    )

    controller = st.sidebar.selectbox(
        "Controller",
        ["rule_based", "adaptive", "comparison"],
        index=0,
        format_func=lambda x: {
            "rule_based": "📏 Rule-Based",
            "adaptive": "🧠 Adaptive Q-Learning",
            "comparison": "⚖️ Compare Both"
        }.get(x, x),
        help="Select the HVAC control strategy"
    )

    st.sidebar.markdown("---")

    # Comfort settings
    st.sidebar.markdown("### 🌡️ Comfort Zone")

    cooling_threshold = st.sidebar.slider(
        "Cooling Threshold (°C)",
        min_value=24.0, max_value=30.0, value=26.0, step=0.5,
        help="Start cooling above this temperature"
    )

    heating_threshold = st.sidebar.slider(
        "Heating Threshold (°C)",
        min_value=15.0, max_value=22.0, value=20.0, step=0.5,
        help="Start heating below this temperature"
    )

    st.sidebar.markdown("---")

    # Energy settings
    st.sidebar.markdown("### 💡 Energy")

    electricity_rate = st.sidebar.number_input(
        "Electricity Rate ($/kWh)",
        min_value=0.01, max_value=1.00, value=0.12, step=0.01,
        help="Local electricity cost for savings projections"
    )

    comfort_weight = st.sidebar.slider(
        "Comfort Priority",
        min_value=0.0, max_value=1.0, value=0.7, step=0.1,
        help="0.0 = Maximum energy savings, 1.0 = Maximum comfort",
        format="%.1f"
    )

    st.sidebar.markdown("---")

    # Run button
    run_clicked = st.sidebar.button(
        "▶️  Run Simulation",
        use_container_width=True,  # Keep for st.button (not deprecated there)
        type="primary"
    )

    return {
        "season": season,
        "days": days,
        "controller": controller,
        "cooling_threshold": cooling_threshold,
        "heating_threshold": heating_threshold,
        "electricity_rate": electricity_rate,
        "comfort_weight": comfort_weight,
        "run_clicked": run_clicked,
    }
