"""Virtual Camera Model for Part 2 (Predictive Tracking & Disturbance Handling).

This module provides:
- VirtualCamera representation with 2D pointing center (pan, tilt) in the world environment.
- Configurable Field of View (horizontal FOV, vertical FOV) and arena boundary constraints.
- Detection of whether a beacon / world point is within the current FOV.
- Relative position error computation from the optical axis (camera center).
- Bi-directional coordinate transformations:
    * World coordinates -> Camera sensor coordinates [0, fov_w] x [0, fov_h]
    * Camera sensor coordinates -> World coordinates
- Prepared interface for future pan/tilt steering and coarse-alignment controllers.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from config import VirtualCameraConfig


@dataclass
class CameraTelemetry:
    """Snapshot of virtual camera state and relative beacon observations."""
    center: Tuple[float, float]
    pan: float
    tilt: float
    fov_width: float
    fov_height: float
    fov_bounds: Tuple[float, float, float, float]  # (min_x, max_x, min_y, max_y)
    is_beacon_in_fov: bool
    relative_error: Optional[Tuple[float, float]] = None  # (dx, dy) from center


class VirtualCamera:
    """Virtual 2D camera model with pan/tilt pointing and limited Field of View (FOV)."""

    def __init__(self, config: Optional[VirtualCameraConfig] = None) -> None:
        """Initialize virtual camera with configured FOV and pointing center.
        
        Args:
            config: VirtualCameraConfig instance with FOV and arena dimensions.
        """
        self.config = config or VirtualCameraConfig()
        
        self.arena_width: float = float(self.config.arena_width)
        self.arena_height: float = float(self.config.arena_height)
        self.fov_width: float = float(self.config.fov_width)
        self.fov_height: float = float(self.config.fov_height)
        
        # Center pointing position in world coordinates (pan = center_x, tilt = center_y)
        self._center_x: float = float(self.config.initial_center[0])
        self._center_y: float = float(self.config.initial_center[1])
        
        # Clamp initial center to valid arena bounds
        self._clamp_center()

    def _clamp_center(self) -> None:
        """Keep camera center within configured pan/tilt limits."""
        self._center_x = max(self.config.min_pan, min(self.config.max_pan, self._center_x))
        self._center_y = max(self.config.min_tilt, min(self.config.max_tilt, self._center_y))

    @property
    def center(self) -> Tuple[float, float]:
        """Current optical center (center_x, center_y) in world coordinates."""
        return (self._center_x, self._center_y)

    @property
    def pan(self) -> float:
        """Current horizontal pan position (optical center X in world space)."""
        return self._center_x

    @property
    def tilt(self) -> float:
        """Current vertical tilt position (optical center Y in world space)."""
        return self._center_y

    def set_center(self, center_x: float, center_y: float) -> None:
        """Set camera pointing center directly in world coordinates.
        
        Args:
            center_x: New X center in world pixels.
            center_y: New Y center in world pixels.
        """
        self._center_x = float(center_x)
        self._center_y = float(center_y)
        self._clamp_center()

    def set_pan_tilt(self, pan: float, tilt: float) -> None:
        """Set camera pan and tilt positions.
        
        Args:
            pan: Horizontal pan position.
            tilt: Vertical tilt position.
        """
        self.set_center(pan, tilt)

    def move_pan_tilt(self, delta_pan: float, delta_tilt: float) -> None:
        """Apply incremental pan/tilt motion command.
        
        Args:
            delta_pan: Relative change in pan (pixels).
            delta_tilt: Relative change in tilt (pixels).
        """
        self._center_x += float(delta_pan)
        self._center_y += float(delta_tilt)
        self._clamp_center()

    def set_fov(self, fov_width: float, fov_height: float) -> None:
        """Adjust horizontal and vertical FOV dimensions.
        
        Args:
            fov_width: Horizontal FOV in world pixels.
            fov_height: Vertical FOV in world pixels.
        """
        self.fov_width = max(10.0, float(fov_width))
        self.fov_height = max(10.0, float(fov_height))

    def get_fov_bounds(self) -> Tuple[float, float, float, float]:
        """Compute the world-coordinate rectangular bounding box of the camera FOV.
        
        Returns:
            Tuple of (min_x, max_x, min_y, max_y) in world coordinates.
        """
        half_w = self.fov_width / 2.0
        half_h = self.fov_height / 2.0
        return (
            self._center_x - half_w,
            self._center_x + half_w,
            self._center_y - half_h,
            self._center_y + half_h
        )

    def is_in_fov(self, world_pos: Tuple[float, float]) -> bool:
        """Check if a given world position is inside the camera FOV.
        
        Args:
            world_pos: (x, y) coordinates in world frame.
            
        Returns:
            True if world_pos lies within [min_x, max_x] and [min_y, max_y], False otherwise.
        """
        min_x, max_x, min_y, max_y = self.get_fov_bounds()
        wx, wy = world_pos[0], world_pos[1]
        return (min_x <= wx <= max_x) and (min_y <= wy <= max_y)

    def get_relative_position(self, world_pos: Tuple[float, float]) -> Tuple[float, float]:
        """Calculate relative beacon error vector from optical axis / camera center.
        
        Args:
            world_pos: (x, y) coordinates in world frame.
            
        Returns:
            Tuple of (dx, dy) where dx = world_x - center_x, dy = world_y - center_y.
        """
        return (world_pos[0] - self._center_x, world_pos[1] - self._center_y)

    def world_to_camera(self, world_pos: Tuple[float, float]) -> Tuple[float, float]:
        """Convert world coordinates (wx, wy) into local camera sensor image coordinates (cx, cy).
        
        In camera sensor coordinates, the top-left of the camera FOV is (0, 0),
        and the bottom-right is (fov_width, fov_height).
        
        Args:
            world_pos: (wx, wy) coordinates in world space.
            
        Returns:
            Tuple of (cam_x, cam_y) in camera sensor image coordinates.
        """
        min_x, _, min_y, _ = self.get_fov_bounds()
        cam_x = world_pos[0] - min_x
        cam_y = world_pos[1] - min_y
        return (cam_x, cam_y)

    def camera_to_world(self, camera_pos: Tuple[float, float]) -> Tuple[float, float]:
        """Convert local camera sensor coordinates (cx, cy) back into world coordinates (wx, wy).
        
        Args:
            camera_pos: (cam_x, cam_y) in camera frame.
            
        Returns:
            Tuple of (world_x, world_y) in world space.
        """
        min_x, _, min_y, _ = self.get_fov_bounds()
        world_x = min_x + camera_pos[0]
        world_y = min_y + camera_pos[1]
        return (world_x, world_y)

    def get_telemetry(self, world_beacon_pos: Optional[Tuple[float, float]] = None) -> CameraTelemetry:
        """Retrieve complete camera telemetry and relative observation of the beacon.
        
        Args:
            world_beacon_pos: Optional world beacon position to evaluate visibility and relative error.
            
        Returns:
            CameraTelemetry instance.
        """
        bounds = self.get_fov_bounds()
        in_fov = False
        rel_err = None
        
        if world_beacon_pos is not None:
            in_fov = self.is_in_fov(world_beacon_pos)
            rel_err = self.get_relative_position(world_beacon_pos)
            
        return CameraTelemetry(
            center=self.center,
            pan=self.pan,
            tilt=self.tilt,
            fov_width=self.fov_width,
            fov_height=self.fov_height,
            fov_bounds=bounds,
            is_beacon_in_fov=in_fov,
            relative_error=rel_err
        )

    def reset(self) -> None:
        """Reset camera center to initial configured position."""
        self._center_x = float(self.config.initial_center[0])
        self._center_y = float(self.config.initial_center[1])
        self.fov_width = float(self.config.fov_width)
        self.fov_height = float(self.config.fov_height)
        self._clamp_center()
