"""
HVAC Plant Model — Bidirectional Heat Pump System
=================================================

Models a dual-mode (heating + cooling) residential heat pump / AC unit.

Specifications:
    Cooling: 3.5 kW capacity, COP 3.2 (nominal)
    Heating: 3.0 kW capacity, COP 3.5 (nominal)

Features:
    - Multi-stage operation: OFF / LOW (40%) / HIGH (100%)
    - Compressor short-cycle protection (3-minute minimum ON and OFF time)
    - COP variation with outdoor temperature
    - Energy consumption tracking
    - Bidirectional mode: COOLING / HEATING / IDLE
"""

import numpy as np
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Optional


class HVACMode(Enum):
    """Operating mode of the HVAC system."""
    IDLE = "idle"
    COOLING = "cooling"
    HEATING = "heating"


class HVACStage(IntEnum):
    """HVAC power stage."""
    OFF = 0
    LOW = 1       # 40% capacity
    HIGH = 2      # 100% capacity

    @property
    def capacity_fraction(self) -> float:
        """Fraction of full capacity."""
        return {0: 0.0, 1: 0.40, 2: 1.0}[self.value]


# Combined action: encodes both mode and stage
class HVACAction(IntEnum):
    """Discrete HVAC actions for the controller."""
    HEAT_HIGH = 0
    HEAT_LOW = 1
    OFF = 2
    COOL_LOW = 3
    COOL_HIGH = 4

    @property
    def mode(self) -> HVACMode:
        if self.value <= 1:
            return HVACMode.HEATING
        elif self.value >= 3:
            return HVACMode.COOLING
        return HVACMode.IDLE

    @property
    def stage(self) -> HVACStage:
        if self.value in (0, 4):
            return HVACStage.HIGH
        elif self.value in (1, 3):
            return HVACStage.LOW
        return HVACStage.OFF


@dataclass
class HVACSpecs:
    """HVAC system specifications."""

    # Cooling specifications
    cooling_capacity_w: float = 3500.0   # Watts — full cooling capacity
    cooling_cop_nominal: float = 3.2     # Coefficient of Performance at 35°C outdoor

    # Heating specifications
    heating_capacity_w: float = 3000.0   # Watts — full heating capacity
    heating_cop_nominal: float = 3.5     # COP at 7°C outdoor (heat pump mode)

    # Protection
    min_cycle_time_minutes: int = 3      # Minimum ON or OFF duration

    # COP degradation with temperature
    cop_temp_coefficient: float = 0.02   # COP drops 2% per °C deviation from nominal

    # Nominal outdoor temperatures for COP rating
    cooling_nominal_outdoor: float = 35.0  # °C
    heating_nominal_outdoor: float = 7.0   # °C


class HVACPlant:
    """
    Bidirectional HVAC plant model with compressor protection.

    Tracks:
    - Current operating mode and stage
    - Energy consumption (electrical input, kWh)
    - Thermal energy delivered (heating/cooling output, kWh)
    - Compressor cycling and protection state
    """

    def __init__(self, specs: Optional[HVACSpecs] = None):
        self.specs = specs or HVACSpecs()

        # State
        self.mode = HVACMode.IDLE
        self.stage = HVACStage.OFF
        self.action = HVACAction.OFF

        # Compressor protection
        self._minutes_in_state = 999  # Start with protection satisfied
        self._protection_active = False

        # Energy tracking
        self.energy_consumed_kwh = 0.0    # Electrical input
        self.energy_delivered_kwh = 0.0   # Thermal output
        self.total_runtime_minutes = 0
        self._runtime_by_mode = {"cooling": 0, "heating": 0, "idle": 0}

        # Power log (for instantaneous readings)
        self.current_power_w = 0.0
        self.current_thermal_output_w = 0.0

    def set_action(self, action: HVACAction, dt_minutes: float = 1.0) -> float:
        """
        Set the desired HVAC action and return the heat transfer rate.

        Enforces compressor short-cycle protection. If the requested action
        would violate the minimum cycle time, the previous action is maintained.

        Args:
            action:     Desired HVACAction
            dt_minutes: Timestep duration in minutes

        Returns:
            Q_hvac: Heat transfer to the room (W).
                    Positive = heating, Negative = cooling, Zero = off.
        """
        requested_mode = action.mode
        requested_stage = action.stage

        # Compressor protection check
        current_is_running = self.stage != HVACStage.OFF
        requested_is_running = requested_stage != HVACStage.OFF

        if current_is_running != requested_is_running:
            # Mode transition requested — check protection timer
            if self._minutes_in_state < self.specs.min_cycle_time_minutes:
                self._protection_active = True
                # Reject the transition — maintain current state
                action = self.action
                requested_mode = action.mode
                requested_stage = action.stage
            else:
                self._protection_active = False
                self._minutes_in_state = 0
        else:
            self._protection_active = False

        # Update state
        old_action = self.action
        self.action = action
        self.mode = requested_mode
        self.stage = requested_stage

        if action == old_action:
            self._minutes_in_state += dt_minutes
        else:
            self._minutes_in_state = dt_minutes

        # Calculate thermal output
        Q_hvac = self._compute_thermal_output(dt_minutes)

        # Track energy
        self._track_energy(dt_minutes)

        return Q_hvac

    def _compute_thermal_output(self, dt_minutes: float) -> float:
        """Compute the heat transfer rate to the room (W)."""
        if self.stage == HVACStage.OFF:
            self.current_thermal_output_w = 0.0
            self.current_power_w = 0.0
            return 0.0

        capacity_fraction = self.stage.capacity_fraction

        if self.mode == HVACMode.COOLING:
            # Cooling — negative Q (removes heat from room)
            Q = -self.specs.cooling_capacity_w * capacity_fraction
            self.current_thermal_output_w = Q
        elif self.mode == HVACMode.HEATING:
            # Heating — positive Q (adds heat to room)
            Q = self.specs.heating_capacity_w * capacity_fraction
            self.current_thermal_output_w = Q
        else:
            Q = 0.0
            self.current_thermal_output_w = 0.0

        return Q

    def _track_energy(self, dt_minutes: float) -> None:
        """Track energy consumption and delivery."""
        if self.stage == HVACStage.OFF:
            self.current_power_w = 0.0
            self._runtime_by_mode["idle"] += dt_minutes
            return

        # Calculate electrical power input using COP
        thermal_output = abs(self.current_thermal_output_w)

        if self.mode == HVACMode.COOLING:
            cop = self.specs.cooling_cop_nominal
            self._runtime_by_mode["cooling"] += dt_minutes
        elif self.mode == HVACMode.HEATING:
            cop = self.specs.heating_cop_nominal
            self._runtime_by_mode["heating"] += dt_minutes
        else:
            cop = 1.0
            self._runtime_by_mode["idle"] += dt_minutes

        electrical_power_w = thermal_output / cop
        self.current_power_w = electrical_power_w

        # Accumulate energy (convert W·minutes to kWh)
        dt_hours = dt_minutes / 60.0
        self.energy_consumed_kwh += electrical_power_w * dt_hours / 1000.0
        self.energy_delivered_kwh += thermal_output * dt_hours / 1000.0
        self.total_runtime_minutes += dt_minutes

    def get_cop(self, T_outdoor: float) -> float:
        """
        Get the current COP adjusted for outdoor temperature.

        COP degrades as outdoor temperature moves away from nominal:
        - Cooling: COP drops in hotter weather
        - Heating: COP drops in colder weather (heat pump performance)
        """
        if self.mode == HVACMode.COOLING:
            delta_t = T_outdoor - self.specs.cooling_nominal_outdoor
            cop = self.specs.cooling_cop_nominal * (1 - self.specs.cop_temp_coefficient * delta_t)
        elif self.mode == HVACMode.HEATING:
            delta_t = self.specs.heating_nominal_outdoor - T_outdoor
            cop = self.specs.heating_cop_nominal * (1 - self.specs.cop_temp_coefficient * delta_t)
        else:
            cop = 1.0

        return max(cop, 1.0)  # COP cannot be below 1.0

    def get_status(self) -> dict:
        """Get current HVAC status as a dictionary."""
        return {
            "mode": self.mode.value,
            "stage": self.stage.name,
            "action": self.action.name,
            "power_w": round(self.current_power_w, 1),
            "thermal_output_w": round(self.current_thermal_output_w, 1),
            "energy_consumed_kwh": round(self.energy_consumed_kwh, 3),
            "energy_delivered_kwh": round(self.energy_delivered_kwh, 3),
            "protection_active": self._protection_active,
            "minutes_in_state": self._minutes_in_state,
            "runtime_cooling_min": self._runtime_by_mode["cooling"],
            "runtime_heating_min": self._runtime_by_mode["heating"],
        }

    def reset(self) -> None:
        """Reset the HVAC plant to initial state."""
        self.mode = HVACMode.IDLE
        self.stage = HVACStage.OFF
        self.action = HVACAction.OFF
        self._minutes_in_state = 999
        self._protection_active = False
        self.energy_consumed_kwh = 0.0
        self.energy_delivered_kwh = 0.0
        self.total_runtime_minutes = 0
        self._runtime_by_mode = {"cooling": 0, "heating": 0, "idle": 0}
        self.current_power_w = 0.0
        self.current_thermal_output_w = 0.0
