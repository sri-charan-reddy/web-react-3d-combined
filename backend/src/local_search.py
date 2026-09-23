"""Local Search Around Kalman Predicted Beacon Position for Part 2.

This module provides:
- Bounded, deterministic local search scanning around the Kalman predicted beacon position.
- Smooth waypoint generator (expanding diamond/spiral pattern) constrained to a configurable search radius.
- Integration with VirtualCamera and CameraController to scan for beacon reacquisition.
- Strict isolation: uses ONLY Kalman predicted position as the reference center, NEVER Ground Truth.
"""

from dataclasses import dataclass
import math
from typing import List, Optional, Tuple

from config import LocalSearchConfig


@dataclass
class LocalSearchTelemetry:
    """Telemetry snapshot of local search scanner state."""
    is_active: bool
    search_center: Tuple[float, float]
    search_target: Tuple[float, float]
    current_offset: Tuple[float, float]
    step_index: int
    total_steps: int
    search_radius: float


class LocalSearch:
    """Generates bounded local search waypoints around Kalman predicted beacon coordinates."""

    def __init__(self, config: Optional[LocalSearchConfig] = None) -> None:
        """Initialize local search scanner with pattern parameters.
        
        Args:
            config: LocalSearchConfig instance with radius, step size, and timing.
        """
        self.config = config or LocalSearchConfig()
        
        self.is_active: bool = False
        self.search_center: Tuple[float, float] = (640.0, 360.0)
        self.search_target: Tuple[float, float] = (640.0, 360.0)
        self.current_offset: Tuple[float, float] = (0.0, 0.0)
        
        self.step_index: int = 0
        self.frame_hold_counter: int = 0
        
        # Precompute search offset waypoints pattern
        self.pattern_offsets: List[Tuple[float, float]] = self._generate_pattern()

    def _generate_pattern(self) -> List[Tuple[float, float]]:
        """Construct deterministic expanding diamond/spiral pattern of offset vectors."""
        radius = float(self.config.search_radius_px)
        step = float(self.config.step_size_px)
        offsets: List[Tuple[float, float]] = [(0.0, 0.0)]  # Center first
        
        num_rings = max(1, int(radius / step))
        for r_idx in range(1, num_rings + 1):
            cur_r = r_idx * step
            # Diamond waypoints at radius cur_r
            # Right, Up-Right, Up, Up-Left, Left, Down-Left, Down, Down-Right
            waypoints = [
                (cur_r, 0.0),
                (cur_r * 0.707, cur_r * 0.707),
                (0.0, cur_r),
                (-cur_r * 0.707, cur_r * 0.707),
                (-cur_r, 0.0),
                (-cur_r * 0.707, -cur_r * 0.707),
                (0.0, -cur_r),
                (cur_r * 0.707, -cur_r * 0.707),
            ]
            for wp in waypoints:
                dist = math.sqrt(wp[0]**2 + wp[1]**2)
                if dist <= radius + 1e-3:
                    offsets.append((float(wp[0]), float(wp[1])))
                    
        return offsets

    def update(
        self,
        predicted_pos: Tuple[float, float],
        is_searching: bool
    ) -> Tuple[float, float]:
        """Update search state and compute current target position for camera pointing.
        
        Args:
            predicted_pos: Current Kalman predicted beacon coordinates (x, y).
            is_searching: True if system is in SEARCHING state, False otherwise.
            
        Returns:
            Tuple of (target_x, target_y) to command the CameraController.
        """
        self.search_center = predicted_pos
        
        if not is_searching:
            # Not in search mode -> stay centered on prediction without search offset
            if self.is_active:
                self.reset()
            self.search_target = predicted_pos
            self.current_offset = (0.0, 0.0)
            return predicted_pos

        self.is_active = True

        # Advance pattern waypoint every hold_frames_per_step frames
        self.frame_hold_counter += 1
        if self.frame_hold_counter >= self.config.hold_frames_per_step:
            self.frame_hold_counter = 0
            self.step_index = (self.step_index + 1) % len(self.pattern_offsets)

        self.current_offset = self.pattern_offsets[self.step_index]
        
        # Search target = Kalman predicted position + current search offset
        tgt_x = predicted_pos[0] + self.current_offset[0]
        tgt_y = predicted_pos[1] + self.current_offset[1]
        
        self.search_target = (tgt_x, tgt_y)
        return (tgt_x, tgt_y)

    def get_telemetry(self) -> LocalSearchTelemetry:
        """Retrieve telemetry snapshot of local search state.
        
        Returns:
            LocalSearchTelemetry instance.
        """
        return LocalSearchTelemetry(
            is_active=self.is_active,
            search_center=self.search_center,
            search_target=self.search_target,
            current_offset=self.current_offset,
            step_index=self.step_index,
            total_steps=len(self.pattern_offsets),
            search_radius=self.config.search_radius_px
        )

    def reset(self) -> None:
        """Reset search scanner to beginning of pattern."""
        self.is_active = False
        self.step_index = 0
        self.frame_hold_counter = 0
        self.current_offset = (0.0, 0.0)
