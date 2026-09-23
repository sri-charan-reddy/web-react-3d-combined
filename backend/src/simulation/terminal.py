"""FSOC Terminal and Virtual Camera models.

Angle Convention:
- Screen coordinates: (0,0) at top-left, +X right, +Y down.
- Orientation angle 0.0 deg points horizontally right along +X axis towards Remote Terminal.
- Angle increases clockwise in screen space (0° = Right, 90° = Down, -90° = Up, 180° = Left).
"""

import math
from typing import Tuple, List, Optional, Dict, Any
import numpy as np

from .beacon import OpticalBeacon


class VirtualCamera:
    """Represents an optical acquisition and tracking camera attached to an FSOC terminal.
    
    Attributes:
        x (float): Horizontal sensor position on canvas.
        y (float): Vertical sensor position on canvas.
        orientation_deg (float): Pointing direction angle in degrees (0° = right).
        fov_deg (float): Total angular Field of View spread in degrees.
        image_width (int): Sensor image resolution width in pixels (e.g. 1280).
        image_height (int): Sensor image resolution height in pixels (e.g. 720).
    """

    def __init__(
        self,
        x: float,
        y: float,
        orientation_deg: float = 0.0,
        fov_deg: float = 35.0,
        image_width: int = 1280,
        image_height: int = 720
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.orientation_deg = float(orientation_deg)
        self.fov_deg = float(fov_deg)
        self.image_width = int(image_width)
        self.image_height = int(image_height)

    @property
    def position(self) -> Tuple[float, float]:
        """Returns camera position (x, y)."""
        return (self.x, self.y)

    @position.setter
    def position(self, pos: Tuple[float, float]) -> None:
        """Sets camera position (x, y)."""
        self.x, self.y = float(pos[0]), float(pos[1])

    def get_fov_boundary_rays(
        self, fov_range_px: float
    ) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
        """Calculates boundary rays and central optical axis endpoints for FOV rendering.
        
        Args:
            fov_range_px (float): Visualization reach distance in pixels.
            
        Returns:
            Tuple containing:
            - left_ray_end (x, y)
            - center_ray_end (x, y)
            - right_ray_end (x, y)
        """
        half_fov = self.fov_deg / 2.0
        left_angle_rad = math.radians(self.orientation_deg - half_fov)
        center_angle_rad = math.radians(self.orientation_deg)
        right_angle_rad = math.radians(self.orientation_deg + half_fov)

        left_end = (
            self.x + fov_range_px * math.cos(left_angle_rad),
            self.y + fov_range_px * math.sin(left_angle_rad)
        )
        center_end = (
            self.x + fov_range_px * math.cos(center_angle_rad),
            self.y + fov_range_px * math.sin(center_angle_rad)
        )
        right_end = (
            self.x + fov_range_px * math.cos(right_angle_rad),
            self.y + fov_range_px * math.sin(right_angle_rad)
        )

        return left_end, center_end, right_end

    def get_fov_wedge_polygon(
        self, fov_range_px: float, num_arc_points: int = 30
    ) -> np.ndarray:
        """Computes boundary vertices forming a smooth FOV wedge/cone arc.
        
        Args:
            fov_range_px (float): Reach distance of the FOV cone.
            num_arc_points (int): Number of interpolated points along the arc curve.
            
        Returns:
            np.ndarray: Matrix of shape (N, 2) with integer pixel coordinates for OpenCV poly rendering.
        """
        half_fov = self.fov_deg / 2.0
        start_angle_deg = self.orientation_deg - half_fov
        end_angle_deg = self.orientation_deg + half_fov

        points = [(int(round(self.x)), int(round(self.y)))]

        for i in range(num_arc_points + 1):
            fraction = i / num_arc_points
            angle_deg = start_angle_deg + fraction * (end_angle_deg - start_angle_deg)
            angle_rad = math.radians(angle_deg)
            px = self.x + fov_range_px * math.cos(angle_rad)
            py = self.y + fov_range_px * math.sin(angle_rad)
            points.append((int(round(px)), int(round(py))))

        return np.array(points, dtype=np.int32)

    def to_dict(self) -> Dict[str, Any]:
        """Returns camera configuration as a dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "orientation_deg": self.orientation_deg,
            "fov_deg": self.fov_deg,
            "image_width": self.image_width,
            "image_height": self.image_height
        }


class FSOCTerminal:
    """Represents a Free-Space Optical Communication terminal node.
    
    Attributes:
        terminal_id (str): Unique identifier string (e.g. 'TERMINAL_A').
        name (str): Display name for the terminal node.
        x (float): Horizontal position coordinate.
        y (float): Vertical position coordinate.
        camera (Optional[VirtualCamera]): Virtual camera module if local terminal.
        beacon (Optional[OpticalBeacon]): Optical beacon module if remote terminal.
    """

    def __init__(
        self,
        terminal_id: str,
        name: str,
        x: float,
        y: float,
        camera: Optional[VirtualCamera] = None,
        beacon: Optional[OpticalBeacon] = None
    ) -> None:
        self.terminal_id = str(terminal_id)
        self.name = str(name)
        self.x = float(x)
        self.y = float(y)
        self.camera = camera
        self.beacon = beacon

    @property
    def position(self) -> Tuple[float, float]:
        """Returns (x, y) position of terminal."""
        return (self.x, self.y)

    @position.setter
    def position(self, pos: Tuple[float, float]) -> None:
        """Sets (x, y) position of terminal and syncs attached modules."""
        self.x, self.y = float(pos[0]), float(pos[1])
        if self.camera:
            self.camera.position = (self.x, self.y)
        if self.beacon:
            self.beacon.position = (self.x, self.y)

    def __repr__(self) -> str:
        has_cam = "Camera" if self.camera else ""
        has_bcn = "Beacon" if self.beacon else ""
        modules = ", ".join(filter(None, [has_cam, has_bcn]))
        return f"<FSOCTerminal id='{self.terminal_id}' pos=({self.x:.1f}, {self.y:.1f}) [{modules}]>"
