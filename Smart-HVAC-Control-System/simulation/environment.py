"""
Simulation Environment — Gym-Style Interface
=============================================

Wraps the thermal model, sensors, weather, and occupancy generators
into a unified environment with step/reset interface.

State vector: [T_indoor, T_outdoor, humidity, occupied, hour_of_day, hvac_mode]
Action space: HVACAction (HEAT_HIGH, HEAT_LOW, OFF, COOL_LOW, COOL_HIGH)
Reward:       -α × energy - β × comfort_violation²
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

from simulation.thermal_model import ThermalModel, RoomParameters
from simulation.weather import WeatherGenerator, Season
from simulation.occupancy import OccupancyGenerator
from simulation.sensors import SimulatedDHT22, SimulatedPIR, SensorConfig
from simulation.hvac_plant import HVACPlant, HVACAction, HVACMode
from simulation.data_logger import DataLogger


@dataclass
class ComfortBand:
    """Defines the thermal comfort zone (bidirectional)."""
    cooling_threshold: float = 26.0   # °C — start cooling above this
    heating_threshold: float = 20.0   # °C — start heating below this
    optimal_temp: float = 23.0        # °C — ideal setpoint

    # Unoccupied setbacks (wider band to save energy)
    unoccupied_cooling: float = 28.0  # °C
    unoccupied_heating: float = 18.0  # °C

    # Night setbacks
    night_cooling: float = 27.0       # °C
    night_heating: float = 19.0       # °C

    def is_comfortable(self, temp: float, occupied: bool, hour: float) -> Tuple[bool, float]:
        """
        Check if temperature is within comfort zone.

        Returns:
            (is_comfortable, violation_degrees)
        """
        if not occupied:
            upper = self.unoccupied_cooling
            lower = self.unoccupied_heating
        elif 23.0 <= hour or hour < 6.0:  # Night hours
            upper = self.night_cooling
            lower = self.night_heating
        else:
            upper = self.cooling_threshold
            lower = self.heating_threshold

        if temp > upper:
            return False, temp - upper
        elif temp < lower:
            return False, lower - temp
        else:
            return True, 0.0


class HVACEnvironment:
    """
    Complete HVAC simulation environment.

    Orchestrates:
    - Thermal model (physics)
    - Weather generator (outdoor conditions)
    - Occupancy generator (human presence)
    - Sensor simulation (noisy measurements)
    - HVAC plant (heating/cooling system)
    - Data logging (SQLite storage)
    """

    def __init__(
        self,
        season: Season = Season.SUMMER,
        comfort: Optional[ComfortBand] = None,
        room_params: Optional[RoomParameters] = None,
        db_path: str = "data/simulation.db",
        controller_name: str = "unknown",
        seed: int = 42
    ):
        self.season = season
        self.comfort = comfort or ComfortBand()
        self.controller_name = controller_name

        # Initialize components
        self.thermal_model = ThermalModel(params=room_params)
        self.weather = WeatherGenerator(season=season, seed=seed)
        self.occupancy = OccupancyGenerator(max_occupants=2, seed=seed + 1)
        self.dht22 = SimulatedDHT22(seed=seed + 2)
        self.pir = SimulatedPIR(seed=seed + 3)
        self.hvac = HVACPlant()
        self.logger = DataLogger(db_path=db_path)

        # Simulation state
        self.minute = 0
        self.done = False
        self._max_minutes = 7 * 24 * 60  # 7 days default

    def reset(self, initial_temp: float = 23.0, max_days: int = 7) -> dict:
        """
        Reset the environment for a new episode.

        Args:
            initial_temp: Initial indoor temperature (°C).
            max_days:     Simulation duration in days.

        Returns:
            Initial state dictionary.
        """
        self.minute = 0
        self.done = False
        self._max_minutes = max_days * 24 * 60

        self.thermal_model.reset(initial_temp=initial_temp)
        self.hvac.reset()
        self.logger.clear(controller_type=self.controller_name)

        return self._get_state()

    def step(self, action: HVACAction) -> Tuple[dict, float, bool, dict]:
        """
        Advance the simulation by one timestep (1 minute).

        Args:
            action: HVACAction to apply.

        Returns:
            (state, reward, done, info) tuple.
        """
        if self.done:
            raise RuntimeError("Environment is done. Call reset().")

        hour = (self.minute / 60.0) % 24.0
        day = self.minute // 1440
        day_of_year = 180 if self.season == Season.SUMMER else 1

        # 1. Get weather
        T_outdoor, humidity_outdoor = self.weather.get_weather(self.minute)

        # 2. Get occupancy
        occ = self.occupancy.get_occupancy(self.minute)

        # 3. Apply HVAC action → get heat transfer
        Q_hvac = self.hvac.set_action(action, dt_minutes=1.0)

        # 4. Update thermal model
        state = self.thermal_model.step(
            T_outdoor=T_outdoor,
            humidity_outdoor=humidity_outdoor,
            Q_hvac=Q_hvac,
            n_occupants=occ["n_occupants"],
            hour_of_day=hour,
            day_of_year=day_of_year
        )

        # 5. Simulate sensor readings
        dht_reading = self.dht22.read(
            state.temperature, state.humidity, self.minute
        )
        pir_reading = self.pir.read(
            occ["occupied"], occ["motion_detected"], self.minute
        )

        # 6. Compute comfort
        is_comfortable, violation_deg = self.comfort.is_comfortable(
            state.temperature, occ["occupied"], hour
        )

        # 7. Compute reward
        power_kw = self.hvac.current_power_w / 1000.0
        reward = self._compute_reward(power_kw, violation_deg, occ["occupied"])

        # 8. Log data
        hvac_status = self.hvac.get_status()
        self.logger.log({
            "minute": self.minute,
            "hour": round(hour, 2),
            "day": day,
            "temp_indoor": dht_reading["temperature"],
            "temp_outdoor": round(T_outdoor, 2),
            "humidity_indoor": dht_reading["humidity"],
            "humidity_outdoor": round(humidity_outdoor, 2),
            "occupied": int(pir_reading["occupied_estimate"]),
            "n_occupants": occ["n_occupants"],
            "motion_detected": int(pir_reading["motion_detected"]),
            "temp_indoor_true": round(state.temperature, 3),
            "humidity_indoor_true": round(state.humidity, 2),
            "occupied_true": int(occ["occupied"]),
            "hvac_mode": hvac_status["mode"],
            "hvac_stage": hvac_status["stage"],
            "hvac_action": hvac_status["action"],
            "hvac_power_w": hvac_status["power_w"],
            "hvac_thermal_w": hvac_status["thermal_output_w"],
            "protection_active": int(hvac_status["protection_active"]),
            "energy_consumed_kwh": hvac_status["energy_consumed_kwh"],
            "energy_delivered_kwh": hvac_status["energy_delivered_kwh"],
            "in_comfort_zone": int(is_comfortable),
            "comfort_violation_deg": round(violation_deg, 3),
            "pmv_estimate": self._estimate_pmv(state.temperature, state.humidity),
            "controller_type": self.controller_name,
        })

        # 9. Advance time
        self.minute += 1
        self.done = self.minute >= self._max_minutes

        # 10. Build state
        obs = self._get_state()
        info = {
            "T_outdoor": T_outdoor,
            "humidity_outdoor": humidity_outdoor,
            "is_comfortable": is_comfortable,
            "violation_deg": violation_deg,
            "power_kw": power_kw,
            "hvac_status": hvac_status,
            "day": day,
        }

        return obs, reward, self.done, info

    def _get_state(self) -> dict:
        """Build the current observation state dictionary."""
        hour = (self.minute / 60.0) % 24.0
        T_outdoor, humidity_outdoor = self.weather.get_weather(self.minute)
        occ = self.occupancy.get_occupancy(self.minute)

        return {
            "temp_indoor": self.thermal_model.state.temperature,
            "temp_outdoor": T_outdoor,
            "humidity_indoor": self.thermal_model.state.humidity,
            "humidity_outdoor": humidity_outdoor,
            "occupied": occ["occupied"],
            "n_occupants": occ["n_occupants"],
            "hour": hour,
            "minute": self.minute,
            "hvac_mode": self.hvac.mode.value,
            "hvac_stage": self.hvac.stage.name,
            "hvac_action": self.hvac.action.name,
        }

    def _compute_reward(self, power_kw: float, violation_deg: float,
                        occupied: bool) -> float:
        """
        Compute the reward signal for the controller.

        reward = -w_e × power_kw - w_c × violation²

        Comfort violations are penalized more when occupied.
        """
        w_energy = 1.0
        w_comfort = 10.0 if occupied else 2.0  # Less penalty when empty

        energy_penalty = w_energy * power_kw
        comfort_penalty = w_comfort * (violation_deg ** 2)

        return -(energy_penalty + comfort_penalty)

    def _estimate_pmv(self, temp: float, humidity: float) -> float:
        """
        Simplified PMV (Predicted Mean Vote) estimation.

        Uses a linear approximation around the comfort zone.
        PMV scale: -3 (cold) to +3 (hot), 0 = neutral.
        ASHRAE Standard 55: -0.5 to +0.5 is acceptable.
        """
        # Simplified: linear interpolation based on temp
        # Assumes: clothing=0.6 clo, metabolic=1.2 met, air speed=0.1 m/s
        if temp < 20:
            pmv = -0.3 * (20 - temp)
        elif temp > 26:
            pmv = 0.3 * (temp - 26)
        else:
            # Within comfort zone — slight preference for 23°C
            pmv = 0.1 * (temp - 23.0)

        # Humidity correction (high humidity feels hotter)
        if humidity > 60:
            pmv += 0.05 * (humidity - 60) / 10.0

        return round(float(np.clip(pmv, -3.0, 3.0)), 2)

    def finalize(self) -> dict:
        """
        Finalize the simulation and return summary statistics.

        Call this after the simulation loop completes.
        """
        self.logger.flush()
        summary = self.logger.get_energy_summary(self.controller_name)
        summary["controller"] = self.controller_name
        summary["season"] = self.season.value
        summary["duration_days"] = self._max_minutes / 1440
        return summary

    def close(self):
        """Clean up resources."""
        self.logger.close()
