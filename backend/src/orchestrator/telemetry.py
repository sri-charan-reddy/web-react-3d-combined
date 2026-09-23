"""Telemetry and state snapshot contracts for Part 4 Orchestrator and future frontend."""

from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple, Dict, Any, List
import time


@dataclass
class SystemTelemetry:
    """Comprehensive snapshot of the autonomous FSOC system for logging and frontend telemetry.
    
    Fields required for downstream UI:
    - current_state: Active operational state string (e.g. 'FSOC_ACTIVE', 'OPTICAL_SEARCH')
    - beacon_detected: True if optical beacon spot is presently identified
    - beacon_position: 2D pixel coordinates (x, y) of optical beacon
    - tracking_status: Status string from Part 2 tracker ('LOCKED', 'COASTING', 'SEARCHING', 'LOST')
    - prediction_status: Status of kinematic prediction ('ACTIVE', 'IDLE', 'DEGRADED')
    - optical_recovery_status: Status of optical search and local reacquisition
    - rf_status: Auxiliary RF channel state ('IDLE', 'SCANNING', 'FOUND', 'NO_SIGNAL')
    - terminal_id: Target/identified terminal identifier (e.g. 'TERMINAL_02')
    - authentication_status: Cryptographic authentication state ('UNVERIFIED', 'AUTHENTICATED', 'REJECTED')
    - approximate_direction: Coarse RF bearing angle in degrees [0, 360)
    - alignment_status: Boresight alignment status ('ALIGNED', 'MISALIGNED', 'LOST')
    - fsoc_status: Optical communications link status ('ESTABLISHED', 'SEARCHING', 'DOWN')
    - error_status: Active error description if any
    """
    timestamp: float = field(default_factory=time.time)
    current_state: str = "IDLE"
    beacon_detected: bool = False
    beacon_position: Optional[Tuple[float, float]] = None
    tracking_status: str = "IDLE"
    prediction_status: str = "IDLE"
    optical_recovery_status: str = "IDLE"
    rf_status: str = "IDLE"
    terminal_id: Optional[str] = None
    authentication_status: str = "UNVERIFIED"
    approximate_direction: Optional[float] = None
    alignment_status: str = "LOST"
    fsoc_status: str = "DOWN"
    error_status: Optional[str] = None
    
    # Kinematic & Optical Metrics
    camera_orientation_deg: float = 0.0
    camera_pan: float = 0.0
    camera_tilt: float = 0.0
    pointing_error_px: Optional[float] = None
    pointing_error_deg: Optional[float] = None
    tracking_error: float = 0.0
    rf_rssi: Optional[float] = None
    rf_direction: Optional[float] = None
    tracking_confidence: float = 0.0
    miss_count: int = 0
    recovery_attempt: int = 0
    
    # Real-time Simulation & Terminal Kinematics
    terminal_world_position: Tuple[float, float] = (0.0, 0.0)
    terminal_velocity: Tuple[float, float] = (0.0, 0.0)
    terminal_heading: float = 0.0
    beacon_image_position: Optional[Tuple[float, float]] = None
    predicted_beacon_position: Optional[Tuple[float, float]] = None
    optical_signal_strength: float = 1.0
    optical_link_status: str = "DOWN"
    turbulence_level: str = "LOW"
    vibration_level: float = 0.0
    cloud_occlusion: bool = False
    
    # Terminal & Identification Configuration
    num_terminals: int = 5
    target_terminal: str = "TERMINAL_02"
    target_terminal_name: str = "Terminal-02"
    identification_status: str = "IDENTIFIED"
    
    # Cryptographic Authentication Telemetry (HMAC-SHA256)
    security_algorithm: str = "HMAC-SHA256"
    security_challenge_nonce: str = ""
    security_hmac_sample: str = ""
    security_replay_protected: bool = True
    security_valid: bool = True
    security_stage: str = "AUTHENTICATED"
    
    # High-level demonstration & recovery lifecycle telemetry
    recovery_mechanism: str = "NONE"
    rf_discovery_state: str = "STANDBY"
    rf_discovered_count: int = 0
    rf_total_count: int = 5
    rf_wave_active: bool = False
    optical_search_state: str = "STANDBY"
    optical_tracking_state: str = "STANDBY"
    fsoc_state: str = "STANDBY"
    terminals_overview: List[Dict[str, Any]] = field(default_factory=list)
    
    # Event Log Stream (latest messages)
    recent_events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to JSON-serializable dictionary for API/WebSocket transmission."""
        d = asdict(self)
        if self.beacon_position is not None:
            d["beacon_position"] = list(self.beacon_position)
        if self.beacon_image_position is not None:
            d["beacon_image_position"] = list(self.beacon_image_position)
        if self.predicted_beacon_position is not None:
            d["predicted_beacon_position"] = list(self.predicted_beacon_position)
        d["terminal_world_position"] = list(self.terminal_world_position)
        d["terminal_velocity"] = list(self.terminal_velocity)
        return d
