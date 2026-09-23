"""Kalman-filter-based predictive tracker for moving optical beacons.

This module provides:
- 2D Linear Kalman Filter implementation using OpenCV (cv2.KalmanFilter).
- Kinematic constant-velocity state model [x, y, vx, vy]^T.
- Outlier detection and measurement gating (rejects far-away false positives).
- Finite State Machine with exact states:
    UNINITIALIZED -> TRACKING -> PREDICTING -> SEARCHING -> REACQUIRING -> LOST
- Tracking confidence scoring and miss counter management.
- Complete state telemetry for downstream controller integration.
"""

import math
from typing import Optional, Tuple, Union
import cv2
import numpy as np

from config import KalmanConfig, TrackingStateConfig
from src.tracking_state import BeaconMeasurement, TrackingResult, TrackingState


class KalmanBeaconTracker:
    """Predictive Kalman Filter Tracker with outlier rejection and recovery state machine.
    
    State Vector (4x1):
        x = [x, y, vx, vy]^T
        x, y: 2D position in pixel coordinates
        vx, vy: 2D velocity in pixels per second
    
    Measurement Vector (2x1):
        z = [x_meas, y_meas]^T
    """

    def __init__(
        self,
        kalman_cfg: Optional[KalmanConfig] = None,
        state_cfg: Optional[TrackingStateConfig] = None
    ) -> None:
        """Initialize OpenCV Kalman filter and tracking state machine.
        
        Args:
            kalman_cfg: Kalman filter tuning parameters.
            state_cfg: Tracking state machine and gating configuration.
        """
        self.kalman_cfg = kalman_cfg or KalmanConfig()
        self.state_cfg = state_cfg or TrackingStateConfig()
        
        self.state: TrackingState = TrackingState.UNINITIALIZED
        self.initialized: bool = False
        self.confidence: float = 0.0
        self.miss_count: int = 0
        self.consecutive_hits: int = 0
        self.last_measurement: Optional[Tuple[float, float]] = None
        self.last_measurement_accepted: bool = False
        
        # Internal state buffer (4x1)
        self.current_state: np.ndarray = np.zeros((4, 1), dtype=np.float32)
        
        # Instantiate OpenCV Kalman Filter (4 dynamic params, 2 measurement params)
        self.kf = cv2.KalmanFilter(4, 2, 0)
        self._setup_kalman_matrices()

    def _setup_kalman_matrices(self) -> None:
        """Configure OpenCV Kalman filter matrices from configuration parameters."""
        dt = float(self.kalman_cfg.dt)
        
        # 1. State Transition Matrix F (Constant Velocity Model)
        self.kf.transitionMatrix = np.array([
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ], dtype=np.float32)

        # 2. Measurement Matrix H (we observe position x, y)
        self.kf.measurementMatrix = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0]
        ], dtype=np.float32)

        # 3. Process Noise Covariance Matrix Q
        q_pos = float(self.kalman_cfg.process_noise_std_pos ** 2)
        q_vel = float(self.kalman_cfg.process_noise_std_vel ** 2)
        self.kf.processNoiseCov = np.diag([q_pos, q_pos, q_vel, q_vel]).astype(np.float32)

        # 4. Measurement Noise Covariance Matrix R
        r_meas = float(self.kalman_cfg.measurement_noise_std ** 2)
        self.kf.measurementNoiseCov = np.diag([r_meas, r_meas]).astype(np.float32)

        # 5. Initial Estimation Error Covariance Matrix P
        p_pos = float(self.kalman_cfg.initial_covariance_pos)
        p_vel = float(self.kalman_cfg.initial_covariance_vel)
        self.kf.errorCovPost = np.diag([p_pos, p_pos, p_vel, p_vel]).astype(np.float32)

    def initialize(self, initial_position: Tuple[float, float], timestamp: float = 0.0) -> None:
        """Initialize filter state upon receiving the first valid measurement.
        
        Args:
            initial_position: Initial detected (x, y) coordinates.
            timestamp: Initial measurement timestamp.
        """
        init_x, init_y = float(initial_position[0]), float(initial_position[1])
        
        self.kf.statePost = np.array([[init_x], [init_y], [0.0], [0.0]], dtype=np.float32)
        self.kf.statePre = self.kf.statePost.copy()
        
        p_pos = float(self.kalman_cfg.initial_covariance_pos)
        p_vel = float(self.kalman_cfg.initial_covariance_vel)
        self.kf.errorCovPost = np.diag([p_pos, p_pos, p_vel, p_vel]).astype(np.float32)
        
        self.current_state = self.kf.statePost.copy()
        self.last_measurement = (init_x, init_y)
        self.last_measurement_accepted = True
        self.initialized = True
        self.state = TrackingState.TRACKING
        self.confidence = 1.0
        self.miss_count = 0
        self.consecutive_hits = 1

    def predict(self, dt: Optional[float] = None) -> np.ndarray:
        """Perform the Kalman prediction step using the constant-velocity motion model.
        
        Args:
            dt: Optional dynamic time step delta.
            
        Returns:
            np.ndarray: Predicted state vector [x, y, vx, vy]^T.
        """
        if dt is not None and abs(dt - self.kalman_cfg.dt) > 1e-5:
            self.kf.transitionMatrix[0, 2] = float(dt)
            self.kf.transitionMatrix[1, 3] = float(dt)

        pred_state = self.kf.predict()
        self.current_state = pred_state.copy()
        return pred_state

    def update(self, measured_position: Tuple[float, float], timestamp: float = 0.0) -> np.ndarray:
        """Perform Kalman measurement correction when an accepted detection is available.
        
        Args:
            measured_position: Validated (x, y) coordinates.
            timestamp: Current timestamp.
            
        Returns:
            np.ndarray: Corrected state vector [x, y, vx, vy]^T.
        """
        meas_arr = np.array([[float(measured_position[0])], [float(measured_position[1])]], dtype=np.float32)
        corrected_state = self.kf.correct(meas_arr)
        
        self.current_state = corrected_state.copy()
        self.last_measurement = (float(measured_position[0]), float(measured_position[1]))
        return corrected_state

    def is_measurement_plausible(
        self,
        predicted_pos: Tuple[float, float],
        measured_pos: Tuple[float, float]
    ) -> Tuple[bool, float]:
        """Perform measurement gating / outlier check against prediction.
        
        Computes Euclidean distance between predicted and measured position.
        
        Args:
            predicted_pos: Predicted (x, y) coordinates from Kalman filter.
            measured_pos: Incoming measured (x, y) coordinates.
            
        Returns:
            Tuple of (is_valid boolean, euclidean distance in pixels).
        """
        dx = measured_pos[0] - predicted_pos[0]
        dy = measured_pos[1] - predicted_pos[1]
        dist = math.sqrt(dx * dx + dy * dy)
        
        # In SEARCHING state, gating threshold expands by search radius to allow acquisition across the bounded search area
        gate = self.state_cfg.gating_threshold_px
        if self.state == TrackingState.SEARCHING:
            gate += 140.0  # search_radius_px
            
        is_valid = dist <= gate
        return is_valid, dist

    def process_frame(
        self,
        measurement: Union[BeaconMeasurement, Optional[Tuple[float, float]]],
        timestamp: float = 0.0
    ) -> TrackingResult:
        """Main per-frame state machine processing and predictive tracking loop.
        
        Flow:
        1. Handle UNINITIALIZED state.
        2. STEP 1: Always call kalman.predict().
        3. STEP 2: If measurement exists:
           - If in LOST state: allow controlled reacquisition (re-initialize at measurement, REACQUIRING -> TRACKING).
           - If in TRACKING/PREDICTING/SEARCHING: perform gating check.
             - If plausible (distance <= threshold):
                 - If recovering from miss/search/loss -> state = REACQUIRING
                 - Else -> state = TRACKING
                 - Correct Kalman filter using measurement.
                 - Reset miss_count = 0, boost confidence.
             - If outlier (distance > threshold):
                 - Reject measurement (DO NOT call correct).
                 - Treat as miss: increment miss_count, degrade confidence.
                 - Evaluate state transition: PREDICTING -> SEARCHING -> LOST.
        4. If measurement does not exist (loss / occlusion):
           - DO NOT call correct().
           - Increment miss_count, degrade confidence.
           - Evaluate state transition: PREDICTING -> SEARCHING -> LOST.
        
        Args:
            measurement: BeaconMeasurement object OR raw (x, y) tuple / None.
            timestamp: Frame timestamp in seconds.
            
        Returns:
            TrackingResult with complete state, telemetry, and health metrics.
        """
        # Parse measurement input
        has_detection = False
        meas_pos: Optional[Tuple[float, float]] = None

        if isinstance(measurement, BeaconMeasurement):
            has_detection = measurement.detected and (measurement.position is not None)
            meas_pos = measurement.position if has_detection else None
        elif measurement is not None:
            has_detection = True
            meas_pos = (float(measurement[0]), float(measurement[1]))

        # 1. Handle uninitialized tracker
        if not self.initialized:
            if has_detection and meas_pos is not None:
                self.initialize(meas_pos, timestamp)
                return self.get_current_result(timestamp, is_predicted=False)
            else:
                self.state = TrackingState.UNINITIALIZED
                return TrackingResult(
                    timestamp=timestamp,
                    position=(0.0, 0.0),
                    velocity=(0.0, 0.0),
                    state=TrackingState.UNINITIALIZED,
                    confidence=0.0,
                    is_predicted=False,
                    miss_count=0,
                    measurement_accepted=False,
                    covariance=self.kf.errorCovPost.copy(),
                    frames_without_detection=0
                )

        # 2. STEP 1: Always predict next state ahead using kinematic motion model
        self.predict()
        pred_pos = self.get_current_position()

        # 3. STEP 2: Evaluate incoming measurement
        if has_detection and meas_pos is not None:
            # Special handling for LOST state: dead-reckoned prediction is stale.
            # Allow controlled reacquisition: optical detection with valid confidence (>= 0.4)
            # cleanly re-anchors the filter without being rejected by the stale prediction.
            if self.state == TrackingState.LOST:
                opt_conf = measurement.confidence if isinstance(measurement, BeaconMeasurement) else 1.0
                if opt_conf >= 0.4:
                    self.last_measurement_accepted = True
                    self.initialize(meas_pos, timestamp)
                    self.state = TrackingState.REACQUIRING
                    self.confidence = 0.60
                    self.miss_count = 0
                    self.consecutive_hits = 1
                    return self.get_current_result(timestamp, is_predicted=False)
                else:
                    # Low confidence detection in LOST -> Reject as outlier/noise
                    self.last_measurement_accepted = False
                    self.miss_count += 1
                    self.consecutive_hits = 0
                    self.state = TrackingState.LOST
                    return self.get_current_result(timestamp, is_predicted=True)

            # Gating / outlier check for active tracking states
            plausible, dist = self.is_measurement_plausible(pred_pos, meas_pos)
            
            if plausible:
                # Plausible measurement -> Accepted!
                self.last_measurement_accepted = True
                is_recovering = (self.miss_count > 0) or (self.state in (TrackingState.PREDICTING, TrackingState.SEARCHING, TrackingState.REACQUIRING))
                
                # Correct Kalman filter
                self.update(meas_pos, timestamp)
                self.miss_count = 0
                self.consecutive_hits += 1
                
                # Confidence boost
                self.confidence = min(
                    self.state_cfg.max_confidence,
                    self.confidence + self.state_cfg.confidence_recovery_rate
                )

                # State Transition: REACQUIRING if just recovered, otherwise TRACKING
                if is_recovering and self.state != TrackingState.REACQUIRING:
                    self.state = TrackingState.REACQUIRING
                else:
                    self.state = TrackingState.TRACKING

                return self.get_current_result(timestamp, is_predicted=False)

            else:
                # Outlier measurement -> REJECTED!
                self.last_measurement_accepted = False
                self.miss_count += 1
                self.consecutive_hits = 0
                
                # Degrade confidence
                self.confidence = max(
                    self.state_cfg.min_confidence,
                    self.confidence - self.state_cfg.confidence_decay_rate
                )

                # State transitions: PREDICTING -> SEARCHING -> LOST
                self._update_miss_state()
                return self.get_current_result(timestamp, is_predicted=True)

        else:
            # Detection missing (occlusion / dropout)
            self.last_measurement_accepted = False
            self.miss_count += 1
            self.consecutive_hits = 0
            
            # Degrade confidence
            self.confidence = max(
                self.state_cfg.min_confidence,
                self.confidence - self.state_cfg.confidence_decay_rate
            )

            # State transitions: PREDICTING -> SEARCHING -> LOST
            self._update_miss_state()
            return self.get_current_result(timestamp, is_predicted=True)

    def _update_miss_state(self) -> None:
        """Update FSM state based on consecutive miss count thresholds."""
        if self.miss_count > self.state_cfg.max_prediction_frames:
            self.state = TrackingState.LOST
        elif self.miss_count >= getattr(self.state_cfg, "search_start_frames", 15):
            self.state = TrackingState.SEARCHING
        else:
            self.state = TrackingState.PREDICTING

    def get_current_position(self) -> Tuple[float, float]:
        """Retrieve current estimated (x, y) beacon position.
        
        Returns:
            Tuple of (x, y) coordinates in pixels.
        """
        return (float(self.current_state[0, 0]), float(self.current_state[1, 0]))

    def get_velocity(self) -> Tuple[float, float]:
        """Retrieve current estimated velocity vector (vx, vy).
        
        Returns:
            Tuple of (vx, vy) in pixels per second.
        """
        return (float(self.current_state[2, 0]), float(self.current_state[3, 0]))

    def get_current_result(self, timestamp: float, is_predicted: bool = False) -> TrackingResult:
        """Construct a complete TrackingResult snapshot.
        
        Args:
            timestamp: Current timestamp in seconds.
            is_predicted: Boolean flag indicating if current state is dead-reckoned.
            
        Returns:
            TrackingResult instance.
        """
        pos = self.get_current_position()
        vel = self.get_velocity()
        cov = self.kf.errorCovPost.copy() if hasattr(self.kf, "errorCovPost") else None
        
        return TrackingResult(
            timestamp=timestamp,
            position=pos,
            velocity=vel,
            state=self.state,
            confidence=self.confidence,
            is_predicted=is_predicted,
            miss_count=self.miss_count,
            measurement_accepted=self.last_measurement_accepted,
            covariance=cov,
            frames_without_detection=self.miss_count
        )

    def reset(self) -> None:
        """Reset the tracker back to UNINITIALIZED state."""
        self.state = TrackingState.UNINITIALIZED
        self.initialized = False
        self.confidence = 0.0
        self.miss_count = 0
        self.consecutive_hits = 0
        self.last_measurement = None
        self.last_measurement_accepted = False
        self.current_state = np.zeros((4, 1), dtype=np.float32)
        self._setup_kalman_matrices()
