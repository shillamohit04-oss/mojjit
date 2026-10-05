"""
Simulated Sensors
=================

Simulates DHT22 (temperature + humidity) and PIR (occupancy) sensors
with realistic noise, latency, and failure characteristics.

Sensor Specifications (DHT22):
    - Temperature accuracy: ±0.5°C (we model ±0.3°C Gaussian noise)
    - Humidity accuracy: ±2-5% RH (we model ±2% Gaussian noise)
    - Sampling rate: max 0.5 Hz (2-second minimum interval)
    - Operating range: -40 to 80°C, 0-100% RH

PIR Sensor:
    - Detection range: ~7m, 120° cone
    - False positive rate: ~1% per reading
    - False negative rate: ~3% per reading (occupant is stationary)
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class SensorConfig:
    """Configuration for sensor simulation."""

    # DHT22 noise parameters
    temp_noise_std: float = 0.3        # °C standard deviation
    humidity_noise_std: float = 2.0    # % RH standard deviation

    # DHT22 failure simulation
    read_failure_rate: float = 0.02    # 2% chance of read failure
    min_read_interval_sec: float = 2.0  # Minimum interval between reads

    # PIR sensor parameters
    pir_false_positive_rate: float = 0.01   # 1% false positives
    pir_false_negative_rate: float = 0.03   # 3% false negatives when stationary
    pir_timeout_minutes: float = 5.0        # Timeout after last motion

    # Sensor drift (long-term)
    temp_drift_per_day: float = 0.01   # °C drift per day (very small)
    humidity_drift_per_day: float = 0.05  # %RH drift per day


class SimulatedDHT22:
    """
    Simulated DHT22 temperature and humidity sensor.

    Adds Gaussian noise, occasional read failures,
    and slow sensor drift to true values.
    """

    def __init__(self, config: Optional[SensorConfig] = None, seed: Optional[int] = None):
        self.config = config or SensorConfig()
        self.rng = np.random.default_rng(seed)
        self._read_count = 0
        self._drift_temp = 0.0
        self._drift_humidity = 0.0
        self._last_valid_temp = 23.0
        self._last_valid_humidity = 50.0

    def read(self, true_temp: float, true_humidity: float,
             minute: int) -> dict:
        """
        Simulate a sensor reading.

        Args:
            true_temp:     Actual room temperature (°C)
            true_humidity: Actual room humidity (% RH)
            minute:        Current simulation minute

        Returns:
            Dictionary with:
                - 'temperature': float or None (None = read failure)
                - 'humidity': float or None
                - 'valid': bool
                - 'raw_temp': float (true value before noise)
                - 'raw_humidity': float
        """
        self._read_count += 1

        # Update drift (accumulates slowly over days)
        day = minute / 1440.0
        self._drift_temp = day * self.config.temp_drift_per_day
        self._drift_humidity = day * self.config.humidity_drift_per_day

        # Check for read failure
        if self.rng.random() < self.config.read_failure_rate:
            return {
                "temperature": self._last_valid_temp,  # Return last known good
                "humidity": self._last_valid_humidity,
                "valid": False,
                "raw_temp": true_temp,
                "raw_humidity": true_humidity
            }

        # Apply noise + drift
        measured_temp = (
            true_temp +
            self.rng.normal(0, self.config.temp_noise_std) +
            self._drift_temp
        )
        measured_humidity = (
            true_humidity +
            self.rng.normal(0, self.config.humidity_noise_std) +
            self._drift_humidity
        )

        # Clamp to sensor range
        measured_temp = float(np.clip(measured_temp, -40.0, 80.0))
        measured_humidity = float(np.clip(measured_humidity, 0.0, 100.0))

        # Quantize to sensor resolution (DHT22: 0.1°C, 0.1% RH)
        measured_temp = round(measured_temp, 1)
        measured_humidity = round(measured_humidity, 1)

        self._last_valid_temp = measured_temp
        self._last_valid_humidity = measured_humidity

        return {
            "temperature": measured_temp,
            "humidity": measured_humidity,
            "valid": True,
            "raw_temp": true_temp,
            "raw_humidity": true_humidity
        }


class SimulatedPIR:
    """
    Simulated PIR (Passive Infrared) motion sensor.

    Models:
    - Detection with configurable false positive/negative rates
    - Motion timeout (reports "no occupancy" after timeout with no motion)
    - Realistic detection cone limitations
    """

    def __init__(self, config: Optional[SensorConfig] = None, seed: Optional[int] = None):
        self.config = config or SensorConfig()
        self.rng = np.random.default_rng(seed)
        self._last_motion_minute = -9999
        self._reported_occupied = False

    def read(self, true_occupied: bool, true_motion: bool, minute: int) -> dict:
        """
        Simulate a PIR sensor reading.

        Args:
            true_occupied: Actual occupancy state
            true_motion:   Actual motion event
            minute:        Current simulation minute

        Returns:
            Dictionary with:
                - 'motion_detected': bool
                - 'occupied_estimate': bool (based on timeout logic)
                - 'raw_occupied': bool (ground truth)
        """
        # Simulate detection with error rates
        if true_motion:
            # True motion — detect with some false negative rate
            if self.rng.random() > self.config.pir_false_negative_rate:
                detected = True
            else:
                detected = False
        else:
            # No true motion — check for false positive
            if self.rng.random() < self.config.pir_false_positive_rate:
                detected = True
            else:
                detected = False

        # Update last motion time
        if detected:
            self._last_motion_minute = minute

        # Occupancy estimate based on timeout
        minutes_since_motion = minute - self._last_motion_minute
        self._reported_occupied = minutes_since_motion < self.config.pir_timeout_minutes

        return {
            "motion_detected": detected,
            "occupied_estimate": self._reported_occupied,
            "raw_occupied": true_occupied
        }
