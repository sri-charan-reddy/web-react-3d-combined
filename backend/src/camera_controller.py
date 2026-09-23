"""Virtual Camera Pan/Tilt Movement Controller for Part 2.

This module provides:
- Closed-loop pan/tilt visual servoing controller for the VirtualCamera.
- Target acquisition and tracking based exclusively on Kalman tracker state (TrackingResult).
- Continuous predictive camera pointing during optical occlusions (coasting on prediction).
- Bounded local search scanning when track enters SEARCHING state.
- Proportional error control with configurable maximum pan/tilt slew rates and deadband.
- Safe holding behavior when tracking is LOST or UNINITIALIZED.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

from config import CameraControllerConfig
from src.tracking_state import TrackingResult, TrackingState
from src.virtual_camera import VirtualCamera


class ControllerMode(Enum):
    """Operational mode of the camera pan/tilt movement controller."""
    IDLE = auto()              # Tracker uninitialized; camera stationary
    TRACKING_SERVO = auto()    # Actively centering camera on confirmed Kalman track
    PREDICTIVE_SERVO = auto()  # Moving camera along Kalman predicted position during short occlusion
    SEARCH_SERVO = auto()      # Scanning camera along bounded local search waypoints around prediction
    HOLDING = auto()           # Target LOST or within deadband; holding current orientation


@dataclass
class ControllerTelemetry:
    """Snapshot of camera controller telemetry and pointing error."""
    mode: ControllerMode
    error_x: float             # Horizontal error (target_x - center_x) in pixels
    error_y: float             # Vertical error (target_y - center_y) in pixels
    cmd_velocity_pan: float    # Commanded pan velocity in pixels/second
    cmd_velocity_tilt: float   # Commanded tilt velocity in pixels/second
    delta_pan: float           # Applied pan displacement in current frame
    delta_tilt: float          # Applied tilt displacement in current frame
    in_deadband: bool          # True if error is within deadband threshold


class CameraController:
    """Pan/Tilt motion controller driving VirtualCamera to track, predict, and scan."""

    def __init__(
        self,
        camera: VirtualCamera,
        config: Optional[CameraControllerConfig] = None
    ) -> None:
        """Initialize camera controller with target camera and tuning parameters.
        
        Args:
            camera: VirtualCamera instance to control.
            config: CameraControllerConfig tuning parameters.
        """
        self.camera = camera
        self.config = config or CameraControllerConfig()
        
        self.mode: ControllerMode = ControllerMode.IDLE
        self.last_error_x: float = 0.0
        self.last_error_y: float = 0.0
        self.last_cmd_vx: float = 0.0
        self.last_cmd_vy: float = 0.0
        self.last_delta_pan: float = 0.0
        self.last_delta_tilt: float = 0.0
        self.in_deadband: bool = False

    def update(
        self,
        tracking_result: TrackingResult,
        dt: float = 1.0 / 30.0,
        target_override: Optional[Tuple[float, float]] = None
    ) -> Tuple[float, float]:
        """Compute pointing error and execute smooth pan/tilt motion step.
        
        Algorithm:
        1. Evaluate operational mode from tracking state:
           - UNINITIALIZED -> IDLE (no movement)
           - LOST -> HOLDING (safe stop / hold orientation)
           - SEARCHING -> SEARCH_SERVO (slew toward local search scanning waypoint)
           - PREDICTING -> PREDICTIVE_SERVO (if enabled, follow Kalman prediction)
           - TRACKING / REACQUIRING -> TRACKING_SERVO (center on Kalman track)
        2. Calculate pointing error: error = target - camera_center.
        3. Apply deadband threshold (active in TRACKING/PREDICTING mode).
        4. Calculate proportional velocity: v_cmd = Kp * error.
        5. Clamp velocity to configured max_pan_speed and max_tilt_speed.
        6. Apply displacement delta = v_cmd * dt to camera.
        
        Args:
            tracking_result: Current TrackingResult from KalmanBeaconTracker.
            dt: Frame time delta in seconds.
            target_override: Optional waypoint target (e.g. from LocalSearch module).
            
        Returns:
            Tuple of (delta_pan, delta_tilt) applied in pixels.
        """
        state = tracking_result.state
        
        # 1. Evaluate operational mode and select target coordinates
        if state == TrackingState.UNINITIALIZED:
            self.mode = ControllerMode.IDLE
            self._reset_telemetry()
            return (0.0, 0.0)

        if state == TrackingState.LOST:
            self.mode = ControllerMode.HOLDING
            self._reset_telemetry()
            return (0.0, 0.0)

        if state == TrackingState.SEARCHING:
            self.mode = ControllerMode.SEARCH_SERVO
            target_x, target_y = target_override if target_override is not None else tracking_result.position
        elif state == TrackingState.PREDICTING:
            if self.config.enable_predictive_servo:
                self.mode = ControllerMode.PREDICTIVE_SERVO
                target_x, target_y = tracking_result.position
            else:
                self.mode = ControllerMode.HOLDING
                self._reset_telemetry()
                return (0.0, 0.0)
        else:
            self.mode = ControllerMode.TRACKING_SERVO
            target_x, target_y = tracking_result.position

        # 2. Compute pointing error relative to optical center
        cam_x, cam_y = self.camera.center
        
        error_x = target_x - cam_x
        error_y = target_y - cam_y
        self.last_error_x = error_x
        self.last_error_y = error_y

        # 3. Deadband check (only applied in TRACKING_SERVO to avoid micro-jitter)
        deadband = self.config.deadband_px if self.mode == ControllerMode.TRACKING_SERVO else 0.0
        eff_err_x = 0.0 if abs(error_x) < deadband else error_x
        eff_err_y = 0.0 if abs(error_y) < deadband else error_y
        self.in_deadband = (abs(error_x) < deadband) and (abs(error_y) < deadband) if deadband > 0 else False

        if self.in_deadband:
            self.mode = ControllerMode.HOLDING
            self.last_cmd_vx = 0.0
            self.last_cmd_vy = 0.0
            self.last_delta_pan = 0.0
            self.last_delta_tilt = 0.0
            return (0.0, 0.0)

        # 4. Proportional control
        cmd_vx = self.config.kp_pan * eff_err_x
        cmd_vy = self.config.kp_tilt * eff_err_y

        # 5. Velocity limits clamping (pixels/sec)
        max_vx = self.config.max_pan_speed
        max_vy = self.config.max_tilt_speed
        
        cmd_vx = max(-max_vx, min(max_vx, cmd_vx))
        cmd_vy = max(-max_vy, min(max_vy, cmd_vy))
        
        self.last_cmd_vx = cmd_vx
        self.last_cmd_vy = cmd_vy

        # 6. Compute incremental displacement and apply to camera
        delta_pan = cmd_vx * dt
        delta_tilt = cmd_vy * dt
        
        self.camera.move_pan_tilt(delta_pan, delta_tilt)
        
        self.last_delta_pan = delta_pan
        self.last_delta_tilt = delta_tilt
        
        return (delta_pan, delta_tilt)

    def _reset_telemetry(self) -> None:
        """Reset velocity and displacement telemetry."""
        self.last_error_x = 0.0
        self.last_error_y = 0.0
        self.last_cmd_vx = 0.0
        self.last_cmd_vy = 0.0
        self.last_delta_pan = 0.0
        self.last_delta_tilt = 0.0
        self.in_deadband = False

    def get_telemetry(self) -> ControllerTelemetry:
        """Retrieve current camera controller telemetry snapshot.
        
        Returns:
            ControllerTelemetry instance.
        """
        return ControllerTelemetry(
            mode=self.mode,
            error_x=self.last_error_x,
            error_y=self.last_error_y,
            cmd_velocity_pan=self.last_cmd_vx,
            cmd_velocity_tilt=self.last_cmd_vy,
            delta_pan=self.last_delta_pan,
            delta_tilt=self.last_delta_tilt,
            in_deadband=self.in_deadband
        )

    def reset(self) -> None:
        """Reset controller state."""
        self.mode = ControllerMode.IDLE
        self._reset_telemetry()
