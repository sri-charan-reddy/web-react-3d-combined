"""Finite State Machine state definitions for Part 4 Autonomous FSOC Orchestrator."""

from enum import Enum, auto


class SystemState(Enum):
    """Operational states for the autonomous FSOC recovery and tracking system."""
    IDLE = auto()
    OPTICAL_SEARCH = auto()
    OPTICAL_TRACKING = auto()
    PREDICTIVE_RECOVERY = auto()
    LOCAL_REACQUISITION = auto()
    RF_DISCOVERY = auto()
    RF_AUTHENTICATION = auto()
    RF_DIRECTION_RECOVERY = auto()
    OPTICAL_REACQUISITION = auto()
    FINE_ALIGNMENT = auto()
    FSOC_ACTIVE = auto()
    RECOVERY_FAILED = auto()

    def __str__(self) -> str:
        return self.name
