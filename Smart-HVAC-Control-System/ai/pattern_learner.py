"""
Pattern Learner — Temperature and Occupancy Pattern Recognition
================================================================

Analyzes historical sensor data to identify:
- Daily temperature patterns (peak hours, rate of change)
- Occupancy patterns (regular schedules, anomalies)
- Thermal response characteristics (how fast room heats/cools)

Used by the predictor and energy optimizer for informed decisions.
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Tuple
from collections import defaultdict


class PatternLearner:
    """
    Learns recurring patterns from historical HVAC data.

    Uses sliding-window analysis and simple statistics to identify:
    1. Daily temperature profiles (average hourly temperature)
    2. Occupancy schedules (probability of occupancy per hour)
    3. Thermal response rates (°C/min for heating and cooling)
    4. Peak demand hours
    """

    def __init__(self, window_hours: int = 24):
        """
        Args:
            window_hours: Analysis window size in hours.
        """
        self.window_hours = window_hours

        # Learned patterns
        self.hourly_temp_profile = np.full(24, np.nan)     # Mean temp per hour
        self.hourly_temp_std = np.full(24, np.nan)          # Std dev per hour
        self.hourly_occupancy_prob = np.full(24, 0.5)       # P(occupied) per hour
        self.heating_rate = 0.0     # °C per minute when heating
        self.cooling_rate = 0.0     # °C per minute when cooling
        self.passive_heating_rate = 0.0  # °C per minute (solar + internal gains)
        self.passive_cooling_rate = 0.0  # °C per minute (night cooling)

        # Peak analysis
        self.peak_cooling_hours: List[int] = []
        self.peak_heating_hours: List[int] = []

        # Data buffer
        self._data_buffer: list = []
        self._is_trained = False

    def update(self, data_point: dict) -> None:
        """
        Add a new data point for pattern analysis.

        Args:
            data_point: Dictionary with keys: hour, temp_indoor, temp_outdoor,
                       occupied, hvac_mode, hvac_power_w
        """
        self._data_buffer.append(data_point)

        # Re-analyze every 1440 points (24 hours)
        if len(self._data_buffer) % 1440 == 0:
            self.analyze()

    def analyze(self, df: Optional[pd.DataFrame] = None) -> dict:
        """
        Analyze collected data to extract patterns.

        Args:
            df: Optional DataFrame. If None, uses internal buffer.

        Returns:
            Dictionary with pattern analysis results.
        """
        if df is None:
            if not self._data_buffer:
                return {"status": "no_data"}
            df = pd.DataFrame(self._data_buffer)

        if len(df) < 60:  # Need at least 1 hour of data
            return {"status": "insufficient_data"}

        # 1. Hourly temperature profile
        if "hour" in df.columns and "temp_indoor" in df.columns:
            df["hour_bin"] = df["hour"].apply(lambda h: int(h) % 24)
            hourly = df.groupby("hour_bin")["temp_indoor"]
            self.hourly_temp_profile = hourly.mean().reindex(range(24)).values
            self.hourly_temp_std = hourly.std().reindex(range(24)).fillna(1.0).values

        # 2. Occupancy patterns
        if "occupied" in df.columns:
            occ_hourly = df.groupby("hour_bin")["occupied"].mean()
            self.hourly_occupancy_prob = occ_hourly.reindex(range(24)).fillna(0.5).values

        # 3. Thermal response rates
        if "temp_indoor" in df.columns and "hvac_mode" in df.columns:
            self._compute_thermal_rates(df)

        # 4. Peak demand hours
        if "hvac_power_w" in df.columns:
            power_hourly = df.groupby("hour_bin")["hvac_power_w"].mean()
            high_power_threshold = power_hourly.quantile(0.75)
            self.peak_cooling_hours = [
                h for h in range(24)
                if h in power_hourly.index and power_hourly[h] > high_power_threshold
            ]

        self._is_trained = True

        return {
            "status": "trained",
            "data_points": len(df),
            "avg_temp": float(np.nanmean(self.hourly_temp_profile)),
            "heating_rate_per_min": round(self.heating_rate, 4),
            "cooling_rate_per_min": round(self.cooling_rate, 4),
            "peak_cooling_hours": self.peak_cooling_hours,
            "occupancy_pattern": [round(p, 2) for p in self.hourly_occupancy_prob],
        }

    def _compute_thermal_rates(self, df: pd.DataFrame) -> None:
        """Compute heating/cooling rates from temperature change data."""
        if len(df) < 2:
            return

        # Temperature change per minute
        temp_diff = df["temp_indoor"].diff()

        # Heating rate (when HVAC is heating)
        heating_mask = df["hvac_mode"] == "heating"
        if heating_mask.sum() > 10:
            self.heating_rate = float(temp_diff[heating_mask].mean())

        # Cooling rate (when HVAC is cooling)
        cooling_mask = df["hvac_mode"] == "cooling"
        if cooling_mask.sum() > 10:
            self.cooling_rate = float(temp_diff[cooling_mask].mean())

        # Passive rates (HVAC off)
        idle_mask = df["hvac_mode"] == "idle"
        if idle_mask.sum() > 10:
            passive_diff = temp_diff[idle_mask]
            self.passive_heating_rate = float(passive_diff[passive_diff > 0].mean()) if (passive_diff > 0).any() else 0.0
            self.passive_cooling_rate = float(passive_diff[passive_diff < 0].mean()) if (passive_diff < 0).any() else 0.0

    def predict_occupancy(self, hour: float) -> float:
        """
        Predict probability of occupancy at a given hour.

        Args:
            hour: Hour of day (0–24)

        Returns:
            Probability of occupancy (0.0 to 1.0)
        """
        h = int(hour) % 24
        return float(self.hourly_occupancy_prob[h])

    def predict_temp_trend(self, hour: float) -> str:
        """
        Predict temperature trend direction at a given hour.

        Returns: "rising", "falling", or "stable"
        """
        if not self._is_trained:
            return "stable"

        h = int(hour) % 24
        h_next = (h + 1) % 24

        current = self.hourly_temp_profile[h]
        next_val = self.hourly_temp_profile[h_next]

        if np.isnan(current) or np.isnan(next_val):
            return "stable"

        diff = next_val - current
        if diff > 0.3:
            return "rising"
        elif diff < -0.3:
            return "falling"
        return "stable"

    def get_time_to_target(self, current_temp: float, target_temp: float,
                            mode: str = "cooling") -> float:
        """
        Estimate minutes to reach target temperature.

        Args:
            current_temp: Current indoor temperature (°C)
            target_temp:  Target temperature (°C)
            mode:        "cooling" or "heating"

        Returns:
            Estimated minutes to reach target. Returns 999 if rate is zero.
        """
        delta = abs(target_temp - current_temp)
        rate = abs(self.cooling_rate if mode == "cooling" else self.heating_rate)

        if rate < 0.001:
            return 999.0

        return delta / rate

    @property
    def is_trained(self) -> bool:
        return self._is_trained
