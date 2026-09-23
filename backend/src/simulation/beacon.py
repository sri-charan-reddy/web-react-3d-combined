"""Optical Beacon model for Free-Space Optical Communication (FSOC).

This module defines the optical target beacon located on the remote terminal.
"""

from typing import Tuple, Dict, Any


class OpticalBeacon:
    """Represents a simulated optical beacon emitted by an FSOC terminal.
    
    Attributes:
        x (float): Horizontal position coordinate on the simulation canvas.
        y (float): Vertical position coordinate on the simulation canvas.
        intensity (float): Normalized optical signal intensity [0.0 - 1.0].
        radius (float): Physical/visual radius of the beacon core in pixels.
        active (bool): Operational status of the beacon (emitting vs idle).
    """

    def __init__(
        self,
        x: float,
        y: float,
        radius: float = 14.0,
        intensity: float = 1.0,
        active: bool = True
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.radius = float(radius)
        self.intensity = max(0.0, min(1.0, float(intensity)))
        self.active = bool(active)

    @property
    def position(self) -> Tuple[float, float]:
        """Returns the (x, y) coordinates of the beacon."""
        return (self.x, self.y)

    @position.setter
    def position(self, pos: Tuple[float, float]) -> None:
        """Sets the (x, y) coordinates of the beacon."""
        self.x, self.y = float(pos[0]), float(pos[1])

    def set_active(self, status: bool) -> None:
        """Enables or disables the beacon optical emission."""
        self.active = status

    def set_intensity(self, val: float) -> None:
        """Updates normalized optical intensity [0.0, 1.0]."""
        self.intensity = max(0.0, min(1.0, float(val)))

    def to_dict(self) -> Dict[str, Any]:
        """Returns beacon state as a dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "radius": self.radius,
            "intensity": self.intensity,
            "active": self.active
        }

    def __repr__(self) -> str:
        return f"<OpticalBeacon pos=({self.x:.1f}, {self.y:.1f}) intensity={self.intensity:.2f} active={self.active}>"
