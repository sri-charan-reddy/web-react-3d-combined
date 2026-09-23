"""Main Application Entry Point for FSOC PAT System Phase 1.

Usage:
    python src/main.py
"""

import os
import sys
import time
import yaml
import cv2

# Add src directory to system path for robust module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.simulation.environment import FSOCEnvironment
from src.simulation.camera import VirtualCameraSensor
from src.visualization.renderer import EnvironmentRenderer
from src.detection.beacon_detector import ClassicalBeaconDetector
from src.detection.alignment import AlignmentCalculator
from src.control.pat_controller import VirtualPATController
from src.control.search import SearchController


def load_config(config_path: str) -> dict:
    """Loads YAML configuration file."""
    if not os.path.exists(config_path):
        print(f"[ERROR] Config file not found at: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as exc:
            print(f"[ERROR] Failed to parse config YAML: {exc}")
            sys.exit(1)


def main() -> None:
    """Executes FSOC PAT simulation rendering loop."""
    print("=" * 65)
    print(" Free-Space Optical Communication (FSOC) PAT System")
    print(" Part 1: Closed-Loop PAT Control & 360-Degree Acquisition Search")
    print("=" * 65)

    # 1. Resolve config path relative to project root
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(root_dir, "config", "config.yaml")
    
    print(f"[INFO] Loading configuration from: {config_path}")
    config = load_config(config_path)

    # 2. Instantiate Environment, Camera Sensor, Perception, Controllers & Renderer
    env = FSOCEnvironment(config)
    camera_sensor = VirtualCameraSensor(env.camera)
    
    det_cfg = config.get("detection", {})
    detector = ClassicalBeaconDetector(
        intensity_threshold=det_cfg.get("intensity_threshold", 160),
        min_area=det_cfg.get("min_area", 4.0),
        max_area=det_cfg.get("max_area", 5000.0),
        min_peak_brightness=det_cfg.get("min_peak_brightness", 180)
    )

    align_cfg = config.get("alignment", {})
    alignment_calc = AlignmentCalculator(
        image_width=env.camera.image_width,
        image_height=env.camera.image_height,
        fov_deg=env.camera.fov_deg,
        tolerance_px=align_cfg.get("tolerance_px", 15.0)
    )

    ctrl_cfg = config.get("control", {})
    controller = VirtualPATController(
        kp=ctrl_cfg.get("kp", 0.15),
        max_step_deg=ctrl_cfg.get("max_step_deg", 1.0),
        enabled=ctrl_cfg.get("enabled", True)
    )

    search_cfg = config.get("search", {})
    search_ctrl = SearchController(
        search_speed_deg_per_sec=search_cfg.get("search_speed_deg_per_sec", 30.0),
        max_sweep_deg=search_cfg.get("max_sweep_deg", 360.0),
        enabled=search_cfg.get("enabled", True)
    )

    renderer = EnvironmentRenderer(env, window_name="FSOC PAT System - Part 1")

    print(f"[INFO] Initialized {env}")
    print(f"[INFO] Local Terminal A at ({env.terminal_a.x}, {env.terminal_a.y})")
    print(f"[INFO] Remote Terminal B at ({env.terminal_b.x}, {env.terminal_b.y})")
    print(f"[INFO] Camera Angle: {env.camera.orientation_deg}° | FOV: {env.camera.fov_deg}°")
    print(f"[INFO] Alignment Calculator Initialized (Tolerance: {alignment_calc.tolerance_px:.1f} px).")
    print(f"[INFO] Virtual PAT Controller Initialized (kp={controller.kp}, max_step={controller.max_step_deg}°).")
    print(f"[INFO] 360° Search Controller Initialized (speed={search_ctrl.search_speed}°/s, max_sweep={search_ctrl.max_sweep_deg}°).")
    print("[INFO] Starting OpenCV render loop. Press 'Q' or 'ESC' in window to exit.")
    print("-" * 65)

    # 3. Main Closed-Loop Rendering Loop & Preview Windows
    window_title = "FSOC PAT System - Part 1: Environment & Control"
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow(window_title, env.width, env.height)

    cam_window_title = "VIRTUAL CAMERA IMAGE"
    cv2.namedWindow(cam_window_title, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow(cam_window_title, 640, 360)

    last_time = time.time()
    frame_delay = max(1, env.frame_delay_ms)

    try:
        while True:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            # a. Update simulation state
            env.update(dt)

            # b. Generate Virtual Camera Image
            camera_frame = camera_sensor.capture_frame(env.beacon)

            # c. Detect beacon spot from camera image
            detection_res = detector.detect(camera_frame)

            # d. Calculate boresight alignment error
            alignment_res = alignment_calc.calculate(detection_res)

            # e. Controller Priority Selection (360° Search vs Virtual PAT Tracking)
            search_res = search_ctrl.update(env.camera.orientation_deg, alignment_res, dt)

            if not alignment_res.detected:
                # Beacon is LOST -> SearchController controls camera orientation
                applied_orientation = search_res.new_orientation_deg
                cmd_delta = search_res.delta_orientation_deg
                system_mode = search_res.mode
            else:
                # Beacon is DETECTED -> VirtualPATController controls camera orientation
                ctrl_res = controller.update(env.camera.orientation_deg, alignment_res)
                applied_orientation = ctrl_res.new_orientation_deg
                cmd_delta = ctrl_res.delta_orientation_deg
                system_mode = "ALIGNED" if alignment_res.aligned else "TRACKING"

            # f. Apply selected controller output to update camera orientation
            env.camera.orientation_deg = applied_orientation

            # g. Prepare annotated camera preview frame with telemetry HUD
            cam_preview = camera_frame.copy()
            if detection_res.detected and detection_res.center_x is not None and detection_res.center_y is not None:
                cx, cy = int(round(detection_res.center_x)), int(round(detection_res.center_y))
                r = int(round(max(6, detection_res.radius)))
                
                # Color code reticle: Green for ALIGNED, Amber for TRACKING/MISALIGNED
                color = (0, 255, 0) if alignment_res.aligned else (0, 165, 255)
                
                cv2.circle(cam_preview, (cx, cy), r + 4, color, 1, cv2.LINE_AA)
                cv2.line(cam_preview, (cx - 10, cy), (cx + 10, cy), color, 1, cv2.LINE_AA)
                cv2.line(cam_preview, (cx, cy - 10), (cx, cy + 10), color, 1, cv2.LINE_AA)

            # Telemetry HUD Box Overlay on Camera Preview Window
            box_x, box_y, box_w, box_h = 12, 12, 340, 145
            overlay = cam_preview.copy()
            cv2.rectangle(overlay, (box_x, box_y), (box_x + box_w, box_y + box_h), (25, 20, 15), -1)
            cv2.addWeighted(overlay, 0.75, cam_preview, 0.25, 0, cam_preview)
            cv2.rectangle(cam_preview, (box_x, box_y), (box_x + box_w, box_y + box_h), (70, 60, 45), 1)

            # Format HUD lines according to requirements
            err_x_str = f"{alignment_res.error_x:+.1f} px" if alignment_res.error_x is not None else "N/A"
            err_y_str = f"{alignment_res.error_y:+.1f} px" if alignment_res.error_y is not None else "N/A"
            ang_err_str = f"{alignment_res.angular_error_deg:+.2f} deg" if alignment_res.angular_error_deg is not None else "N/A"
            cmd_str = f"{cmd_delta:+.2f} deg"
            cam_angle_str = f"{env.camera.orientation_deg:.2f} deg"
            sweep_str = f"{search_res.swept_angle_deg:.1f} deg"

            hud_lines = [
                f"MODE          : {system_mode}",
                f"SEARCH SWEEP  : {sweep_str}",
                f"SEARCH CMD    : {cmd_str}",
                f"ERROR X / Y   : {err_x_str}, {err_y_str}",
                f"ANGULAR ERROR : {ang_err_str}",
                f"CAMERA ANGLE  : {cam_angle_str}"
            ]

            mode_color = (0, 255, 0) if system_mode == "ALIGNED" else ((0, 165, 255) if system_mode == "TRACKING" else (0, 220, 255) if system_mode == "SEARCHING" else (0, 0, 255))
            
            for idx, text in enumerate(hud_lines):
                c = mode_color if idx == 0 else (240, 240, 240)
                cv2.putText(
                    cam_preview, text, (box_x + 10, box_y + 18 + idx * 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, c, 1, cv2.LINE_AA
                )

            # g. Render Environment View (Phase 1 World)
            frame = renderer.render()

            # Display windows
            cv2.imshow(window_title, frame)
            cv2.imshow(cam_window_title, cam_preview)

            # Handle user input (Q/q or ESC key)
            key = cv2.waitKey(frame_delay) & 0xFF
            if key in (ord('q'), ord('Q'), 27):  # 27 is ESC key
                print(f"[INFO] User exit requested (key code: {key}). Exiting simulation loop.")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt detected. Exiting...")
    finally:
        # Release OpenCV resources cleanly
        cv2.destroyAllWindows()
        print("[INFO] Simulation stopped cleanly. OpenCV windows destroyed.")


if __name__ == "__main__":
    main()
