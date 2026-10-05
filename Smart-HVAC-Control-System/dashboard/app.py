"""
Smart HVAC Control System — Streamlit Dashboard
=================================================

Premium monitoring and control dashboard for the HVAC simulation.

Features:
- Real-time temperature and humidity gauges
- Time-series charts with comfort zone visualization
- Energy consumption tracking and analysis
- HVAC operating state timeline
- Controller comparison (rule-based vs adaptive)
- Interactive simulation controls

Usage:
    streamlit run dashboard/app.py
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import streamlit as st
import pandas as pd
import numpy as np

from dashboard.styles.theme import PAGE_CONFIG, CUSTOM_CSS, COLORS
from dashboard.components.gauges import temperature_gauge, humidity_gauge, hvac_status_indicator
from dashboard.components.charts import (
    temperature_timeseries, energy_consumption_chart,
    hvac_state_timeline, comfort_heatmap, comparison_bar_chart
)
from dashboard.components.controls import render_sidebar_controls
from dashboard.components.energy_report import render_energy_summary, render_comparison_summary
from simulation.environment import HVACEnvironment, ComfortBand
from simulation.weather import Season
from simulation.data_logger import DataLogger
from simulation.hvac_plant import HVACAction
from controllers.rule_based import RuleBasedController
from controllers.adaptive_qlearning import AdaptiveQLearningController
from ai.energy_optimizer import EnergyOptimizer


# Page configuration
st.set_page_config(**PAGE_CONFIG)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def run_sim(controller_type, season, days, cooling_threshold, heating_threshold, seed=42):
    """Run simulation and return the DataFrame."""
    season_map = {
        "summer": Season.SUMMER, "winter": Season.WINTER,
        "spring": Season.SPRING, "fall": Season.FALL,
    }
    season_enum = season_map.get(season, Season.SUMMER)

    initial_temps = {
        Season.SUMMER: 28.0, Season.WINTER: 18.0,
        Season.SPRING: 22.0, Season.FALL: 22.0,
    }

    comfort = ComfortBand(
        cooling_threshold=cooling_threshold,
        heating_threshold=heating_threshold,
    )

    db_path = os.path.join(project_root, "data", f"dash_{controller_type}_{season}.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    env = HVACEnvironment(
        season=season_enum,
        comfort=comfort,
        db_path=db_path,
        controller_name=controller_type,
        seed=seed,
    )

    if controller_type == "adaptive":
        controller = AdaptiveQLearningController(seed=seed)
        # Quick warm-start
        rule_ctrl = RuleBasedController(
            cooling_threshold=cooling_threshold,
            heating_threshold=heating_threshold,
        )
        warm_db = os.path.join(project_root, "data", "dash_warmstart.db")
        warm_env = HVACEnvironment(
            season=season_enum, comfort=comfort,
            db_path=warm_db, controller_name="warmstart", seed=seed + 100,
        )
        warm_env.reset(initial_temp=initial_temps[season_enum], max_days=1)
        controller.warm_start_from_rule_based(warm_env, rule_ctrl, n_steps=1440)
        warm_env.close()
        try:
            os.remove(warm_db)
        except OSError:
            pass
    else:
        controller = RuleBasedController(
            cooling_threshold=cooling_threshold,
            heating_threshold=heating_threshold,
        )

    state = env.reset(initial_temp=initial_temps[season_enum], max_days=days)

    progress_bar = st.progress(0, text="Simulating...")
    total_steps = days * 1440

    step = 0
    while not env.done:
        action = controller.compute_action(state)
        next_state, reward, done, info = env.step(action)
        controller.update(state, action, reward, next_state, done)
        state = next_state
        step += 1

        if step % 720 == 0:  # Update progress every 12 hours
            progress_bar.progress(step / total_steps,
                                  text=f"Day {step // 1440 + 1}/{days}...")

    progress_bar.progress(1.0, text="Complete!")
    summary = env.finalize()

    logger = DataLogger(db_path=db_path)
    df = logger.get_dataframe(controller_type)
    logger.close()
    env.close()

    return df, summary


def main():
    # Header
    st.markdown("""
    <div style='text-align: center; padding: 10px 0 20px 0;'>
        <h1 style='font-size: 2.2rem; background: linear-gradient(135deg, #3b82f6, #06b6d4, #10b981);
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                    margin-bottom: 4px;'>
            🌡️ Smart HVAC Control System
        </h1>
        <p style='color: #94a3b8; font-size: 1.0rem; margin: 0;'>
            Bidirectional Climate Control • AI-Optimized • Real-Time Monitoring
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar controls
    params = render_sidebar_controls()

    # About section in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style='text-align: center; color: #64748b; font-size: 0.8rem;'>
        <p>Smart HVAC Control System v1.0</p>
        <p>RC Thermal Model • Q-Learning AI</p>
        <p>Bidirectional Heat Pump Control</p>
    </div>
    """, unsafe_allow_html=True)

    if params["run_clicked"]:
        if params["controller"] == "comparison":
            # Run both controllers
            st.markdown("## ⚖️ Controller Comparison")
            st.markdown("Running both controllers under identical conditions...")

            col_left, col_right = st.columns(2)

            with col_left:
                st.markdown("### 📏 Rule-Based Controller")
                df_rule, summary_rule = run_sim(
                    "rule_based", params["season"], params["days"],
                    params["cooling_threshold"], params["heating_threshold"]
                )

            with col_right:
                st.markdown("### 🧠 Adaptive Q-Learning")
                df_adaptive, summary_adaptive = run_sim(
                    "adaptive", params["season"], params["days"],
                    params["cooling_threshold"], params["heating_threshold"]
                )

            # Analysis
            optimizer = EnergyOptimizer(params["electricity_rate"])
            report_rule = optimizer.analyze(df_rule, "Rule-Based")
            report_adaptive = optimizer.analyze(df_adaptive, "Adaptive")
            comparison = optimizer.compare(report_rule, report_adaptive)
            annual = optimizer.project_annual_savings(report_rule, report_adaptive)

            st.markdown("---")
            render_comparison_summary(comparison, annual)

            st.markdown("---")

            # Side-by-side energy reports
            col1, col2 = st.columns(2)
            with col1:
                render_energy_summary(report_rule, "Rule-Based Energy")
            with col2:
                render_energy_summary(report_adaptive, "Adaptive Energy")

            st.markdown("---")

            # Comparison charts
            tab1, tab2, tab3 = st.tabs(["🌡️ Temperature", "⚡ Energy", "📊 Comparison"])

            with tab1:
                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(
                        temperature_timeseries(df_rule, "Rule-Based Temperature"),
                        width='stretch'
                    )
                with col2:
                    st.plotly_chart(
                        temperature_timeseries(df_adaptive, "Adaptive Temperature"),
                        width='stretch'
                    )

            with tab2:
                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(
                        energy_consumption_chart(df_rule, "Rule-Based Energy"),
                        width='stretch'
                    )
                with col2:
                    st.plotly_chart(
                        energy_consumption_chart(df_adaptive, "Adaptive Energy"),
                        width='stretch'
                    )

            with tab3:
                st.plotly_chart(
                    comparison_bar_chart(comparison, "Controller Comparison"),
                    width='stretch'
                )

        else:
            # Single controller run
            ctrl_label = "📏 Rule-Based" if params["controller"] == "rule_based" else "🧠 Adaptive Q-Learning"
            st.markdown(f"## {ctrl_label} Controller")

            df, summary = run_sim(
                params["controller"], params["season"], params["days"],
                params["cooling_threshold"], params["heating_threshold"]
            )

            if df.empty:
                st.error("No simulation data generated. Please try again.")
                return

            # Current state gauges
            st.markdown("### 📡 Current State")
            last = df.iloc[-1]

            g1, g2, g3 = st.columns(3)
            with g1:
                st.plotly_chart(
                    temperature_gauge(last["temp_indoor"], "Indoor Temp"),
                    width='stretch'
                )
            with g2:
                st.plotly_chart(
                    humidity_gauge(last["humidity_indoor"], "Indoor Humidity"),
                    width='stretch'
                )
            with g3:
                st.plotly_chart(
                    hvac_status_indicator(
                        last.get("hvac_mode", "idle"),
                        last.get("hvac_stage", "OFF"),
                        last.get("hvac_power_w", 0)
                    ),
                    width='stretch'
                )
                # Additional metrics
                st.metric("Outdoor Temp", f"{last['temp_outdoor']:.1f}°C")
                occ_text = "🟢 Occupied" if last.get("occupied", 0) else "⚫ Unoccupied"
                st.markdown(f"**Occupancy:** {occ_text}")

            st.markdown("---")

            # Energy report
            optimizer = EnergyOptimizer(params["electricity_rate"])
            report = optimizer.analyze(df, params["controller"])
            render_energy_summary(report)

            st.markdown("---")

            # Charts
            tab1, tab2, tab3, tab4 = st.tabs([
                "🌡️ Temperature", "⚡ Energy", "🔄 HVAC States", "🗺️ Heatmap"
            ])

            with tab1:
                st.plotly_chart(
                    temperature_timeseries(df),
                    width='stretch'
                )

            with tab2:
                st.plotly_chart(
                    energy_consumption_chart(df),
                    width='stretch'
                )

            with tab3:
                st.plotly_chart(
                    hvac_state_timeline(df),
                    width='stretch'
                )

            with tab4:
                st.plotly_chart(
                    comfort_heatmap(df),
                    width='stretch'
                )

    else:
        # Landing page
        st.markdown("""
        <div style='text-align: center; padding: 60px 20px;'>
            <div style='font-size: 4rem; margin-bottom: 16px;'>🏠</div>
            <h2 style='color: #94a3b8; font-weight: 400; margin-bottom: 24px;'>
                Configure your simulation in the sidebar and click
                <span style='color: #3b82f6; font-weight: 600;'>Run Simulation</span>
            </h2>
            <div style='display: flex; justify-content: center; gap: 40px; margin-top: 40px;'>
                <div style='text-align: center;'>
                    <div style='font-size: 2rem;'>❄️🔥</div>
                    <p style='color: #64748b; margin-top: 8px;'>Bidirectional<br>Heat Pump Control</p>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 2rem;'>🧠</div>
                    <p style='color: #64748b; margin-top: 8px;'>Q-Learning<br>Adaptive AI</p>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 2rem;'>📊</div>
                    <p style='color: #64748b; margin-top: 8px;'>Energy Analytics<br>& Optimization</p>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 2rem;'>⚖️</div>
                    <p style='color: #64748b; margin-top: 8px;'>Controller<br>Comparison</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
