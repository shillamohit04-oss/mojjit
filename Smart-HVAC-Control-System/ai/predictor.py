"""
Temperature Predictor — Short-Term Forecasting
===============================================

Predicts indoor temperature 15/30/60 minutes ahead using
a lightweight linear regression model.

Features:
    - Current indoor temperature
    - Outdoor temperature
    - HVAC state (encoded)
    - Hour of day (sin/cos encoded for cyclicity)
    - Occupancy state

Use cases:
    - Predictive pre-cooling before occupancy
    - Predictive pre-heating in winter mornings
    - Avoiding overshooting setpoints
"""

import numpy as np
from typing import Optional, List
from collections import deque


class TemperaturePredictor:
    """
    Lightweight linear regression predictor for indoor temperature.

    Uses a sliding window of recent data and retrains periodically.
    Designed to run on constrained hardware (no heavy ML libraries needed).
    """

    def __init__(
        self,
        horizons: list = None,
        buffer_size: int = 1440,    # 24 hours of 1-min data
        retrain_interval: int = 60  # Retrain every 60 minutes
    ):
        """
        Args:
            horizons:          Prediction horizons in minutes [15, 30, 60]
            buffer_size:       Number of recent data points to keep
            retrain_interval:  Minutes between model retraining
        """
        self.horizons = horizons or [15, 30, 60]
        self.buffer_size = buffer_size
        self.retrain_interval = retrain_interval

        # Data buffer
        self._buffer = deque(maxlen=buffer_size)
        self._step_count = 0

        # Model weights (one per horizon)
        # Features: [temp_in, temp_out, hvac_power, hour_sin, hour_cos, occupied, bias]
        self.n_features = 7
        self._weights = {h: np.zeros(self.n_features) for h in self.horizons}
        self._is_trained = False

    def update(self, state: dict) -> None:
        """
        Add a new data point to the buffer.

        Args:
            state: Dictionary with keys: temp_indoor, temp_outdoor,
                   hvac_power_w (or hvac_stage), hour, occupied
        """
        features = self._extract_features(state)
        self._buffer.append({
            "features": features,
            "temp": state.get("temp_indoor", 23.0),
            "minute": state.get("minute", self._step_count)
        })

        self._step_count += 1

        # Retrain periodically
        if self._step_count % self.retrain_interval == 0 and len(self._buffer) > max(self.horizons) + 50:
            self._train()

    def predict(self, state: dict) -> dict:
        """
        Predict future indoor temperature.

        Args:
            state: Current state dictionary.

        Returns:
            Dictionary mapping horizon (minutes) to predicted temperature.
        """
        if not self._is_trained:
            # Fallback: return current temperature
            current = state.get("temp_indoor", 23.0)
            return {h: current for h in self.horizons}

        features = self._extract_features(state)
        predictions = {}

        for h in self.horizons:
            pred = float(np.dot(self._weights[h], features))
            # Clamp to reasonable range
            pred = np.clip(pred, 5.0, 50.0)
            predictions[h] = round(pred, 2)

        return predictions

    def _extract_features(self, state: dict) -> np.ndarray:
        """Extract feature vector from state dictionary."""
        hour = state.get("hour", 12.0)

        # Encode HVAC power
        hvac_power = 0.0
        if "hvac_power_w" in state:
            hvac_power = state["hvac_power_w"] / 1000.0  # Normalize to kW
        elif "hvac_stage" in state:
            stage_map = {"OFF": 0.0, "LOW": 0.4, "HIGH": 1.0}
            hvac_power = stage_map.get(state["hvac_stage"], 0.0)

        # Check if heating or cooling (sign matters)
        mode = state.get("hvac_mode", "idle")
        if mode == "heating":
            hvac_power = abs(hvac_power)
        elif mode == "cooling":
            hvac_power = -abs(hvac_power)

        features = np.array([
            state.get("temp_indoor", 23.0),
            state.get("temp_outdoor", 25.0),
            hvac_power,
            np.sin(2 * np.pi * hour / 24.0),  # Hour cyclical encoding
            np.cos(2 * np.pi * hour / 24.0),
            1.0 if state.get("occupied", True) else 0.0,
            1.0  # Bias term
        ])
        return features

    def _train(self) -> None:
        """Train linear regression models for each prediction horizon."""
        data = list(self._buffer)
        n = len(data)

        for horizon in self.horizons:
            if n <= horizon + 10:
                continue

            # Build training data
            X = []
            y = []

            for i in range(n - horizon):
                X.append(data[i]["features"])
                y.append(data[i + horizon]["temp"])

            X = np.array(X)
            y = np.array(y)

            # Ridge regression (L2 regularization for stability)
            lambda_reg = 0.01
            try:
                XtX = X.T @ X + lambda_reg * np.eye(self.n_features)
                Xty = X.T @ y
                self._weights[horizon] = np.linalg.solve(XtX, Xty)
                self._is_trained = True
            except np.linalg.LinAlgError:
                pass  # Keep previous weights on failure

    def should_precool(self, state: dict, target_temp: float = 26.0,
                       occupancy_expected_minutes: int = 30) -> bool:
        """
        Determine if pre-cooling should start.

        Returns True if predicted temperature will exceed target
        within the expected occupancy window.
        """
        predictions = self.predict(state)

        for horizon, pred_temp in predictions.items():
            if horizon <= occupancy_expected_minutes and pred_temp > target_temp:
                return True
        return False

    def should_preheat(self, state: dict, target_temp: float = 20.0,
                       occupancy_expected_minutes: int = 30) -> bool:
        """
        Determine if pre-heating should start.

        Returns True if predicted temperature will drop below target
        within the expected occupancy window.
        """
        predictions = self.predict(state)

        for horizon, pred_temp in predictions.items():
            if horizon <= occupancy_expected_minutes and pred_temp < target_temp:
                return True
        return False

    @property
    def is_trained(self) -> bool:
        return self._is_trained
