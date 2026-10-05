"""
Thermal Model — First-Order RC (Resistance-Capacitance) Model
=============================================================

Models a single-zone residential room as a lumped-capacitance thermal system.

Physics:
    C × dT_in/dt = (T_out - T_in) / R  - Q_hvac  + Q_internal  + Q_solar

Where:
    C          = Thermal capacitance of the room (J/°C)
    R          = Thermal resistance of the building envelope (°C/W)
    T_in       = Indoor temperature (°C)
    T_out      = Outdoor temperature (°C)
    Q_hvac     = HVAC heat transfer (W) — positive = heating, negative = cooling
    Q_internal = Internal heat gains from occupants + equipment (W)
    Q_solar    = Solar heat gain through windows (W)

Assumptions documented in implementation_plan.md.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RoomParameters:
    """Physical parameters of the simulated room."""

    # Room geometry
    length: float = 5.0          # m
    width: float = 4.0           # m
    height: float = 3.0          # m

    # Thermal properties
    R_envelope: float = 0.004    # Thermal resistance (°C/W) — overall envelope
    C_thermal: float = 2.5e6    # Thermal capacitance (J/°C) — room + furniture + air

    # Window properties
    window_area: float = 4.0     # m² — total window area
    shgc: float = 0.4            # Solar Heat Gain Coefficient (double-glazed)
    window_orientation: float = 180.0  # degrees from north (180 = south-facing)

    # Internal gains
    occupant_heat: float = 75.0   # W per occupant (sensible heat, seated)
    equipment_heat: float = 150.0  # W baseline (always-on electronics)

    @property
    def volume(self) -> float:
        """Room volume in m³."""
        return self.length * self.width * self.height

    @property
    def floor_area(self) -> float:
        """Floor area in m²."""
        return self.length * self.width


@dataclass
class ThermalState:
    """Current thermal state of the room."""
    temperature: float = 23.0    # °C — initial indoor temperature
    humidity: float = 50.0       # % RH — initial relative humidity
    timestamp_minutes: int = 0   # Minutes since simulation start


class ThermalModel:
    """
    First-order RC thermal model for a single-zone room.

    Uses Euler integration at configurable timestep (default: 1 minute).
    Includes solar gain modeling, occupant heat, and equipment loads.
    """

    def __init__(self, params: Optional[RoomParameters] = None, dt_seconds: float = 60.0):
        """
        Args:
            params: Room physical parameters. Uses defaults if None.
            dt_seconds: Integration timestep in seconds. Default = 60s (1 minute).
        """
        self.params = params or RoomParameters()
        self.dt = dt_seconds
        self.state = ThermalState()

        # Humidity model parameters
        self._humidity_time_constant = 600.0  # seconds — how fast humidity responds
        self._base_humidity = 50.0

    def reset(self, initial_temp: float = 23.0, initial_humidity: float = 50.0) -> ThermalState:
        """Reset the model to initial conditions."""
        self.state = ThermalState(
            temperature=initial_temp,
            humidity=initial_humidity,
            timestamp_minutes=0
        )
        return self.state

    def step(
        self,
        T_outdoor: float,
        humidity_outdoor: float,
        Q_hvac: float,
        n_occupants: int,
        hour_of_day: float,
        day_of_year: int = 180
    ) -> ThermalState:
        """
        Advance the thermal model by one timestep.

        Args:
            T_outdoor:        Outdoor temperature (°C)
            humidity_outdoor:  Outdoor relative humidity (%)
            Q_hvac:           HVAC heat transfer (W). Positive = heating, negative = cooling.
            n_occupants:      Number of occupants in the room
            hour_of_day:      Current hour (0.0–24.0, fractional)
            day_of_year:      Day of year (1–365) for solar calculations

        Returns:
            Updated ThermalState
        """
        p = self.params
        T_in = self.state.temperature

        # === Heat flows ===

        # 1. Envelope heat transfer (conduction + convection + infiltration)
        Q_envelope = (T_outdoor - T_in) / p.R_envelope  # W

        # 2. Internal heat gains
        Q_internal = (n_occupants * p.occupant_heat) + p.equipment_heat  # W

        # 3. Solar heat gain (simplified model)
        Q_solar = self._compute_solar_gain(hour_of_day, day_of_year)  # W

        # === Temperature update (Euler integration) ===
        dT_dt = (Q_envelope + Q_hvac + Q_internal + Q_solar) / p.C_thermal  # °C/s
        T_new = T_in + dT_dt * self.dt

        # Clamp to physically reasonable bounds
        T_new = np.clip(T_new, -10.0, 55.0)

        # === Humidity update (simplified model) ===
        # Indoor humidity is influenced by outdoor humidity, occupants, and HVAC
        humidity_new = self._update_humidity(
            self.state.humidity, humidity_outdoor, Q_hvac, n_occupants
        )

        # === Update state ===
        self.state.temperature = float(T_new)
        self.state.humidity = float(humidity_new)
        self.state.timestamp_minutes += int(self.dt / 60.0)

        return self.state

    def _compute_solar_gain(self, hour_of_day: float, day_of_year: int) -> float:
        """
        Simplified solar heat gain through windows.

        Uses a bell-curve approximation for solar irradiance,
        peaking at solar noon. Accounts for window orientation and SHGC.

        Args:
            hour_of_day: Current hour (0–24)
            day_of_year: Day of year (1–365)

        Returns:
            Solar heat gain in Watts
        """
        p = self.params

        # Solar irradiance peaks at noon, zero at night
        # Using a cosine model: I = I_max × cos(π × (hour - 12) / 12)
        if 6.0 <= hour_of_day <= 18.0:
            solar_angle = np.pi * (hour_of_day - 12.0) / 12.0
            # Peak irradiance varies by season (higher in summer)
            seasonal_factor = 0.7 + 0.3 * np.cos(2 * np.pi * (day_of_year - 172) / 365)
            I_peak = 800.0 * seasonal_factor  # W/m² — peak direct + diffuse on surface
            irradiance = I_peak * max(0, np.cos(solar_angle))
        else:
            irradiance = 0.0

        # Heat gain through windows
        Q_solar = irradiance * p.window_area * p.shgc

        return Q_solar

    def _update_humidity(
        self,
        humidity_current: float,
        humidity_outdoor: float,
        Q_hvac: float,
        n_occupants: int
    ) -> float:
        """
        Simplified humidity model.

        - Trends toward outdoor humidity via infiltration
        - Occupants add moisture (≈50 g/h per person)
        - Cooling removes moisture (dehumidification)
        - Heating reduces relative humidity (temp increase, same absolute moisture)

        Returns:
            Updated indoor relative humidity (%)
        """
        # Infiltration effect — slowly moves indoor toward outdoor
        alpha = self.dt / self._humidity_time_constant
        alpha = min(alpha, 0.1)  # Stability limit

        humidity_target = humidity_outdoor

        # Occupant moisture generation (+1.5% RH per occupant per timestep at 1 min)
        occupant_moisture = n_occupants * 1.5 * (self.dt / 3600.0)

        # HVAC effects
        hvac_dehumid = 0.0
        if Q_hvac < -500:  # Significant cooling — dehumidification
            hvac_dehumid = -2.0 * (self.dt / 3600.0)  # Remove ~2% RH per hour
        elif Q_hvac > 500:  # Heating — reduces RH (same absolute, higher temp)
            hvac_dehumid = -1.0 * (self.dt / 3600.0)

        humidity_new = (
            humidity_current * (1 - alpha) +
            humidity_target * alpha +
            occupant_moisture +
            hvac_dehumid
        )

        return float(np.clip(humidity_new, 15.0, 95.0))

    def get_thermal_load(self, T_outdoor: float) -> float:
        """
        Calculate the current thermal load on the room (W).
        Positive = room is gaining heat, Negative = room is losing heat.
        Useful for sizing and diagnostics.
        """
        T_in = self.state.temperature
        return (T_outdoor - T_in) / self.params.R_envelope

    def steady_state_temperature(self, T_outdoor: float, Q_hvac: float = 0.0,
                                  Q_internal: float = 150.0, Q_solar: float = 0.0) -> float:
        """
        Calculate the steady-state indoor temperature analytically.
        At steady state: dT/dt = 0 → T_in = T_out + R × (Q_hvac + Q_internal + Q_solar)
        """
        p = self.params
        return T_outdoor + p.R_envelope * (Q_hvac + Q_internal + Q_solar)
