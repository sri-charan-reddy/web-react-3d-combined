"""Configuration settings for Part 2: Predictive Tracking & Disturbance Handling.

This module defines all tunable parameters for:
- Beacon Motion Simulation (initial coordinates, velocity, boundary margins, random seed)
- Disturbance & Occlusion Simulation (noise std, jitter std, occlusion intervals, outliers, FOV dependency)
- Virtual Camera Model (center/pan/tilt, FOV width/height, arena boundaries)
- Camera Pan/Tilt Controller (speeds, proportional gains, deadband, predictive servoing)
- Local Search Scanner (search start threshold, search radius, step size, hold duration)
- Tracking State Machine & Gating (gating threshold, max prediction frames, confidence dynamics)
- Kalman Filter (process & measurement noise, covariance matrices)
- Visualizer & Demonstration settings (window size, frame rates, color schemes)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class BeaconSimConfig:
    """Ground-truth beacon motion simulation parameters."""
    arena_width: int = 1280
    arena_height: int = 720
    # Starts beacon offset from camera center (640, 360) inside initial FOV to demonstrate pan/tilt acquisition
    start_pos: Tuple[float, float] = (750.0, 360.0)
    start_velocity: Tuple[float, float] = (2.5, 1.0)   # pixels per frame
    speed_magnitude: float = 2.8                       # nominal speed in pixels per frame
    heading_noise_std: float = 0.04                    # slight steering / trajectory perturbation per frame (rad)
    margin: float = 50.0                               # boundary safety margin to trigger smooth bounce / turn
    random_seed: Optional[int] = 42                    # seed for reproducible ground truth motion


from enum import Enum


class TurbulenceLevel(Enum):
    """Atmospheric turbulence severity levels."""
    OFF = "OFF"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class AtmosphericTurbulenceConfig:
    """Configuration parameters for atmospheric optical turbulence simulation."""
    enabled: bool = True
    level: TurbulenceLevel = TurbulenceLevel.MEDIUM
    temporal_correlation: float = 0.88   # Autoregressive correlation coefficient rho in [0, 1)
    
    # 1D Standard deviation of position perturbation for each level (pixels)
    std_low: float = 3.0
    std_medium: float = 6.5
    std_high: float = 14.0
    
    # Maximum allowable displacement envelope limits (pixels)
    max_displacement_low: float = 8.0
    max_displacement_medium: float = 18.0
    max_displacement_high: float = 35.0
    
    # Scintillation / intensity fluctuation settings
    enable_scintillation: bool = True
    scintillation_std: float = 0.08      # Standard deviation of normalized intensity fluctuation
    
    # Deterministic random seed
    random_seed: Optional[int] = 202


@dataclass
class DisturbanceConfig:
    """Disturbance, measurement noise, and occlusion simulation parameters."""
    enable_measurement_noise: bool = True
    measurement_noise_std: float = 4.0                 # Standard deviation of optical measurement noise (pixels)
    enable_jitter: bool = True
    jitter_std: float = 1.0                            # High-frequency camera jitter noise (pixels)
    turbulence: AtmosphericTurbulenceConfig = field(default_factory=AtmosphericTurbulenceConfig)
    enable_occlusions: bool = True
    # Demonstrates Scenario B (short loss: 60..80), Scenario C (extended loss: 150..195 triggering local search)
    occlusion_intervals: List[Tuple[int, int]] = field(
        default_factory=lambda: [(60, 80), (150, 195)]
    )
    # Demonstrates Scenario D (far-away false detection spikes / outliers)
    enable_outliers: bool = True
    outlier_events: List[Tuple[int, Tuple[float, float]]] = field(
        default_factory=lambda: [(290, (1100.0, 100.0)), (291, (1100.0, 100.0))]
    )
    require_fov_for_detection: bool = True             # When True, beacon must be within VirtualCamera FOV to be detected
    default_confidence: float = 0.95                   # Confidence assigned to valid detections
    random_seed: Optional[int] = 101                   # seed for reproducible disturbance / noise generation


@dataclass
class VirtualCameraConfig:
    """Virtual camera field-of-view and pointing parameters."""
    arena_width: int = 1280
    arena_height: int = 720
    initial_center: Tuple[float, float] = (640.0, 360.0)
    fov_width: float = 500.0                           # Horizontal FOV in world pixels
    fov_height: float = 380.0                          # Vertical FOV in world pixels
    min_pan: float = 0.0                               # Minimum pan limit in world pixels
    max_pan: float = 1280.0                            # Maximum pan limit in world pixels
    min_tilt: float = 0.0                              # Minimum tilt limit in world pixels
    max_tilt: float = 720.0                            # Maximum tilt limit in world pixels


@dataclass
class CameraControllerConfig:
    """Pan/Tilt camera movement controller tuning parameters."""
    max_pan_speed: float = 240.0                       # Maximum pan velocity in pixels per second
    max_tilt_speed: float = 240.0                      # Maximum tilt velocity in pixels per second
    kp_pan: float = 3.0                                # Proportional gain for pan axis (1/s)
    kp_tilt: float = 3.0                               # Proportional gain for tilt axis (1/s)
    deadband_px: float = 2.5                           # Deadband tolerance in pixels (suppresses micro-jitter)
    enable_predictive_servo: bool = True               # Follow Kalman prediction during PREDICTING state
    stop_on_lost: bool = True                          # Hold orientation when tracking state is LOST


@dataclass
class LocalSearchConfig:
    """Bounded local search pattern and scanning parameters."""
    search_start_frames: int = 15                      # Consecutive miss frames before triggering local search (PREDICTING -> SEARCHING)
    search_radius_px: float = 140.0                    # Bounded search radius around Kalman prediction (pixels)
    step_size_px: float = 45.0                         # Distance step between scan waypoints (pixels)
    hold_frames_per_step: int = 4                      # Number of frames to hold each search waypoint
    max_prediction_frames: int = 55                    # Total miss limit before declaring track LOST


@dataclass
class KalmanConfig:
    """Kalman filter tuning parameters."""
    dt: float = 1.0 / 30.0                             # Nominal time step (30 FPS)
    process_noise_std_pos: float = 0.5                 # Standard deviation of position process noise
    process_noise_std_vel: float = 1.0                 # Standard deviation of velocity process noise
    measurement_noise_std: float = 4.0                 # Standard deviation of optical measurement noise (pixels)
    initial_covariance_pos: float = 10.0               # Initial position uncertainty
    initial_covariance_vel: float = 100.0              # Initial velocity uncertainty


@dataclass
class TrackingStateConfig:
    """State machine, confidence dynamics, and outlier rejection gating parameters."""
    gating_threshold_px: float = 85.0                  # Max distance between prediction and measurement to accept (pixels)
    search_start_frames: int = 15                      # Miss frames to transition from PREDICTING to SEARCHING
    max_prediction_frames: int = 55                    # Max consecutive frames in (PREDICTING + SEARCHING) before LOST
    confidence_decay_rate: float = 0.02                # Per-frame confidence decay during missing/rejected detections
    confidence_recovery_rate: float = 0.15             # Confidence recovery boost per accepted valid measurement
    min_confidence: float = 0.05                       # Minimum floor for tracking confidence
    max_confidence: float = 1.0                        # Maximum ceiling for tracking confidence


@dataclass
class VisualizerConfig:
    """Visualization window and overlay styling."""
    window_name: str = "SIH Part 2 - Predictive Tracking & Local Search"
    canvas_width: int = 1280
    canvas_height: int = 720
    fps: int = 30
    trail_length: int = 80                             # Number of historical points to display
    show_ground_truth: bool = True
    show_measurements: bool = True
    show_camera_fov: bool = True                       # Display virtual camera FOV rectangle and crosshair
    show_local_search: bool = True                     # Display local search radius and current search target


@dataclass
class SystemConfig:
    """Global system configuration aggregating all component configurations."""
    beacon: BeaconSimConfig = field(default_factory=BeaconSimConfig)
    disturbance: DisturbanceConfig = field(default_factory=DisturbanceConfig)
    camera: VirtualCameraConfig = field(default_factory=VirtualCameraConfig)
    controller: CameraControllerConfig = field(default_factory=CameraControllerConfig)
    search: LocalSearchConfig = field(default_factory=LocalSearchConfig)
    kalman: KalmanConfig = field(default_factory=KalmanConfig)
    tracking: TrackingStateConfig = field(default_factory=TrackingStateConfig)
    visualizer: VisualizerConfig = field(default_factory=VisualizerConfig)


# Default system configuration instance
DEFAULT_CONFIG = SystemConfig()
