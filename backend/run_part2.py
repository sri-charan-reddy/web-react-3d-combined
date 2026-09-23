"""Part 2: Predictive Tracking, Turbulence Simulation & Camera Control Launcher.

Coordinates:
- BeaconSimulator & Ground Truth Motion
- DisturbanceSimulator & Atmospheric Turbulence
- VirtualCamera Model & FOV
- CameraController (Closed-loop Pan/Tilt)
- KalmanBeaconTracker (Predictive Tracking & Outlier Rejection)
- LocalSearch (Bounded Reacquisition)
- TrackingVisualizer (Live OpenCV HUD)

Usage:
    python run_part2.py
"""

from config import DEFAULT_CONFIG, SystemConfig
from main import run_demonstration

if __name__ == "__main__":
    run_demonstration(DEFAULT_CONFIG)
