"""Comprehensive Integration Test Suite for Part 4 Autonomous FSOC Orchestrator.

Covers all 6 required evaluation scenarios:
- TEST 1: Beacon immediately detected (OPTICAL_SEARCH -> OPTICAL_TRACKING -> FINE_ALIGNMENT -> FSOC_ACTIVE)
- TEST 2: Beacon temporarily disappears (OPTICAL_TRACKING -> PREDICTIVE_RECOVERY -> LOCAL_REACQUISITION -> OPTICAL_TRACKING)
- TEST 3: Optical recovery completely fails (OPTICAL_SEARCH/RECOVERY -> RF_DISCOVERY -> AUTHENTICATION -> RF_DIRECTION_RECOVERY -> OPTICAL_REACQUISITION)
- TEST 4: RF authentication fails (RF_DISCOVERY -> RF_AUTHENTICATION -> RECOVERY_FAILED)
- TEST 5: Correct RF authentication followed by optical reacquisition (RF_DIRECTION_RECOVERY -> OPTICAL_REACQUISITION -> TRACKING -> FINE_ALIGNMENT -> FSOC_ACTIVE)
- TEST 6: Existing Part 1, Part 2, and Part 3 modules still run independently without modification
"""

import os
import sys
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.orchestrator.states import SystemState
from src.orchestrator.controller import FSOCRecoveryOrchestrator


def test_1_beacon_immediately_detected():
    """TEST 1: Beacon immediately detected.
    Expected: OPTICAL_SEARCH -> OPTICAL_TRACKING -> FINE_ALIGNMENT -> FSOC_ACTIVE
    """
    print("\n" + "=" * 70)
    print("RUNNING TEST 1: Beacon Immediately Detected -> FSOC_ACTIVE")
    print("=" * 70)
    
    orchestrator = FSOCRecoveryOrchestrator(target_terminal_id="TERMINAL_02")
    # Align camera with beacon so it's immediately within initial FOV
    orchestrator.env.camera.orientation_deg = 38.0
    orchestrator.start()
    
    states_visited = [orchestrator.state]
    
    for step_i in range(100):
        telemetry = orchestrator.step(dt=0.1)
        if orchestrator.state != states_visited[-1]:
            states_visited.append(orchestrator.state)
            print(f"Step {step_i:3d}: State -> {orchestrator.state.name}")
        if orchestrator.state == SystemState.FSOC_ACTIVE:
            break

    print("States Visited Sequence:", [s.name for s in states_visited])
    assert SystemState.OPTICAL_SEARCH in states_visited, "Must visit OPTICAL_SEARCH"
    assert SystemState.OPTICAL_TRACKING in states_visited, "Must visit OPTICAL_TRACKING"
    assert SystemState.FINE_ALIGNMENT in states_visited, "Must visit FINE_ALIGNMENT"
    assert orchestrator.state == SystemState.FSOC_ACTIVE, f"Must reach FSOC_ACTIVE, got {orchestrator.state}"
    assert orchestrator.telemetry.fsoc_status == "ESTABLISHED"
    print(">>> PASS: Test 1 Passed!")


def test_2_beacon_temporarily_disappears():
    """TEST 2: Beacon temporarily disappears.
    Expected: OPTICAL_TRACKING -> PREDICTIVE_RECOVERY -> LOCAL_REACQUISITION -> OPTICAL_TRACKING
    """
    print("\n" + "=" * 70)
    print("RUNNING TEST 2: Temporary Optical Loss & Predictive/Local Recovery")
    print("=" * 70)

    orchestrator = FSOCRecoveryOrchestrator(target_terminal_id="TERMINAL_02")
    orchestrator.env.camera.orientation_deg = 38.0
    orchestrator.start()

    # Reach tracking/active
    for _ in range(50):
        orchestrator.step(dt=0.1)
        if orchestrator.state == SystemState.FSOC_ACTIVE:
            break
    assert orchestrator.state == SystemState.FSOC_ACTIVE, "Precondition failed: Not in FSOC_ACTIVE"

    # 1. Temporary miss -> dead-reckoning PREDICTIVE_RECOVERY
    orchestrator.env.beacon.active = False
    orchestrator.step(dt=0.1)
    assert orchestrator.state == SystemState.PREDICTIVE_RECOVERY, "Must enter PREDICTIVE_RECOVERY"
    print("Step: Successfully entered PREDICTIVE_RECOVERY on optical drop")

    # Coast for 15 frames into LOCAL_REACQUISITION
    for _ in range(16):
        orchestrator.step(dt=0.1)
    assert orchestrator.state == SystemState.LOCAL_REACQUISITION, "Must enter LOCAL_REACQUISITION"
    print("Step: Successfully entered LOCAL_REACQUISITION on extended drop")

    # 2. Re-enable beacon: verify reacquisition directly from local search
    orchestrator.env.beacon.active = True
    orchestrator.step(dt=0.1)
    assert orchestrator.state in (SystemState.OPTICAL_TRACKING, SystemState.FINE_ALIGNMENT, SystemState.FSOC_ACTIVE), \
        f"Must return to tracking, got {orchestrator.state}"
    print(f"Step: Successfully restored to {orchestrator.state.name} upon beacon detection")
    print(">>> PASS: Test 2 Passed!")


def test_3_optical_recovery_completely_fails():
    """TEST 3: Optical recovery completely fails.
    Expected: OPTICAL_SEARCH/RECOVERY -> RF_DISCOVERY -> AUTHENTICATION -> RF_DIRECTION_RECOVERY -> OPTICAL_REACQUISITION
    """
    print("\n" + "=" * 70)
    print("RUNNING TEST 3: Deep Optical Loss Escalation to RF Recovery")
    print("=" * 70)

    orchestrator = FSOCRecoveryOrchestrator(target_terminal_id="TERMINAL_02")
    orchestrator.env.camera.orientation_deg = 38.0
    orchestrator.start()

    # Reach tracking first
    for _ in range(50):
        orchestrator.step(dt=0.1)
        if orchestrator.state == SystemState.FSOC_ACTIVE:
            break

    # Completely deactivate optical beacon
    orchestrator.env.beacon.active = False
    states_observed = []

    for step_i in range(100):
        orchestrator.step(dt=0.1)
        if orchestrator.state not in states_observed:
            states_observed.append(orchestrator.state)
            print(f"Step {step_i:3d}: State -> {orchestrator.state.name}")
        if orchestrator.state == SystemState.OPTICAL_REACQUISITION:
            break

    print("Sequence observed:", [s.name for s in states_observed])
    assert SystemState.PREDICTIVE_RECOVERY in states_observed, "Must enter PREDICTIVE_RECOVERY"
    assert SystemState.LOCAL_REACQUISITION in states_observed, "Must enter LOCAL_REACQUISITION"
    assert SystemState.RF_DISCOVERY in states_observed, "Must enter RF_DISCOVERY"
    assert SystemState.RF_AUTHENTICATION in states_observed, "Must enter RF_AUTHENTICATION"
    assert SystemState.RF_DIRECTION_RECOVERY in states_observed, "Must enter RF_DIRECTION_RECOVERY"
    assert orchestrator.state == SystemState.OPTICAL_REACQUISITION, f"Must reach OPTICAL_REACQUISITION, got {orchestrator.state}"
    assert orchestrator.telemetry.approximate_direction is not None
    print(f"Recovered coarse RF direction: {orchestrator.telemetry.approximate_direction} deg")
    print(">>> PASS: Test 3 Passed!")


def test_4_rf_authentication_fails():
    """TEST 4: RF authentication fails.
    Expected: RF_DISCOVERY -> RF_AUTHENTICATION -> RECOVERY_FAILED
    """
    print("\n" + "=" * 70)
    print("RUNNING TEST 4: Rogue Impostor Terminal & Authentication Rejection")
    print("=" * 70)

    # Instantiate orchestrator with invalid / rogue secret
    orchestrator = FSOCRecoveryOrchestrator(
        target_terminal_id="TERMINAL_02",
        target_secret="UNAUTHORIZED_ROGUE_KEY"
    )
    orchestrator.search_controller.search_speed = 60.0
    orchestrator.env.beacon.active = False
    orchestrator.start()

    for step_i in range(120):
        orchestrator.step(dt=0.1)
        if orchestrator.state == SystemState.RECOVERY_FAILED:
            print(f"Step {step_i:2d}: State transitioned to -> RECOVERY_FAILED")
            break

    assert orchestrator.state == SystemState.RECOVERY_FAILED, f"Must reach RECOVERY_FAILED, got {orchestrator.state}"
    assert orchestrator.telemetry.authentication_status == "REJECTED"
    print("Step: Successfully rejected rogue terminal and halted in RECOVERY_FAILED")
    print(">>> PASS: Test 4 Passed!")


def test_5_rf_direction_to_optical_reacquisition_to_fsoc():
    """TEST 5: Correct RF authentication followed by optical reacquisition.
    Expected: RF_DIRECTION_RECOVERY -> OPTICAL_REACQUISITION -> TRACKING -> FINE_ALIGNMENT -> FSOC_ACTIVE
    """
    print("\n" + "=" * 70)
    print("RUNNING TEST 5: Complete Handshake from RF Recovery to FSOC_ACTIVE")
    print("=" * 70)

    orchestrator = FSOCRecoveryOrchestrator(target_terminal_id="TERMINAL_02")
    orchestrator.env.camera.orientation_deg = 38.0
    orchestrator.start()

    # Reach active state first
    for _ in range(50):
        orchestrator.step(dt=0.1)
        if orchestrator.state == SystemState.FSOC_ACTIVE:
            break
    assert orchestrator.state == SystemState.FSOC_ACTIVE

    # Sever link completely to trigger full RF recovery
    orchestrator.env.beacon.active = False
    for _ in range(80):
        orchestrator.step(dt=0.1)
        if orchestrator.state == SystemState.OPTICAL_REACQUISITION:
            break

    assert orchestrator.state == SystemState.OPTICAL_REACQUISITION
    print("Reached OPTICAL_REACQUISITION via RF bearing slew")

    # Step through optical reacquisition, fine alignment, and link restoration
    for step_i in range(30):
        orchestrator.step(dt=0.1)
        if orchestrator.state == SystemState.FSOC_ACTIVE:
            print(f"Step {step_i:2d}: Successfully re-established FSOC_ACTIVE!")
            break

    assert orchestrator.state == SystemState.FSOC_ACTIVE, f"Must restore to FSOC_ACTIVE, got {orchestrator.state}"
    assert orchestrator.telemetry.fsoc_status == "ESTABLISHED"
    print(">>> PASS: Test 5 Passed!")


def test_6_independent_parts_still_pass():
    """TEST 6: Existing Part 1, Part 2, and Part 3 modules still run independently."""
    print("\n" + "=" * 70)
    print("RUNNING TEST 6: Independent Execution of Parts 1, 2, and 3")
    print("=" * 70)

    # 1. Part 3 RF Module
    import test_rf_discovery_Ashish as part3_tests
    print("[Verifying Part 3 Independent Execution...]")
    part3_tests.test_case_1_successful_recovery()
    part3_tests.test_case_2_wrong_terminal()
    part3_tests.test_case_3_authentication_failure()
    part3_tests.test_case_4_no_terminal_found()
    part3_tests.test_case_5_dynamic_direction()
    part3_tests.test_case_6_distance_based_rssi()
    part3_tests.test_case_7_secret_not_exposed_in_discovery()
    print(">>> Part 3: 7/7 independent tests PASSED.")

    # 2. Part 2 Kalman & Tracking State Module
    print("[Verifying Part 2 Independent Execution...]")
    from src.tracking_state import TrackingState, BeaconMeasurement
    from src.kalman_tracker import KalmanBeaconTracker
    from src.local_search import LocalSearch, LocalSearchConfig
    
    tracker = KalmanBeaconTracker()
    meas = BeaconMeasurement(timestamp=1.0, position=(640.0, 360.0), detected=True, confidence=0.95)
    res = tracker.process_frame(meas, timestamp=1.0)
    assert res.state == TrackingState.TRACKING
    assert abs(res.position[0] - 640.0) < 5.0
    
    ls = LocalSearch(LocalSearchConfig())
    wpt = ls.update((640.0, 360.0), is_searching=True)
    assert len(wpt) == 2
    print(">>> Part 2: Kalman tracker & LocalSearch independent verification PASSED.")

    # 3. Part 1 Optical Detection & Environment Module
    print("[Verifying Part 1 Independent Execution...]")
    from src.simulation.environment import FSOCEnvironment
    from src.simulation.camera import VirtualCameraSensor
    from src.detection.beacon_detector import ClassicalBeaconDetector
    from src.detection.alignment import AlignmentCalculator

    env = FSOCEnvironment({"simulation": {"width": 1280, "height": 720}})
    cam_sensor = VirtualCameraSensor(env.camera)
    detector = ClassicalBeaconDetector()
    frame = cam_sensor.capture_frame(env.beacon)
    det_res = detector.detect(frame)
    calc = AlignmentCalculator(image_width=1280, image_height=720, fov_deg=35.0)
    align_res = calc.calculate(det_res)
    assert align_res is not None
    print(">>> Part 1: Environment, CameraSensor & ClassicalBeaconDetector independent verification PASSED.")

    print(">>> PASS: Test 6 Passed!")


def run_all_tests():
    """Execute all integration test cases sequentially."""
    print("=" * 78)
    print("PART 4: AUTONOMOUS FSOC ADAPTIVE RECOVERY INTEGRATION TEST SUITE")
    print("=" * 78)

    test_1_beacon_immediately_detected()
    test_2_beacon_temporarily_disappears()
    test_3_optical_recovery_completely_fails()
    test_4_rf_authentication_fails()
    test_5_rf_direction_to_optical_reacquisition_to_fsoc()
    test_6_independent_parts_still_pass()

    print("\n" + "=" * 78)
    print("ALL 6 INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 78)


if __name__ == "__main__":
    run_all_tests()
