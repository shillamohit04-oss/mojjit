"""
Energy Optimizer — Comfort vs Energy Trade-off
===============================================

Provides Pareto-optimal trade-off analysis between:
- Thermal comfort (maintaining temperature in comfort zone)
- Energy consumption (minimizing kWh)

Features:
- Adjustable comfort weight (0.0 = max savings, 1.0 = max comfort)
- Daily/weekly energy projections
- Cost estimation at configurable electricity rate
- Comparison reporting (before vs after optimization)
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class EnergyReport:
    """Energy consumption report for a simulation period."""
    period_days: float
    total_energy_kwh: float
    daily_avg_kwh: float
    peak_power_w: float
    avg_power_w: float
    cooling_energy_kwh: float
    heating_energy_kwh: float
    comfort_score: float           # 0–100%
    comfort_violations_minutes: int
    avg_violation_deg: float
    cost_estimate: float           # $ at given rate
    cop_effective: float           # Effective COP over period


class EnergyOptimizer:
    """
    Analyzes and optimizes the energy/comfort trade-off.

    Provides:
    1. Energy consumption analysis from simulation data
    2. Comfort compliance metrics
    3. Comparison between controllers
    4. Cost projections
    5. Optimization recommendations
    """

    def __init__(self, electricity_rate: float = 0.12):
        """
        Args:
            electricity_rate: Electricity cost in $/kWh. Default = $0.12/kWh.
        """
        self.electricity_rate = electricity_rate

    def analyze(self, df: pd.DataFrame, controller_name: str = "") -> EnergyReport:
        """
        Analyze simulation data and produce an energy report.

        Args:
            df:              DataFrame from DataLogger.get_dataframe()
            controller_name: Name of the controller for labeling.

        Returns:
            EnergyReport with detailed metrics.
        """
        if df.empty:
            return EnergyReport(
                period_days=0, total_energy_kwh=0, daily_avg_kwh=0,
                peak_power_w=0, avg_power_w=0, cooling_energy_kwh=0,
                heating_energy_kwh=0, comfort_score=100, comfort_violations_minutes=0,
                avg_violation_deg=0, cost_estimate=0, cop_effective=1.0
            )

        total_minutes = df["minute"].max() - df["minute"].min() + 1
        period_days = total_minutes / 1440.0

        # Energy consumption
        total_energy = df["energy_consumed_kwh"].iloc[-1] if "energy_consumed_kwh" in df else 0
        total_delivered = df["energy_delivered_kwh"].iloc[-1] if "energy_delivered_kwh" in df else 0

        # Cooling vs heating breakdown
        cooling_minutes = (df["hvac_mode"] == "cooling").sum()
        heating_minutes = (df["hvac_mode"] == "heating").sum()
        total_active = cooling_minutes + heating_minutes

        cooling_fraction = cooling_minutes / max(total_active, 1)
        heating_fraction = heating_minutes / max(total_active, 1)

        cooling_energy = total_energy * cooling_fraction
        heating_energy = total_energy * heating_fraction

        # Power statistics
        peak_power = df["hvac_power_w"].max() if "hvac_power_w" in df else 0
        avg_power = df["hvac_power_w"].mean() if "hvac_power_w" in df else 0

        # Comfort metrics
        if "in_comfort_zone" in df:
            comfort_score = df["in_comfort_zone"].mean() * 100
            violations = (~df["in_comfort_zone"].astype(bool)).sum()
        else:
            comfort_score = 100.0
            violations = 0

        avg_violation = df["comfort_violation_deg"].mean() if "comfort_violation_deg" in df else 0

        # Effective COP
        cop = total_delivered / max(total_energy, 0.001)

        return EnergyReport(
            period_days=round(period_days, 1),
            total_energy_kwh=round(total_energy, 2),
            daily_avg_kwh=round(total_energy / max(period_days, 1), 2),
            peak_power_w=round(peak_power, 0),
            avg_power_w=round(avg_power, 0),
            cooling_energy_kwh=round(cooling_energy, 2),
            heating_energy_kwh=round(heating_energy, 2),
            comfort_score=round(comfort_score, 1),
            comfort_violations_minutes=int(violations),
            avg_violation_deg=round(avg_violation, 3),
            cost_estimate=round(total_energy * self.electricity_rate, 2),
            cop_effective=round(cop, 2)
        )

    def compare(self, report_baseline: EnergyReport,
                report_optimized: EnergyReport) -> dict:
        """
        Compare two controllers and compute improvement metrics.

        Args:
            report_baseline:  EnergyReport from rule-based controller
            report_optimized: EnergyReport from adaptive controller

        Returns:
            Dictionary with comparison metrics and percentage improvements.
        """
        def safe_pct(baseline, optimized):
            if baseline == 0:
                return 0.0
            return round((baseline - optimized) / baseline * 100, 1)

        return {
            "energy_savings_pct": safe_pct(
                report_baseline.total_energy_kwh,
                report_optimized.total_energy_kwh
            ),
            "energy_saved_kwh": round(
                report_baseline.total_energy_kwh - report_optimized.total_energy_kwh, 2
            ),
            "cost_saved": round(
                report_baseline.cost_estimate - report_optimized.cost_estimate, 2
            ),
            "comfort_change_pct": round(
                report_optimized.comfort_score - report_baseline.comfort_score, 1
            ),
            "violation_reduction_pct": safe_pct(
                report_baseline.comfort_violations_minutes,
                report_optimized.comfort_violations_minutes
            ),
            "peak_power_reduction_pct": safe_pct(
                report_baseline.peak_power_w,
                report_optimized.peak_power_w
            ),
            "cop_improvement_pct": round(
                (report_optimized.cop_effective - report_baseline.cop_effective) /
                max(report_baseline.cop_effective, 0.01) * 100, 1
            ),
            "baseline": {
                "daily_kwh": report_baseline.daily_avg_kwh,
                "comfort_score": report_baseline.comfort_score,
                "cost": report_baseline.cost_estimate,
            },
            "optimized": {
                "daily_kwh": report_optimized.daily_avg_kwh,
                "comfort_score": report_optimized.comfort_score,
                "cost": report_optimized.cost_estimate,
            }
        }

    def project_annual_savings(self, report_baseline: EnergyReport,
                                report_optimized: EnergyReport) -> dict:
        """
        Project annual energy and cost savings.

        Assumes the simulation period is representative of the season.
        """
        days = max(report_baseline.period_days, 1)
        scale = 365.0 / days

        baseline_annual = report_baseline.total_energy_kwh * scale
        optimized_annual = report_optimized.total_energy_kwh * scale

        return {
            "baseline_annual_kwh": round(baseline_annual, 0),
            "optimized_annual_kwh": round(optimized_annual, 0),
            "annual_savings_kwh": round(baseline_annual - optimized_annual, 0),
            "annual_cost_savings": round(
                (baseline_annual - optimized_annual) * self.electricity_rate, 2
            ),
            "annual_co2_saved_kg": round(
                (baseline_annual - optimized_annual) * 0.42, 1  # 0.42 kg CO2/kWh average grid
            ),
        }

    @staticmethod
    def compute_pareto_frontier(
        energy_values: List[float],
        comfort_values: List[float]
    ) -> List[Tuple[float, float]]:
        """
        Compute the Pareto frontier for energy vs comfort trade-off.

        Points on the frontier represent optimal trade-offs where
        improving one metric necessarily worsens the other.

        Returns:
            List of (energy, comfort) tuples on the Pareto frontier.
        """
        points = sorted(zip(energy_values, comfort_values), key=lambda x: x[0])
        frontier = []
        max_comfort = -np.inf

        for energy, comfort in points:
            if comfort > max_comfort:
                frontier.append((energy, comfort))
                max_comfort = comfort

        return frontier
