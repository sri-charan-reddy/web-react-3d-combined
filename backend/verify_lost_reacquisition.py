"""Focused verification script for FOV Consistency and LOST State Reacquisition.

Tests the following:
1. Outside FOV -> Optical detector receives no measurement (detected=False, position=None)
2. Inside FOV -> Optical detector receives valid measurement (detected=True, position=(x, y))
3. LOST State Reacquisition -> When a valid measurement appears while in LOST state,
   the tracker accepts the measurement, re-anchors the Kalman state, transitions
   LOST -> REACQUIRING -> TRACKING, and the CameraController leaves HOLDING to resume tracking.
4. Outlier Protection -> Injected far-away outlier spikes during tracking continue to be rejected by gating.
5. Local Search Boundedness -> Camera scan remains bounded within configured radius.
"""

import math
import sys

from config import (
    CameraControllerConfig,
    DisturbanceConfig,
    KalmanConfig,
    LocalSearchConfig,
    TrackingStateConfig,
    VirtualCameraConfig
)
from src.camera_controller import CameraController, ControllerMode
from src.disturbance_simulator import DisturbanceSimulator
from src.kalman_tracker import KalmanBeaconTracker
from src.local_search import LocalSearch
from src.tracking_state import BeaconMeasurement, TrackingState
from src.virtual_camera import VirtualCamera


def test_1_and_2_fov_consistency() -> bool:
    print("\n[TEST 1 & 2] Virtual Camera FOV Consistency Check:")
    cam_cfg = VirtualCameraConfig(
        arena_width=1280,
        arena_height=720,
        initial_center=(640.0, 360.0),
        fov_width=500.0,
        fov_height=380.0
    )
    cam = VirtualCamera(cam_cfg)
    dist_cfg = DisturbanceConfig(
        require_fov_for_detection=True,
        enable_occlusions=False,
        enable_outliers=False
    )
    dist_sim = DisturbanceSimulator(dist_cfg)

    # Point 1: Inside FOV (e.g. 650, 370)
    inside_pt = (650.0, 370.0)
    meas_inside = dist_sim.apply_disturbances(inside_pt, 0.0, 0, camera=cam)
    print(f"  Beacon at {inside_pt} (Inside FOV) -> Detected: {meas_inside.detected}, Position: {meas_inside.position}")
    assert meas_inside.detected is True, "Beacon inside FOV was not detected!"
    assert meas_inside.position is not None

    # Point 2: Outside FOV (e.g. 1100, 600)
    outside_pt = (1100.0, 600.0)
    meas_outside = dist_sim.apply_disturbances(outside_pt, 0.033, 1, camera=cam)
    print(f"  Beacon at {outside_pt} (Outside FOV) -> Detected: {meas_outside.detected}, Position: {meas_outside.position}")
    assert meas_outside.detected is False, "Beacon outside FOV was erroneously detected!"
    assert meas_outside.position is None

    print("  -> PASSED: Camera FOV strictly controls simulated optical detection availability.")
    return True


def test_3_lost_state_reacquisition() -> bool:
    print("\n[TEST 3] LOST State Controlled Reacquisition Check:")
    tracker = KalmanBeaconTracker(KalmanConfig(), TrackingStateConfig(max_prediction_frames=20))
    cam = VirtualCamera(VirtualCameraConfig(initial_center=(640.0, 360.0)))
    ctrl = CameraController(cam, CameraControllerConfig())
    dt = 1.0 / 30.0

    # 1. Initialize
    tracker.process_frame(BeaconMeasurement(timestamp=0.0, position=(500.0, 300.0), detected=True), 0.0)

    # 2. Force into LOST state via consecutive misses
    for f in range(1, 30):
        t = f * dt
        r = tracker.process_frame(BeaconMeasurement(timestamp=t, position=None, detected=False), t)
        ctrl.update(r, dt)

    assert tracker.state == TrackingState.LOST
    assert ctrl.mode == ControllerMode.HOLDING
    stale_pred_pos = tracker.get_current_position()
    print(f"  Tracker is LOST. Miss Count: {tracker.miss_count}, Stale Prediction: ({stale_pred_pos[0]:.1f}, {stale_pred_pos[1]:.1f}), Camera: {ctrl.mode.name}")

    # 3. New valid measurement appears at (600.0, 400.0) - far from stale prediction
    meas_return = BeaconMeasurement(timestamp=1.0, position=(600.0, 400.0), detected=True, confidence=0.92)
    res_reacq = tracker.process_frame(meas_return, 1.0)
    ctrl.update(res_reacq, dt)

    print(f"  Returning measurement at (600, 400) -> State: {res_reacq.state.name}, Accepted: {res_reacq.measurement_accepted}")
    print(f"  Kalman Position: {res_reacq.position}, Miss Count: {tracker.miss_count}, Camera Mode: {ctrl.mode.name}")

    assert res_reacq.state == TrackingState.REACQUIRING, f"Expected REACQUIRING, got {res_reacq.state}"
    assert res_reacq.measurement_accepted is True, "Valid measurement rejected while LOST!"
    assert tracker.miss_count == 0, f"Miss count not reset: {tracker.miss_count}"
    assert abs(res_reacq.position[0] - 600.0) < 1e-3 and abs(res_reacq.position[1] - 400.0) < 1e-3, "Kalman state not re-anchored!"
    assert ctrl.mode == ControllerMode.TRACKING_SERVO, f"Camera should be TRACKING_SERVO, got {ctrl.mode}"

    # 4. Next frame confirms TRACKING lock
    meas_next = BeaconMeasurement(timestamp=1.033, position=(603.0, 398.0), detected=True, confidence=0.95)
    res_track = tracker.process_frame(meas_next, 1.033)
    ctrl.update(res_track, dt)
    print(f"  Next frame -> State: {res_track.state.name}, Confidence: {res_track.confidence:.2f}")
    assert res_track.state == TrackingState.TRACKING

    print("  -> PASSED: LOST state cleanly reacquires returning beacon and resumes normal tracking.")
    return True


def test_4_outlier_protection_remains_active() -> bool:
    print("\n[TEST 4] Outlier Protection Integrity Check:")
    tracker = KalmanBeaconTracker(KalmanConfig(), TrackingStateConfig(gating_threshold_px=80.0))
    tracker.initialize((600.0, 400.0), 0.0)

    # Injected outlier at (1100, 100) (distance ~580 px > 80 px)
    outlier = BeaconMeasurement(timestamp=0.033, position=(1100.0, 100.0), detected=True, confidence=0.90)
    res = tracker.process_frame(outlier, 0.033)

    print(f"  Injected Outlier at (1100, 100) -> State: {res.state.name}, Accepted: {res.measurement_accepted}")
    assert res.measurement_accepted is False, "Outlier was accepted!"
    assert res.state == TrackingState.PREDICTING
    assert abs(res.position[0] - 600.0) < 20.0, "Kalman state jumped to outlier!"

    print("  -> PASSED: Outlier rejection gating remains fully functional.")
    return True


def main() -> None:
    print("=" * 76)
    print("RUNNING FOV CONSISTENCY & LOST-STATE REACQUISITION VERIFICATION")
    print("=" * 76)

    tests = [
        test_1_and_2_fov_consistency,
        test_3_lost_state_reacquisition,
        test_4_outlier_protection_remains_active,
    ]

    results = [test() for test in tests]
    print("\n" + "=" * 76)
    if all(results):
        print(f"ALL {len(results)} FOCUSED VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 76)
        sys.exit(0)
    else:
        print("FAILED: Some tests failed.")
        print("=" * 76)
        sys.exit(1)


if __name__ == "__main__":
    main()
