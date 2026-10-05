"""
Adaptive Q-Learning Controller
===============================

Reinforcement Learning controller that learns optimal HVAC control
through interaction with the environment.

State Space (discretized):
    - Temperature: 20 bins (10°C to 40°C)
    - Hour of day: 24 bins
    - Occupancy: 2 bins (occupied / unoccupied)
    - Outdoor temperature: 10 bins (0°C to 45°C)
    Total: 20 × 24 × 2 × 10 = 9,600 states

Action Space:
    HEAT_HIGH (0), HEAT_LOW (1), OFF (2), COOL_LOW (3), COOL_HIGH (4)
    Total: 5 actions

Reward Function:
    r = -w_e × power_kW - w_c × max(0, |T - T_opt| - deadband)²

Learning Parameters:
    - α (learning rate): 0.1
    - γ (discount factor): 0.95
    - ε (exploration): 1.0 → 0.05 over 3 days (4,320 steps)
"""

import numpy as np
import json
import os
from typing import Optional

from controllers.base_controller import BaseController
from controllers.utils import (
    discretize_temperature, discretize_hour, exponential_decay
)
from simulation.hvac_plant import HVACAction


class AdaptiveQLearningController(BaseController):
    """
    Q-Learning HVAC controller with adaptive exploration.

    Features:
    - Tabular Q-learning with discretized state space
    - ε-greedy exploration with exponential decay
    - Warm-start from rule-based controller data
    - Online adaptation during deployment
    - Q-table persistence (save/load)
    """

    # State discretization parameters
    TEMP_BINS = 20
    TEMP_LOW = 10.0
    TEMP_HIGH = 40.0
    HOUR_BINS = 24
    OCC_BINS = 2
    OUTDOOR_BINS = 10
    OUTDOOR_LOW = 0.0
    OUTDOOR_HIGH = 45.0
    N_ACTIONS = 5

    def __init__(
        self,
        alpha: float = 0.15,      # Learning rate
        gamma: float = 0.95,      # Discount factor
        epsilon_start: float = 0.15, # Very low — warm-start provides good initial policy
        epsilon_end: float = 0.03,
        epsilon_decay_steps: int = 1440,  # 1 day decay (warm-start covers exploration)
        comfort_weight: float = 10.0,
        energy_weight: float = 1.0,
        seed: Optional[int] = None
    ):
        super().__init__(name="adaptive_qlearning")

        self.alpha = alpha
        self.gamma = gamma
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay_steps = epsilon_decay_steps
        self.comfort_weight = comfort_weight
        self.energy_weight = energy_weight
        self.rng = np.random.default_rng(seed)

        # Q-table: state → action values
        n_states = self.TEMP_BINS * self.HOUR_BINS * self.OCC_BINS * self.OUTDOOR_BINS
        self.q_table = np.zeros((n_states, self.N_ACTIONS))

        # Initialize with slight preference for OFF action (energy saving prior)
        self.q_table[:, HVACAction.OFF.value] = 0.1

        # Training state
        self.step_count = 0
        self.episode_rewards = []
        self._current_episode_reward = 0.0
        self._training_mode = True

    def _state_to_index(self, state: dict) -> int:
        """Convert continuous state to discrete Q-table index."""
        temp_bin = discretize_temperature(
            state["temp_indoor"], self.TEMP_LOW, self.TEMP_HIGH, self.TEMP_BINS
        )
        hour_bin = discretize_hour(state.get("hour", 12.0), self.HOUR_BINS)
        occ_bin = 1 if state.get("occupied", True) else 0
        outdoor_bin = discretize_temperature(
            state.get("temp_outdoor", 25.0),
            self.OUTDOOR_LOW, self.OUTDOOR_HIGH, self.OUTDOOR_BINS
        )

        # Flatten multi-dimensional index to 1D
        index = (
            temp_bin * (self.HOUR_BINS * self.OCC_BINS * self.OUTDOOR_BINS) +
            hour_bin * (self.OCC_BINS * self.OUTDOOR_BINS) +
            occ_bin * self.OUTDOOR_BINS +
            outdoor_bin
        )
        return min(index, len(self.q_table) - 1)

    @property
    def epsilon(self) -> float:
        """Current exploration rate."""
        return exponential_decay(
            self.epsilon_start, self.epsilon_end,
            self.step_count, self.epsilon_decay_steps
        )

    def compute_action(self, state: dict) -> HVACAction:
        """
        Select action using ε-greedy policy with physical safety filter.

        The safety filter prevents physically nonsensical actions
        (e.g., heating when T > 26°C) regardless of Q-table values.
        """
        state_idx = self._state_to_index(state)

        if self._training_mode and self.rng.random() < self.epsilon:
            # Exploration — random action, but weighted toward reasonable choices
            action_idx = self._smart_explore(state)
        else:
            # Exploitation — choose best Q-value from ALLOWED actions
            allowed = self._get_allowed_actions(state)
            q_values = self.q_table[state_idx].copy()
            # Mask out disallowed actions
            for i in range(self.N_ACTIONS):
                if i not in allowed:
                    q_values[i] = -np.inf
            action_idx = int(np.argmax(q_values))

        action = HVACAction(action_idx)
        self._record_action(action)
        self.step_count += 1

        return action

    def _get_allowed_actions(self, state: dict) -> list:
        """
        Get physically allowed actions based on current temperature.

        Prevents heating when hot and cooling when cold — basic
        thermodynamic sanity that no Q-value should override.
        """
        temp = state["temp_indoor"]
        allowed = [HVACAction.OFF.value]  # OFF is always allowed

        if temp > 24.0:
            # Warm or hot — allow cooling, block heating
            allowed.extend([HVACAction.COOL_LOW.value, HVACAction.COOL_HIGH.value])
        elif temp < 22.0:
            # Cool or cold — allow heating, block cooling
            allowed.extend([HVACAction.HEAT_LOW.value, HVACAction.HEAT_HIGH.value])
        else:
            # In comfortable range — allow everything (agent can optimize)
            allowed = list(range(self.N_ACTIONS))

        return allowed

    def _smart_explore(self, state: dict) -> int:
        """
        Intelligent exploration — bias random actions toward reasonable choices.

        For example: don't heat when it's 35°C, don't cool when it's 5°C.
        This dramatically speeds up learning.
        """
        temp = state["temp_indoor"]
        weights = np.ones(self.N_ACTIONS)

        if temp > 26.0:
            # Hot — only allow cooling or OFF (NEVER heat when hot)
            weights[HVACAction.COOL_HIGH.value] = 5.0
            weights[HVACAction.COOL_LOW.value] = 3.0
            weights[HVACAction.OFF.value] = 1.0
            weights[HVACAction.HEAT_HIGH.value] = 0.0  # Physically nonsensical
            weights[HVACAction.HEAT_LOW.value] = 0.0
        elif temp < 20.0:
            # Cold — only allow heating or OFF (NEVER cool when cold)
            weights[HVACAction.HEAT_HIGH.value] = 5.0
            weights[HVACAction.HEAT_LOW.value] = 3.0
            weights[HVACAction.OFF.value] = 1.0
            weights[HVACAction.COOL_HIGH.value] = 0.0  # Physically nonsensical
            weights[HVACAction.COOL_LOW.value] = 0.0
        else:
            # Comfortable — strongly prefer OFF, allow mild adjustments
            weights[HVACAction.OFF.value] = 6.0
            weights[HVACAction.COOL_LOW.value] = 1.0
            weights[HVACAction.HEAT_LOW.value] = 1.0
            weights[HVACAction.COOL_HIGH.value] = 0.5
            weights[HVACAction.HEAT_HIGH.value] = 0.5

        # Normalize to probabilities (handle zero-sum edge case)
        total = weights.sum()
        if total == 0:
            weights = np.ones(self.N_ACTIONS)
            total = weights.sum()
        probs = weights / total
        return int(self.rng.choice(self.N_ACTIONS, p=probs))

    def update(self, state: dict, action: HVACAction, reward: float,
               next_state: dict, done: bool) -> None:
        """
        Q-learning update rule:
            Q(s,a) ← Q(s,a) + α × [r + γ × max Q(s',a') - Q(s,a)]
        """
        if not self._training_mode:
            return

        s = self._state_to_index(state)
        a = action.value
        s_next = self._state_to_index(next_state)

        # Q-learning update
        current_q = self.q_table[s, a]
        if done:
            target = reward
        else:
            target = reward + self.gamma * np.max(self.q_table[s_next])

        self.q_table[s, a] += self.alpha * (target - current_q)

        # Track episode reward
        self._current_episode_reward += reward

    def warm_start_from_rule_based(self, env, rule_controller, n_steps: int = 1440) -> None:
        """
        Pre-train the Q-table by observing the rule-based controller.

        Runs the rule-based controller for n_steps and uses its
        state-action-reward transitions to initialize Q-values.

        Args:
            env:             HVACEnvironment instance
            rule_controller: RuleBasedController instance
            n_steps:         Number of steps to observe
        """
        state = env.reset()
        for _ in range(n_steps):
            action = rule_controller.compute_action(state)
            next_state, reward, done, _ = env.step(action)
            self.update(state, action, reward, next_state, done)
            state = next_state
            if done:
                break

        # Reset environment after warm-start
        env.reset()
        print(f"[Q-Learning] Warm-start complete: {n_steps} transitions observed.")

    def set_training_mode(self, training: bool) -> None:
        """Enable or disable training (exploration + Q-table updates)."""
        self._training_mode = training

    def save_q_table(self, path: str = "data/q_table.npy") -> None:
        """Save Q-table to disk."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        np.save(path, self.q_table)
        # Save metadata
        meta = {
            "step_count": self.step_count,
            "epsilon": self.epsilon,
            "alpha": self.alpha,
            "gamma": self.gamma,
            "state_shape": list(self.q_table.shape),
        }
        meta_path = path.replace(".npy", "_meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"[Q-Learning] Q-table saved to {path} ({self.step_count} steps)")

    def load_q_table(self, path: str = "data/q_table.npy") -> bool:
        """Load Q-table from disk. Returns True if successful."""
        if os.path.exists(path):
            self.q_table = np.load(path)
            meta_path = path.replace(".npy", "_meta.json")
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                self.step_count = meta.get("step_count", 0)
            print(f"[Q-Learning] Q-table loaded from {path}")
            return True
        return False

    def reset(self) -> None:
        """Reset controller state (preserves Q-table)."""
        super().reset()
        self._current_episode_reward = 0.0

    def get_stats(self) -> dict:
        """Get training and performance statistics."""
        stats = super().get_stats()
        stats.update({
            "step_count": self.step_count,
            "epsilon": round(self.epsilon, 4),
            "q_table_mean": float(np.mean(self.q_table)),
            "q_table_max": float(np.max(self.q_table)),
            "q_table_nonzero_pct": float(
                np.count_nonzero(self.q_table) / self.q_table.size * 100
            ),
            "training_mode": self._training_mode,
        })
        return stats
