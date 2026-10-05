"""
Weather Generator
=================

Generates realistic outdoor temperature and humidity profiles
with both seasonal and diurnal variations.

Supports:
- Summer profile (cooling-dominant scenario)
- Winter profile (heating-dominant scenario)
- Transitional season (spring/fall — exercises both modes)
- Day-to-day random variation for realism
"""

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Season(Enum):
    """Seasonal profiles for outdoor weather."""
    SUMMER = "summer"
    WINTER = "winter"
    SPRING = "spring"      # Transitional — exercises both heating and cooling
    FALL = "fall"


@dataclass
class WeatherProfile:
    """Defines the temperature and humidity characteristics of a season."""
    temp_mean: float        # Mean daily temperature (°C)
    temp_amplitude: float   # Daily temperature swing (°C) — half-range
    temp_min_hour: float    # Hour of daily minimum temperature (typically ~5am)
    humidity_mean: float    # Mean relative humidity (%)
    humidity_amplitude: float  # Daily humidity swing (%)

    @classmethod
    def from_season(cls, season: Season) -> "WeatherProfile":
        """Create a profile from a season enum."""
        profiles = {
            Season.SUMMER: cls(
                temp_mean=30.0, temp_amplitude=9.0,
                temp_min_hour=5.0, humidity_mean=55.0, humidity_amplitude=15.0
            ),
            Season.WINTER: cls(
                temp_mean=8.0, temp_amplitude=6.0,
                temp_min_hour=6.0, humidity_mean=65.0, humidity_amplitude=10.0
            ),
            Season.SPRING: cls(
                temp_mean=20.0, temp_amplitude=8.0,
                temp_min_hour=5.5, humidity_mean=55.0, humidity_amplitude=12.0
            ),
            Season.FALL: cls(
                temp_mean=18.0, temp_amplitude=7.0,
                temp_min_hour=6.0, humidity_mean=60.0, humidity_amplitude=12.0
            ),
        }
        return profiles[season]


class WeatherGenerator:
    """
    Generates outdoor temperature and humidity time series.

    Uses a sinusoidal diurnal pattern with random day-to-day variation
    and optional multi-day weather events (cold fronts, heat waves).
    """

    def __init__(
        self,
        profile: Optional[WeatherProfile] = None,
        season: Season = Season.SUMMER,
        seed: Optional[int] = None
    ):
        """
        Args:
            profile: Custom weather profile. If None, derived from season.
            season:  Season enum (used when profile is None).
            seed:    Random seed for reproducibility.
        """
        self.profile = profile or WeatherProfile.from_season(season)
        self.rng = np.random.default_rng(seed)

        # Day-to-day variation state
        self._daily_offset = 0.0
        self._daily_offset_target = 0.0
        self._current_day = -1

    def get_weather(self, minute: int) -> tuple[float, float]:
        """
        Get outdoor temperature and humidity at a given simulation minute.

        Args:
            minute: Minutes since simulation start.

        Returns:
            Tuple of (temperature_celsius, humidity_percent)
        """
        hour = (minute / 60.0) % 24.0
        day = minute // 1440  # 1440 minutes per day

        # Update daily variation if new day
        if day != self._current_day:
            self._current_day = day
            self._daily_offset_target = self.rng.normal(0, 3.0)  # ±3°C day-to-day
            # Smooth transition
            self._daily_offset = (
                0.7 * self._daily_offset + 0.3 * self._daily_offset_target
            )

        # Diurnal temperature pattern
        # Minimum at temp_min_hour, maximum at temp_min_hour + 12
        phase = 2 * np.pi * (hour - self.profile.temp_min_hour) / 24.0
        temp = (
            self.profile.temp_mean +
            self._daily_offset -
            self.profile.temp_amplitude * np.cos(phase)
        )

        # Add realistic short-term noise (±0.5°C)
        temp += self.rng.normal(0, 0.3)

        # Humidity — anti-correlated with temperature (higher at night)
        humidity_phase = 2 * np.pi * (hour - self.profile.temp_min_hour) / 24.0
        humidity = (
            self.profile.humidity_mean +
            self.profile.humidity_amplitude * np.cos(humidity_phase)  # Peaks when temp is lowest
        )
        humidity += self.rng.normal(0, 2.0)
        humidity = float(np.clip(humidity, 20.0, 95.0))

        return float(temp), humidity

    def generate_series(self, duration_minutes: int, dt_minutes: int = 1) -> dict:
        """
        Generate a complete weather time series.

        Args:
            duration_minutes: Total duration in minutes.
            dt_minutes:       Timestep in minutes.

        Returns:
            Dictionary with 'minutes', 'temperature', 'humidity' arrays.
        """
        minutes = np.arange(0, duration_minutes, dt_minutes)
        temps = np.zeros(len(minutes))
        humids = np.zeros(len(minutes))

        for i, m in enumerate(minutes):
            temps[i], humids[i] = self.get_weather(int(m))

        return {
            "minutes": minutes,
            "temperature": temps,
            "humidity": humids
        }
