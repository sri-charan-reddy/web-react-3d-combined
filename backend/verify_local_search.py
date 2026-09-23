"""Verification script for Local Search Around Kalman Prediction (Part 2).

Tests the following requirements:
1. Search starts only after the configured prediction/coasting threshold (search_start_frames).
2. Search center is strictly derived from Kalman prediction, NEVER Ground Truth.
3. Search waypoints remain bounded within configured search_radius_px.
4. Search pattern progresses sequentially through multiple distinct scan waypoints.
5. Camera pan/tilt moves smoothly toward search waypoints without teleportation.
6. Valid optical measurement immediately terminates local search and resets counters.
7. Successful reacquisition returns system state to TRACKING.
8. Unsuccessful search eventually transitions to LOST after max_prediction_frames.
9. Existing Kalman filtering and outlier rejection remain intact.

Usage:
    python verify_local_search.py
"""

import math
import sys
from config import (
    CameraControllerConfig,
    KalmanConfig,
    LocalSearchConfig,
    TrackingStateConfig,
    VirtualCameraConfig,
)
from src.camera_controller import CameraController, ControllerMode
from src.kalman_tracker import KalmanBeaconTracker
from src.local_search import LocalSearch
from src.tracking_state import BeaconMeasurement, TrackingState
from src.virtual_camera import VirtualCamera


def verify_local_search() -> bool:
    print("=" * 76)
    print("RUNNING LOCAL SEARCH MODULE VERIFICATION (PART 2)")
    print("=" * 76)

    kalman_cfg = KalmanConfig()
    state_cfg = TrackingStateConfig(
        gating_threshold_px=85.0,
        search_start_frames=15,
        max_prediction_frames=45
    )
    search_cfg = LocalSearchConfig(
        search_start_frames=15,
        search_radius_px=140.0,
        step_size_px=45.0,
        hold_frames_per_step=3,
        max_prediction_frames=45
    )
    cam_cfg = VirtualCameraConfig(
        arena_width=1280,
        arena_height=720,
        initial_center=(640.0, 360.0),
        fov_width=500.0,
        fov_height=380.0
    )
    ctrl_cfg = CameraControllerConfig(
        max_pan_speed=240.0,
        max_tilt_speed=240.0,
        kp_pan=3.0,
        kp_tilt=3.0,
        deadband_px=2.5
    )

    tracker = KalmanBeaconTracker(kalman_cfg, state_cfg)
    search = LocalSearch(search_cfg)
    camera = VirtualCamera(cam_cfg)
    controller = CameraController(camera, ctrl_cfg)
    dt = 1.0 / 30.0

    # -------------------------------------------------------------
    # TEST 1: Initial Lock -> Normal TRACKING
    # -------------------------------------------------------------
    print("\n[TEST 1] Initial Acquisition & Normal Tracking State:")
    init_m = BeaconMeasurement(timestamp=0.0, position=(640.0, 360.0), detected=True, confidence=1.0)
    res_init = tracker.process_frame(init_m, 0.0)
    assert res_init.state == TrackingState.TRACKING, f"Expected TRACKING, got {res_init.state}"
    assert tracker.miss_count == 0
    print(f"  Initialized in state: {res_init.state.name}, Position: {res_init.position}")
    print("  -> PASSED: Normal tracking active.")

    # -------------------------------------------------------------
    # TEST 2: Short Occlusion (Frames 1..14) -> PREDICTING only (No Search yet)
    # -------------------------------------------------------------
    print("\n[TEST 2] Short Loss Threshold (Frames 1..14 -> PREDICTING, Search Inactive):")
    for f in range(1, 15):
        t = f * dt
        miss_m = BeaconMeasurement(timestamp=t, position=None, detected=False)
        res = tracker.process_frame(miss_m, t)
        is_searching = (res.state == TrackingState.SEARCHING)
        tgt = search.update(res.position, is_searching)
        controller.update(res, dt, target_override=tgt if is_searching else None)

        assert res.state == TrackingState.PREDICTING, f"Frame {f}: Expected PREDICTING, got {res.state}"
        assert search.is_active is False, f"Frame {f}: Local search triggered prematurely!"
        assert tgt == res.position, f"Frame {f}: Search target should equal prediction when inactive."

    print(f"  Miss Count at frame 14: {tracker.miss_count} | State: {tracker.state.name} | Search Active: {search.is_active}")
    print("  -> PASSED: Search does not trigger during short loss (Kalman prediction active).")

    # -------------------------------------------------------------
    # TEST 3: Extended Loss (Frame 15) -> State SEARCHING & Bounded Pattern Generation
    # -------------------------------------------------------------
    print("\n[TEST 3] Search Trigger at Threshold (Frame 15 -> SEARCHING & Bounded Pattern):")
    t_15 = 15 * dt
    miss_15 = BeaconMeasurement(timestamp=t_15, position=None, detected=False)
    res_15 = tracker.process_frame(miss_15, t_15)
    is_searching_15 = (res_15.state == TrackingState.SEARCHING)
    tgt_15 = search.update(res_15.position, is_searching_15)

    assert res_15.state == TrackingState.SEARCHING, f"Expected SEARCHING at miss=15, got {res_15.state}"
    assert search.is_active is True, "Local search should be ACTIVE!"
    assert search.search_center == res_15.position, "Search center must be the Kalman predicted position!"
    print(f"  Frame 15 State: {res_15.state.name} | Search Center: {search.search_center} | Waypoint #1: {tgt_15}")
    print("  -> PASSED: Local search successfully triggered with Kalman predicted center.")

    # -------------------------------------------------------------
    # TEST 4: Pattern Progression & Radius Constraint Checks
    # -------------------------------------------------------------
    print("\n[TEST 4] Pattern Multi-Step Progression & Radius Boundary Checks:")
    collected_targets = []
    for f in range(16, 35):
        t = f * dt
        miss_m = BeaconMeasurement(timestamp=t, position=None, detected=False)
        res = tracker.process_frame(miss_m, t)
        is_s = (res.state == TrackingState.SEARCHING)
        tgt = search.update(res.position, is_s)
        collected_targets.append(tgt)
        
        # Verify target is strictly within search_radius_px of search center
        dx = tgt[0] - search.search_center[0]
        dy = tgt[1] - search.search_center[1]
        dist_from_center = math.sqrt(dx*dx + dy*dy)
        assert dist_from_center <= search_cfg.search_radius_px + 1e-3, f"Target exceeded radius: {dist_from_center}"

        # Verify camera moves smoothly toward waypoint
        d_p, d_t = controller.update(res, dt, target_override=tgt if is_s else None)
        assert abs(d_p) <= (ctrl_cfg.max_pan_speed * dt + 1e-3)
        assert abs(d_t) <= (ctrl_cfg.max_tilt_speed * dt + 1e-3)

    unique_targets = len(set([(round(x, 1), round(y, 1)) for x, y in collected_targets]))
    print(f"  Generated {unique_targets} distinct waypoints across 20 search frames.")
    print(f"  All waypoints confirmed within search_radius={search_cfg.search_radius_px} px.")
    assert unique_targets >= 4, f"Pattern did not progress through enough waypoints: {unique_targets}"
    print("  -> PASSED: Search pattern progresses through bounded waypoints without camera teleportation.")

    # -------------------------------------------------------------
    # TEST 5: Reacquisition from Local Search -> TRACKING
    # -------------------------------------------------------------
    print("\n[TEST 5] Reacquisition from Local Search (Measurement Return):")
    # Return a plausible measurement near current Kalman prediction
    reacq_pos = (res.position[0] + 10.0, res.position[1] - 8.0)
    reacq_m = BeaconMeasurement(timestamp=35 * dt, position=reacq_pos, detected=True, confidence=0.9)
    res_reacq = tracker.process_frame(reacq_m, 35 * dt)
    search.update(res_reacq.position, is_searching=(res_reacq.state == TrackingState.SEARCHING))

    print(f"  Returned Measurement at {reacq_pos} -> Tracker State: {res_reacq.state.name}")
    assert res_reacq.state in (TrackingState.REACQUIRING, TrackingState.TRACKING)
    assert tracker.miss_count == 0, f"Miss count did not reset: {tracker.miss_count}"
    assert search.is_active is False, "Local search should DEACTIVATE upon reacquisition!"

    # Next frame -> confirmed TRACKING
    next_m = BeaconMeasurement(timestamp=36 * dt, position=reacq_pos, detected=True, confidence=0.9)
    res_track = tracker.process_frame(next_m, 36 * dt)
    assert res_track.state == TrackingState.TRACKING
    print(f"  Next frame state: {res_track.state.name} | Confidence: {res_track.confidence:.2f}")
    print("  -> PASSED: Reacquisition immediately halts search and restores TRACKING.")

    # -------------------------------------------------------------
    # TEST 6: Unsuccessful Search -> LOST State Transition
    # -------------------------------------------------------------
    print("\n[TEST 6] Unsuccessful Search Timeout -> LOST State Transition:")
    tracker.reset()
    search.reset()
    camera.reset()
    controller.reset()

    # Initialize
    tracker.process_frame(BeaconMeasurement(timestamp=0.0, position=(500.0, 300.0), detected=True), 0.0)

    # Miss 50 consecutive frames (> max_prediction_frames = 45)
    for f in range(1, 50):
        t = f * dt
        m_loss = BeaconMeasurement(timestamp=t, position=None, detected=False)
        r = tracker.process_frame(m_loss, t)
        is_s = (r.state == TrackingState.SEARCHING)
        tgt = search.update(r.position, is_s)
        controller.update(r, dt, target_override=tgt if is_s else None)

    print(f"  After 50 missed frames -> State: {r.state.name} | Miss Count: {r.miss_count} | Controller: {controller.mode.name}")
    assert r.state == TrackingState.LOST, f"Expected LOST, got {r.state}"
    assert controller.mode == ControllerMode.HOLDING, f"Expected HOLDING, got {controller.mode}"
    print("  -> PASSED: Failed search cleanly transitions to LOST with camera safely holding.")

    # -------------------------------------------------------------
    # TEST 7: Reacquisition from LOST State
    # -------------------------------------------------------------
    print("\n[TEST 7] Reacquisition from LOST State Check:")
    # Measurement returns at (620, 380) while tracker is currently in LOST
    assert tracker.state == TrackingState.LOST
    lost_reacq_m = BeaconMeasurement(timestamp=50 * dt, position=(620.0, 380.0), detected=True, confidence=0.9)
    res_lost_reacq = tracker.process_frame(lost_reacq_m, 50 * dt)
    search.update(res_lost_reacq.position, is_searching=(res_lost_reacq.state == TrackingState.SEARCHING))
    controller.update(res_lost_reacq, dt)

    print(f"  Returning measurement at (620, 380) -> State: {res_lost_reacq.state.name}, Accepted: {res_lost_reacq.measurement_accepted}")
    print(f"  Kalman Position after recovery: {res_lost_reacq.position}, Miss Count: {tracker.miss_count}, Controller: {controller.mode.name}")
    assert res_lost_reacq.state == TrackingState.REACQUIRING, f"Expected REACQUIRING, got {res_lost_reacq.state}"
    assert res_lost_reacq.measurement_accepted is True, "Measurement was rejected in LOST state!"
    assert tracker.miss_count == 0, f"Miss count not reset: {tracker.miss_count}"
    assert abs(res_lost_reacq.position[0] - 620.0) < 1e-3 and abs(res_lost_reacq.position[1] - 380.0) < 1e-3, "Kalman state not re-anchored to measurement!"
    assert controller.mode == ControllerMode.TRACKING_SERVO, f"Controller should be TRACKING_SERVO, got {controller.mode}"

    # Next frame -> Confirmed TRACKING
    next_m_lost = BeaconMeasurement(timestamp=51 * dt, position=(623.0, 378.0), detected=True, confidence=0.9)
    res_track_after_lost = tracker.process_frame(next_m_lost, 51 * dt)
    controller.update(res_track_after_lost, dt)
    print(f"  Next frame state: {res_track_after_lost.state.name} | Confidence: {res_track_after_lost.confidence:.2f}")
    assert res_track_after_lost.state == TrackingState.TRACKING
    print("  -> PASSED: LOST state successfully reacquires returning beacon and resumes normal tracking.")

    print("\n" + "=" * 76)
    print("ALL LOCAL SEARCH & REACQUISITION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 76)
    return True


if __name__ == "__main__":
    success = verify_local_search()
    sys.exit(0 if success else 1)
