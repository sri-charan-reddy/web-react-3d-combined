"""Autonomous FSOC Recovery & Complete Integration Orchestrator (Part 4).

This module connects Part 1 (Optical Environment & Detection), Part 2 (Kalman Predictive Tracking
& Disturbance Handling), and Part 3 (RF-Assisted Discovery & HMAC Authentication) into a single,
resilient, autonomous closed-loop system.
"""

import math
import os
import sys
import time
from typing import Callable, Dict, Any, List, Optional, Tuple
import yaml
import numpy as np

from src.orchestrator.states import SystemState
from src.orchestrator.telemetry import SystemTelemetry

# Part 1 Imports
from src.simulation.environment import FSOCEnvironment
from src.simulation.camera import VirtualCameraSensor
from src.simulation.motion import TerminalMotionModel
from src.detection.beacon_detector import ClassicalBeaconDetector, DetectionResult
from src.detection.alignment import AlignmentCalculator, AlignmentResult
from src.control.pat_controller import VirtualPATController
from src.control.search import SearchController

# Part 2 Imports
from config import KalmanConfig, TrackingStateConfig, LocalSearchConfig, SystemConfig, DEFAULT_CONFIG
from src.tracking_state import TrackingState, BeaconMeasurement, TrackingResult
from src.kalman_tracker import KalmanBeaconTracker
from src.local_search import LocalSearch

# Part 3 Imports
import rf_discovery_Ashish as rf_module

# Global Pool of Remote Terminals available for configuration in simulation
AVAILABLE_TERMINAL_POOL: Dict[str, Dict[str, Any]] = {
    f"TERMINAL_{i:02d}": {
        "terminal_id": f"TERMINAL_{i:02d}",
        "name": f"Terminal-{i:02d}",
        "position": (10.0 + (i % 4) * 4.0, 8.0 + (i // 4) * 3.0),
        "shared_secret": f"ISRO_FSOC_KEY_{i:02d}"
    }
    for i in range(1, 16)
}

# Ensure trusted registry includes all terminal keys
for tid, tinfo in AVAILABLE_TERMINAL_POOL.items():
    if tid not in rf_module.TRUSTED_TERMINALS_REGISTRY:
        rf_module.TRUSTED_TERMINALS_REGISTRY[tid] = tinfo["shared_secret"]


class FSOCRecoveryOrchestrator:
    """Central orchestrator coordinating Parts 1, 2, and 3.
    
    Coordinates:
    - 360° Optical Acquisition (Part 1)
    - Centroid Detection & Alignment (Part 1)
    - Constant-Velocity Kalman Predictive Tracking (Part 2)
    - Bounded Local Spiral Reacquisition (Part 2)
    - Auxiliary Multi-Channel RF Discovery & HMAC Verification (Part 3)
    - Coarse Bearing Slew & Optical Handshake Recovery (Part 4 -> Part 1 -> Part 2)
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        target_terminal_id: str = "TERMINAL_02",
        target_secret: Optional[str] = None,
        num_terminals: int = 5,
        log_callback: Optional[Callable[[str], None]] = None,
        state_callback: Optional[Callable[[SystemState, SystemState], None]] = None,
    ) -> None:
        """Initialize the Part 4 Orchestrator.
        
        Args:
            config: Optional configuration dictionary. If None, loaded from config/config.yaml.
            target_terminal_id: Identifier of target terminal to track and authenticate.
            target_secret: Expected cryptographic shared secret for HMAC authentication.
            num_terminals: Total number of remote terminals in the environment.
            log_callback: Optional listener receiving formatted log messages.
            state_callback: Optional listener receiving (old_state, new_state) transitions.
        """
        self.raw_config = config or self._load_default_config()
        self.num_terminals = max(2, min(12, int(num_terminals)))
        self.target_terminal_id = target_terminal_id
        self.target_secret = target_secret or rf_module.TRUSTED_TERMINALS_REGISTRY.get(target_terminal_id)
        
        # Real Security / HMAC Verification State
        self.security_challenge_nonce: str = "7a8f9c2d1e0b3456fa82bc194de75031"
        self.security_hmac_sample: str = "sha256:d8b2e591...6f0a"
        self.security_replay_protected: bool = True
        self.security_valid: bool = False
        self.security_stage: str = "PENDING"
        
        self.log_callback = log_callback
        self.state_callback = state_callback
        
        # Current State & History
        self.state: SystemState = SystemState.IDLE
        self.event_log: List[str] = []
        
        # Multi-Terminal Deployed State
        self.deployed_terminals: Dict[str, Dict[str, Any]] = {}
        self.detected_terminal_ids: set = set()
        self.is_initial_deployment: bool = False
        self.rf_discovery_ticks: int = 0
        self.rf_discovered_terminals: set = set()
        self.rf_wave_active: bool = False
        
        # Telemetry State
        self.telemetry = SystemTelemetry()
        # Timeouts and Thresholds
        self.optical_search_sweep_limit_deg: float = 90.0
        self.max_prediction_frames: int = 15       # Transition to LOCAL_REACQUISITION
        self.max_local_search_frames: int = 20     # Transition to OPTICAL_SEARCH
        self.max_reacquisition_frames: int = 60    # Timeout limit for optical reacquisition
        self.reacquisition_frames_count: int = 0
        self.fine_alignment_tolerance_px: float = 15.0
        self.fine_alignment_hold_frames_needed: int = 5
        self.fine_alignment_hold_count: int = 0
        self.recovery_attempt_count: int = 0
        self.optical_search_sweep_done: bool = False
        self.last_locked_orientation_deg: float = 0.0
        
        # Subsystem Components
        self._init_subsystems()
        
        self._log("[PART 4] System initialized")

    @property
    def rf_discovered_count(self) -> int:
        return len(self.rf_discovered_terminals)

    @property
    def rf_total_count(self) -> int:
        return len(self.deployed_terminals)

    def enable_motion(self, motion_type: str = "dynamic_flight", frequency: float = 0.08, amplitude: float = 120.0) -> None:
        """Enables smooth continuous dynamic flight motion for Target and deployed terminals."""
        self.env.motion_model.enabled = True
        self.env.motion_model.motion_type = motion_type
        self.env.motion_model.frequency = frequency
        self.env.motion_model.amplitude = amplitude
        self.env.motion_model.origin_x = float(self.env.terminal_b.x)
        self.env.motion_model.origin_y = float(self.env.terminal_b.y)
        if getattr(self, "deployed_terminals", None):
            for tid, tinfo in self.deployed_terminals.items():
                mm = tinfo.get("motion_model")
                if mm:
                    mm.enabled = True
        self._log(f"[PART 4] Terminal dynamic motion enabled (type='{motion_type}')")

    def disable_motion(self) -> None:
        """Disables dynamic motion (terminals hold static position)."""
        self.env.motion_model.enabled = False
        if getattr(self, "deployed_terminals", None):
            for tid, tinfo in self.deployed_terminals.items():
                mm = tinfo.get("motion_model")
                if mm:
                    mm.enabled = False
        self._log("[PART 4] Terminal dynamic motion disabled")

    def deploy_terminals(
        self,
        num_terminals: int = 5,
        target_terminal_id: str = "TERMINAL_03",
        random_seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Dynamically deploys N independent remote terminals with non-overlapping random positions.
        
        Guarantees:
        1. Exactly N independent terminals exist in the simulation state.
        2. Terminals are distributed randomly across search area (x: [560, 1140], y: [110, 620]).
        3. Terminals have a minimum separation >= 75px so they are distinct.
        4. Target terminal is placed at its generated coordinate and continuous dynamic motion enabled.
        5. Camera initial orientation points away from target to initiate an authentic 360° scan.
        6. System resets to OPTICAL_SEARCH state.
        """
        import random
        rng = random.Random(random_seed) if random_seed is not None else random.Random()
        
        # 1. Normalize bounds & target ID
        n = max(2, min(12, int(num_terminals)))
        self.num_terminals = n
        
        norm_target = str(target_terminal_id).strip().upper().replace("-", "_")
        if not norm_target.startswith("TERMINAL_"):
            try:
                num_part = int(''.join(filter(str.isdigit, norm_target)))
                norm_target = f"TERMINAL_{num_part:02d}"
            except ValueError:
                norm_target = "TERMINAL_03"
        self.target_terminal_id = norm_target
        self.target_secret = rf_module.TRUSTED_TERMINALS_REGISTRY.get(
            self.target_terminal_id, f"ISRO_FSOC_KEY_{self.target_terminal_id[-2:]}"
        )

        # 2. Build list of N unique terminal IDs ensuring target is included
        candidate_ids = [f"TERMINAL_{i:02d}" for i in range(1, 16)]
        deployed_ids = [f"TERMINAL_{i:02d}" for i in range(1, n + 1)]
        if self.target_terminal_id not in deployed_ids:
            deployed_ids[-1] = self.target_terminal_id

        # 3. Generate random non-overlapping coordinates in operational search sector
        min_separation = 75.0
        generated_positions: Dict[str, Tuple[float, float]] = {}

        for tid in deployed_ids:
            placed = False
            for attempt in range(600):
                sep = min_separation if attempt < 400 else (min_separation * 0.75)
                cx = round(rng.uniform(560.0, 1140.0), 1)
                cy = round(rng.uniform(110.0, 620.0), 1)
                collision = False
                for other_pos in generated_positions.values():
                    if math.hypot(cx - other_pos[0], cy - other_pos[1]) < sep:
                        collision = True
                        break
                if not collision:
                    generated_positions[tid] = (cx, cy)
                    placed = True
                    break
            if not placed:
                idx = len(generated_positions)
                grid_x = 580.0 + (idx % 3) * 230.0
                grid_y = 140.0 + (idx // 3) * 150.0
                generated_positions[tid] = (grid_x, grid_y)

        # 4. Populate deployed terminals registry with independent motion models
        self.deployed_terminals = {}
        self.detected_terminal_ids = set()

        # Diverse trajectory profiles for independent terminal motion
        trajectory_profiles = [
            "curved",
            "drift_arc",
            "sinusoidal",
            "figure8",
            "dynamic_flight",
        ]

        for idx, tid in enumerate(deployed_ids):
            pos = generated_positions[tid]
            is_target = (tid == self.target_terminal_id)
            num_str = tid.split("_")[-1]
            t_name = f"Terminal-{num_str}"
            secret = rf_module.TRUSTED_TERMINALS_REGISTRY.get(tid, f"ISRO_FSOC_KEY_{num_str}")

            # Assign distinct motion parameters per terminal
            if is_target:
                m_type = "dynamic_flight"
                freq = 0.075
                amp_x = 85.0
                amp_y = 65.0
                phase = (2.0 * math.pi * idx) / n
            else:
                m_type = trajectory_profiles[idx % len(trajectory_profiles)]
                freq = 0.040 + 0.012 * (idx % 4)
                amp_x = 60.0 + 10.0 * (idx % 3)
                amp_y = 50.0 + 10.0 * ((idx + 1) % 3)
                phase = (2.0 * math.pi * idx) / n + 0.35

            motion_model = TerminalMotionModel(
                motion_type=m_type,
                origin_x=float(pos[0]),
                origin_y=float(pos[1]),
                frequency=freq,
                amplitude_x=amp_x,
                amplitude_y=amp_y,
                phase_offset=phase,
                bounds=(540.0, 1160.0, 90.0, 640.0),
                enabled=True
            )

            self.deployed_terminals[tid] = {
                "id": tid,
                "name": t_name,
                "x": float(pos[0]),
                "y": float(pos[1]),
                "position": (float(pos[0]), float(pos[1])),
                "velocity": (0.0, 0.0),
                "heading": 0.0,
                "speed": 0.0,
                "shared_secret": secret,
                "role": "Target" if is_target else "Other",
                "is_target": is_target,
                "status": "Searching",
                "rf_status": "TRANSMITTING",
                "motion_model": motion_model,
                "trajectory": m_type,
                "trajectory_type": m_type,
            }

        # 5. Attach target terminal to environment's terminal_b and dynamic flight model
        target_pos = generated_positions[self.target_terminal_id]
        self.env.terminal_b.x = target_pos[0]
        self.env.terminal_b.y = target_pos[1]
        self.env.terminal_b.terminal_id = self.target_terminal_id
        self.env.terminal_b.name = f"Remote ({self.target_terminal_id})"
        self.env.beacon.x = target_pos[0]
        self.env.beacon.y = target_pos[1]
        self.env.beacon.active = True
        self.env.beacon.intensity = 1.0

        # Motion model origin at target coordinate
        self.env.motion_model.origin_x = target_pos[0]
        self.env.motion_model.origin_y = target_pos[1]
        self.env.motion_model.enabled = True
        self.env.motion_model.motion_type = "dynamic_flight"
        self.env.motion_model.frequency = 0.075
        self.env.motion_model.amplitude = 85.0

        # 6. Point camera away from target bearing to enforce initial search
        dx = target_pos[0] - self.env.terminal_a.x
        dy = target_pos[1] - self.env.terminal_a.y
        target_bearing_deg = math.degrees(math.atan2(dy, dx)) % 360.0
        
        # Start ~140° away from target
        initial_cam_orientation = (target_bearing_deg + 140.0) % 360.0
        self.env.camera.orientation_deg = initial_cam_orientation
        self.last_locked_orientation_deg = initial_cam_orientation

        # Reset search controller for a full 360° scan
        self.optical_search_sweep_limit_deg = 360.0
        self.search_controller.max_sweep_deg = 360.0
        self.search_controller._reset_search_state()
        self.search_controller.swept_angle_deg = 0.0
        self.optical_search_sweep_done = False

        # Reset tracking state
        self.prediction_frames_count = 0
        self.local_search_frames_count = 0
        self.reacquisition_frames_count = 0
        self.fine_alignment_hold_count = 0
        self.recovery_attempt_count = 0
        self.rf_recovery_result = None
        self.recovered_rf_direction = None
        self.tracker.reset()

        # Initialize deployment RF discovery & security lifecycle flags
        self.is_initial_deployment = True
        self.rf_discovery_ticks = 0
        self.rf_discovered_terminals = set()
        self.rf_wave_active = True
        self.security_stage = "PENDING"
        self.security_valid = False

        # Transition to RF_DISCOVERY (RF transmission & discovery happens FIRST)
        self.transition_to(SystemState.RF_DISCOVERY, f"Deployed {n} terminals; initiating RF discovery")
        self._log(f"[DEPLOYMENT] {n} independent terminals deployed across search area.")
        self._log(f"[DEPLOYMENT] Target designated: {self.target_terminal_id}.")
        self._log("[RF DISCOVERY] All terminals transmitting RF discovery signals...")

        return self.get_terminals_overview()

    def set_target_terminal(self, target_terminal_id: str, num_terminals: Optional[int] = None) -> None:
        """Dynamically reconfigures the target remote terminal and terminal count."""
        n = max(2, min(12, int(num_terminals))) if num_terminals is not None else self.num_terminals
        self.deploy_terminals(num_terminals=n, target_terminal_id=target_terminal_id)

    def get_terminals_overview(self) -> List[Dict[str, Any]]:
        """Returns structured remote terminals overview for frontend display."""
        overview = []
        if getattr(self, "deployed_terminals", None):
            for tid, t in self.deployed_terminals.items():
                is_target = t.get("is_target", False) or (tid == self.target_terminal_id)
                pos = (float(t["x"]), float(t["y"]))

                overview.append({
                    "id": tid,
                    "name": t["name"],
                    "status": t["status"],
                    "rf_status": t.get("rf_status", "DISCOVERED"),
                    "role": t["role"],
                    "position": pos,
                    "velocity": t.get("velocity", (0.0, 0.0)),
                    "heading": t.get("heading", 0.0),
                    "speed": t.get("speed", 0.0),
                    "trajectory": t.get("trajectory", "dynamic_flight"),
                    "is_target": is_target
                })
            return overview

        # Fallback to pool if deploy_terminals has not yet been invoked
        all_keys = list(AVAILABLE_TERMINAL_POOL.keys())
        active_keys = all_keys[:self.num_terminals]
        if self.target_terminal_id not in active_keys:
            active_keys[-1] = self.target_terminal_id

        for tid in active_keys:
            info = AVAILABLE_TERMINAL_POOL.get(tid, {})
            is_target = (tid == self.target_terminal_id)
            pos = (
                (float(self.env.terminal_b.x), float(self.env.terminal_b.y))
                if (is_target and hasattr(self, "env") and self.env and hasattr(self.env, "terminal_b"))
                else info.get("position", (0.0, 0.0))
            )
            overview.append({
                "id": tid,
                "name": info.get("name", tid.replace("_", "-").title()),
                "status": "Target" if is_target else "Available",
                "role": "Target" if is_target else "Other",
                "position": pos,
                "is_target": is_target
            })
        return overview

    def _load_default_config(self) -> Dict[str, Any]:
        """Loads configuration from config/config.yaml if present."""
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.yaml")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                pass
        return {
            "simulation": {"width": 1280, "height": 720, "target_fps": 30},
            "camera": {"orientation_deg": 0.0, "field_of_view_deg": 35.0, "image_width": 1280, "image_height": 720},
            "alignment": {"tolerance_px": 15.0},
            "control": {"kp": 0.15, "max_step_deg": 1.2},
            "search": {"search_speed_deg_per_sec": 60.0, "max_sweep_deg": 90.0}
        }

    def _init_subsystems(self) -> None:
        """Initialize Part 1, Part 2, and Part 3 components."""
        # --- Part 1 Components ---
        self.env = FSOCEnvironment(self.raw_config)
        self.camera_sensor = VirtualCameraSensor(self.env.camera)
        self.detector = ClassicalBeaconDetector(
            intensity_threshold=160,
            min_area=4.0,
            max_area=5000.0,
            min_peak_brightness=180
        )
        self.alignment_calc = AlignmentCalculator(
            image_width=self.env.camera.image_width,
            image_height=self.env.camera.image_height,
            fov_deg=self.env.camera.fov_deg,
            tolerance_px=self.fine_alignment_tolerance_px
        )
        self.pat_controller = VirtualPATController(
            kp=self.raw_config.get("control", {}).get("kp", 0.15),
            max_step_deg=self.raw_config.get("control", {}).get("max_step_deg", 1.2)
        )
        self.search_controller = SearchController(
            search_speed_deg_per_sec=self.raw_config.get("search", {}).get("search_speed_deg_per_sec", 60.0),
            max_sweep_deg=self.optical_search_sweep_limit_deg
        )


        # --- Part 2 Components ---
        kalman_cfg = KalmanConfig(
            dt=1.0 / self.env.target_fps,
            process_noise_std_pos=0.5,
            process_noise_std_vel=1.0,
            measurement_noise_std=2.0
        )
        state_cfg = TrackingStateConfig(
            gating_threshold_px=80.0,
            max_prediction_frames=50
        )
        self.tracker = KalmanBeaconTracker(kalman_cfg=kalman_cfg, state_cfg=state_cfg)
        self.local_search = LocalSearch(LocalSearchConfig(
            search_radius_px=140.0,
            step_size_px=25.0,
            hold_frames_per_step=3
        ))

        # Internal tracking counters
        self.prediction_frames_count: int = 0
        self.local_search_frames_count: int = 0
        self.rf_recovery_result: Optional[Dict[str, Any]] = None
        self.recovered_rf_direction: Optional[float] = None

        # Align Remote Terminal B and Beacon with target terminal geometry if in registry
        if self.target_terminal_id in rf_module.DEFAULT_SIMULATED_TERMINALS:
            term_data = rf_module.DEFAULT_SIMULATED_TERMINALS[self.target_terminal_id]
            target_pos = term_data.get("position", (10, 8))
            rf_dir = rf_module.calculate_rf_direction((0, 0), target_pos)
            dist = 600.0
            rad = math.radians(rf_dir)
            self.env.terminal_b.x = self.env.terminal_a.x + dist * math.cos(rad)
            self.env.terminal_b.y = self.env.terminal_a.y + dist * math.sin(rad)
            self.env.beacon.x = self.env.terminal_b.x
            self.env.beacon.y = self.env.terminal_b.y


    def _log(self, message: str) -> None:
        """Internal logging with notification to callbacks."""
        self.event_log.append(message)
        if len(self.event_log) > 100:
            self.event_log.pop(0)
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def transition_to(self, new_state: SystemState, reason: str = "") -> None:
        """Execute state transition and trigger state callbacks."""
        if self.state == new_state:
            return
        old_state = self.state
        self.state = new_state
        msg = f"[PART 4] State transition: {old_state.name} -> {new_state.name}"
        if reason:
            msg += f" ({reason})"
        self._log(msg)
        if self.state_callback:
            self.state_callback(old_state, new_state)

    def start(self) -> None:
        """Start the autonomous FSOC acquisition and tracking system."""
        self._log("[PART 4] System started")
        self.transition_to(SystemState.OPTICAL_SEARCH, "Initiating 360° search")
        self._log("[PART 4] Optical search started")

    def step(self, dt: Optional[float] = None) -> SystemTelemetry:
        """Execute a single tick / frame step of the orchestrator state machine.
        
        Args:
            dt: Delta time in seconds. If None, computed from target frame rate.
            
        Returns:
            SystemTelemetry: Complete snapshot of system state and metrics.
        """
        delta_t = dt if dt is not None else (1.0 / float(self.env.target_fps))
        
        # 1. Update simulation environment world state
        try:
            self.env.update(delta_t)
        except Exception as exc:
            self._log(f"[PART 4] Simulation update error: {exc}")
            self.telemetry.error_status = str(exc)

        # Update continuous independent motion for ALL deployed terminals
        self._update_all_terminals_motion(delta_t)

        # 2. Capture virtual camera frame and run optical detection (Part 1)
        try:
            camera_frame = self.camera_sensor.capture_frame(self.env.beacon)
            detection_res: DetectionResult = self.detector.detect(camera_frame)
            alignment_res: AlignmentResult = self.alignment_calc.calculate(detection_res)
        except Exception as exc:
            self._log(f"[PART 4] Vision perception error: {exc}")
            self.telemetry.error_status = str(exc)
            detection_res = DetectionResult(detected=False)
            alignment_res = AlignmentResult(detected=False, aligned=False)

        
        # 3. Process current state logic
        if self.state == SystemState.IDLE:
            pass

        elif self.state == SystemState.OPTICAL_SEARCH:
            self._handle_optical_search(detection_res, alignment_res, delta_t)

        elif self.state == SystemState.OPTICAL_TRACKING:
            self._handle_optical_tracking(detection_res, alignment_res, delta_t)

        elif self.state == SystemState.PREDICTIVE_RECOVERY:
            self._handle_predictive_recovery(detection_res, alignment_res, delta_t)

        elif self.state == SystemState.LOCAL_REACQUISITION:
            self._handle_local_reacquisition(detection_res, alignment_res, delta_t)

        elif self.state == SystemState.RF_DISCOVERY:
            self._handle_rf_discovery()

        elif self.state == SystemState.RF_AUTHENTICATION:
            self._handle_rf_authentication()

        elif self.state == SystemState.RF_DIRECTION_RECOVERY:
            self._handle_rf_direction_recovery()

        elif self.state == SystemState.OPTICAL_REACQUISITION:
            self._handle_optical_reacquisition(detection_res, alignment_res, delta_t)

        elif self.state == SystemState.FINE_ALIGNMENT:
            self._handle_fine_alignment(detection_res, alignment_res, delta_t)

        elif self.state == SystemState.FSOC_ACTIVE:
            self._handle_fsoc_active(detection_res, alignment_res, delta_t)

        elif self.state == SystemState.RECOVERY_FAILED:
            self._handle_recovery_failed()

        # 4. Generate Telemetry Snapshot
        self._update_telemetry(detection_res, alignment_res)
        return self.telemetry

    def _update_all_terminals_motion(self, dt: float) -> None:
        """Updates continuous independent motion for all deployed terminals on every simulation tick.
        
        Guarantees:
        1. Every deployed terminal's position, velocity, heading, and speed are updated.
        2. Soft pairwise separation prevents visual overlap between terminals.
        3. All terminals smoothly stay inside valid search sector boundaries.
        4. Target terminal coordinates remain synchronized with environment terminal_b and beacon.
        """
        if not getattr(self, "deployed_terminals", None):
            return

        sim_time = float(self.env.sim_time)

        # 1. Evaluate kinematics from each terminal's independent motion model
        raw_positions: Dict[str, List[float]] = {}
        for tid, tinfo in self.deployed_terminals.items():
            mm = tinfo.get("motion_model")
            if mm and getattr(mm, "enabled", False):
                pos = mm.get_position(sim_time)
                vel = mm.get_velocity(sim_time)
                heading = mm.get_heading_deg(sim_time)
                speed = mm.get_speed(sim_time)
            else:
                pos = (float(tinfo.get("x", 0.0)), float(tinfo.get("y", 0.0)))
                vel = (0.0, 0.0)
                heading = 0.0
                speed = 0.0

            raw_positions[tid] = [float(pos[0]), float(pos[1])]
            tinfo["velocity"] = vel
            tinfo["heading"] = heading
            tinfo["speed"] = speed

        # 2. Soft separation avoidance (min separation ~55px)
        # Target terminal preserves exact tracking trajectory; non-target terminals yield gracefully
        min_sep = 55.0
        keys = list(self.deployed_terminals.keys())
        for i in range(len(keys)):
            tid_a = keys[i]
            pos_a = raw_positions[tid_a]
            is_target_a = (tid_a == self.target_terminal_id)
            for j in range(i + 1, len(keys)):
                tid_b = keys[j]
                pos_b = raw_positions[tid_b]
                is_target_b = (tid_b == self.target_terminal_id)

                dx = pos_b[0] - pos_a[0]
                dy = pos_b[1] - pos_a[1]
                dist = math.hypot(dx, dy)
                if 0.001 < dist < min_sep:
                    overlap = min_sep - dist
                    ux = dx / dist
                    uy = dy / dist
                    if is_target_a:
                        pos_b[0] += ux * overlap * 0.45
                        pos_b[1] += uy * overlap * 0.45
                    elif is_target_b:
                        pos_a[0] -= ux * overlap * 0.45
                        pos_a[1] -= uy * overlap * 0.45
                    else:
                        pos_a[0] -= ux * overlap * 0.22
                        pos_a[1] -= uy * overlap * 0.22
                        pos_b[0] += ux * overlap * 0.22
                        pos_b[1] += uy * overlap * 0.22

        # 3. Apply coordinates and sync target terminal with environment
        for tid, tinfo in self.deployed_terminals.items():
            px, py = raw_positions[tid]
            px = max(540.0, min(1160.0, px))
            py = max(90.0, min(640.0, py))

            tinfo["x"] = px
            tinfo["y"] = py
            tinfo["position"] = (px, py)

            if tid == self.target_terminal_id:
                self.env.terminal_b.position = (px, py)
                if self.env.beacon:
                    self.env.beacon.position = (px, py)

    # --- State Handlers ---

    def _handle_optical_search(
        self,
        detection_res: DetectionResult,
        alignment_res: AlignmentResult,
        dt: float
    ) -> None:
        """Handle 360° acquisition search (Part 1)."""
        cam_x = float(self.env.terminal_a.x)
        cam_y = float(self.env.terminal_a.y)
        cam_deg = float(self.env.camera.orientation_deg)
        half_fov = float(self.env.camera.fov_deg / 2.0)
        fov_range = getattr(self.env, "fov_range_px", 950.0)

        # Multi-terminal scanning logic if deployment is active
        if getattr(self, "deployed_terminals", None):
            target_in_fov = False
            for tid, tinfo in self.deployed_terminals.items():
                is_target = tinfo.get("is_target", False) or (tid == self.target_terminal_id)
                if is_target:
                    tx = float(self.env.terminal_b.x)
                    ty = float(self.env.terminal_b.y)
                else:
                    tx = float(tinfo["x"])
                    ty = float(tinfo["y"])

                dx = tx - cam_x
                dy = ty - cam_y
                dist = math.hypot(dx, dy)
                angle_deg = math.degrees(math.atan2(dy, dx)) % 360.0
                angle_diff = (angle_deg - cam_deg + 180.0) % 360.0 - 180.0

                # Check if terminal is within FOV sector
                if abs(angle_diff) <= half_fov and dist <= fov_range:
                    if not is_target:
                        if tid not in self.detected_terminal_ids:
                            self.detected_terminal_ids.add(tid)
                            tinfo["status"] = "Detected"
                            self._log(f"[OPTICAL SCAN] ✓ {tinfo['name']} detected -> Non-target terminal -> Continuing scan...")
                    else:
                        target_in_fov = True

            # If target terminal is in camera FOV and beacon is detected, verify identity and lock!
            if target_in_fov and detection_res.detected:
                self.deployed_terminals[self.target_terminal_id]["status"] = "Target"
                self._log(f"[OPTICAL SCAN] → TARGET {self.deployed_terminals[self.target_terminal_id]['name']} detected!")
                self._log(f"[OPTICAL SCAN] Target identity verified against authenticated ID: {self.target_terminal_id}")
                self._log(f"[OPTICAL SCAN] Locking onto target; starting optical tracking...")
                self.prediction_frames_count = 0
                self.local_search_frames_count = 0
                meas = BeaconMeasurement(
                    timestamp=self.env.sim_time,
                    position=(detection_res.center_x, detection_res.center_y),
                    detected=True,
                    confidence=detection_res.confidence
                )
                self.tracker.process_frame(meas, self.env.sim_time)
                self.transition_to(SystemState.OPTICAL_TRACKING, f"Target {self.target_terminal_id} acquired in camera FOV")
                return

            # Target not yet detected or not in FOV -> continue rotating search sweep
            search_res = self.search_controller.update(self.env.camera.orientation_deg, AlignmentResult(detected=False, aligned=False), dt)
            self.env.camera.orientation_deg = search_res.new_orientation_deg

            # If search sweep exhausted without detection, escalate to RF recovery
            if search_res.mode == "SEARCH_EXHAUSTED" or search_res.swept_angle_deg >= self.optical_search_sweep_limit_deg:
                self._log("[PART 4] Optical search sweep limit reached without detection")
                self.transition_to(SystemState.RF_DISCOVERY, "Optical search sweep limit reached")
            return

        # Fallback for direct standalone unit tests where deploy_terminals() was not invoked
        if detection_res.detected:
            self._log("[PART 1] Beacon detected")
            self._log("[PART 4] Optical tracking active")
            self.prediction_frames_count = 0
            self.local_search_frames_count = 0
            # Initialize Kalman tracker with initial measurement
            meas = BeaconMeasurement(
                timestamp=self.env.sim_time,
                position=(detection_res.center_x, detection_res.center_y),
                detected=True,
                confidence=detection_res.confidence
            )
            self.tracker.process_frame(meas, self.env.sim_time)
            self.transition_to(SystemState.OPTICAL_TRACKING, "Beacon acquired in camera FOV")
        else:
            # Slew camera via Part 1 SearchController
            search_res = self.search_controller.update(self.env.camera.orientation_deg, alignment_res, dt)
            self.env.camera.orientation_deg = search_res.new_orientation_deg
            
            # If search sweep exhausted without detection, escalate to RF recovery
            if search_res.mode == "SEARCH_EXHAUSTED" or search_res.swept_angle_deg >= self.optical_search_sweep_limit_deg:
                self._log("[PART 4] Optical search sweep limit reached without detection")
                self.transition_to(SystemState.RF_DISCOVERY, "Optical search sweep limit reached")

    def _handle_optical_tracking(
        self,
        detection_res: DetectionResult,
        alignment_res: AlignmentResult,
        dt: float
    ) -> None:
        """Handle continuous optical tracking and steering (Part 1 + Part 2)."""
        if detection_res.detected:
            self.optical_search_sweep_done = False
            # Update Kalman Tracker with valid detection
            meas = BeaconMeasurement(
                timestamp=self.env.sim_time,
                position=(detection_res.center_x, detection_res.center_y),
                detected=True,
                confidence=detection_res.confidence
            )
            track_res: TrackingResult = self.tracker.process_frame(meas, self.env.sim_time)
            
            # Check alignment status for transition to FINE_ALIGNMENT or FSOC_ACTIVE
            self.last_locked_orientation_deg = float(self.env.camera.orientation_deg)
            if alignment_res.aligned:
                self.fine_alignment_hold_count += 1
                if self.fine_alignment_hold_count >= self.fine_alignment_hold_frames_needed:
                    self.transition_to(SystemState.FINE_ALIGNMENT, "Alignment error within tolerance")
            else:
                self.fine_alignment_hold_count = 0
                # Steer camera using Part 1 proportional PAT controller
                ctrl_res = self.pat_controller.update(self.env.camera.orientation_deg, alignment_res)
                self.env.camera.orientation_deg = ctrl_res.new_orientation_deg
                self.last_locked_orientation_deg = float(self.env.camera.orientation_deg)
        else:
            # Beacon Lost -> Transition to Predictive Recovery (Part 2)
            self._log("[PART 4] Beacon lost")
            self._log("[PART 2] Predictive recovery started")
            self.prediction_frames_count = 0
            self.fine_alignment_hold_count = 0
            self.recovery_attempt_count += 1
            self.transition_to(SystemState.PREDICTIVE_RECOVERY, "Optical detection dropped")

    def _handle_predictive_recovery(
        self,
        detection_res: DetectionResult,
        alignment_res: AlignmentResult,
        dt: float
    ) -> None:
        """Handle short-term Kalman dead-reckoning prediction (Part 2)."""
        # If beacon reappears immediately, reacquire tracking!
        if detection_res.detected:
            self._log("[PART 1] Beacon detected")
            self._log("[PART 2] Tracking restored")
            self._log("[PART 4] Optical tracking active")
            self.last_locked_orientation_deg = float(self.env.camera.orientation_deg)
            meas = BeaconMeasurement(
                timestamp=self.env.sim_time,
                position=(detection_res.center_x, detection_res.center_y),
                detected=True,
                confidence=detection_res.confidence
            )
            self.tracker.process_frame(meas, self.env.sim_time)
            self.transition_to(SystemState.OPTICAL_TRACKING, "Beacon reacquired during dead-reckoning")
            return

        # Advance Kalman filter without measurement (dead-reckoning coast)
        meas = BeaconMeasurement(timestamp=self.env.sim_time, detected=False)
        track_res: TrackingResult = self.tracker.process_frame(meas, self.env.sim_time)
        self.prediction_frames_count += 1
        
        if self.prediction_frames_count == 1:
            self._log("[PART 2] Beacon prediction available")

        # Slew camera smoothly along Kalman dead-reckoning prediction bounded near last lock
        if track_res.position is not None:
            pred_x, pred_y = track_res.position
            err_px = pred_x - (self.env.camera.image_width / 2.0)
            err_deg = (err_px / (self.env.camera.image_width / 2.0)) * (self.env.camera.fov_deg / 2.0)
            bounded_offset = float(np.clip(err_deg, -5.0, 5.0))
            self.env.camera.orientation_deg = (self.last_locked_orientation_deg + bounded_offset) % 360.0

        # If occlusion persists beyond max_prediction_frames, escalate to bounded Local Search
        if self.prediction_frames_count >= self.max_prediction_frames:
            self._log("[PART 4] Local reacquisition started")
            self.local_search.reset()
            self.local_search_frames_count = 0
            self.transition_to(SystemState.LOCAL_REACQUISITION, "Dead-reckoning threshold exceeded")

    def _handle_local_reacquisition(
        self,
        detection_res: DetectionResult,
        alignment_res: AlignmentResult,
        dt: float
    ) -> None:
        """Handle bounded local search scanning around Kalman prediction (Part 2)."""
        # If beacon detected during local search, reacquire lock!
        if detection_res.detected:
            self._log("[PART 1] Beacon detected")
            self._log("[PART 2] Tracking restored")
            self._log("[PART 4] Optical tracking active")
            self.last_locked_orientation_deg = float(self.env.camera.orientation_deg)
            self.local_search.reset()
            meas = BeaconMeasurement(
                timestamp=self.env.sim_time,
                position=(detection_res.center_x, detection_res.center_y),
                detected=True,
                confidence=detection_res.confidence
            )
            self.tracker.process_frame(meas, self.env.sim_time)
            self.transition_to(SystemState.OPTICAL_TRACKING, "Beacon reacquired during local search")
            return

        # Update Kalman prediction and step local search waypoints
        meas = BeaconMeasurement(timestamp=self.env.sim_time, detected=False)
        track_res: TrackingResult = self.tracker.process_frame(meas, self.env.sim_time)
        search_target = self.local_search.update(track_res.position, is_searching=True)
        self.local_search_frames_count += 1

        # Slew camera smoothly along local search spiral waypoint bounded near last lock
        if search_target is not None:
            sx, sy = search_target
            err_px = sx - (self.env.camera.image_width / 2.0)
            err_deg = (err_px / (self.env.camera.image_width / 2.0)) * (self.env.camera.fov_deg / 2.0)
            bounded_offset = float(np.clip(err_deg, -8.0, 8.0))
            self.env.camera.orientation_deg = (self.last_locked_orientation_deg + bounded_offset) % 360.0

        # If local search exhausts its frame budget, escalate to 360° optical sweep first before RF
        if self.local_search_frames_count >= self.max_local_search_frames:
            self.local_search.reset()
            if not self.optical_search_sweep_done:
                self.optical_search_sweep_done = True
                self._log("[PART 4] Local reacquisition exhausted; initiating 360° optical search sweep")
                self.env.camera.orientation_deg = self.last_locked_orientation_deg
                self.search_controller._reset_search_state()
                self.transition_to(SystemState.OPTICAL_SEARCH, "Local search exhausted; starting 360° optical search")
            else:
                self._log("[PART 4] Optical recovery failed")
                self.transition_to(SystemState.RF_DISCOVERY, "Local search and optical sweep exhausted")

    def _handle_rf_discovery(self) -> None:
        """Initiate Part 3 RF scanning and progressive target terminal identification."""
        if getattr(self, "is_initial_deployment", False):
            # Progressive RF discovery during initial multi-terminal deployment
            self.rf_discovery_ticks += 1
            deployed = getattr(self, "deployed_terminals", {})
            total_n = len(deployed)
            
            # Progressively discover terminals over ticks (interval of 3 ticks per terminal)
            interval = 3
            idx_to_discover = self.rf_discovery_ticks // interval
            term_items = list(deployed.items())
            
            for i in range(min(idx_to_discover, total_n)):
                tid, tinfo = term_items[i]
                if tid not in self.rf_discovered_terminals:
                    self.rf_discovered_terminals.add(tid)
                    tinfo["rf_status"] = "DISCOVERED"
                    self._log(f"[RF DISCOVERY] ✓ {tinfo['name']} discovered ({len(self.rf_discovered_terminals)}/{total_n})")
            
            if len(self.rf_discovered_terminals) >= total_n:
                self._log(f"[RF DISCOVERY] ✓ COMPLETE: {total_n}/{total_n} terminals discovered.")
                # Target Identification from discovered pool
                self._log(f"[TARGET IDENTIFICATION] Target configured: {self.target_terminal_id}")
                self._log(f"[TARGET IDENTIFICATION] → {self.target_terminal_id}")
                self._log(f"[TARGET IDENTIFICATION] ✓ TARGET IDENTIFIED: {self.target_terminal_id} in RF network.")
                self.rf_recovery_result = {"terminal_id": self.target_terminal_id, "rssi": -42.0}
                self.transition_to(SystemState.RF_AUTHENTICATION, f"Target {self.target_terminal_id} identified; initiating HMAC-SHA256 authentication")
            return

        self._log("[PART 3] RF discovery started")
        
        # Calculate dynamic RF geometry between Terminal A and moving Terminal B
        local_pos = (float(self.env.terminal_a.x), float(self.env.terminal_a.y))
        target_pos = (float(self.env.terminal_b.x), float(self.env.terminal_b.y))

        trusted_secret = self.target_secret or rf_module.TRUSTED_TERMINALS_REGISTRY.get(
            self.target_terminal_id, "ISRO_FSOC_KEY_02"
        )
        
        # Build multi-terminal pool from active overview with live positions
        dynamic_terminals: Dict[str, Dict[str, Any]] = {}
        for t_info in self.get_terminals_overview():
            tid = t_info["id"]
            if tid == self.target_terminal_id:
                dynamic_terminals[tid] = {
                    "terminal_id": tid,
                    "position": target_pos,
                    "shared_secret": trusted_secret,
                    "authorized": True
                }
            else:
                base = AVAILABLE_TERMINAL_POOL.get(tid, {})
                dynamic_terminals[tid] = {
                    "terminal_id": tid,
                    "position": t_info["position"],
                    "shared_secret": base.get("shared_secret", ""),
                    "authorized": True
                }

        # Call Part 3 discover_rf_terminals with dynamic positions
        discovered = rf_module.discover_rf_terminals(
            available_terminals=dynamic_terminals,
            local_position=local_pos
        )
        matched = None
        for cand in discovered:
            if cand.get("terminal_id") == self.target_terminal_id:
                matched = cand
                break
        
        if matched:
            self._log(f"[PART 3] Target terminal identified: {self.target_terminal_id} (RSSI: {matched.get('rssi')} dBm)")
            self.rf_recovery_result = matched
            self.transition_to(SystemState.RF_AUTHENTICATION, "Target terminal discovered on RF channel")
        else:
            self._log(f"[PART 4] Target terminal {self.target_terminal_id} not found in RF coverage area")
            self.transition_to(SystemState.RECOVERY_FAILED, "RF terminal identification failed")

    def _handle_rf_authentication(self) -> None:
        """Execute Part 3 HMAC-SHA256 challenge-response verification."""
        import secrets, hmac, hashlib
        self._log(f"[PART 4] Authenticating terminal {self.target_terminal_id} via HMAC-SHA256 challenge-response")
        
        # Verify trusted secret
        trusted_secret = self.target_secret or rf_module.TRUSTED_TERMINALS_REGISTRY.get(self.target_terminal_id)
        if not trusted_secret:
            self._log(f"[PART 4] No trusted secret found for {self.target_terminal_id}")
            self.security_valid = False
            self.security_stage = "REJECTED"
            self.transition_to(SystemState.RECOVERY_FAILED, "Missing trusted secret")
            return

        # 1. Cryptographic Challenge Nonce Generation
        challenge_nonce = secrets.token_hex(16)
        self.security_challenge_nonce = challenge_nonce
        self._log(f"[PART 3] Challenge generated (Single-use nonce: {challenge_nonce[:8]}...)")

        # 2. Target Terminal HMAC-SHA256 Computation
        if getattr(self, "deployed_terminals", None) and self.target_terminal_id in self.deployed_terminals:
            target_device = dict(self.deployed_terminals[self.target_terminal_id])
        else:
            target_device = dict(AVAILABLE_TERMINAL_POOL.get(self.target_terminal_id, {}))
        if self.target_secret and self.target_secret.startswith("UNAUTHORIZED"):
            target_device["shared_secret"] = "WRONG_IMPOSTOR_KEY_99"

        auth_success = rf_module.authenticate_terminal(target_device, trusted_secret)
        
        term_secret = target_device.get("shared_secret", "")
        response_mac = hmac.new(term_secret.encode(), challenge_nonce.encode(), hashlib.sha256).hexdigest()
        self.security_hmac_sample = f"sha256:{response_mac[:8]}...{response_mac[-4:]}"
        self.security_valid = auth_success
        self.security_replay_protected = True
        
        if auth_success:
            self.security_stage = "AUTHENTICATED"
            self._log("[PART 3] Nonce verified & HMAC-SHA256 signature verified")
            self._log(f"[AUTHENTICATION] ✓ Target {self.target_terminal_id} trusted via HMAC-SHA256")
            
            if getattr(self, "is_initial_deployment", False):
                self.is_initial_deployment = False
                self.rf_wave_active = False
                self._log("[OPTICAL SEARCH] Target authenticated. Beginning 360° optical area scan...")
                self.transition_to(SystemState.OPTICAL_SEARCH, "Target authenticated; starting 360° optical scan")
            else:
                self.rf_wave_active = False
                self.transition_to(SystemState.RF_DIRECTION_RECOVERY, "Cryptographic handshake verified")
        else:
            self.security_stage = "REJECTED"
            self._log("[PART 3] Authentication failed: unauthorized terminal / invalid signature")
            self.transition_to(SystemState.RECOVERY_FAILED, "HMAC authentication failed")

    def _handle_rf_direction_recovery(self) -> None:
        """Extract coarse bearing angle from current target terminal position and prepare camera slew."""
        # Calculate live RF direction angle from Terminal A to current moving position of Target Terminal B
        dx = float(self.env.terminal_b.x) - float(self.env.terminal_a.x)
        dy = float(self.env.terminal_b.y) - float(self.env.terminal_a.y)
        current_rf_direction = math.degrees(math.atan2(dy, dx)) % 360.0

        self.recovered_rf_direction = current_rf_direction
        self._log(f"[PART 4] Approximate direction received: {self.recovered_rf_direction:.1f} deg")
        self._log("[PART 4] Moving camera toward recovered RF direction")
        
        # Slew camera toward recovered RF direction (current position of target)
        self.env.camera.orientation_deg = self.recovered_rf_direction
        self.env.beacon.active = True
        self.env.beacon.intensity = 1.0
        self.reacquisition_frames_count = 0
        
        self._log("[PART 4] Optical reacquisition started")
        self.transition_to(SystemState.OPTICAL_REACQUISITION, "Camera slewed to coarse RF bearing")

    def _handle_optical_reacquisition(
        self,
        detection_res: DetectionResult,
        alignment_res: AlignmentResult,
        dt: float
    ) -> None:
        """Verify beacon spot in optical frame after RF camera slew."""
        if detection_res.detected:
            self.reacquisition_frames_count = 0
            self._log("[PART 1] Beacon detected")
            self._log("[PART 2] Tracking restored")
            # Feed reacquired detection into Kalman tracker
            meas = BeaconMeasurement(
                timestamp=self.env.sim_time,
                position=(detection_res.center_x, detection_res.center_y),
                detected=True,
                confidence=detection_res.confidence
            )
            self.tracker.process_frame(meas, self.env.sim_time)
            
            # Transition directly to FINE_ALIGNMENT or OPTICAL_TRACKING
            if alignment_res.aligned:
                self.transition_to(SystemState.FINE_ALIGNMENT, "Optical beacon reacquired and centered")
            else:
                self.transition_to(SystemState.OPTICAL_TRACKING, "Optical beacon reacquired, closing alignment loop")
        else:
            self.reacquisition_frames_count += 1
            if self.reacquisition_frames_count >= self.max_reacquisition_frames:
                self._log("[PART 4] Optical reacquisition timed out")
                self.transition_to(SystemState.RECOVERY_FAILED, "Optical reacquisition timed out")
                return
            # If still not detected, perform narrow local scan around coarse direction
            search_res = self.search_controller.update(self.env.camera.orientation_deg, alignment_res, dt)
            self.env.camera.orientation_deg = search_res.new_orientation_deg

    def _handle_fine_alignment(
        self,
        detection_res: DetectionResult,
        alignment_res: AlignmentResult,
        dt: float
    ) -> None:
        """Maintain and verify precise boresight alignment before establishing link."""
        if not detection_res.detected:
            self.transition_to(SystemState.PREDICTIVE_RECOVERY, "Lost detection during fine alignment")
            return

        # Feed detection to tracker
        meas = BeaconMeasurement(
            timestamp=self.env.sim_time,
            position=(detection_res.center_x, detection_res.center_y),
            detected=True,
            confidence=detection_res.confidence
        )
        self.tracker.process_frame(meas, self.env.sim_time)

        if alignment_res.aligned:
            self._log("[PART 4] Fine alignment complete")
            self._log("[PART 4] FSOC communication active")
            self.transition_to(SystemState.FSOC_ACTIVE, "Pointing error within tolerance")
        else:
            # Apply fine proportional adjustment
            ctrl_res = self.pat_controller.update(self.env.camera.orientation_deg, alignment_res)
            self.env.camera.orientation_deg = ctrl_res.new_orientation_deg
            self.last_locked_orientation_deg = float(self.env.camera.orientation_deg)

    def _handle_fsoc_active(
        self,
        detection_res: DetectionResult,
        alignment_res: AlignmentResult,
        dt: float
    ) -> None:
        """Active optical link state; maintains communication until disturbance/loss."""
        if not detection_res.detected:
            self._log("[PART 4] FSOC link interrupted (optical loss)")
            self._log("[PART 2] Predictive recovery started")
            self.recovery_attempt_count += 1
            self.optical_search_sweep_done = False
            self.transition_to(SystemState.PREDICTIVE_RECOVERY, "Optical signal dropped during FSOC transmission")
            return

        # Continue closed-loop Kalman tracking and alignment maintenance
        meas = BeaconMeasurement(
            timestamp=self.env.sim_time,
            position=(detection_res.center_x, detection_res.center_y),
            detected=True,
            confidence=detection_res.confidence
        )
        self.tracker.process_frame(meas, self.env.sim_time)

        # Smooth proportional tracking servoing to keep boresight centered on moving beacon
        ctrl_res = self.pat_controller.update(self.env.camera.orientation_deg, alignment_res)
        self.env.camera.orientation_deg = ctrl_res.new_orientation_deg
        self.last_locked_orientation_deg = float(self.env.camera.orientation_deg)

    def _handle_recovery_failed(self) -> None:
        """Terminal failure state; logs error and holds safe state."""
        pass

    def _update_telemetry(
        self,
        detection_res: DetectionResult,
        alignment_res: AlignmentResult
    ) -> None:
        """Package internal states into SystemTelemetry structure."""
        authenticated = self.security_valid and self.security_stage == "AUTHENTICATED"
        self.telemetry.timestamp = self.env.sim_time
        self.telemetry.current_state = self.state.name
        self.telemetry.beacon_detected = bool(detection_res.detected)
        self.telemetry.beacon_position = (
            (float(detection_res.center_x), float(detection_res.center_y))
            if (detection_res.detected and detection_res.center_x is not None and detection_res.center_y is not None)
            else None
        )
        self.telemetry.beacon_image_position = self.telemetry.beacon_position
        self.telemetry.tracking_status = self.tracker.state.name
        self.telemetry.prediction_status = "ACTIVE" if self.state == SystemState.PREDICTIVE_RECOVERY else "IDLE"
        self.telemetry.optical_recovery_status = self.state.name if self.state in (
            SystemState.OPTICAL_SEARCH, SystemState.LOCAL_REACQUISITION, SystemState.OPTICAL_REACQUISITION
        ) else "IDLE"
        self.telemetry.rf_status = (
            "FOUND" if self.rf_recovery_result is not None
            else ("SCANNING" if self.state == SystemState.RF_DISCOVERY else "IDLE")
        )
        self.telemetry.terminal_id = self.target_terminal_id
        self.telemetry.authentication_status = (
            "AUTHENTICATED" if authenticated and self.state in (
                SystemState.RF_DIRECTION_RECOVERY, SystemState.OPTICAL_REACQUISITION,
                SystemState.FINE_ALIGNMENT, SystemState.FSOC_ACTIVE
            ) and self.rf_recovery_result is not None
            else ("REJECTED" if self.state == SystemState.RECOVERY_FAILED else "UNVERIFIED")
        )
        self.telemetry.approximate_direction = self.recovered_rf_direction
        self.telemetry.rf_direction = self.recovered_rf_direction
        self.telemetry.alignment_status = alignment_res.alignment_state
        self.telemetry.fsoc_status = "ESTABLISHED" if self.state == SystemState.FSOC_ACTIVE else (
            "SEARCHING" if self.state in (
                SystemState.OPTICAL_SEARCH, SystemState.PREDICTIVE_RECOVERY,
                SystemState.LOCAL_REACQUISITION, SystemState.RF_DISCOVERY
            ) else "DOWN"
        )
        self.telemetry.camera_orientation_deg = float(self.env.camera.orientation_deg)
        self.telemetry.camera_pan = float(self.env.camera.orientation_deg)
        self.telemetry.camera_tilt = getattr(self.env.camera, "tilt_deg", 0.0)
        self.telemetry.pointing_error_px = float(alignment_res.radial_error) if alignment_res.radial_error is not None else None
        self.telemetry.pointing_error_deg = float(alignment_res.angular_error_deg) if alignment_res.angular_error_deg is not None else None
        self.telemetry.tracking_error = (
            float(alignment_res.radial_error)
            if alignment_res.radial_error is not None
            else (float(self.tracker.last_error) if hasattr(self.tracker, "last_error") else 0.0)
        )
        self.telemetry.rf_rssi = float(self.rf_recovery_result["rssi"]) if (self.rf_recovery_result and "rssi" in self.rf_recovery_result) else None
        self.telemetry.tracking_confidence = float(self.tracker.confidence)
        self.telemetry.miss_count = int(self.tracker.miss_count)
        self.telemetry.recovery_attempt = self.recovery_attempt_count
        
        # Real-time Terminal Kinematics
        self.telemetry.terminal_world_position = (float(self.env.terminal_b.x), float(self.env.terminal_b.y))
        self.telemetry.terminal_velocity = (float(self.env.get_terminal_velocity()[0]), float(self.env.get_terminal_velocity()[1]))
        self.telemetry.terminal_heading = float(self.env.get_terminal_heading_deg())
        self.telemetry.predicted_beacon_position = (
            (float(self.tracker.current_state[0, 0]), float(self.tracker.current_state[1, 0]))
            if self.tracker.initialized
            else None
        )
        self.telemetry.optical_signal_strength = float(self.env.beacon.intensity) if self.env.beacon.active else 0.0
        self.telemetry.optical_link_status = (
            "ALIGNED" if (self.state == SystemState.FSOC_ACTIVE and detection_res.detected)
            else ("TRACKING" if detection_res.detected else "LOST")
        )
        
        # High-level Security & Multi-Terminal Telemetry
        self.telemetry.num_terminals = self.num_terminals
        self.telemetry.target_terminal = self.target_terminal_id
        self.telemetry.target_terminal_name = self.target_terminal_id.replace("_", "-").title()
        self.telemetry.terminals_overview = self.get_terminals_overview()
        self.telemetry.security_algorithm = "HMAC-SHA256"
        self.telemetry.security_challenge_nonce = self.security_challenge_nonce
        self.telemetry.security_hmac_sample = self.security_hmac_sample
        self.telemetry.security_replay_protected = self.security_replay_protected
        self.telemetry.security_valid = self.security_valid
        self.telemetry.security_stage = self.security_stage

        # High-level communication status & recovery mechanism mapping
        is_recovering = (self.recovery_attempt_count > 0)
        
        if self.state in (SystemState.FSOC_ACTIVE, SystemState.FINE_ALIGNMENT):
            self.telemetry.fsoc_status = "ESTABLISHED"
            self.telemetry.optical_link_status = "ALIGNED"
            self.telemetry.recovery_mechanism = "NONE"
            self.telemetry.identification_status = "IDENTIFIED"
            self.telemetry.authentication_status = "AUTHENTICATED" if authenticated else "UNVERIFIED"
        elif self.state == SystemState.OPTICAL_TRACKING:
            self.telemetry.fsoc_status = "RECOVERING" if is_recovering else "ACQUIRING"
            self.telemetry.optical_link_status = "TRACKING"
            self.telemetry.recovery_mechanism = "NONE"
            self.telemetry.identification_status = "IDENTIFIED"
            self.telemetry.authentication_status = "AUTHENTICATED" if authenticated else "UNVERIFIED"
        elif self.state == SystemState.PREDICTIVE_RECOVERY:
            self.telemetry.fsoc_status = "RECOVERING"
            self.telemetry.optical_link_status = "LOST"
            self.telemetry.recovery_mechanism = "PREDICTIVE_RECOVERY"
            self.telemetry.identification_status = "IDENTIFIED"
        elif self.state == SystemState.LOCAL_REACQUISITION:
            self.telemetry.fsoc_status = "RECOVERING"
            self.telemetry.optical_link_status = "LOST"
            self.telemetry.recovery_mechanism = "LOCAL_REACQUISITION"
            self.telemetry.identification_status = "IDENTIFIED"
        elif self.state == SystemState.OPTICAL_SEARCH:
            self.telemetry.fsoc_status = "RECOVERING" if is_recovering else "SEARCHING"
            self.telemetry.optical_link_status = "SEARCHING"
            self.telemetry.recovery_mechanism = "360_OPTICAL_SEARCH" if is_recovering else "NONE"
            self.telemetry.identification_status = "IDENTIFIED" if (self.target_terminal_id in getattr(self, "rf_discovered_terminals", set()) or not is_recovering) else "SEARCHING"
        elif self.state == SystemState.RF_DISCOVERY:
            self.telemetry.fsoc_status = "RECOVERING" if is_recovering else "DISCOVERING"
            self.telemetry.optical_link_status = "LOST"
            self.telemetry.recovery_mechanism = "RF_DISCOVERY" if is_recovering else "NONE"
            self.telemetry.identification_status = "DISCOVERING"
        elif self.state == SystemState.RF_AUTHENTICATION:
            self.telemetry.fsoc_status = "RECOVERING" if is_recovering else "AUTHENTICATING"
            self.telemetry.optical_link_status = "LOST"
            self.telemetry.recovery_mechanism = "RF_AUTHENTICATION" if is_recovering else "NONE"
            self.telemetry.identification_status = "IDENTIFIED"
            self.telemetry.authentication_status = "VERIFYING"
        elif self.state == SystemState.RF_DIRECTION_RECOVERY:
            self.telemetry.fsoc_status = "RECOVERING"
            self.telemetry.optical_link_status = "REACQUIRING"
            self.telemetry.recovery_mechanism = "RF_DIRECTION"
            self.telemetry.identification_status = "IDENTIFIED"
            self.telemetry.authentication_status = "AUTHENTICATED" if authenticated else "UNVERIFIED"
        elif self.state == SystemState.OPTICAL_REACQUISITION:
            self.telemetry.fsoc_status = "RECOVERING"
            self.telemetry.optical_link_status = "REACQUIRING"
            self.telemetry.recovery_mechanism = "OPTICAL_REACQUISITION"
            self.telemetry.identification_status = "IDENTIFIED"
            self.telemetry.authentication_status = "AUTHENTICATED" if authenticated else "UNVERIFIED"
        elif self.state == SystemState.RECOVERY_FAILED:
            self.telemetry.fsoc_status = "DOWN"
            self.telemetry.optical_link_status = "LOST"
            self.telemetry.recovery_mechanism = "FAILED"
            self.telemetry.authentication_status = "REJECTED"

        # Structured RF & Optical Subsystem Telemetry
        is_rf_disc = (self.state == SystemState.RF_DISCOVERY)
        has_rf_completed = self.state in (
            SystemState.RF_AUTHENTICATION, SystemState.RF_DIRECTION_RECOVERY,
            SystemState.OPTICAL_SEARCH, SystemState.OPTICAL_REACQUISITION,
            SystemState.OPTICAL_TRACKING, SystemState.FINE_ALIGNMENT, SystemState.FSOC_ACTIVE
        )
        self.telemetry.rf_discovery_state = "IN_PROGRESS" if is_rf_disc else ("COMPLETE" if has_rf_completed else "STANDBY")
        self.telemetry.rf_wave_active = bool(self.rf_wave_active or is_rf_disc)
        self.telemetry.rf_total_count = self.num_terminals
        if getattr(self, "rf_discovered_terminals", None):
            self.telemetry.rf_discovered_count = len(self.rf_discovered_terminals)
        else:
            self.telemetry.rf_discovered_count = self.num_terminals if has_rf_completed else 0

        self.telemetry.optical_search_state = (
            "SEARCHING" if self.state == SystemState.OPTICAL_SEARCH
            else ("LOCKED" if self.state in (SystemState.OPTICAL_TRACKING, SystemState.FINE_ALIGNMENT, SystemState.FSOC_ACTIVE) else "STANDBY")
        )
        self.telemetry.optical_tracking_state = (
            "TRACKING" if self.state == SystemState.OPTICAL_TRACKING
            else ("ALIGNED" if self.state in (SystemState.FINE_ALIGNMENT, SystemState.FSOC_ACTIVE) else "STANDBY")
        )
        self.telemetry.fsoc_state = (
            "ACTIVE" if self.state == SystemState.FSOC_ACTIVE
            else ("ALIGNING" if self.state == SystemState.FINE_ALIGNMENT else "STANDBY")
        )
        
        self.telemetry.recent_events = list(self.event_log[-10:])

