"""
Occupancy Pattern Generator
============================

Simulates realistic human occupancy patterns for a residential room.

Features:
- Weekday/weekend schedules with different patterns
- Stochastic arrival/departure with configurable variance
- Multiple occupants support
- PIR motion event generation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OccupancySchedule:
    """Defines a daily occupancy pattern."""

    # List of (start_hour, end_hour, probability) tuples
    # probability = chance of being occupied during that window
    occupied_windows: list = field(default_factory=list)

    # Stochastic variation in arrival/departure (minutes)
    arrival_variance: float = 15.0   # minutes standard deviation
    departure_variance: float = 20.0

    @classmethod
    def weekday(cls) -> "OccupancySchedule":
        """Typical weekday schedule for a working adult."""
        return cls(
            occupied_windows=[
                (0.0, 7.0, 0.95),     # Sleeping — occupied
                (7.0, 8.0, 0.70),     # Getting ready — usually occupied
                (8.0, 17.5, 0.05),    # At work — rarely home
                (17.5, 19.0, 0.60),   # Coming home — transitional
                (19.0, 23.0, 0.90),   # Evening — occupied
                (23.0, 24.0, 0.95),   # Going to bed — occupied
            ]
        )

    @classmethod
    def weekend(cls) -> "OccupancySchedule":
        """Typical weekend schedule."""
        return cls(
            occupied_windows=[
                (0.0, 9.0, 0.95),     # Sleeping in
                (9.0, 11.0, 0.75),    # Morning
                (11.0, 15.0, 0.40),   # Might go out
                (15.0, 18.0, 0.60),   # Afternoon
                (18.0, 24.0, 0.85),   # Evening — mostly home
            ]
        )


class OccupancyGenerator:
    """
    Generates occupancy data for simulation.

    Produces:
    - Binary occupancy state (occupied / unoccupied)
    - Number of occupants (1-3 when occupied)
    - PIR motion events with realistic detection patterns
    """

    def __init__(
        self,
        max_occupants: int = 2,
        seed: Optional[int] = None
    ):
        """
        Args:
            max_occupants: Maximum number of occupants in the room.
            seed:          Random seed for reproducibility.
        """
        self.max_occupants = max_occupants
        self.rng = np.random.default_rng(seed)

        self._weekday_schedule = OccupancySchedule.weekday()
        self._weekend_schedule = OccupancySchedule.weekend()

        # State tracking
        self._last_motion_minute = -999
        self._occupancy_state = False
        self._transition_cooldown = 0

    def get_occupancy(self, minute: int) -> dict:
        """
        Get occupancy state at a given simulation minute.

        Args:
            minute: Minutes since simulation start.

        Returns:
            Dictionary with:
                - 'occupied': bool
                - 'n_occupants': int (0 if unoccupied)
                - 'motion_detected': bool (PIR sensor event)
        """
        hour = (minute / 60.0) % 24.0
        day = (minute // 1440) % 7  # 0=Monday, 6=Sunday

        # Select schedule
        is_weekend = day >= 5
        schedule = self._weekend_schedule if is_weekend else self._weekday_schedule

        # Determine base occupancy probability for this hour
        base_prob = 0.0
        for start_h, end_h, prob in schedule.occupied_windows:
            if start_h <= hour < end_h:
                base_prob = prob
                break

        # Add stochastic variation using schedule variance
        arrival_noise = self.rng.normal(0, schedule.arrival_variance / 60.0)  # Convert to hours
        adjusted_prob = np.clip(base_prob + arrival_noise * 0.05, 0.0, 1.0)

        # Determine occupancy with hysteresis (prevent rapid switching)
        if self._transition_cooldown > 0:
            self._transition_cooldown -= 1
        else:
            new_state = self.rng.random() < adjusted_prob
            if new_state != self._occupancy_state:
                self._occupancy_state = new_state
                self._transition_cooldown = 10  # 10-minute cooldown after transition

        # Number of occupants
        if self._occupancy_state:
            # More occupants in evening hours
            if 18.0 <= hour <= 22.0 and not is_weekend:
                n_occupants = min(self.max_occupants, max(1, int(self.rng.poisson(1.5))))
            else:
                n_occupants = max(1, int(self.rng.poisson(0.8)))
            n_occupants = min(n_occupants, self.max_occupants)
        else:
            n_occupants = 0

        # PIR motion detection
        motion = False
        if self._occupancy_state and n_occupants > 0:
            # Motion detected periodically when occupied (people move around)
            # Higher probability during active hours, lower during sleep
            if 0.0 <= hour < 6.0:
                motion_prob = 0.02  # Sleeping — rare motion
            elif 6.0 <= hour < 8.0:
                motion_prob = 0.30  # Getting ready — frequent motion
            else:
                motion_prob = 0.15  # Normal activity

            motion = self.rng.random() < motion_prob

        return {
            "occupied": self._occupancy_state,
            "n_occupants": n_occupants,
            "motion_detected": motion
        }

    def generate_series(self, duration_minutes: int, dt_minutes: int = 1) -> dict:
        """
        Generate a complete occupancy time series.

        Args:
            duration_minutes: Total duration in minutes.
            dt_minutes:       Timestep in minutes.

        Returns:
            Dictionary with arrays: 'minutes', 'occupied', 'n_occupants', 'motion'
        """
        minutes = np.arange(0, duration_minutes, dt_minutes)
        occupied = np.zeros(len(minutes), dtype=bool)
        n_occupants = np.zeros(len(minutes), dtype=int)
        motion = np.zeros(len(minutes), dtype=bool)

        for i, m in enumerate(minutes):
            state = self.get_occupancy(int(m))
            occupied[i] = state["occupied"]
            n_occupants[i] = state["n_occupants"]
            motion[i] = state["motion_detected"]

        return {
            "minutes": minutes,
            "occupied": occupied,
            "n_occupants": n_occupants,
            "motion": motion
        }
