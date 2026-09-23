"""SIH Part 2: Predictive Tracking & Disturbance Handling - Final Performance Benchmark.

This standalone benchmarking script executes a deterministic, headless evaluation
of the complete Part 2 tracking pipeline:
1. Beacon ground-truth motion simulation (BeaconSimulator)
2. Optical disturbances, noise, atmospheric turbulence, occlusions, and outliers (DisturbanceSimulator)
3. Virtual Camera FOV consistency and pointing model (VirtualCamera)
4. Kalman Filter predictive tracking, gating, and state machine (KalmanBeaconTracker)
5. Bounded Local Search around Kalman prediction (LocalSearch)
6. Closed-loop Pan/Tilt Camera Controller (CameraController)

Deterministic Test Scenarios Evaluated:
- Scenario A: Normal tracking & pan/tilt acquisition slewing (Frames 0..59)
- Scenario B: Short optical loss dead-reckoning (Frames 60..72 -> PREDICTING -> REACQUIRING)
- Scenario C: Extended optical loss with local search (Frames 120..155 -> SEARCHING -> REACQUIRING)
- Scenario D: Reacquisition verification (immediate state restoration and covariance convergence)
- Scenario E: Atmospheric optical turbulence (continuous AR(1) Gauss-Markov medium turbulence)
- Scenario F: False outlier detection rejection (Frames 190..191 -> Outlier gating rejection)
- Scenario G: Deep optical loss reaching LOST state & recovery (Frames 230..295 -> LOST -> REACQUIRING)

Outputs Generated:
- Formatted console performance summary report
- Machine-readable JSON summary: results/part2_performance.json
- Per-frame telemetry CSV log: results/part2_performance.csv

Usage:
    python benchmark_part2.py
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import (
    AtmosphericTurbulenceConfig,
    BeaconSimConfig,
    CameraControllerConfig,
    DisturbanceConfig,
    KalmanConfig,
    LocalSearchConfig,
    SystemConfig,
    TrackingStateConfig,
    TurbulenceLevel,
    VirtualCameraConfig,
)
from src.beacon_simulator import BeaconSimulator
from src.camera_controller import CameraController
from src.disturbance_simulator import DisturbanceSimulator
from src.kalman_tracker import KalmanBeaconTracker
from src.local_search import LocalSearch
from src.tracking_state import TrackingState, TrackingResult, BeaconMeasurement
from src.virtual_camera import VirtualCamera


def get_benchmark_config() -> SystemConfig:
    """Create a deterministic SystemConfig designed for comprehensive Part 2 benchmark evaluation.
    
    Includes:
    - Normal tracking baseline
    - Short occlusion (13 frames: PREDICTING only)
    - Extended occlusion (36 frames: PREDICTING -> SEARCHING)
    - Outlier spikes at (1100, 100) (rejected by gating)
    - Deep occlusion (66 frames: PREDICTING -> SEARCHING -> LOST -> Reacquisition)
    - Medium atmospheric turbulence active throughout
    """
    cfg = SystemConfig()
    
    # 1. Deterministic beacon motion
    cfg.beacon = BeaconSimConfig(
        arena_width=1280,
        arena_height=720,
        start_pos=(750.0, 360.0),
        start_velocity=(2.5, 1.0),
        speed_magnitude=2.8,
        heading_noise_std=0.04,
        margin=50.0,
        random_seed=42
    )
    
    # 2. Atmospheric optical turbulence (MEDIUM severity)
    cfg.disturbance.turbulence = AtmosphericTurbulenceConfig(
        enabled=True,
        level=TurbulenceLevel.MEDIUM,
        temporal_correlation=0.88,
        std_medium=6.5,
        max_displacement_medium=18.0,
        enable_scintillation=True,
        random_seed=202
    )
    
    # 3. Scheduled occlusions and outliers for scenarios A through G
    cfg.disturbance = DisturbanceConfig(
        enable_measurement_noise=True,
        measurement_noise_std=4.0,
        enable_jitter=True,
        jitter_std=1.0,
        turbulence=cfg.disturbance.turbulence,
        enable_occlusions=True,
        occlusion_intervals=[(60, 72), (120, 155), (230, 295)],
        enable_outliers=True,
        outlier_events=[(190, (1100.0, 100.0)), (191, (1100.0, 100.0))],
        require_fov_for_detection=True,
        default_confidence=0.95,
        random_seed=101
    )
    
    # 4. Virtual Camera
    cfg.camera = VirtualCameraConfig(
        arena_width=1280,
        arena_height=720,
        initial_center=(640.0, 360.0),
        fov_width=500.0,
        fov_height=380.0
    )
    
    # 5. Camera Controller
    cfg.controller = CameraControllerConfig(
        max_pan_speed=240.0,
        max_tilt_speed=240.0,
        kp_pan=3.0,
        kp_tilt=3.0,
        deadband_px=2.5,
        enable_predictive_servo=True,
        stop_on_lost=True
    )
    
    # 6. Local Search Scanner
    cfg.search = LocalSearchConfig(
        search_start_frames=15,
        search_radius_px=140.0,
        step_size_px=45.0,
        hold_frames_per_step=4,
        max_prediction_frames=55
    )
    
    # 7. Kalman Filter
    cfg.kalman = KalmanConfig(
        dt=1.0 / 30.0,
        process_noise_std_pos=0.5,
        process_noise_std_vel=1.0,
        measurement_noise_std=4.0,
        initial_covariance_pos=10.0,
        initial_covariance_vel=100.0
    )
    
    # 8. Tracking State & Gating
    cfg.tracking = TrackingStateConfig(
        gating_threshold_px=85.0,
        search_start_frames=15,
        max_prediction_frames=55,
        confidence_decay_rate=0.02,
        confidence_recovery_rate=0.15,
        min_confidence=0.05,
        max_confidence=1.0
    )
    
    return cfg


class BenchmarkRunner:
    """Deterministic headless benchmark runner and telemetry collector for Part 2."""

    def __init__(self, config: Optional[SystemConfig] = None, total_frames: int = 400) -> None:
        """Initialize benchmark components.
        
        Args:
            config: System configuration. Defaults to deterministic benchmark config.
            total_frames: Total simulation frames to execute.
        """
        self.config = config or get_benchmark_config()
        self.total_frames = total_frames
        self.dt = self.config.kalman.dt
        self.target_fps = 1.0 / max(1e-6, self.dt)
        
        # Pipeline components
        self.beacon_sim = BeaconSimulator(self.config.beacon)
        self.disturbance_sim = DisturbanceSimulator(self.config.disturbance)
        self.camera = VirtualCamera(self.config.camera)
        self.local_search = LocalSearch(self.config.search)
        self.camera_controller = CameraController(self.camera, self.config.controller)
        self.tracker = KalmanBeaconTracker(self.config.kalman, self.config.tracking)

    def run(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Execute the deterministic simulation benchmark loop.
        
        Returns:
            Tuple containing:
            1. Consolidated summary dictionary with all performance metrics.
            2. Per-frame telemetry list for CSV export.
        """
        # Reset all components to initial states
        self.beacon_sim.reset()
        self.disturbance_sim.reset()
        self.camera.reset()
        self.local_search.reset()
        self.camera_controller.reset()
        self.tracker.reset()

        # Telemetry containers
        telemetry_rows: List[Dict[str, Any]] = []
        frame_proc_times_ms: List[float] = []
        tracking_errors: List[float] = []
        tracking_errors_by_state: Dict[str, List[float]] = {s.name: [] for s in TrackingState}
        camera_tracking_errors: List[float] = []
        controller_mode_counts: Dict[str, int] = {}

        state_counts: Dict[str, int] = {s.name: 0 for s in TrackingState}

        # Event tracking accumulators
        first_lock_frame: Optional[int] = None
        first_lock_time_s: Optional[float] = None
        locked_frames_count = 0
        detected_frames_count = 0
        outliers_injected_count = len(self.config.disturbance.outlier_events)
        outliers_rejected_count = 0
        
        detection_loss_events = 0
        local_search_activations = 0
        successful_reacquisitions = 0
        reacquisitions_from_searching = 0
        reacquisitions_from_lost = 0
        failed_searches = 0
        lost_state_entries = 0
        lost_recoveries = 0

        prev_state = TrackingState.UNINITIALIZED

        # Benchmark start timestamp (Wall-clock)
        sim_wall_start = time.perf_counter()

        for frame_idx in range(self.total_frames):
            timestamp = frame_idx * self.dt
            
            # High-resolution per-frame compute time measurement
            frame_compute_start = time.perf_counter()

            # 1. Ground truth beacon motion simulation
            ground_truth_pos = self.beacon_sim.step(self.dt)

            # 2. Disturbance simulation (turbulence, noise, occlusions, outliers)
            # Virtual camera FOV determines whether beacon is physically visible
            measurement = self.disturbance_sim.apply_disturbances(
                ground_truth_pos, timestamp, frame_idx, camera=self.camera
            )

            # 3. Kalman Filter with Outlier Rejection & State Machine
            # Tracker receives strictly optical detection data; ground truth is completely hidden.
            tracking_result = self.tracker.process_frame(measurement, timestamp)

            # 4. Local Search Waypoint Generation
            # Operates strictly around Kalman predicted position (never ground truth)
            is_searching = (tracking_result.state == TrackingState.SEARCHING)
            search_target = self.local_search.update(tracking_result.position, is_searching)

            # 5. Closed-loop Pan/Tilt Camera Controller Step
            self.camera_controller.update(
                tracking_result,
                self.dt,
                target_override=search_target if is_searching else None
            )

            frame_compute_end = time.perf_counter()
            proc_time_ms = (frame_compute_end - frame_compute_start) * 1000.0
            frame_proc_times_ms.append(proc_time_ms)

            # --- METRIC ACCUMULATION (OFFLINE EVALUATION ONLY) ---

            # State counts
            curr_state_name = tracking_result.state.name
            state_counts[curr_state_name] += 1

            # Detection count
            if measurement.detected:
                detected_frames_count += 1

            # Initial lock acquisition
            if first_lock_frame is None and tracking_result.state == TrackingState.TRACKING:
                first_lock_frame = frame_idx
                first_lock_time_s = timestamp

            # Locked frames
            if tracking_result.state in (TrackingState.TRACKING, TrackingState.REACQUIRING):
                locked_frames_count += 1

            # Outlier rejection
            if measurement.detected and not tracking_result.measurement_accepted:
                outliers_rejected_count += 1

            # State transition events
            if prev_state in (TrackingState.TRACKING, TrackingState.REACQUIRING) and tracking_result.state in (
                TrackingState.PREDICTING, TrackingState.SEARCHING, TrackingState.LOST
            ):
                detection_loss_events += 1

            if prev_state != TrackingState.SEARCHING and tracking_result.state == TrackingState.SEARCHING:
                local_search_activations += 1

            if prev_state != TrackingState.REACQUIRING and tracking_result.state == TrackingState.REACQUIRING:
                successful_reacquisitions += 1
                if prev_state == TrackingState.SEARCHING:
                    reacquisitions_from_searching += 1
                elif prev_state == TrackingState.LOST:
                    reacquisitions_from_lost += 1

            if prev_state == TrackingState.SEARCHING and tracking_result.state == TrackingState.LOST:
                failed_searches += 1

            if prev_state != TrackingState.LOST and tracking_result.state == TrackingState.LOST:
                lost_state_entries += 1

            if prev_state == TrackingState.LOST and tracking_result.state in (
                TrackingState.REACQUIRING, TrackingState.TRACKING
            ):
                lost_recoveries += 1

            # Tracking error (Kalman Track vs Ground Truth)
            err_px = math.hypot(
                tracking_result.position[0] - ground_truth_pos[0],
                tracking_result.position[1] - ground_truth_pos[1]
            )
            tracking_errors.append(err_px)
            tracking_errors_by_state[curr_state_name].append(err_px)

            # Camera pointing tracking error
            cam_center = self.camera.center
            cam_err_px = math.hypot(
                cam_center[0] - ground_truth_pos[0],
                cam_center[1] - ground_truth_pos[1]
            )
            camera_tracking_errors.append(cam_err_px)
            
            ctrl_mode = self.camera_controller.mode.name
            controller_mode_counts[ctrl_mode] = controller_mode_counts.get(ctrl_mode, 0) + 1

            # Append telemetry row for CSV logging
            telemetry_rows.append({
                "frame": frame_idx,
                "timestamp": f"{timestamp:.4f}",
                "ground_truth_x": f"{ground_truth_pos[0]:.2f}",
                "ground_truth_y": f"{ground_truth_pos[1]:.2f}",
                "measurement_x": f"{measurement.position[0]:.2f}" if measurement.position is not None else "",
                "measurement_y": f"{measurement.position[1]:.2f}" if measurement.position is not None else "",
                "kalman_x": f"{tracking_result.position[0]:.2f}",
                "kalman_y": f"{tracking_result.position[1]:.2f}",
                "tracking_error": f"{err_px:.2f}",
                "state": curr_state_name,
                "confidence": f"{tracking_result.confidence:.2f}",
                "camera_x": f"{cam_center[0]:.2f}",
                "camera_y": f"{cam_center[1]:.2f}",
                "detection": "True" if measurement.detected else "False",
                "measurement_accepted": "True" if tracking_result.measurement_accepted else "False",
                "local_search_active": "True" if is_searching else "False",
                "processing_time_ms": f"{proc_time_ms:.4f}"
            })

            prev_state = tracking_result.state

        sim_wall_end = time.perf_counter()
        total_wall_duration_s = max(1e-6, sim_wall_end - sim_wall_start)
        actual_fps = self.total_frames / total_wall_duration_s
        virtual_duration_s = self.total_frames * self.dt

        # Statistical calculations
        post_lock_frames = self.total_frames - (first_lock_frame or 0)
        lock_retention_pct = (locked_frames_count / max(1, post_lock_frames)) * 100.0
        detection_availability_pct = (detected_frames_count / max(1, self.total_frames)) * 100.0

        avg_proc_time_ms = float(np.mean(frame_proc_times_ms))
        max_proc_time_ms = float(np.max(frame_proc_times_ms))
        min_proc_time_ms = float(np.min(frame_proc_times_ms))
        median_proc_time_ms = float(np.median(frame_proc_times_ms))
        p95_proc_time_ms = float(np.percentile(frame_proc_times_ms, 95))
        p99_proc_time_ms = float(np.percentile(frame_proc_times_ms, 99))
        std_proc_time_ms = float(np.std(frame_proc_times_ms))

        avg_tracking_err = float(np.mean(tracking_errors))
        max_tracking_err = float(np.max(tracking_errors))
        min_tracking_err = float(np.min(tracking_errors))
        std_tracking_err = float(np.std(tracking_errors))

        # Error breakdown by state
        err_tracking_mode = float(np.mean(tracking_errors_by_state["TRACKING"])) if tracking_errors_by_state["TRACKING"] else 0.0
        err_predicting_mode = float(np.mean(tracking_errors_by_state["PREDICTING"])) if tracking_errors_by_state["PREDICTING"] else 0.0
        err_searching_mode = float(np.mean(tracking_errors_by_state["SEARCHING"])) if tracking_errors_by_state["SEARCHING"] else 0.0
        err_lost_mode = float(np.mean(tracking_errors_by_state["LOST"])) if tracking_errors_by_state["LOST"] else 0.0

        avg_cam_err = float(np.mean(camera_tracking_errors))
        max_cam_err = float(np.max(camera_tracking_errors))

        # Validation Checks
        validation_checks = [
            {
                "name": "Frame Count Integrity",
                "passed": len(telemetry_rows) == self.total_frames,
                "details": f"{len(telemetry_rows)} / {self.total_frames} frames processed"
            },
            {
                "name": "State Distribution Sum",
                "passed": sum(state_counts.values()) == self.total_frames,
                "details": f"Sum of state counts ({sum(state_counts.values())}) == total frames ({self.total_frames})"
            },
            {
                "name": "Metrics Numeric Validity",
                "passed": not (
                    math.isnan(actual_fps) or math.isnan(avg_tracking_err) or
                    math.isnan(avg_proc_time_ms) or math.isnan(lock_retention_pct)
                ),
                "details": "All computed performance metrics are strictly finite numbers"
            },
            {
                "name": "Initial Lock Acquisition",
                "passed": first_lock_frame is not None and first_lock_frame <= 2,
                "details": f"Initial TRACKING lock acquired at frame #{first_lock_frame}"
            },
            {
                "name": "Short Detection-Loss Handling",
                "passed": state_counts["PREDICTING"] > 0 and successful_reacquisitions >= 1,
                "details": f"PREDICTING state entered ({state_counts['PREDICTING']} frames) and reacquired"
            },
            {
                "name": "Local Search Activation",
                "passed": local_search_activations > 0 and state_counts["SEARCHING"] > 0,
                "details": f"Local search activated ({local_search_activations} times, {state_counts['SEARCHING']} frames in SEARCHING)"
            },
            {
                "name": "Local Search Reacquisition",
                "passed": reacquisitions_from_searching > 0,
                "details": f"{reacquisitions_from_searching} successful reacquisitions from bounded local search"
            },
            {
                "name": "LOST State Entry & Reacquisition",
                "passed": state_counts["LOST"] > 0 and lost_recoveries > 0,
                "details": f"LOST state entered ({state_counts['LOST']} frames) and successfully recovered ({lost_recoveries} times)"
            },
            {
                "name": "Outlier Rejection Gating",
                "passed": outliers_rejected_count >= outliers_injected_count,
                "details": f"{outliers_rejected_count} / {outliers_injected_count} injected false outliers rejected by gating"
            },
            {
                "name": "Tracking Accuracy in Locked State",
                "passed": err_tracking_mode < 15.0,
                "details": f"Average error in TRACKING state: {err_tracking_mode:.2f} px (under medium turbulence)"
            }
        ]

        overall_passed = all(c["passed"] for c in validation_checks)

        summary: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "benchmark_name": "SIH Part 2 - Predictive Tracking & Disturbance Handling",
            "validation_verdict": "PASS" if overall_passed else "FAIL",
            "simulation": {
                "total_frames": self.total_frames,
                "virtual_duration_s": virtual_duration_s,
                "wall_clock_duration_s": total_wall_duration_s,
                "target_fps": self.target_fps,
                "actual_fps": actual_fps,
            },
            "processing_time_ms": {
                "mean": avg_proc_time_ms,
                "max": max_proc_time_ms,
                "min": min_proc_time_ms,
                "median": median_proc_time_ms,
                "p95": p95_proc_time_ms,
                "p99": p99_proc_time_ms,
                "std": std_proc_time_ms,
            },
            "tracking_accuracy_px": {
                "mean_overall": avg_tracking_err,
                "max_overall": max_tracking_err,
                "min_overall": min_tracking_err,
                "std_overall": std_tracking_err,
                "mean_in_tracking": err_tracking_mode,
                "mean_in_predicting": err_predicting_mode,
                "mean_in_searching": err_searching_mode,
                "mean_in_lost": err_lost_mode,
            },
            "lock_retention": {
                "lock_retention_pct": lock_retention_pct,
                "first_lock_frame": first_lock_frame,
                "first_lock_time_s": first_lock_time_s,
                "locked_frames": locked_frames_count,
                "post_lock_frames": post_lock_frames,
            },
            "detection_availability": {
                "availability_pct": detection_availability_pct,
                "detected_frames": detected_frames_count,
                "occluded_or_outside_fov_frames": self.total_frames - detected_frames_count,
            },
            "state_distribution": state_counts,
            "recovery_events": {
                "detection_loss_events": detection_loss_events,
                "local_search_activations": local_search_activations,
                "successful_reacquisitions": successful_reacquisitions,
                "reacquisitions_from_searching": reacquisitions_from_searching,
                "reacquisitions_from_lost": reacquisitions_from_lost,
                "failed_searches": failed_searches,
                "lost_state_entries": lost_state_entries,
                "lost_recoveries": lost_recoveries,
            },
            "robustness": {
                "outliers_injected": outliers_injected_count,
                "outliers_rejected": outliers_rejected_count,
                "atmospheric_turbulence_level": self.config.disturbance.turbulence.level.value,
                "atmospheric_turbulence_std_px": self.config.disturbance.turbulence.std_medium,
                "measurement_noise_std_px": self.config.disturbance.measurement_noise_std,
                "camera_jitter_std_px": self.config.disturbance.jitter_std,
            },
            "camera_controller": {
                "mean_camera_tracking_error_px": avg_cam_err,
                "max_camera_tracking_error_px": max_cam_err,
                "mode_distribution": controller_mode_counts,
            },
            "configuration": {
                "beacon_start_pos": list(self.config.beacon.start_pos),
                "beacon_velocity": list(self.config.beacon.start_velocity),
                "beacon_random_seed": self.config.beacon.random_seed,
                "disturbance_random_seed": self.config.disturbance.random_seed,
                "turbulence_random_seed": self.config.disturbance.turbulence.random_seed,
                "occlusion_intervals": self.config.disturbance.occlusion_intervals,
                "outlier_events": [list(item) for item in self.config.disturbance.outlier_events],
                "gating_threshold_px": self.config.tracking.gating_threshold_px,
                "search_start_frames": self.config.tracking.search_start_frames,
                "search_radius_px": self.config.search.search_radius_px,
                "max_prediction_frames": self.config.tracking.max_prediction_frames,
                "camera_fov": [self.config.camera.fov_width, self.config.camera.fov_height],
            },
            "validation_checks": validation_checks,
        }

        return summary, telemetry_rows


def print_benchmark_report(summary: Dict[str, Any]) -> None:
    """Print the structured console report matching the SIH benchmark specification.
    
    Args:
        summary: Benchmark summary metrics dictionary.
    """
    sim = summary["simulation"]
    proc = summary["processing_time_ms"]
    trk = summary["tracking_accuracy_px"]
    lock = summary["lock_retention"]
    det = summary["detection_availability"]
    states = summary["state_distribution"]
    rec = summary["recovery_events"]
    rob = summary["robustness"]
    total_f = sim["total_frames"]

    print("=" * 60)
    print("SIH PART 2 — PREDICTIVE TRACKING PERFORMANCE BENCHMARK")
    print("=" * 60)
    print("")
    print("Simulation:")
    print(f"  Frames:                  {sim['total_frames']}")
    print(f"  Duration:                {sim['virtual_duration_s']:.2f} s (Simulated) | {sim['wall_clock_duration_s']:.4f} s (Wall-clock)")
    print(f"  Target FPS:              {sim['target_fps']:.1f} FPS")
    print(f"  Actual FPS:              {sim['actual_fps']:.1f} FPS (Throughput: {sim['actual_fps']:,.0f} frames/sec)")
    print("")
    print("Processing:")
    print(f"  Average frame time:      {proc['mean']:.4f} ms")
    print(f"  Maximum frame time:      {proc['max']:.4f} ms")
    print("")
    print("Tracking:")
    print(f"  Average tracking error:  {trk['mean_overall']:.2f} px (Locked state: {trk['mean_in_tracking']:.2f} px)")
    print(f"  Maximum tracking error:  {trk['max_overall']:.2f} px")
    print(f"  Lock retention:          {lock['lock_retention_pct']:.1f}%")
    print(f"  Detection availability:  {det['availability_pct']:.1f}%")
    print("")
    print("State distribution:")
    print(f"  TRACKING:                {states.get('TRACKING', 0):3d} frames ({states.get('TRACKING', 0)/total_f*100:5.1f}%)")
    print(f"  PREDICTING:              {states.get('PREDICTING', 0):3d} frames ({states.get('PREDICTING', 0)/total_f*100:5.1f}%)")
    print(f"  SEARCHING:               {states.get('SEARCHING', 0):3d} frames ({states.get('SEARCHING', 0)/total_f*100:5.1f}%)")
    print(f"  REACQUIRING:             {states.get('REACQUIRING', 0):3d} frames ({states.get('REACQUIRING', 0)/total_f*100:5.1f}%)")
    print(f"  LOST:                    {states.get('LOST', 0):3d} frames ({states.get('LOST', 0)/total_f*100:5.1f}%)")
    print("")
    print("Recovery:")
    print(f"  Detection-loss events:   {rec['detection_loss_events']}")
    print(f"  Local-search activations:{rec['local_search_activations']}")
    print(f"  Successful reacquisitions: {rec['successful_reacquisitions']} (From Search: {rec['reacquisitions_from_searching']}, From Lost: {rec['reacquisitions_from_lost']})")
    print(f"  Failed searches:         {rec['failed_searches']}")
    print(f"  LOST recoveries:         {rec['lost_recoveries']}")
    print("")
    print("Robustness:")
    print(f"  Outliers injected:       {rob['outliers_injected']}")
    print(f"  Outliers rejected:       {rob['outliers_rejected']}")
    print(f"  Atmospheric turbulence:  Level={rob['atmospheric_turbulence_level']} (std={rob['atmospheric_turbulence_std_px']:.1f} px)")
    print(f"  Camera disturbance:      Noise std={rob['measurement_noise_std_px']:.1f} px, Jitter std={rob['camera_jitter_std_px']:.1f} px")
    print("")
    print("=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    print("")
    print("Validation Summary:")
    for check in summary["validation_checks"]:
        mark = "[PASS]" if check["passed"] else "[FAIL]"
        print(f"  {mark:6s} {check['name']:32s}: {check['details']}")
    print("-" * 60)
    print(f"Overall Verdict: {summary['validation_verdict']}")
    print("=" * 60)


def save_results(
    summary: Dict[str, Any],
    telemetry_rows: List[Dict[str, Any]],
    json_path: str = "results/part2_performance.json",
    csv_path: str = "results/part2_performance.csv"
) -> None:
    """Save benchmark results to JSON and CSV files.
    
    Args:
        summary: Summary metrics dictionary.
        telemetry_rows: Per-frame telemetry records.
        json_path: Destination JSON file path.
        csv_path: Destination CSV file path.
    """
    # Create results directory automatically if it does not exist
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)

    # 1. Save JSON summary
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[Output] Performance summary saved to: {json_path}")

    # 2. Save CSV telemetry
    csv_fieldnames = [
        "frame",
        "timestamp",
        "ground_truth_x",
        "ground_truth_y",
        "measurement_x",
        "measurement_y",
        "kalman_x",
        "kalman_y",
        "tracking_error",
        "state",
        "confidence",
        "camera_x",
        "camera_y",
        "detection",
        "measurement_accepted",
        "local_search_active",
        "processing_time_ms"
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
        writer.writeheader()
        writer.writerows(telemetry_rows)
    print(f"[Output] Per-frame telemetry saved to:  {csv_path}")


def main() -> int:
    """CLI entry point for running Part 2 benchmark."""
    parser = argparse.ArgumentParser(
        description="SIH Part 2 - Predictive Tracking & Disturbance Handling Performance Benchmark"
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=400,
        help="Number of simulation frames to run (default: 400)"
    )
    parser.add_argument(
        "--json-output",
        type=str,
        default="results/part2_performance.json",
        help="Output JSON summary path (default: results/part2_performance.json)"
    )
    parser.add_argument(
        "--csv-output",
        type=str,
        default="results/part2_performance.csv",
        help="Output CSV telemetry path (default: results/part2_performance.csv)"
    )
    args = parser.parse_args()

    config = get_benchmark_config()
    runner = BenchmarkRunner(config=config, total_frames=args.frames)
    
    summary, telemetry = runner.run()
    
    print_benchmark_report(summary)
    save_results(summary, telemetry, json_path=args.json_output, csv_path=args.csv_output)

    return 0 if summary["validation_verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
