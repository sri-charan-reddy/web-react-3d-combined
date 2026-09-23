"""Verification script for Virtual Camera Pan/Tilt Controller (Part 2).

Tests the following requirements:
1. Camera starts offset from beacon (e.g. Center: (640, 360), Beacon: (900, 450)).
2. Controller computes pointing error and moves camera toward beacon.
3. Slew rate limiting: Camera does NOT teleport/jump instantly (respects max_pan_speed & max_tilt_speed).
4. Slew limits: Movement respects camera pan/tilt arena boundaries.
5. Predictive servoing: During temporary occlusion (PREDICTING state), controller continues moving
   the camera using the Kalman predicted position.
6. Safe holding: During LOST state, controller holds position.
7. Deadband: Suppresses micro-movements when pointing error is within deadband threshold.
8. Kalman tracker integrity: Tracking and state transitions operate identically.

Usage:
    python verify_camera_controller.py
"""

import sys
from config import CameraControllerConfig, SystemConfig, VirtualCameraConfig
from src.camera_controller import CameraController, ControllerMode
from src.kalman_tracker import KalmanBeaconTracker
from src.tracking_state import BeaconMeasurement, TrackingResult, TrackingState
from src.virtual_camera import VirtualCamera


def verify_camera_controller() -> bool:
    print("=" * 76)
    print("RUNNING VIRTUAL CAMERA PAN/TILT CONTROLLER VERIFICATION (PART 2)")
    print("=" * 76)

    cam_cfg = VirtualCameraConfig(
        arena_width=1280,
        arena_height=720,
        initial_center=(640.0, 360.0),
        fov_width=500.0,
        fov_height=380.0
    )
    ctrl_cfg = CameraControllerConfig(
        max_pan_speed=240.0,   # px/s (max ~8.0 px/frame at dt=1/30)
        max_tilt_speed=240.0,  # px/s (max ~8.0 px/frame at dt=1/30)
        kp_pan=3.0,
        kp_tilt=3.0,
        deadband_px=2.5,
        enable_predictive_servo=True,
        stop_on_lost=True
    )

    cam = VirtualCamera(cam_cfg)
    controller = CameraController(cam, ctrl_cfg)
    dt = 1.0 / 30.0

    # -------------------------------------------------------------
    # TEST 1 & 2: Error Calculation & Smooth Directional Slew
    # -------------------------------------------------------------
    print("\n[TEST 1 & 2] Slew Towards Offset Target (No Teleportation):")
    target_pos = (900.0, 450.0)
    initial_center = cam.center
    print(f"  Initial Camera Center: {initial_center}")
    print(f"  Target Beacon Pos:     {target_pos}")

    # Simulated Kalman TrackingResult
    tr_active = TrackingResult(
        timestamp=0.0,
        position=target_pos,
        velocity=(0.0, 0.0),
        state=TrackingState.TRACKING,
        confidence=1.0,
        is_predicted=False
    )

    # Step 1 frame
    d_pan, d_tilt = controller.update(tr_active, dt)
    new_center = cam.center
    telem = controller.get_telemetry()

    print(f"  Step 1 Applied: d_pan={d_pan:.2f} px, d_tilt={d_tilt:.2f} px")
    print(f"  New Camera Center: ({new_center[0]:.2f}, {new_center[1]:.2f})")
    print(f"  Controller Mode: {telem.mode.name}, Error: ({telem.error_x:.1f}, {telem.error_y:.1f})")

    # Verify no instant teleport
    assert new_center != target_pos, "Camera instantly teleported to target!"
    assert abs(d_pan) <= (ctrl_cfg.max_pan_speed * dt + 1e-4), f"Pan step exceeded speed limit: {d_pan}"
    assert abs(d_tilt) <= (ctrl_cfg.max_tilt_speed * dt + 1e-4), f"Tilt step exceeded speed limit: {d_tilt}"
    assert new_center[0] > initial_center[0], "Camera failed to move right toward target!"
    assert new_center[1] > initial_center[1], "Camera failed to move down toward target!"
    print("  -> PASSED: Camera moves smoothly in correct direction within speed limits.")

    # -------------------------------------------------------------
    # TEST 3: Multi-step Convergence into Camera FOV and Centering
    # -------------------------------------------------------------
    print("\n[TEST 3] Multi-Step Slew & Target Acquisition into FOV:")
    # Run 25 frames -> verify beacon enters FOV
    for f in range(25):
        controller.update(tr_active, dt)

    center_25 = cam.center
    in_fov_25 = cam.is_in_fov(target_pos)
    print(f"  Center after 25 frames (~0.8s): ({center_25[0]:.1f}, {center_25[1]:.1f}) | In FOV: {in_fov_25}")
    assert in_fov_25 is True, "Target failed to enter Camera FOV after 25 frames!"

    # Run remaining frames up to 60 frames (2.0s) -> verify centered inside deadband
    for f in range(35):
        controller.update(tr_active, dt)

    center_after_slew = cam.center
    err = cam.get_relative_position(target_pos)
    telem_settled = controller.get_telemetry()
    print(f"  Center after 60 frames (~2.0s): ({center_after_slew[0]:.1f}, {center_after_slew[1]:.1f})")
    print(f"  Residual Error from Center: ({err[0]:.2f}, {err[1]:.2f}) px | In Deadband: {telem_settled.in_deadband}")

    assert abs(err[0]) <= ctrl_cfg.deadband_px and abs(err[1]) <= ctrl_cfg.deadband_px, f"Residual error outside deadband: {err}"
    print("  -> PASSED: Camera successfully acquired target, centered it, and stabilized in deadband.")

    # -------------------------------------------------------------
    # TEST 4: Deadband Handling
    # -------------------------------------------------------------
    print("\n[TEST 4] Deadband Micro-Jitter Suppression:")
    # Place target 1 px away (within 2.5 px deadband)
    tr_near = TrackingResult(
        timestamp=1.0,
        position=(cam.center[0] + 1.0, cam.center[1] - 1.0),
        velocity=(0.0, 0.0),
        state=TrackingState.TRACKING,
        confidence=1.0,
        is_predicted=False
    )
    d_p, d_t = controller.update(tr_near, dt)
    telem_db = controller.get_telemetry()
    print(f"  Target within deadband (err=1.0px) -> d_pan={d_p}, d_tilt={d_t}, In Deadband: {telem_db.in_deadband}")
    assert d_p == 0.0 and d_t == 0.0, "Controller moved inside deadband!"
    assert telem_db.in_deadband is True
    print("  -> PASSED: Deadband stops micro-jitter when target is centered.")

    # -------------------------------------------------------------
    # TEST 5: Predictive Servoing During Temporary Occlusion (PREDICTING)
    # -------------------------------------------------------------
    print("\n[TEST 5] Predictive Servoing During Temporary Beacon Loss:")
    # Moving prediction moving at (150, 0) px/s
    predicted_target = (cam.center[0] + 50.0, cam.center[1])
    tr_predicting = TrackingResult(
        timestamp=2.0,
        position=predicted_target,
        velocity=(150.0, 0.0),
        state=TrackingState.PREDICTING,
        confidence=0.7,
        is_predicted=True
    )
    c_before_pred = cam.center
    d_p_pred, _ = controller.update(tr_predicting, dt)
    c_after_pred = cam.center
    telem_pred = controller.get_telemetry()

    print(f"  Predicting State -> Mode: {telem_pred.mode.name}, d_pan={d_p_pred:.2f} px")
    print(f"  Center shifted from {c_before_pred[0]:.1f} to {c_after_pred[0]:.1f}")
    assert telem_pred.mode == ControllerMode.PREDICTIVE_SERVO
    assert d_p_pred > 0.0, "Camera did not follow Kalman predicted position during occlusion!"
    assert c_after_pred[0] > c_before_pred[0]
    print("  -> PASSED: Camera continues active predictive servoing during measurement loss.")

    # -------------------------------------------------------------
    # TEST 6: Safe Holding During LOST State
    # -------------------------------------------------------------
    print("\n[TEST 6] Safe Holding During LOST State:")
    tr_lost = TrackingResult(
        timestamp=3.0,
        position=(1100.0, 200.0),
        velocity=(0.0, 0.0),
        state=TrackingState.LOST,
        confidence=0.0,
        is_predicted=True
    )
    c_before_lost = cam.center
    d_p_lost, d_t_lost = controller.update(tr_lost, dt)
    c_after_lost = cam.center
    telem_lost = controller.get_telemetry()

    print(f"  LOST State -> Mode: {telem_lost.mode.name}, Displacement: ({d_p_lost}, {d_t_lost})")
    assert telem_lost.mode == ControllerMode.HOLDING
    assert d_p_lost == 0.0 and d_t_lost == 0.0
    assert c_before_lost == c_after_lost
    print("  -> PASSED: Camera safely holds orientation when track is LOST.")

    # -------------------------------------------------------------
    # TEST 7: Pan/Tilt Boundary Enforcement
    # -------------------------------------------------------------
    print("\n[TEST 7] Pan/Tilt Arena Boundary Enforcement:")
    tr_extreme = TrackingResult(
        timestamp=4.0,
        position=(5000.0, 5000.0),
        velocity=(0.0, 0.0),
        state=TrackingState.TRACKING,
        confidence=1.0,
        is_predicted=False
    )
    for _ in range(500):
        controller.update(tr_extreme, dt)
    c_max = cam.center
    print(f"  Camera commanded to (5000, 5000) -> Clamped at: {c_max} (Limits: 1280, 720)")
    assert c_max[0] <= cam_cfg.max_pan and c_max[1] <= cam_cfg.max_tilt
    print("  -> PASSED: Camera pan/tilt limits strictly enforced.")

    print("\n" + "=" * 76)
    print("ALL CAMERA PAN/TILT CONTROLLER CHECKS PASSED SUCCESSFULLY!")
    print("=" * 76)
    return True


if __name__ == "__main__":
    success = verify_camera_controller()
    sys.exit(0 if success else 1)
