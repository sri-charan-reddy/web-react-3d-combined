"""Beacon ground-truth motion simulator for Part 2.

This module provides:
- Ground-truth 2D kinematic trajectory generation.
- Configurable initial position and velocity vectors.
- Frame-by-frame movement with realistic slight trajectory perturbations.
- Boundary collision detection and reflection to keep the beacon inside the camera frame.
- Reproducible simulation via a configurable random seed.
"""

import math
from typing import Optional, Tuple
import numpy as np

from config import BeaconSimConfig


class BeaconSimulator:
    """Simulates realistic 2D ground-truth motion dynamics of an optical beacon."""

    def __init__(self, config: Optional[BeaconSimConfig] = None) -> None:
        """Initialize the beacon simulator with trajectory settings and boundary constraints.
        
        Args:
            config: Beacon motion simulation parameters.
        """
        self.config = config or BeaconSimConfig()
        self.rng = np.random.RandomState(self.config.random_seed)
        
        # State coordinates and velocities
        self.position: np.ndarray = np.array(self.config.start_pos, dtype=np.float64)
        self.velocity: np.ndarray = np.array(self.config.start_velocity, dtype=np.float64)
        
        # Calculate initial heading and speed
        self.speed: float = float(np.linalg.norm(self.velocity))
        if self.speed < 1e-3:
            self.speed = self.config.speed_magnitude
            self.velocity = np.array([self.speed, 0.0], dtype=np.float64)
        self.heading: float = math.atan2(self.velocity[1], self.velocity[0])
        
        self.frame_count: int = 0
        self.time: float = 0.0

    def step(self, dt: float = 1.0 / 30.0) -> Tuple[float, float]:
        """Advance the beacon motion simulation by one frame step.
        
        Applies slight heading perturbation, updates position, checks frame boundaries,
        and returns the resulting true position.
        
        Args:
            dt: Time increment in seconds.
            
        Returns:
            Tuple of (x, y) ground-truth beacon coordinates in pixels.
        """
        # 1. Apply slight random heading perturbation for natural motion curve
        if self.config.heading_noise_std > 0:
            delta_theta = self.rng.normal(0.0, self.config.heading_noise_std)
            self.heading += float(delta_theta)
            # Normalize heading to [-pi, pi]
            self.heading = (self.heading + math.pi) % (2 * math.pi) - math.pi

        # 2. Update velocity vector based on current speed and heading
        self.velocity[0] = self.speed * math.cos(self.heading)
        self.velocity[1] = self.speed * math.sin(self.heading)

        # 3. Update position (scaled to 30 FPS nominal frame step)
        scale_factor = dt * 30.0
        self.position[0] += self.velocity[0] * scale_factor
        self.position[1] += self.velocity[1] * scale_factor

        # 4. Boundary handling: bounce if beacon reaches canvas borders
        margin = self.config.margin
        min_x = margin
        max_x = self.config.arena_width - margin
        min_y = margin
        max_y = self.config.arena_height - margin

        bounced = False
        if self.position[0] <= min_x:
            self.position[0] = min_x
            self.velocity[0] = abs(self.velocity[0])
            bounced = True
        elif self.position[0] >= max_x:
            self.position[0] = max_x
            self.velocity[0] = -abs(self.velocity[0])
            bounced = True

        if self.position[1] <= min_y:
            self.position[1] = min_y
            self.velocity[1] = abs(self.velocity[1])
            bounced = True
        elif self.position[1] >= max_y:
            self.position[1] = max_y
            self.velocity[1] = -abs(self.velocity[1])
            bounced = True

        if bounced:
            self.heading = math.atan2(self.velocity[1], self.velocity[0])

        self.frame_count += 1
        self.time += dt
        return self.get_ground_truth_position()

    def get_ground_truth_position(self) -> Tuple[float, float]:
        """Retrieve the current true position of the beacon.
        
        Returns:
            Tuple of (x, y) ground-truth beacon coordinates in pixels.
        """
        return (float(self.position[0]), float(self.position[1]))

    def get_ground_truth_velocity(self) -> Tuple[float, float]:
        """Retrieve the current true velocity vector of the beacon.
        
        Returns:
            Tuple of (vx, vy) ground-truth velocities in pixels per frame.
        """
        return (float(self.velocity[0]), float(self.velocity[1]))

    def reset(self) -> None:
        """Reset the simulator back to initial conditions and reset RNG."""
        self.rng = np.random.RandomState(self.config.random_seed)
        self.position = np.array(self.config.start_pos, dtype=np.float64)
        self.velocity = np.array(self.config.start_velocity, dtype=np.float64)
        self.speed = float(np.linalg.norm(self.velocity))
        if self.speed < 1e-3:
            self.speed = self.config.speed_magnitude
            self.velocity = np.array([self.speed, 0.0], dtype=np.float64)
        self.heading = math.atan2(self.velocity[1], self.velocity[0])
        self.frame_count = 0
        self.time = 0.0
