"""Beacon Motion Model for FSOC Simulation.

This module provides deterministic kinematic trajectory generation (e.g., 1D sinusoidal
or 2D circular) for the remote optical beacon as a function of simulation time.
"""

import math
from typing import Tuple, Dict, Any


class BeaconMotionModel:
    """Calculates dynamic beacon coordinates (x, y) as a function of simulation time.
    
    Attributes:
        motion_type (str): Trajectory type ("sinusoidal", "circular").
        axis (str): Oscillation axis ("y" or "x").
        amplitude (float): Oscillation displacement magnitude in pixels.
        frequency (float): Motion frequency in Hz.
        origin_x (float): Baseline horizontal origin coordinate.
        origin_y (float): Baseline vertical origin coordinate.
        enabled (bool): Master toggle for kinematic motion updates.
    """

    def __init__(
        self,
        motion_type: str = "sinusoidal",
        axis: str = "y",
        amplitude: float = 80.0,
        frequency: float = 0.15,
        origin_x: float = 1100.0,
        origin_y: float = 360.0,
        enabled: bool = False,
    ) -> None:
        self.motion_type = str(motion_type).lower()
        self.axis = str(axis).lower()
        self.amplitude = float(amplitude)
        self.frequency = float(frequency)
        self.origin_x = float(origin_x)
        self.origin_y = float(origin_y)
        self.enabled = bool(enabled)

    def get_position(self, sim_time: float) -> Tuple[float, float]:
        """Computes current (x, y) beacon coordinates at simulation time t.
        
        Args:
            sim_time (float): Elapsed simulation time in seconds.
            
        Returns:
            Tuple[float, float]: Updated (x, y) world coordinates.
        """
        if not self.enabled:
            return (self.origin_x, self.origin_y)

        if self.motion_type == "sinusoidal":
            displacement = self.amplitude * math.sin(2.0 * math.pi * self.frequency * sim_time)
            if self.axis == "x":
                return (self.origin_x + displacement, self.origin_y)
            else:  # Default 'y' axis
                return (self.origin_x, self.origin_y + displacement)
        elif self.motion_type == "circular":
            angle = 2.0 * math.pi * self.frequency * sim_time
            x = self.origin_x + self.amplitude * math.cos(angle)
            y = self.origin_y + self.amplitude * math.sin(angle)
            return (x, y)
        elif self.motion_type in ("dynamic_flight", "curved", "flight"):
            # Smooth curved 2D flight with multi-harmonic velocity and heading changes
            f1 = self.frequency
            f2 = self.frequency * 1.618  # Golden ratio harmonic for non-repeating smooth trajectory
            f3 = self.frequency * 0.732
            
            amp_x = self.amplitude * 1.4
            amp_y = self.amplitude * 0.9
            
            x = self.origin_x + amp_x * math.cos(2.0 * math.pi * f1 * sim_time) + (self.amplitude * 0.4) * math.sin(2.0 * math.pi * f2 * sim_time)
            y = self.origin_y + amp_y * math.sin(2.0 * math.pi * f1 * sim_time) + (self.amplitude * 0.35) * math.cos(2.0 * math.pi * f3 * sim_time)
            
            # Clamp within arena bounds to prevent flying off canvas
            x = max(100.0, min(1180.0, x))
            y = max(80.0, min(640.0, y))
            return (x, y)
        else:
            # Fallback to static origin
            return (self.origin_x, self.origin_y)

    def get_velocity(self, sim_time: float) -> Tuple[float, float]:
        """Calculates instantaneous 2D velocity vector (vx, vy) in pixels/sec."""
        if not self.enabled:
            return (0.0, 0.0)
        
        dt = 0.01
        p1 = self.get_position(sim_time)
        p2 = self.get_position(sim_time + dt)
        vx = (p2[0] - p1[0]) / dt
        vy = (p2[1] - p1[1]) / dt
        return (vx, vy)

    def get_heading_deg(self, sim_time: float) -> float:
        """Calculates instantaneous heading angle in degrees [0, 360)."""
        vx, vy = self.get_velocity(sim_time)
        if abs(vx) < 1e-4 and abs(vy) < 1e-4:
            return 0.0
        angle = math.degrees(math.atan2(vy, vx))
        return (angle + 360.0) % 360.0

    def get_speed(self, sim_time: float) -> float:
        """Calculates instantaneous speed magnitude in pixels/sec."""
        vx, vy = self.get_velocity(sim_time)
        return float(math.hypot(vx, vy))

    def to_dict(self) -> Dict[str, Any]:
        """Returns motion model parameters as a dictionary."""
        return {
            "motion_type": self.motion_type,
            "axis": self.axis,
            "amplitude": self.amplitude,
            "frequency": self.frequency,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "enabled": self.enabled,
        }


class TerminalMotionModel:
    """Independent kinematic trajectory generator for individual remote FSOC terminals.
    
    Provides continuous, smooth motion with distinct physical characteristics:
    - 'dynamic_flight': Multi-harmonic golden ratio trajectory
    - 'drift_arc': Smooth drifting elliptical arc with angular precession
    - 'curved': Harmonic sweeping curved flight path
    - 'sinusoidal': Weaving S-curve across dual axes
    - 'figure8': Lissajous lemniscate figure-8
    
    Guarantees:
    - Smooth C-infinity boundary confinement via hyperbolic tangent (tanh) soft margins
      preventing edge sticking, abrupt rebounds, or canvas exits.
    - Continuous heading, velocity, and speed derivation.
    """

    def __init__(
        self,
        motion_type: str = "dynamic_flight",
        origin_x: float = 850.0,
        origin_y: float = 360.0,
        frequency: float = 0.05,
        amplitude_x: float = 80.0,
        amplitude_y: float = 60.0,
        phase_offset: float = 0.0,
        bounds: Tuple[float, float, float, float] = (540.0, 1160.0, 90.0, 640.0),
        enabled: bool = True,
    ) -> None:
        self.motion_type = str(motion_type).lower()
        self.origin_x = float(origin_x)
        self.origin_y = float(origin_y)
        self.frequency = float(frequency)
        self.amplitude_x = float(amplitude_x)
        self.amplitude_y = float(amplitude_y)
        self.phase_offset = float(phase_offset)
        self.min_x, self.max_x, self.min_y, self.max_y = bounds
        self.enabled = bool(enabled)

    @staticmethod
    def _soft_contain(val: float, min_val: float, max_val: float, margin: float = 35.0) -> float:
        """Smoothly and continuously confines val within [min_val, max_val] via tanh."""
        if val > max_val - margin:
            u = (val - (max_val - margin)) / margin
            return (max_val - margin) + margin * math.tanh(u)
        elif val < min_val + margin:
            u = ((min_val + margin) - val) / margin
            return (min_val + margin) - margin * math.tanh(u)
        return val

    def get_position(self, sim_time: float) -> Tuple[float, float]:
        """Calculates current (x, y) world coordinates at simulation time t."""
        if not self.enabled:
            return (self.origin_x, self.origin_y)

        t = sim_time
        f = self.frequency
        phi = self.phase_offset
        ax = self.amplitude_x
        ay = self.amplitude_y

        if self.motion_type == "drift_arc":
            # Slow drifting elliptical arc with slow precession
            theta = 2.0 * math.pi * f * t + phi
            prec = 0.15 * 2.0 * math.pi * f * t
            u = ax * math.cos(theta)
            v = ay * math.sin(theta)
            dx = u * math.cos(prec) - v * math.sin(prec)
            dy = u * math.sin(prec) + v * math.cos(prec)

        elif self.motion_type == "curved":
            # Sweeping curved trajectory with distinct harmonic overtones
            dx = ax * math.cos(2.0 * math.pi * f * t + phi) + (ax * 0.30) * math.cos(2.0 * math.pi * (1.414 * f) * t + phi)
            dy = ay * math.sin(2.0 * math.pi * f * t + phi) + (ay * 0.25) * math.sin(2.0 * math.pi * (0.732 * f) * t + 0.5 * phi)

        elif self.motion_type == "sinusoidal":
            # Weaving S-curve trajectory
            dx = ax * math.sin(2.0 * math.pi * f * t + phi) + (ax * 0.20) * math.sin(2.0 * math.pi * (0.5 * f) * t)
            dy = ay * math.sin(4.0 * math.pi * f * t + 2.0 * phi) + (ay * 0.15) * math.cos(2.0 * math.pi * (1.2 * f) * t)

        elif self.motion_type == "figure8":
            # Lissajous figure-8 lemniscate
            dx = ax * math.sin(2.0 * math.pi * f * t + phi)
            dy = ay * math.sin(4.0 * math.pi * f * t + 2.0 * phi + 0.3) + (ay * 0.20) * math.cos(2.0 * math.pi * (0.8 * f) * t)

        else:
            # Default "dynamic_flight": Golden ratio multi-harmonic
            f1 = f
            f2 = f * 1.618
            f3 = f * 0.732
            dx = ax * math.cos(2.0 * math.pi * f1 * t + phi) + (ax * 0.35) * math.sin(2.0 * math.pi * f2 * t + 0.7 * phi)
            dy = ay * math.sin(2.0 * math.pi * f1 * t + phi) + (ay * 0.30) * math.cos(2.0 * math.pi * f3 * t + 1.2 * phi)

        raw_x = self.origin_x + dx
        raw_y = self.origin_y + dy

        x = self._soft_contain(raw_x, self.min_x, self.max_x)
        y = self._soft_contain(raw_y, self.min_y, self.max_y)
        return (x, y)

    def get_velocity(self, sim_time: float) -> Tuple[float, float]:
        """Calculates instantaneous 2D velocity vector (vx, vy) in pixels/sec."""
        if not self.enabled:
            return (0.0, 0.0)
        dt = 0.01
        p1 = self.get_position(sim_time)
        p2 = self.get_position(sim_time + dt)
        vx = (p2[0] - p1[0]) / dt
        vy = (p2[1] - p1[1]) / dt
        return (vx, vy)

    def get_heading_deg(self, sim_time: float) -> float:
        """Calculates instantaneous heading angle in degrees [0, 360)."""
        vx, vy = self.get_velocity(sim_time)
        if abs(vx) < 1e-4 and abs(vy) < 1e-4:
            return 0.0
        angle = math.degrees(math.atan2(vy, vx))
        return (angle + 360.0) % 360.0

    def get_speed(self, sim_time: float) -> float:
        """Calculates instantaneous speed magnitude in pixels/sec."""
        vx, vy = self.get_velocity(sim_time)
        return float(math.hypot(vx, vy))

    def to_dict(self) -> Dict[str, Any]:
        """Returns motion model parameters as a dictionary."""
        return {
            "motion_type": self.motion_type,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "frequency": self.frequency,
            "amplitude_x": self.amplitude_x,
            "amplitude_y": self.amplitude_y,
            "phase_offset": self.phase_offset,
            "enabled": self.enabled,
        }

