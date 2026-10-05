"""
Rule-Based Bidirectional Controller
====================================

Industry-standard three-zone HVAC control with:
- Cooling zone (T > 26°C)
- Heating zone (T < 20°C)
- Idle deadband zone (20–26°C)

Features:
- Hysteresis (±0.5°C) to prevent oscillation
- Occupancy-aware setback (wider deadband when unoccupied)
- Night setback for sleeping hours
- Humidity override for dehumidification
- Compressor protection (enforced by HVAC plant, respected here)

This serves as the BASELINE controller for comparison against
the adaptive Q-Learning controller.
"""

from controllers.base_controller import BaseController
from simulation.hvac_plant import HVACAction


class RuleBasedController(BaseController):
    """
    Three-zone rule-based HVAC controller.

    Decision Logic:
        OCCUPIED:
            T > 26.0 + hyst → COOL_HIGH
            T > 26.0        → COOL_LOW
            T < 20.0 - hyst → HEAT_HIGH
            T < 20.0        → HEAT_LOW
            20.0 ≤ T ≤ 26.0 → OFF (idle)
            RH > 70%        → COOL_LOW (dehumidify)

        UNOCCUPIED:
            T > 28.0 → COOL_LOW  (furnishing protection)
            T < 18.0 → HEAT_LOW  (freeze protection)
            else     → OFF

        NIGHT (23:00–06:00, occupied):
            Comfort band relaxed by ±1°C → 19–27°C
    """

    def __init__(
        self,
        cooling_threshold: float = 26.0,
        heating_threshold: float = 20.0,
        hysteresis: float = 0.5,
        unoccupied_cooling: float = 28.0,
        unoccupied_heating: float = 18.0,
        night_cooling: float = 27.0,
        night_heating: float = 19.0,
        humidity_override: float = 70.0,
    ):
        super().__init__(name="rule_based")

        self.cooling_threshold = cooling_threshold
        self.heating_threshold = heating_threshold
        self.hysteresis = hysteresis
        self.unoccupied_cooling = unoccupied_cooling
        self.unoccupied_heating = unoccupied_heating
        self.night_cooling = night_cooling
        self.night_heating = night_heating
        self.humidity_override = humidity_override

        # Internal state for hysteresis tracking
        self._current_zone = "idle"  # "cooling", "heating", "idle"

    def compute_action(self, state: dict) -> HVACAction:
        """
        Compute the HVAC action based on current sensor state.

        Uses three-zone logic with hysteresis to prevent rapid cycling.
        """
        temp = state["temp_indoor"]
        humidity = state.get("humidity_indoor", 50.0)
        occupied = state.get("occupied", True)
        hour = state.get("hour", 12.0)

        # Determine active thresholds based on occupancy and time
        is_night = hour >= 23.0 or hour < 6.0

        if not occupied:
            cool_on = self.unoccupied_cooling
            cool_off = self.unoccupied_cooling - self.hysteresis
            heat_on = self.unoccupied_heating
            heat_off = self.unoccupied_heating + self.hysteresis
        elif is_night:
            cool_on = self.night_cooling
            cool_off = self.night_cooling - self.hysteresis
            heat_on = self.night_heating
            heat_off = self.night_heating + self.hysteresis
        else:
            cool_on = self.cooling_threshold
            cool_off = self.cooling_threshold - self.hysteresis
            heat_on = self.heating_threshold
            heat_off = self.heating_threshold + self.hysteresis

        # === Zone determination with hysteresis ===
        action = HVACAction.OFF

        if self._current_zone == "cooling":
            # Currently cooling — continue until temp drops below cool_off
            if temp <= cool_off:
                self._current_zone = "idle"
                action = HVACAction.OFF
            elif temp > cool_on + 2.0:
                # Far above threshold — use HIGH
                action = HVACAction.COOL_HIGH
            else:
                action = HVACAction.COOL_LOW

        elif self._current_zone == "heating":
            # Currently heating — continue until temp rises above heat_off
            if temp >= heat_off:
                self._current_zone = "idle"
                action = HVACAction.OFF
            elif temp < heat_on - 2.0:
                # Far below threshold — use HIGH
                action = HVACAction.HEAT_HIGH
            else:
                action = HVACAction.HEAT_LOW

        else:  # idle
            # Check if we need to enter cooling or heating
            if temp > cool_on + self.hysteresis:
                self._current_zone = "cooling"
                if temp > cool_on + 2.0:
                    action = HVACAction.COOL_HIGH
                else:
                    action = HVACAction.COOL_LOW
            elif temp < heat_on - self.hysteresis:
                self._current_zone = "heating"
                if temp < heat_on - 2.0:
                    action = HVACAction.HEAT_HIGH
                else:
                    action = HVACAction.HEAT_LOW
            else:
                action = HVACAction.OFF

        # === Humidity override ===
        if humidity > self.humidity_override and action == HVACAction.OFF:
            action = HVACAction.COOL_LOW  # Force dehumidification
            self._current_zone = "cooling"

        # === Unoccupied energy saving ===
        if not occupied and action != HVACAction.OFF:
            # Limit to LOW power when unoccupied
            if action == HVACAction.COOL_HIGH:
                action = HVACAction.COOL_LOW
            elif action == HVACAction.HEAT_HIGH:
                action = HVACAction.HEAT_LOW

        self._record_action(action)
        return action

    def reset(self) -> None:
        """Reset controller state."""
        super().reset()
        self._current_zone = "idle"

    def get_stats(self) -> dict:
        """Get controller statistics including zone tracking."""
        stats = super().get_stats()
        stats["current_zone"] = self._current_zone
        return stats
