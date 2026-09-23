"""Tracking state definitions and data structures for Part 2.

This module defines:
- TrackingState: Finite State Machine (FSM) states:
    UNINITIALIZED, TRACKING, PREDICTING, SEARCHING, REACQUIRING, LOST
- BeaconMeasurement: Standard input container representing optical detection data from Part 1
- TrackingResult: Standard output container provided to downstream controllers (Part 4)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple
import numpy as np


class TrackingState(Enum):
    """Operational states of the predictive tracking finite state machine."""
    UNINITIALIZED = auto()  # No valid initial detection; awaiting initial lock
    TRACKING = auto()       # Valid measurement received; Kalman predict + correct
    PREDICTING = auto()     # Short temporary miss; Kalman predict only (dead reckoning)
    SEARCHING = auto()      # Extended miss; local search scanning around Kalman predicted position
    REACQUIRING = auto()    # Measurement returned after miss/search; passed gating check
    LOST = auto()           # Detection lost longer than max_prediction_frames limit


@dataclass
class BeaconMeasurement:
    """Input data contract representing an optical beacon detection from Part 1.
    
    Attributes:
        timestamp: Monotonic time in seconds when detection occurred.
        position: Measured (x, y) coordinates in pixel space (or camera frame).
        detected: Boolean flag indicating if beacon was detected in the current frame.
        confidence: Optical detector detection confidence score in [0.0, 1.0].
        raw_bbox: Optional bounding box (x, y, w, h) from detector.
    """
    timestamp: float
    position: Optional[Tuple[float, float]] = None
    detected: bool = False
    confidence: float = 0.0
    raw_bbox: Optional[Tuple[float, float, float, float]] = None


@dataclass
class TrackingResult:
    """Output data contract for downstream controller consumption (Part 4).
    
    Attributes:
        timestamp: Time of the state estimation in seconds.
        position: Estimated / predicted 2D position (x, y).
        velocity: Estimated velocity vector (vx, vy) in pixels/second.
        state: Current TrackingState of the system.
        confidence: Normalized tracking health / confidence score in [0.0, 1.0].
        is_predicted: True if this result is purely dead-reckoned without measurement update.
        miss_count: Number of consecutive frames without an accepted measurement.
        measurement_accepted: True if the current frame measurement passed gating and corrected the filter.
        covariance: 4x4 or 2x2 error covariance matrix representing state uncertainty.
        frames_without_detection: Deprecated alias for miss_count.
    """
    timestamp: float
    position: Tuple[float, float]
    velocity: Tuple[float, float]
    state: TrackingState
    confidence: float
    is_predicted: bool
    miss_count: int = 0
    measurement_accepted: bool = False
    covariance: Optional[np.ndarray] = None
    frames_without_detection: int = 0


@dataclass
class PerformanceMetrics:
    """Consolidated performance and quality metrics for SIH Part 2 evaluation."""
    simulation_duration: float = 0.0     # Elapsed simulation time in seconds
    total_frames: int = 0                # Total frames processed
    avg_fps: float = 0.0                 # Average frames per second
    acquisition_time_s: float = 0.0      # Seconds until first valid TRACKING lock
    acquisition_frame: int = 0           # Frame index when first locked
    current_tracking_error_px: float = 0.0 # Instantaneous Euclidean error
    avg_tracking_error_px: float = 0.0   # Mean Euclidean error between Kalman state & ground truth
    max_tracking_error_px: float = 0.0   # Max tracking error observed
    lock_retention_pct: float = 0.0      # % of frames in TRACKING/REACQUIRING state post-lock
    avg_processing_time_ms: float = 0.0  # Mean CPU compute time per frame in milliseconds
    occlusion_count: int = 0             # Number of temporary occlusion / miss intervals
    reacquisition_count: int = 0         # Number of successful re-locks
    rejected_outlier_count: int = 0      # Number of rejected outlier detections


class PerformanceTracker:
    """Diagnostic performance monitor tracking tracking accuracy, latency, and retention."""

    def __init__(self) -> None:
        """Initialize performance metrics accumulators."""
        self.reset()

    def reset(self) -> None:
        """Reset all metric statistics."""
        self.start_timestamp: Optional[float] = None
        self.latest_timestamp: float = 0.0
        self.total_frames: int = 0
        self.first_lock_frame: Optional[int] = None
        self.first_lock_time: Optional[float] = None
        self.tracking_errors: list = []
        self.processing_times_ms: list = []
        self.locked_frames_count: int = 0
        self.occlusion_count: int = 0
        self.reacquisition_count: int = 0
        self.rejected_outlier_count: int = 0
        self._prev_state: TrackingState = TrackingState.UNINITIALIZED
        self.current_error: float = 0.0

    def update(
        self,
        ground_truth: Tuple[float, float],
        measurement: BeaconMeasurement,
        tracking_result: TrackingResult,
        frame_idx: int,
        timestamp: float,
        frame_compute_time_s: float = 0.0
    ) -> PerformanceMetrics:
        """Update metrics for the current frame.
        
        Args:
            ground_truth: True (x, y) beacon coordinates (used solely for metric validation).
            measurement: Current optical measurement.
            tracking_result: Current Kalman tracking estimation.
            frame_idx: Simulation frame index.
            timestamp: Simulation timestamp in seconds.
            frame_compute_time_s: Per-frame CPU execution time in seconds.
            
        Returns:
            PerformanceMetrics snapshot.
        """
        if self.start_timestamp is None:
            self.start_timestamp = timestamp
        self.latest_timestamp = timestamp
        self.total_frames += 1

        # Track frame compute latency
        proc_ms = frame_compute_time_s * 1000.0
        self.processing_times_ms.append(proc_ms)

        # 1. Initial lock acquisition
        if self.first_lock_frame is None and tracking_result.state == TrackingState.TRACKING:
            self.first_lock_frame = frame_idx
            self.first_lock_time = timestamp - self.start_timestamp

        # 2. Tracking accuracy error (Euclidean distance between Kalman position and Ground Truth)
        if tracking_result.state in (TrackingState.TRACKING, TrackingState.PREDICTING, TrackingState.SEARCHING, TrackingState.REACQUIRING):
            dx = tracking_result.position[0] - ground_truth[0]
            dy = tracking_result.position[1] - ground_truth[1]
            self.current_error = float(np.sqrt(dx * dx + dy * dy))
            self.tracking_errors.append(self.current_error)

        # 3. Lock retention count (frames in active lock)
        if tracking_result.state in (TrackingState.TRACKING, TrackingState.REACQUIRING):
            self.locked_frames_count += 1

        # 4. State transition counts
        if self._prev_state in (TrackingState.TRACKING, TrackingState.REACQUIRING) and tracking_result.state in (TrackingState.PREDICTING, TrackingState.SEARCHING, TrackingState.LOST):
            self.occlusion_count += 1
            
        if tracking_result.state == TrackingState.REACQUIRING and self._prev_state != TrackingState.REACQUIRING:
            self.reacquisition_count += 1

        # 5. Outlier rejection count
        if measurement.detected and not tracking_result.measurement_accepted:
            self.rejected_outlier_count += 1

        self._prev_state = tracking_result.state

        # Compute summary metrics
        duration = max(0.001, self.latest_timestamp - self.start_timestamp)
        avg_fps = float(self.total_frames / duration) if duration > 0 else 30.0
        avg_err = float(np.mean(self.tracking_errors)) if self.tracking_errors else 0.0
        max_err = float(np.max(self.tracking_errors)) if self.tracking_errors else 0.0
        
        post_lock_frames = (self.total_frames - (self.first_lock_frame or 0))
        retention = float(100.0 * self.locked_frames_count / max(1, post_lock_frames)) if self.first_lock_frame is not None else 0.0
        avg_proc_ms = float(np.mean(self.processing_times_ms)) if self.processing_times_ms else 0.0

        return PerformanceMetrics(
            simulation_duration=duration,
            total_frames=self.total_frames,
            avg_fps=avg_fps,
            acquisition_time_s=self.first_lock_time or 0.0,
            acquisition_frame=self.first_lock_frame or 0,
            current_tracking_error_px=self.current_error,
            avg_tracking_error_px=avg_err,
            max_tracking_error_px=max_err,
            lock_retention_pct=retention,
            avg_processing_time_ms=avg_proc_ms,
            occlusion_count=self.occlusion_count,
            reacquisition_count=self.reacquisition_count,
            rejected_outlier_count=self.rejected_outlier_count
        )

