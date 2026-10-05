"""
Energy Report Component
========================

Renders energy consumption reports and comparison cards.
"""

import streamlit as st
from ai.energy_optimizer import EnergyReport


def render_energy_summary(report: EnergyReport, title: str = "Energy Report"):
    """
    Render an energy consumption summary card.

    Args:
        report: EnergyReport from the energy optimizer.
        title:  Section title.
    """
    st.markdown(f"### ⚡ {title}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Energy",
            f"{report.total_energy_kwh:.1f} kWh",
            help="Total electrical energy consumed"
        )
    with col2:
        st.metric(
            "Daily Average",
            f"{report.daily_avg_kwh:.1f} kWh/day",
            help="Average daily consumption"
        )
    with col3:
        st.metric(
            "Peak Power",
            f"{report.peak_power_w:.0f} W",
            help="Maximum instantaneous power"
        )
    with col4:
        st.metric(
            "Est. Cost",
            f"${report.cost_estimate:.2f}",
            help="Estimated electricity cost"
        )

    col5, col6, col7, col8 = st.columns(4)

    with col5:
        st.metric(
            "Comfort Score",
            f"{report.comfort_score:.1f}%",
            help="Percentage of time in comfort zone"
        )
    with col6:
        st.metric(
            "Violations",
            f"{report.comfort_violations_minutes} min",
            help="Minutes outside comfort zone"
        )
    with col7:
        st.metric(
            "Effective COP",
            f"{report.cop_effective:.2f}",
            help="Coefficient of Performance"
        )
    with col8:
        st.metric(
            "Cooling / Heating",
            f"{report.cooling_energy_kwh:.1f} / {report.heating_energy_kwh:.1f} kWh",
            help="Energy split between cooling and heating"
        )


def render_comparison_summary(comparison: dict, annual: dict):
    """
    Render a controller comparison summary.

    Args:
        comparison: Comparison dictionary from EnergyOptimizer.compare()
        annual:     Annual projection dictionary
    """
    st.markdown("### 📊 Improvement Summary")

    col1, col2, col3, col4 = st.columns(4)

    energy_pct = comparison.get("energy_savings_pct", 0)
    with col1:
        st.metric(
            "Energy Savings",
            f"{energy_pct:.1f}%",
            delta=f"{comparison.get('energy_saved_kwh', 0):.1f} kWh saved",
            delta_color="normal" if energy_pct > 0 else "inverse"
        )
    with col2:
        st.metric(
            "Cost Saved",
            f"${comparison.get('cost_saved', 0):.2f}",
            delta=f"${annual.get('annual_cost_savings', 0):.0f}/year projected"
        )
    with col3:
        comfort = comparison.get("comfort_change_pct", 0)
        st.metric(
            "Comfort Change",
            f"{comfort:+.1f}%",
            delta_color="normal" if comfort >= 0 else "inverse"
        )
    with col4:
        st.metric(
            "CO₂ Reduction",
            f"{annual.get('annual_co2_saved_kg', 0):.0f} kg/yr",
            help="Estimated annual CO₂ reduction"
        )
