"""
Base Controller — Abstract Interface
=====================================

Defines the interface that all HVAC controllers must implement.
Separates the control strategy from the simulation environment.
"""

from abc import ABC, abstractmethod
from simulation.hvac_plant import HVACAction


class BaseController(ABC):
    """
    Abstract base class for HVAC controllers.

    All controllers must implement:
        - compute_action(state) → HVACAction
        - reset()

    Optional:
        - update(state, action, reward, next_state) — for learning controllers
        - get_stats() — controller-specific statistics
    """

    def __init__(self, name: str = "base"):
        self.name = name
        self._total_actions = 0
        self._action_counts = {a.name: 0 for a in HVACAction}

    @abstractmethod
    def compute_action(self, state: dict) -> HVACAction:
        """
        Compute the HVAC action given the current state.

        Args:
            state: Dictionary with keys:
                - temp_indoor (float): Indoor temperature (°C)
                - temp_outdoor (float): Outdoor temperature (°C)
                - humidity_indoor (float): Indoor humidity (%)
                - occupied (bool): Occupancy state
                - n_occupants (int): Number of occupants
                - hour (float): Hour of day (0–24)
                - hvac_mode (str): Current HVAC mode
                - hvac_stage (str): Current HVAC stage
                - hvac_action (str): Current HVAC action name

        Returns:
            HVACAction to apply.
        """
        pass

    def update(self, state: dict, action: HVACAction, reward: float,
               next_state: dict, done: bool) -> None:
        """
        Update the controller after taking an action (for learning controllers).

        Default implementation does nothing (stateless controllers).
        """
        pass

    def reset(self) -> None:
        """Reset the controller state for a new episode."""
        self._total_actions = 0
        self._action_counts = {a.name: 0 for a in HVACAction}

    def _record_action(self, action: HVACAction) -> None:
        """Record an action for statistics tracking."""
        self._total_actions += 1
        self._action_counts[action.name] += 1

    def get_stats(self) -> dict:
        """Get controller statistics."""
        return {
            "name": self.name,
            "total_actions": self._total_actions,
            "action_distribution": {
                k: v / max(self._total_actions, 1)
                for k, v in self._action_counts.items()
            }
        }
