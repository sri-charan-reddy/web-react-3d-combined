"""Main entry point and standalone demonstration script for Part 2.

This script coordinates:
1. Beacon ground-truth motion simulation (BeaconSimulator).
2. Optical disturbance, measurement noise, occlusions, and outlier injection (DisturbanceSimulator).
3. Virtual Camera Model (VirtualCamera).
4. Kalman-filter-based predictive tracking and recovery state machine (KalmanBeaconTracker).
5. Bounded Local Search around Kalman prediction (LocalSearch).
6. Closed-loop Camera Pan/Tilt Movement Controller (CameraController).
7. Real-time OpenCV visualization displaying:
   - GREEN: Ground Truth (GT)
   - YELLOW: Optical Measurements (MEAS)
   - RED MARKER: Rejected Outlier Measurements
   - BLUE: Kalman Predicted / Corrected Track
   - SLATE RECTANGLE: Moving Virtual Camera Field of View (FOV)
   - CYAN/GOLD CIRCLE & WAYPOINTS: Bounded Local Search Scan Pattern
   - Comprehensive HUD telemetry (State, Confidence, Miss Count, Local Search & Pan/Tilt Status).

Demonstration Scenarios Covered:
- Scenario A: Initial Pan/Tilt Acquisition & Tracking (camera slews from center (640,360) to beacon (750,360))
- Scenario B: Short detection loss (PREDICTING -> Camera continues predictive pan/tilt servoing)
- Scenario C: Extended detection loss (PREDICTING -> SEARCHING: Local search scans bounded region around Kalman prediction -> REACQUIRING)
- Scenario D: False/far detection rejection (OUTLIER REJECTED, Camera does not jump)

Usage:
    python main.py
"""

import os
import sys
import time

# Automatically re-execute within local .venv if running with system Python
_venv_python = os.path.abspath(os.path.join(os.path.dirname(__file__), ".venv", "bin", "python3"))
if os.path.exists(_venv_python) and sys.executable != _venv_python:
    try:
        import cv2, yaml, numpy  # test if current python already has required packages
    except ImportError:
        os.execv(_venv_python, [_venv_python] + sys.argv)

from config import DEFAULT_CONFIG, SystemConfig


def run_demonstration(config: SystemConfig = DEFAULT_CONFIG) -> None:
    """Run the live predictive tracking, local search, turbulence, and camera control demonstration loop.
    
    Args:
        config: System configuration settings.
    """
    try:
        import cv2
        from src.beacon_simulator import BeaconSimulator
        from src.disturbance_simulator import DisturbanceSimulator
        from src.virtual_camera import VirtualCamera
        from src.camera_controller import CameraController
        from src.local_search import LocalSearch
        from src.kalman_tracker import KalmanBeaconTracker
        from src.tracking_state import TrackingState, PerformanceTracker
        from src.visualizer import TrackingVisualizer
    except ImportError as e:
        print(f"[ERROR] Required dependency missing: {e}")
        print("Please install requirements using: pip install -r requirements.txt")
        sys.exit(1)

    print("=" * 78)
    print("SIH Part 2: Predictive Tracking, Turbulence Simulation & Camera Control")
    print("=" * 78)
    print("Scenarios Scheduled:")
    print("  - Frames   0.. 59: Pan/Tilt Slew & Acquisition [TRACKING_SERVO]")
    print("  - Frames  60.. 80: Short occlusion [PREDICTIVE_SERVO -> REACQUIRING]")
    print("  - Frames 150..195: Extended occlusion [PREDICTING -> SEARCHING (Local Search) -> REACQUIRING]")
    print("  - Frames 290..291: Far outlier at (1100, 100) [REJECTED, Camera Stable]")
    print("-" * 78)
    print("Interactive Controls:")
    print("  [SPACE]  - Pause / Resume simulation")
    print("  [T]      - Toggle / Cycle Atmospheric Turbulence (OFF -> LOW -> MED -> HIGH)")
    print("  [F]      - Inject a 60-frame (~2 sec) false outlier at (1100, 100)")
    print("  [R]      - Reset simulation, camera, search, and tracker to initial state")
    print("  [Q/ESC]  - Quit demonstration")
    print("=" * 78)
    
    beacon_sim = BeaconSimulator(config.beacon)
    disturbance_sim = DisturbanceSimulator(config.disturbance)
    camera = VirtualCamera(config.camera)
    local_search = LocalSearch(config.search)
    camera_controller = CameraController(camera, config.controller)
    tracker = KalmanBeaconTracker(config.kalman, config.tracking)
    perf_tracker = PerformanceTracker()
    visualizer = TrackingVisualizer(config.visualizer)
    
    window_name = config.visualizer.window_name
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    
    frame_idx = 0
    fps = config.visualizer.fps
    dt = 1.0 / max(1, fps)
    paused = False
    
    prev_time = time.time()
    actual_fps = float(fps)
    last_metrics = None
    
    try:
        while True:
            loop_start = time.time()
            
            if not paused:
                timestamp = frame_idx * dt
                
                # 1. Ground truth beacon motion simulation
                ground_truth_pos = beacon_sim.step(dt)
                
                # 2. Disturbance simulation (atmospheric turbulence, noise, scheduled occlusions, outliers)
                # Virtual camera FOV determines whether beacon is visible to the optical detector
                measurement = disturbance_sim.apply_disturbances(ground_truth_pos, timestamp, frame_idx, camera=camera)
                
                # 3. Kalman Filter with Outlier Rejection & State Machine (PREDICTING -> SEARCHING -> LOST)
                # Tracker receives strictly optical detection data; ground truth is completely hidden.
                tracking_result = tracker.process_frame(measurement, timestamp)
                
                # 4. Local Search Waypoint Generation
                # Operates around the CURRENT KALMAN PREDICTED POSITION (never ground truth)
                is_searching = (tracking_result.state == TrackingState.SEARCHING)
                search_target = local_search.update(tracking_result.position, is_searching)
                
                # 5. Closed-loop Pan/Tilt Camera Controller Step
                # Steers camera toward search target during SEARCHING, or Kalman track during TRACKING/PREDICTING
                camera_controller.update(
                    tracking_result,
                    dt,
                    target_override=search_target if is_searching else None
                )
                
                # Record loop compute time
                compute_time_s = time.time() - loop_start
                
                # 6. Update Performance Metrics
                metrics = perf_tracker.update(
                    ground_truth=ground_truth_pos,
                    measurement=measurement,
                    tracking_result=tracking_result,
                    frame_idx=frame_idx,
                    timestamp=timestamp,
                    frame_compute_time_s=compute_time_s
                )
                last_metrics = metrics
                
                # 7. Render visual frame
                canvas = visualizer.render_frame(
                    ground_truth=ground_truth_pos,
                    measurement=measurement,
                    tracking_result=tracking_result,
                    frame_idx=frame_idx,
                    fps_display=actual_fps,
                    camera=camera,
                    controller=camera_controller,
                    search=local_search,
                    turbulence=disturbance_sim.turbulence,
                    metrics=metrics
                )
                
                cv2.imshow(window_name, canvas)
                frame_idx += 1
            else:
                # Paused loop
                key = cv2.waitKey(30) & 0xFF
                if key in (ord('q'), ord('Q'), 27):
                    break
                elif key == ord(' '):
                    paused = False
                elif key in (ord('t'), ord('T')):
                    new_lvl = disturbance_sim.turbulence.toggle_level()
                    print(f"[Frame {frame_idx}] Atmospheric turbulence level changed to: {new_lvl.value}")
                elif key in (ord('f'), ord('F')):
                    disturbance_sim.trigger_manual_outlier((1100.0, 100.0), duration_frames=60)
                    print(f"[Frame {frame_idx}] Manual outlier triggered at (1100.0, 100.0) for 60 frames (~2 sec).")
                elif key in (ord('r'), ord('R')):
                    beacon_sim.reset()
                    disturbance_sim.reset()
                    camera.reset()
                    local_search.reset()
                    camera_controller.reset()
                    tracker.reset()
                    perf_tracker.reset()
                    visualizer.reset()
                    frame_idx = 0
                    paused = False
                continue
            
            # Telemetry FPS calculation
            curr_time = time.time()
            elapsed = curr_time - prev_time
            if elapsed > 0:
                actual_fps = 0.9 * actual_fps + 0.1 * (1.0 / elapsed)
            prev_time = curr_time
            
            # Frame timing
            compute_time = curr_time - loop_start
            wait_ms = max(1, int((dt - compute_time) * 1000))
            
            key = cv2.waitKey(wait_ms) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                print("Exit requested by user.")
                break
            elif key == ord(' '):
                paused = True
            elif key in (ord('t'), ord('T')):
                new_lvl = disturbance_sim.turbulence.toggle_level()
                print(f"[Frame {frame_idx}] Atmospheric turbulence level changed to: {new_lvl.value}")
            elif key in (ord('f'), ord('F')):
                disturbance_sim.trigger_manual_outlier((1100.0, 100.0), duration_frames=60)
                print(f"[Frame {frame_idx}] Manual outlier triggered at (1100.0, 100.0) for 60 frames (~2 sec).")
            elif key in (ord('r'), ord('R')):
                beacon_sim.reset()
                disturbance_sim.reset()
                camera.reset()
                local_search.reset()
                camera_controller.reset()
                tracker.reset()
                perf_tracker.reset()
                visualizer.reset()
                frame_idx = 0

    finally:
        cv2.destroyAllWindows()
        print("\n" + "=" * 78)
        print("SIH PART 2: FINAL TRACKING PERFORMANCE SUMMARY")
        print("=" * 78)
        if last_metrics is not None:
            print(f"  Simulation Duration:       {last_metrics.simulation_duration:.2f} s ({last_metrics.total_frames} frames)")
            print(f"  Average Frame Rate:        {last_metrics.avg_fps:.1f} FPS")
            print(f"  Initial Lock Time:         {last_metrics.acquisition_time_s:.2f} s (Frame #{last_metrics.acquisition_frame})")
            print(f"  Average Tracking Error:    {last_metrics.avg_tracking_error_px:.2f} px")
            print(f"  Maximum Tracking Error:    {last_metrics.max_tracking_error_px:.2f} px")
            print(f"  Track Lock Retention:      {last_metrics.lock_retention_pct:.1f}%")
            print(f"  Average Processing Time:   {last_metrics.avg_processing_time_ms:.3f} ms / frame")
            print(f"  Temporary Loss Intervals:  {last_metrics.occlusion_count}")
            print(f"  Successful Reacquisitions: {last_metrics.reacquisition_count}")
            print(f"  Rejected False Outliers:   {last_metrics.rejected_outlier_count}")
        print("=" * 78)
        print("Demonstration ended successfully.")


def main() -> None:
    """CLI entry point supporting all Team Raynex FSOC PAT subsystems."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Team Raynex FSOC Pointing, Acquisition and Tracking (PAT) System"
    )
    parser.add_argument(
        "--part",
        type=str,
        default="4",
        choices=["1", "2", "3", "4", "gui", "dashboard", "benchmark", "test", "all-tests"],
        help="Subsystem to execute: '4' (Part 4 Console Orchestrator - default), 'gui'/'dashboard' (Web Mission Control UI), '1' (Part 1 Virtual PAT), '2' (Part 2 Predictive Tracking), '3' (Part 3 RF Discovery), 'benchmark', 'test' (Integration Test Suite)",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch the Interactive Web Mission Control Dashboard",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="deep-loss",
        choices=["normal", "temporary-loss", "deep-loss", "rogue-auth"],
        help="Operational scenario for Part 4: 'normal', 'temporary-loss', 'deep-loss', 'rogue-auth' (default: 'deep-loss')",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=90,
        help="Maximum simulation frames for Part 4 (default: 90)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run Part 4 without console sleep delay",
    )

    args = parser.parse_args()

    if args.dashboard or args.part in ("gui", "dashboard"):
        print("[LAUNCHER] Launching Team Raynex FSOC Mission Control Web Dashboard...")
        from run_dashboard import main as run_dashboard_main
        run_dashboard_main()
    elif args.part == "4":
        print("[LAUNCHER] Launching Part 4: Autonomous Adaptive Recovery Orchestrator...")
        from run_part4 import run_orchestration
        delay = 0.0 if args.fast else 0.03
        run_orchestration(scenario=args.scenario, max_steps=args.steps, delay=delay)
    elif args.part == "1":
        print("[LAUNCHER] Launching Part 1: Virtual FSOC PAT Environment & Detection...")
        from run_part1 import run_part1_main
        run_part1_main()
    elif args.part == "2":
        try:
            run_demonstration()
        except KeyboardInterrupt:
            print("\nDemonstration interrupted by user.")
            sys.exit(0)
    elif args.part == "3":
        print("[LAUNCHER] Launching Part 3: RF Discovery & Authentication Suite...")
        from run_part3 import run_all_tests
        run_all_tests()
    elif args.part == "test":
        print("[LAUNCHER] Launching Part 4 Integration Test Suite...")
        from tests.test_part4_integration import run_all_tests
        run_all_tests()
    elif args.part == "all-tests":
        print("[LAUNCHER] Launching Master Quality & Test Evaluation Suite (All 56 Tests)...")
        from run_all_tests import main as run_master_suite
        sys.exit(run_master_suite(argv=[]))
    elif args.part == "benchmark":
        print("[LAUNCHER] Launching Part 2 Performance Benchmark...")
        import subprocess
        subprocess.run([sys.executable, "benchmark_part2.py"], check=True)


if __name__ == "__main__":
    main()


