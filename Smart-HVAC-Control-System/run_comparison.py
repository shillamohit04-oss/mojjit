"""
run_comparison.py — Controller Comparison
==========================================

Runs both rule-based and adaptive controllers on identical conditions
and generates a comparison report with energy efficiency analysis.

Usage:
    python run_comparison.py                    # Compare in summer
    python run_comparison.py --season winter    # Compare in winter
    python run_comparison.py --days 14          # 14-day comparison
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_simulation import run_simulation
from simulation.data_logger import DataLogger
from ai.energy_optimizer import EnergyOptimizer


def run_comparison(season: str = "summer", days: int = 7, seed: int = 42):
    """
    Run both controllers and compare results.

    Args:
        season: Season profile
        days:   Simulation duration
        seed:   Random seed (same for both runs)
    """
    print("╔" + "═"*58 + "╗")
    print("║" + "  SMART HVAC CONTROL SYSTEM — CONTROLLER COMPARISON".center(58) + "║")
    print("╚" + "═"*58 + "╝")
    print()

    # Run rule-based controller
    print("▶ Running Rule-Based Controller...")
    print("─" * 60)
    summary_rule = run_simulation(
        controller_type="rule_based",
        season=season,
        days=days,
        seed=seed,
        verbose=True
    )
    print()

    # Run adaptive controller (same conditions)
    print("▶ Running Adaptive Q-Learning Controller...")
    print("─" * 60)
    summary_adaptive = run_simulation(
        controller_type="adaptive",
        season=season,
        days=days,
        seed=seed,
        verbose=True
    )
    print()

    # Load data for detailed analysis
    optimizer = EnergyOptimizer(electricity_rate=0.12)

    db_rule = DataLogger(db_path=f"data/sim_rule_based_{season}.db")
    db_adaptive = DataLogger(db_path=f"data/sim_adaptive_{season}.db")

    df_rule = db_rule.get_dataframe("rule_based")
    df_adaptive = db_adaptive.get_dataframe("adaptive")

    report_rule = optimizer.analyze(df_rule, "Rule-Based")
    report_adaptive = optimizer.analyze(df_adaptive, "Adaptive Q-Learning")

    comparison = optimizer.compare(report_rule, report_adaptive)
    annual = optimizer.project_annual_savings(report_rule, report_adaptive)

    # Print comparison report
    print("╔" + "═"*58 + "╗")
    print("║" + "  COMPARISON RESULTS".center(58) + "║")
    print("╚" + "═"*58 + "╝")
    print()

    print(f"  {'Metric':<35} {'Rule-Based':>10} {'Adaptive':>10}")
    print(f"  {'─'*35} {'─'*10} {'─'*10}")
    print(f"  {'Total Energy (kWh)':<35} {report_rule.total_energy_kwh:>10.2f} {report_adaptive.total_energy_kwh:>10.2f}")
    print(f"  {'Daily Average (kWh/day)':<35} {report_rule.daily_avg_kwh:>10.2f} {report_adaptive.daily_avg_kwh:>10.2f}")
    print(f"  {'Peak Power (W)':<35} {report_rule.peak_power_w:>10.0f} {report_adaptive.peak_power_w:>10.0f}")
    print(f"  {'Avg Power (W)':<35} {report_rule.avg_power_w:>10.0f} {report_adaptive.avg_power_w:>10.0f}")
    print(f"  {'Cooling Energy (kWh)':<35} {report_rule.cooling_energy_kwh:>10.2f} {report_adaptive.cooling_energy_kwh:>10.2f}")
    print(f"  {'Heating Energy (kWh)':<35} {report_rule.heating_energy_kwh:>10.2f} {report_adaptive.heating_energy_kwh:>10.2f}")
    print(f"  {'Comfort Score (%)':<35} {report_rule.comfort_score:>10.1f} {report_adaptive.comfort_score:>10.1f}")
    print(f"  {'Violations (minutes)':<35} {report_rule.comfort_violations_minutes:>10d} {report_adaptive.comfort_violations_minutes:>10d}")
    print(f"  {'Effective COP':<35} {report_rule.cop_effective:>10.2f} {report_adaptive.cop_effective:>10.2f}")
    print(f"  {'Cost Estimate ($)':<35} {report_rule.cost_estimate:>10.2f} {report_adaptive.cost_estimate:>10.2f}")
    print()

    print(f"  ┌──────────────────────────────────────────────┐")
    print(f"  │  IMPROVEMENT SUMMARY                         │")
    print(f"  ├──────────────────────────────────────────────┤")
    print(f"  │  Energy savings:     {comparison['energy_savings_pct']:>6.1f}%  ({comparison['energy_saved_kwh']:.2f} kWh)    │")
    print(f"  │  Cost savings:       ${comparison['cost_saved']:>6.2f}                    │")
    print(f"  │  Comfort change:     {comparison['comfort_change_pct']:>+6.1f}%                    │")
    print(f"  │  Violation reduction: {comparison['violation_reduction_pct']:>5.1f}%                    │")
    print(f"  └──────────────────────────────────────────────┘")
    print()

    print(f"  ┌──────────────────────────────────────────────┐")
    print(f"  │  ANNUAL PROJECTIONS                          │")
    print(f"  ├──────────────────────────────────────────────┤")
    print(f"  │  Baseline annual:    {annual['baseline_annual_kwh']:>8.0f} kWh              │")
    print(f"  │  Optimized annual:   {annual['optimized_annual_kwh']:>8.0f} kWh              │")
    print(f"  │  Annual savings:     {annual['annual_savings_kwh']:>8.0f} kWh              │")
    print(f"  │  Annual cost saved:  ${annual['annual_cost_savings']:>7.2f}                  │")
    print(f"  │  CO₂ reduction:      {annual['annual_co2_saved_kg']:>8.1f} kg               │")
    print(f"  └──────────────────────────────────────────────┘")
    print()

    # Export comparison to CSV
    import pandas as pd
    comparison_df = pd.DataFrame({
        "Metric": [
            "Total Energy (kWh)", "Daily Avg (kWh)", "Peak Power (W)",
            "Avg Power (W)", "Comfort Score (%)", "Violations (min)",
            "Cost ($)", "Effective COP"
        ],
        "Rule-Based": [
            report_rule.total_energy_kwh, report_rule.daily_avg_kwh,
            report_rule.peak_power_w, report_rule.avg_power_w,
            report_rule.comfort_score, report_rule.comfort_violations_minutes,
            report_rule.cost_estimate, report_rule.cop_effective
        ],
        "Adaptive": [
            report_adaptive.total_energy_kwh, report_adaptive.daily_avg_kwh,
            report_adaptive.peak_power_w, report_adaptive.avg_power_w,
            report_adaptive.comfort_score, report_adaptive.comfort_violations_minutes,
            report_adaptive.cost_estimate, report_adaptive.cop_effective
        ]
    })
    comparison_df.to_csv("data/comparison_results.csv", index=False)
    print(f"  Results saved to data/comparison_results.csv")

    db_rule.close()
    db_adaptive.close()

    return comparison


def main():
    parser = argparse.ArgumentParser(
        description="Smart HVAC — Controller Comparison"
    )
    parser.add_argument(
        "--season", "-s",
        choices=["summer", "winter", "spring", "fall"],
        default="summer",
        help="Season profile (default: summer)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int, default=7,
        help="Simulation duration in days (default: 7)"
    )
    parser.add_argument(
        "--seed",
        type=int, default=42,
        help="Random seed (default: 42)"
    )

    args = parser.parse_args()
    os.makedirs("data", exist_ok=True)

    run_comparison(season=args.season, days=args.days, seed=args.seed)


if __name__ == "__main__":
    main()
