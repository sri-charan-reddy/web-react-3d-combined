"""Verification script for VirtualCamera Model in Part 2.

Tests the following 5 requirements:
1. Beacon inside FOV -> reported as visible (is_in_fov == True)
2. Beacon outside FOV -> reported as not visible (is_in_fov == False)
3. Camera center/pan/tilt and FOV bounds are computed correctly
4. Coordinate transformations: world_to_camera and camera_to_world are exact inverses
5. Existing Kalman tracking behavior continues working unchanged with the camera integration

Usage:
    python verify_camera.py
"""

import sys
from config import DEFAULT_CONFIG, VirtualCameraConfig
from src.virtual_camera import VirtualCamera, CameraTelemetry
from src.kalman_tracker import KalmanBeaconTracker
from src.tracking_state import BeaconMeasurement, TrackingState


def verify_virtual_camera() -> bool:
    print("=" * 70)
    print("RUNNING VIRTUAL CAMERA MODEL VERIFICATION (PART 2)")
    print("=" * 70)

    # Setup camera with known center and FOV
    cfg = VirtualCameraConfig(
        arena_width=1280,
        arena_height=720,
        initial_center=(640.0, 360.0),
        fov_width=500.0,
        fov_height=380.0
    )
    cam = VirtualCamera(cfg)

    # -------------------------------------------------------------
    # TEST 1 & 3: Center, FOV Bounds, and Telemetry
    # -------------------------------------------------------------
    center = cam.center
    pan, tilt = cam.pan, cam.tilt
    bounds = cam.get_fov_bounds()
    expected_bounds = (390.0, 890.0, 170.0, 550.0)

    print("\n[TEST 1 & 3] Camera Center & FOV Bounds:")
    print(f"  Center:   {center} (Expected: (640.0, 360.0))")
    print(f"  Pan/Tilt: ({pan}, {tilt})")
    print(f"  Bounds:   {bounds} (Expected: {expected_bounds})")

    assert center == (640.0, 360.0), f"Center mismatch: {center}"
    assert pan == 640.0 and tilt == 360.0, f"Pan/Tilt mismatch: {pan}, {tilt}"
    assert bounds == expected_bounds, f"Bounds mismatch: {bounds} != {expected_bounds}"
    print("  -> PASSED: Camera Center and FOV bounds computed accurately.")

    # -------------------------------------------------------------
    # TEST 2: Beacon Visibility Inside vs Outside FOV
    # -------------------------------------------------------------
    inside_pt = (640.0, 360.0)       # Center -> Inside
    inside_pt_2 = (400.0, 200.0)     # Near top-left inside
    outside_pt_1 = (100.0, 100.0)    # Far top-left outside
    outside_pt_2 = (1100.0, 600.0)   # Far bottom-right outside

    print("\n[TEST 2] Beacon Inside vs Outside FOV Check:")
    vis_inside_1 = cam.is_in_fov(inside_pt)
    vis_inside_2 = cam.is_in_fov(inside_pt_2)
    vis_outside_1 = cam.is_in_fov(outside_pt_1)
    vis_outside_2 = cam.is_in_fov(outside_pt_2)

    print(f"  Point {inside_pt}: in_fov = {vis_inside_1} (Expected: True)")
    print(f"  Point {inside_pt_2}: in_fov = {vis_inside_2} (Expected: True)")
    print(f"  Point {outside_pt_1}: in_fov = {vis_outside_1} (Expected: False)")
    print(f"  Point {outside_pt_2}: in_fov = {vis_outside_2} (Expected: False)")

    assert vis_inside_1 and vis_inside_2, "Inside points failed visibility check!"
    assert not vis_outside_1 and not vis_outside_2, "Outside points failed visibility check!"

    # Relative Error
    rel_err = cam.get_relative_position((650.0, 370.0))
    print(f"  Relative error from center for (650, 370): {rel_err} (Expected: (10.0, 10.0))")
    assert rel_err == (10.0, 10.0), f"Relative error mismatch: {rel_err}"
    print("  -> PASSED: Beacon visibility and relative error reporting verified.")

    # -------------------------------------------------------------
    # TEST 4: Coordinate Transformations (World <-> Camera Image)
    # -------------------------------------------------------------
    print("\n[TEST 4] Coordinate Transformations (World <-> Camera):")
    world_test_pts = [
        (640.0, 360.0),  # Camera optical axis -> should be (250.0, 190.0) in camera frame
        (390.0, 170.0),  # Top-left of FOV -> should be (0.0, 0.0)
        (890.0, 550.0),  # Bottom-right of FOV -> should be (500.0, 380.0)
        (500.0, 300.0)
    ]

    for w_pt in world_test_pts:
        cam_pt = cam.world_to_camera(w_pt)
        reconstructed_w_pt = cam.camera_to_world(cam_pt)
        print(f"  World: {w_pt} -> Camera Sensor: {cam_pt} -> Reconstructed World: {reconstructed_w_pt}")
        assert abs(reconstructed_w_pt[0] - w_pt[0]) < 1e-5, f"X mismatch on {w_pt}"
        assert abs(reconstructed_w_pt[1] - w_pt[1]) < 1e-5, f"Y mismatch on {w_pt}"

    print("  -> PASSED: World-to-camera and camera-to-world transformations are exact.")

    # -------------------------------------------------------------
    # TEST 5: Pan / Tilt Adjustment & Motion
    # -------------------------------------------------------------
    print("\n[TEST 5] Pan / Tilt Steering Commands:")
    cam.move_pan_tilt(50.0, -30.0)
    new_center = cam.center
    new_bounds = cam.get_fov_bounds()
    print(f"  Moved (+50, -30) -> New Center: {new_center}, New Bounds: {new_bounds}")
    assert new_center == (690.0, 330.0), f"New center mismatch: {new_center}"
    assert new_bounds == (440.0, 940.0, 140.0, 520.0), f"New bounds mismatch: {new_bounds}"
    print("  -> PASSED: Pan/Tilt motion update verified.")

    # -------------------------------------------------------------
    # TEST 6: Kalman Tracker Compatibility Verification
    # -------------------------------------------------------------
    print("\n[TEST 6] Kalman Tracker Regression Check:")
    tracker = KalmanBeaconTracker(DEFAULT_CONFIG.kalman, DEFAULT_CONFIG.tracking)
    m1 = BeaconMeasurement(timestamp=0.0, position=(300.0, 250.0), detected=True, confidence=0.95)
    res1 = tracker.process_frame(m1, 0.0)
    assert res1.state == TrackingState.TRACKING, f"Tracker state error: {res1.state}"
    assert tracker.initialized is True

    # Prediction frame (occlusion)
    m_loss = BeaconMeasurement(timestamp=0.033, position=None, detected=False)
    res2 = tracker.process_frame(m_loss, 0.033)
    assert res2.state == TrackingState.PREDICTING, f"Tracker state error on miss: {res2.state}"
    assert res2.is_predicted is True
    print(f"  Kalman Init State: {res1.state.name}, Coasting State: {res2.state.name}, Pos: {res2.position}")
    print("  -> PASSED: Kalman Filter tracking operates with full integrity.")

    print("\n" + "=" * 70)
    print("ALL VIRTUAL CAMERA MODEL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = verify_virtual_camera()
    sys.exit(0 if success else 1)
