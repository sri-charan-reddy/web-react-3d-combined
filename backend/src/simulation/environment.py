"""FSOC Environment model managing world simulation state and terminals.

This module encapsulates environment dimensions, time progression, and terminal references.
It contains strictly simulation logic and holds no dependencies on rendering libraries.
"""

from typing import Dict, Any, Optional, Tuple
from .terminal import FSOCTerminal, VirtualCamera
from .beacon import OpticalBeacon
from .motion import BeaconMotionModel


class FSOCEnvironment:
    """Manages the 2D simulation environment, bounds, terminals, time progression.
    
    Attributes:
        width (int): Simulation canvas width in pixels.
        height (int): Simulation canvas height in pixels.
        target_fps (int): Target frame rate for simulation updates.
        frame_delay_ms (int): Milliseconds delay per frame for renderer loop.
        grid_spacing (int): Pixel spacing for environment visual grid.
        grid_visible (bool): Flag indicating if background grid is active.
        terminal_a (FSOCTerminal): Local Terminal instance (hosting camera).
        terminal_b (FSOCTerminal): Remote Terminal instance (hosting beacon).
        motion_model (BeaconMotionModel): Dynamic kinematic motion model for remote beacon.
        sim_time (float): Elapsed simulation time in seconds.
        frame_count (int): Total rendered frames processed.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        sim_cfg = config.get("simulation", {})
        self.width = int(sim_cfg.get("width", 1280))
        self.height = int(sim_cfg.get("height", 720))
        self.target_fps = int(sim_cfg.get("target_fps", 30))
        self.frame_delay_ms = int(sim_cfg.get("frame_delay_ms", 33))
        self.grid_spacing = int(sim_cfg.get("grid_spacing", 80))
        self.grid_visible = bool(sim_cfg.get("grid_visible", True))

        # Build Terminal A (Local) & Attached Virtual Camera
        term_a_cfg = config.get("terminal_a", {})
        cam_cfg = config.get("camera", {})
        pos_a = term_a_cfg.get("position", [180, 360])
        
        self.camera = VirtualCamera(
            x=cam_cfg.get("position", pos_a)[0],
            y=cam_cfg.get("position", pos_a)[1],
            orientation_deg=cam_cfg.get("orientation_deg", 0.0),
            fov_deg=cam_cfg.get("field_of_view_deg", 35.0),
            image_width=cam_cfg.get("image_width", 1280),
            image_height=cam_cfg.get("image_height", 720)
        )
        
        self.terminal_a = FSOCTerminal(
            terminal_id=term_a_cfg.get("id", "TERMINAL_A"),
            name=term_a_cfg.get("name", "Local Terminal A"),
            x=pos_a[0],
            y=pos_a[1],
            camera=self.camera
        )

        # Build Terminal B (Remote) & Attached Optical Beacon
        term_b_cfg = config.get("terminal_b", {})
        bcn_cfg = config.get("beacon", {})
        pos_b = term_b_cfg.get("position", [1100, 360])

        self.beacon = OpticalBeacon(
            x=bcn_cfg.get("position", pos_b)[0],
            y=bcn_cfg.get("position", pos_b)[1],
            radius=bcn_cfg.get("radius", 14.0),
            intensity=bcn_cfg.get("intensity", 1.0),
            active=bcn_cfg.get("active", True)
        )

        self.terminal_b = FSOCTerminal(
            terminal_id=term_b_cfg.get("id", "TERMINAL_B"),
            name=term_b_cfg.get("name", "Remote Terminal B"),
            x=pos_b[0],
            y=pos_b[1],
            beacon=self.beacon
        )

        self.fov_range_px = float(cam_cfg.get("fov_range_px", 950))

        # Build Beacon Motion Model
        motion_cfg = sim_cfg.get("beacon_motion", {})
        self.motion_model = BeaconMotionModel(
            motion_type=motion_cfg.get("type", "sinusoidal"),
            axis=motion_cfg.get("axis", "y"),
            amplitude=motion_cfg.get("amplitude", 80.0),
            frequency=motion_cfg.get("frequency", 0.15),
            origin_x=self.terminal_b.x,
            origin_y=self.terminal_b.y,
            enabled=motion_cfg.get("enabled", False)
        )

        # Simulation metrics
        self.sim_time = 0.0
        self.frame_count = 0

    def update(self, dt: float = 0.033) -> None:
        """Advances simulation clock and updates environment state.
        
        Args:
            dt (float): Delta time in seconds since last frame update.
        """
        self.sim_time += dt
        self.frame_count += 1

        # Update dynamic beacon position if motion model is enabled
        if self.motion_model and self.motion_model.enabled:
            new_pos = self.motion_model.get_position(self.sim_time)
            self.terminal_b.position = new_pos

    def get_baseline_distance(self) -> float:
        """Calculates Euclidean baseline distance in pixels between Terminal A and B."""
        dx = self.terminal_b.x - self.terminal_a.x
        dy = self.terminal_b.y - self.terminal_a.y
        return float((dx**2 + dy**2) ** 0.5)

    def get_terminal_velocity(self) -> Tuple[float, float]:
        """Calculates current velocity vector (vx, vy) of Terminal B in pixels/sec."""
        if self.motion_model and self.motion_model.enabled:
            return self.motion_model.get_velocity(self.sim_time)
        return (0.0, 0.0)

    def get_terminal_heading_deg(self) -> float:
        """Calculates current heading angle of Terminal B in degrees [0, 360)."""
        if self.motion_model and self.motion_model.enabled:
            return self.motion_model.get_heading_deg(self.sim_time)
        return 0.0

    def get_terminal_speed(self) -> float:
        """Calculates current speed of Terminal B in pixels/sec."""
        if self.motion_model and self.motion_model.enabled:
            return self.motion_model.get_speed(self.sim_time)
        return 0.0

    def __repr__(self) -> str:
        return (
            f"<FSOCEnvironment size=({self.width}x{self.height}) "
            f"term_a='{self.terminal_a.terminal_id}' term_b='{self.terminal_b.terminal_id}' "
            f"time={self.sim_time:.2f}s frames={self.frame_count}>"
        )
