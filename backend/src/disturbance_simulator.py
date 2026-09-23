"""Disturbance, measurement noise, and occlusion simulator for Part 2.

This module provides:
- Camera measurement noise injection (zero-mean Gaussian noise on x and y).
- High-frequency camera jitter disturbance simulation.
- Configurable temporary detection loss / occlusion schedules.
- Configurable false-positive outlier measurement injection (e.g. far-away optical false lock).
- Clean optical measurement generation matching the Part 1 -> Part 2 interface contract.
"""

from typing import List, Optional, Tuple
import numpy as np

from config import DisturbanceConfig
from src.atmospheric_turbulence import AtmosphericTurbulence
from src.tracking_state import BeaconMeasurement
from src.virtual_camera import VirtualCamera


class DisturbanceSimulator:
    """Simulates optical measurement noise, sensor jitter, atmospheric turbulence, temporary loss, and outliers."""

    def __init__(self, config: Optional[DisturbanceConfig] = None) -> None:
        """Initialize disturbance, occlusion, turbulence, and outlier parameters.
        
        Args:
            config: Disturbance configuration settings.
        """
        self.config = config or DisturbanceConfig()
        self.rng = np.random.RandomState(self.config.random_seed)
        self.turbulence = AtmosphericTurbulence(getattr(self.config, "turbulence", None))
        self.current_frame: int = 0
        self.manual_outlier_remaining_frames: int = 0
        self.manual_outlier_pos: Tuple[float, float] = (1100.0, 100.0)

    def is_occluded(self, frame_idx: int) -> bool:
        """Check if the beacon detection is currently lost/occluded for the given frame index.
        
        Args:
            frame_idx: Current simulation frame number.
            
        Returns:
            True if detection is lost during this frame, False otherwise.
        """
        if not self.config.enable_occlusions:
            return False
        for start_f, end_f in self.config.occlusion_intervals:
            if start_f <= frame_idx <= end_f:
                return True
        return False

    def get_configured_outlier(self, frame_idx: int) -> Optional[Tuple[float, float]]:
        """Check if a false-positive outlier measurement is active for this frame.
        
        Args:
            frame_idx: Current frame index.
            
        Returns:
            False outlier coordinates (x, y) if active, else None.
        """
        # 1. Check persistent manual outlier (active for duration_frames)
        if self.manual_outlier_remaining_frames > 0:
            self.manual_outlier_remaining_frames -= 1
            return self.manual_outlier_pos

        # 2. Check scheduled config outliers
        if not self.config.enable_outliers:
            return None
        for f_idx, out_pos in self.config.outlier_events:
            if f_idx == frame_idx:
                return out_pos
        return None

    def trigger_manual_outlier(
        self,
        outlier_pos: Tuple[float, float] = (1100.0, 100.0),
        duration_frames: int = 60
    ) -> None:
        """Trigger a manual false-detection outlier that persists for duration_frames.
        
        Args:
            outlier_pos: Deliberately wrong/far (x, y) coordinate to inject.
            duration_frames: Number of consecutive frames to keep outlier active (default 60).
        """
        self.manual_outlier_pos = outlier_pos
        self.manual_outlier_remaining_frames = duration_frames

    def add_measurement_noise(self, optical_pos: Tuple[float, float]) -> Tuple[float, float]:
        """Add Gaussian sensor noise and camera jitter to the optical position.
        
        Args:
            optical_pos: (x, y) beacon coordinates after atmospheric propagation.
            
        Returns:
            Noisy (x, y) coordinates representing optical detection.
        """
        meas_x, meas_y = optical_pos[0], optical_pos[1]

        # 1. Optical sensor measurement noise
        if self.config.enable_measurement_noise and self.config.measurement_noise_std > 0:
            noise = self.rng.normal(0.0, self.config.measurement_noise_std, size=2)
            meas_x += float(noise[0])
            meas_y += float(noise[1])

        # 2. Camera mechanical jitter noise
        if self.config.enable_jitter and self.config.jitter_std > 0:
            jitter = self.rng.normal(0.0, self.config.jitter_std, size=2)
            meas_x += float(jitter[0])
            meas_y += float(jitter[1])

        return (meas_x, meas_y)

    def apply_disturbances(
        self,
        ground_truth_pos: Tuple[float, float],
        timestamp: float,
        frame_idx: int,
        camera: Optional[VirtualCamera] = None
    ) -> BeaconMeasurement:
        """Produce an optical BeaconMeasurement from ground-truth position.
        
        Evaluates outliers, occlusions, virtual camera FOV visibility,
        atmospheric turbulence, and Gaussian measurement noise.
        Ground truth is passed by value and is never altered.
        
        Args:
            ground_truth_pos: True (x, y) beacon position.
            timestamp: Timestamp in seconds.
            frame_idx: Current simulation frame number.
            camera: Optional VirtualCamera instance to enforce FOV visibility.
            
        Returns:
            BeaconMeasurement data structure.
        """
        self.current_frame = frame_idx

        # 1. Check for active manual or scheduled outlier detection spike
        outlier = self.get_configured_outlier(frame_idx)
        if outlier is not None:
            return BeaconMeasurement(
                timestamp=timestamp,
                position=outlier,
                detected=True,
                confidence=0.85,
                raw_bbox=None
            )

        # 2. Check for optical occlusion (detection loss)
        if self.is_occluded(frame_idx):
            return BeaconMeasurement(
                timestamp=timestamp,
                position=None,
                detected=False,
                confidence=0.0,
                raw_bbox=None
            )

        # 3. Check Virtual Camera FOV visibility (beacon must be within camera FOV)
        if getattr(self.config, "require_fov_for_detection", True) and camera is not None:
            if not camera.is_in_fov(ground_truth_pos):
                return BeaconMeasurement(
                    timestamp=timestamp,
                    position=None,
                    detected=False,
                    confidence=0.0,
                    raw_bbox=None
                )

        # 4. Step A: Optical observation undergoes atmospheric turbulence
        turb_pos = self.turbulence.apply(ground_truth_pos)

        # 5. Step B: Sensor noise & camera jitter
        noisy_pos = self.add_measurement_noise(turb_pos)

        # 6. Step C: Scintillation effect on detection confidence
        conf = float(np.clip(self.config.default_confidence * self.turbulence.scintillation_factor, 0.1, 1.0))

        return BeaconMeasurement(
            timestamp=timestamp,
            position=noisy_pos,
            detected=True,
            confidence=conf,
            raw_bbox=None
        )

    def reset(self) -> None:
        """Reset the disturbance simulator, turbulence model, and internal RNG."""
        self.rng = np.random.RandomState(self.config.random_seed)
        self.turbulence.reset()
        self.current_frame = 0
        self.manual_outlier_remaining_frames = 0

