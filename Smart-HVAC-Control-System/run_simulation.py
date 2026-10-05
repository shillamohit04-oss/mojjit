"""
run_simulation.py — Main Simulation Entry Point
================================================

Runs a 7-day HVAC simulation with a selectable controller
and generates output data for analysis and dashboard visualization.

Usage:
    python run_simulation.py                      # Run with default (rule-based)
    python run_simulation.py --controller adaptive # Run with Q-learning
    python run_simulation.py --season winter       # Run winter scenario
    python run_simulation.py --days 14             # Run for 14 days
"""

import sys
import os
import argparse
import time
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation.environment import HVACEnvironment, ComfortBand
from simulation.weather import Season
from simulation.hvac_plant import HVACAction
from controllers.rule_based import RuleBasedController
from controllers.adaptive_qlearning import AdaptiveQLearningController
from ai.pattern_learner import PatternLearner
from ai.predictor import TemperaturePredictor


def run_simulation(
    controller_type: str = "rule_based",
    season: str = "summer",
    days: int = 7,
    seed: int = 42,
    verbose: bool = True
) -> dict:
    """
    Run a complete HVAC simulation.

    Args:
        controller_type: "rule_based" or "adaptive"
        season:         "summer", "winter", "spring", "fall"
        days:           Simulation duration in days
        seed:           Random seed for reproducibility
        verbose:        Print progress updates

    Returns:
        Summary statistics dictionary
    """
    # Map season string to enum
    season_map = {
        "summer": Season.SUMMER,
        "winter": Season.WINTER,
        "spring": Season.SPRING,
        "fall": Season.FALL,
    }
    season_enum = season_map.get(season, Season.SUMMER)

    # Set initial temperature based on season
    initial_temps = {
        Season.SUMMER: 28.0,   # Room starts warm
        Season.WINTER: 18.0,   # Room starts cold
        Season.SPRING: 22.0,
        Season.FALL: 22.0,
    }
    initial_temp = initial_temps[season_enum]

    # Database path per controller
    db_path = f"data/sim_{controller_type}_{season}.db"

    if verbose:
        print(f"{'='*60}")
        print(f"  Smart HVAC Control System — Simulation")
        print(f"{'='*60}")
        print(f"  Controller:  {controller_type}")
        print(f"  Season:      {season}")
        print(f"  Duration:    {days} days ({days * 24} hours)")
        print(f"  Initial T:   {initial_temp}°C")
        print(f"  Database:    {db_path}")
        print(f"{'='*60}")
        print()

    # Create environment
    env = HVACEnvironment(
        season=season_enum,
        db_path=db_path,
        controller_name=controller_type,
        seed=seed
    )

    # Create controller
    if controller_type == "adaptive":
        controller = AdaptiveQLearningController(seed=seed)
        # Warm-start: train on rule-based policy for 3 days with HIGH exploration
        if verbose:
            print("[*] Warm-starting Q-learning from rule-based policy (3 days)...")
        # Temporarily set high exploration for warm-start learning
        old_epsilon = controller.epsilon_start
        controller.epsilon_start = 0.5  # Explore more during warm-start
        controller.epsilon_decay_steps = 4320  # 3 days decay
        rule_ctrl = RuleBasedController()
        warm_env = HVACEnvironment(
            season=season_enum,
            db_path="data/warmstart_temp.db",
            controller_name="warmstart",
            seed=seed + 100
        )
        warm_env.reset(initial_temp=initial_temp, max_days=3)
        controller.warm_start_from_rule_based(warm_env, rule_ctrl, n_steps=4320)
        warm_env.close()
        # Clean up temp database
        try:
            os.remove("data/warmstart_temp.db")
        except OSError:
            pass
        # Reset step count and set low epsilon for deployment
        controller.step_count = 0
        controller.epsilon_start = 0.15
        controller.epsilon_decay_steps = 1440
    else:
        controller = RuleBasedController()

    # Create AI helpers
    pattern_learner = PatternLearner()
    predictor = TemperaturePredictor()

    # Reset environment
    state = env.reset(initial_temp=initial_temp, max_days=days)

    # Simulation loop
    total_steps = days * 24 * 60
    start_time = time.time()
    reward_sum = 0.0
    step_count = 0

    if verbose:
        print(f"[*] Starting simulation ({total_steps:,} timesteps)...\n")

    while not env.done:
        # Controller decision
        action = controller.compute_action(state)

        # Step environment
        next_state, reward, done, info = env.step(action)

        # Update learning controller
        controller.update(state, action, reward, next_state, done)

        # Update AI helpers
        pattern_learner.update({
            "hour": state["hour"],
            "temp_indoor": state["temp_indoor"],
            "temp_outdoor": state["temp_outdoor"],
            "occupied": state["occupied"],
            "hvac_mode": state["hvac_mode"],
            "hvac_power_w": info.get("power_kw", 0) * 1000,
        })
        predictor.update(state)

        reward_sum += reward
        step_count += 1
        state = next_state

        # Progress update every simulated day
        if verbose and step_count % 1440 == 0:
            day_num = step_count // 1440
            elapsed = time.time() - start_time
            avg_reward = reward_sum / step_count

            print(f"  Day {day_num}/{days}  |  "
                  f"T_in={state['temp_indoor']:.1f}°C  |  "
                  f"T_out={state['temp_outdoor']:.1f}°C  |  "
                  f"HVAC={state['hvac_action']:10s}  |  "
                  f"Avg Reward={avg_reward:.3f}  |  "
                  f"Elapsed={elapsed:.1f}s")

    # Finalize
    summary = env.finalize()
    elapsed_total = time.time() - start_time

    # Add AI analysis
    pattern_analysis = pattern_learner.analyze()

    if verbose:
        print(f"\n{'='*60}")
        print(f"  SIMULATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Wall-clock time:        {elapsed_total:.1f}s")
        print(f"  Total energy consumed:  {summary.get('total_energy_kwh', 0):.2f} kWh")
        print(f"  Daily average:          {summary.get('daily_avg_kwh', 0):.2f} kWh/day")
        print(f"  Comfort violations:     {summary.get('comfort_violation_pct', 0):.1f}%")
        print(f"  Avg power:              {summary.get('avg_power_w', 0):.0f} W")

        if controller_type == "adaptive":
            q_stats = controller.get_stats()
            print(f"\n  [Q-Learning Stats]")
            print(f"  Final epsilon:          {q_stats['epsilon']}")
            print(f"  Q-table coverage:       {q_stats['q_table_nonzero_pct']:.1f}%")
            controller.save_q_table(f"data/q_table_{season}.npy")

        if pattern_analysis.get("status") == "trained":
            print(f"\n  [Pattern Analysis]")
            print(f"  Heating rate:           {pattern_analysis['heating_rate_per_min']:.4f} °C/min")
            print(f"  Cooling rate:           {pattern_analysis['cooling_rate_per_min']:.4f} °C/min")
            print(f"  Peak cooling hours:     {pattern_analysis['peak_cooling_hours']}")

        print(f"{'='*60}")

    # Save summary
    summary["elapsed_seconds"] = elapsed_total
    summary["pattern_analysis"] = pattern_analysis

    env.close()
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Smart HVAC Control System — Simulation Runner"
    )
    parser.add_argument(
        "--controller", "-c",
        choices=["rule_based", "adaptive"],
        default="rule_based",
        help="Controller type (default: rule_based)"
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
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    summary = run_simulation(
        controller_type=args.controller,
        season=args.season,
        days=args.days,
        seed=args.seed,
        verbose=not args.quiet
    )


if __name__ == "__main__":
    main()
