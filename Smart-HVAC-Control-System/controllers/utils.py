"""
Controller Utilities
====================

Shared helper functions for HVAC controllers.
"""

import numpy as np


def discretize_temperature(temp: float, low: float = 10.0, high: float = 40.0,
                           n_bins: int = 20) -> int:
    """
    Discretize a continuous temperature into a bin index.

    Args:
        temp:   Temperature value (°C)
        low:    Lower bound of the range
        high:   Upper bound of the range
        n_bins: Number of discrete bins

    Returns:
        Bin index (0 to n_bins-1)
    """
    clamped = np.clip(temp, low, high)
    bin_idx = int((clamped - low) / (high - low) * (n_bins - 1))
    return min(bin_idx, n_bins - 1)


def discretize_hour(hour: float, n_bins: int = 24) -> int:
    """Discretize hour of day into a bin index."""
    return int(hour) % n_bins


def compute_comfort_score(temp: float, comfort_low: float = 20.0,
                          comfort_high: float = 26.0) -> float:
    """
    Compute a normalized comfort score (0 = uncomfortable, 1 = perfect).

    Uses a trapezoidal function:
    - 1.0 within [comfort_low, comfort_high]
    - Linearly decreasing outside the range
    - 0.0 when more than 5°C outside range
    """
    if comfort_low <= temp <= comfort_high:
        return 1.0

    if temp < comfort_low:
        distance = comfort_low - temp
    else:
        distance = temp - comfort_high

    return max(0.0, 1.0 - distance / 5.0)


def exponential_decay(initial: float, final: float, step: int,
                      total_steps: int) -> float:
    """
    Exponential decay schedule (e.g., for epsilon in ε-greedy).

    Args:
        initial:     Starting value
        final:       Minimum value
        step:        Current step
        total_steps: Total number of steps for decay

    Returns:
        Decayed value
    """
    if step >= total_steps:
        return final
    decay_rate = -np.log(final / initial) / total_steps
    return max(final, initial * np.exp(-decay_rate * step))
