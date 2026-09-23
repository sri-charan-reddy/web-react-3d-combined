"""FSOC PAT System Package.

Contains modules for:
- Part 1: Virtual FSOC PAT Environment, Classical Optical Detection, and Coarse Alignment
- Part 2: Kalman Predictive Tracking, Disturbance Simulation, and Local Reacquisition
- Part 3: RF-Assisted Discovery, Identification, and HMAC Authentication
- Part 4: Autonomous Adaptive Recovery & Complete Integration Orchestrator
"""

__version__ = "1.0.0"

# Part 4 Exports
from src.orchestrator import (
    SystemState,
    SystemTelemetry,
    FSOCRecoveryOrchestrator,
)

# Part 2 Exports
from src.tracking_state import (
    TrackingState,
    BeaconMeasurement,
    TrackingResult,
    PerformanceMetrics,
    PerformanceTracker
)
from src.atmospheric_turbulence import (
    AtmosphericTurbulence,
    TurbulenceLevel,
    AtmosphericTurbulenceConfig,
    TurbulenceTelemetry
)
from src.kalman_tracker import KalmanBeaconTracker
from src.beacon_simulator import BeaconSimulator
from src.disturbance_simulator import DisturbanceSimulator
from src.virtual_camera import VirtualCamera, CameraTelemetry
from src.camera_controller import CameraController, ControllerMode, ControllerTelemetry
from src.local_search import LocalSearch, LocalSearchTelemetry
from src.visualizer import TrackingVisualizer

__all__ = [
    "__version__",
    "SystemState",
    "SystemTelemetry",
    "FSOCRecoveryOrchestrator",
    "TrackingState",
    "BeaconMeasurement",
    "TrackingResult",
    "PerformanceMetrics",
    "PerformanceTracker",
    "AtmosphericTurbulence",
    "TurbulenceLevel",
    "AtmosphericTurbulenceConfig",
    "TurbulenceTelemetry",
    "KalmanBeaconTracker",
    "BeaconSimulator",
    "DisturbanceSimulator",
    "VirtualCamera",
    "CameraTelemetry",
    "CameraController",
    "ControllerMode",
    "ControllerTelemetry",
    "LocalSearch",
    "LocalSearchTelemetry",
    "TrackingVisualizer",
]
