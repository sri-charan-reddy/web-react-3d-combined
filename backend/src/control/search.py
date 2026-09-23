"""Software-only 360-Degree Acquisition Search Controller.

This module executes a controlled 360-degree rotational search when the optical beacon
is LOST, slew-rotating the camera orientation until the beacon enters the camera FOV
or the 360-degree sweep is exhausted.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from src.detection.alignment import AlignmentResult


@dataclass
class SearchResult:
    """Encapsulates output status and orientation commands for the acquisition search controller.
    
    Attributes:
        delta_orientation_deg (float): Angular rotation step in degrees applied in current frame.
        new_orientation_deg (float): Resulting camera pointing orientation in degrees.
        active (bool): True if an active search rotation is occurring.
        mode (str): Operational search state ("IDLE", "SEARCHING", "TRACKING", "SEARCH_EXHAUSTED").
        swept_angle_deg (float): Accumulated angular sweep degrees during current search attempt.
    """
    delta_orientation_deg: float
    new_orientation_deg: float
    active: bool
    mode: str
    swept_angle_deg: float

    def to_dict(self) -> Dict[str, Any]:
        """Returns search result metrics as a dictionary."""
        return {
            "delta_orientation_deg": self.delta_orientation_deg,
            "new_orientation_deg": self.new_orientation_deg,
            "active": self.active,
            "mode": self.mode,
            "swept_angle_deg": self.swept_angle_deg,
        }


class SearchController:
    """Acquisition Search Controller executing controlled 360° sweeps on beacon loss.
    
    Attributes:
        search_speed (float): Rotation speed in degrees per second (e.g. 30.0).
        max_sweep_deg (float): Maximum allowed angular sweep angle in degrees (e.g. 360.0).
        enabled (bool): Master toggle for search capability.
    """

    def __init__(
        self,
        search_speed_deg_per_sec: float = 30.0,
        max_sweep_deg: float = 360.0,
        enabled: bool = True
    ) -> None:
        self.search_speed = float(search_speed_deg_per_sec)
        self.max_sweep_deg = float(max_sweep_deg)
        self.enabled = bool(enabled)
        
        self.is_searching: bool = False
        self.swept_angle_deg: float = 0.0
        self.search_start_orientation_deg: Optional[float] = None

    def update(
        self,
        current_orientation_deg: float,
        alignment_res: AlignmentResult,
        dt: float
    ) -> SearchResult:
        """Processes perception state and updates 360-degree search execution.
        
        Args:
            current_orientation_deg (float): Current camera orientation in degrees.
            alignment_res (AlignmentResult): Boresight alignment & detection metrics.
            dt (float): Delta time in seconds since last frame update.
            
        Returns:
            SearchResult: Slew step command, new orientation, active flag, mode, and sweep angle.
        """
        # Rule 1: If search is disabled in configuration
        if not self.enabled:
            self._reset_search_state()
            return SearchResult(
                delta_orientation_deg=0.0,
                new_orientation_deg=float(current_orientation_deg),
                active=False,
                mode="IDLE",
                swept_angle_deg=0.0
            )

        # Rule 2: If beacon is DETECTED, search halts immediately
        if alignment_res.detected:
            self._reset_search_state()
            return SearchResult(
                delta_orientation_deg=0.0,
                new_orientation_deg=float(current_orientation_deg),
                active=False,
                mode="TRACKING",
                swept_angle_deg=0.0
            )

        # Rule 3: Beacon is LOST -> Execute or evaluate search
        if not self.is_searching:
            # Initialize a new 360-degree search attempt
            self.is_searching = True
            self.search_start_orientation_deg = float(current_orientation_deg)
            self.swept_angle_deg = 0.0

        # Check if 360° sweep limit has already been reached
        if self.swept_angle_deg >= self.max_sweep_deg:
            self.is_searching = False
            return SearchResult(
                delta_orientation_deg=0.0,
                new_orientation_deg=float(current_orientation_deg),
                active=False,
                mode="SEARCH_EXHAUSTED",
                swept_angle_deg=self.swept_angle_deg
            )

        # Calculate incremental search rotation step
        desired_step = self.search_speed * max(0.0, float(dt))
        remaining_sweep = self.max_sweep_deg - self.swept_angle_deg
        step = min(desired_step, remaining_sweep)

        # Accumulate sweep angle and update target orientation
        self.swept_angle_deg += step
        new_orientation = float(current_orientation_deg + step)

        if self.swept_angle_deg >= self.max_sweep_deg:
            self.is_searching = False

        return SearchResult(
            delta_orientation_deg=step,
            new_orientation_deg=new_orientation,
            active=True,
            mode="SEARCHING",
            swept_angle_deg=self.swept_angle_deg
        )

    def _reset_search_state(self) -> None:
        """Resets internal search state counters."""
        self.is_searching = False
        self.swept_angle_deg = 0.0
        self.search_start_orientation_deg = None
