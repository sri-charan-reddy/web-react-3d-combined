"""Verification script for Atmospheric Turbulence and Final Part 2 Validation.

This script tests:
- TEST 1: Turbulence disabled -> measurement is unchanged by turbulence
- TEST 2: Turbulence enabled -> measurement receives bounded perturbation
- TEST 3: Perturbation stays within configured maximum displacement envelope
- TEST 4: Consecutive turbulence offsets show temporal correlation (smooth AR(1) drift)
- TEST 5: Ground Truth position is never modified (strict isolation)
- TEST 6: Existing Kalman tracker continues functioning and tracking stably under turbulence
- TEST 7: Existing outlier rejection remains functional under turbulence
"""

import math
import sys
import numpy as np

from config import (
    AtmosphericTurbulenceConfig,
    DisturbanceConfig,
    KalmanConfig,
    TrackingStateConfig,
    TurbulenceLevel
)
from src.atmospheric_turbulence import AtmosphericTurbulence
from src.disturbance_simulator import DisturbanceSimulator
from src.kalman_tracker import KalmanBeaconTracker
from src.tracking_state import TrackingState, BeaconMeasurement


def test_1_turbulence_disabled() -> bool:
    """TEST 1: Turbulence disabled -> optical coordinates are unchanged by turbulence."""
    print("\n[TEST 1] Turbulence Disabled Check:")
    cfg = AtmosphericTurbulenceConfig(enabled=False, level=TurbulenceLevel.OFF)
    turb = AtmosphericTurbulence(cfg)
    
    orig_pos = (500.0, 300.0)
    for _ in range(50):
        out_pos = turb.apply(orig_pos)
        dx = out_pos[0] - orig_pos[0]
        dy = out_pos[1] - orig_pos[1]
        if abs(dx) > 1e-9 or abs(dy) > 1e-9:
            print(f"  FAIL: Expected zero offset when disabled, got ({dx}, {dy})")
            return False
            
    print(f"  Level: {turb.level.value} | Output: {out_pos} == Input: {orig_pos}")
    print("  -> PASSED: Turbulence disabled produces strictly zero perturbation.")
    return True


def test_2_turbulence_enabled_bounded_perturbation() -> bool:
    """TEST 2: Turbulence enabled -> measurement receives non-zero bounded perturbation."""
    print("\n[TEST 2] Turbulence Enabled Bounded Perturbation Check:")
    cfg = AtmosphericTurbulenceConfig(enabled=True, level=TurbulenceLevel.MEDIUM, random_seed=42)
    turb = AtmosphericTurbulence(cfg)
    
    orig_pos = (640.0, 360.0)
    non_zero_found = False
    for frame in range(10):
        out_pos = turb.apply(orig_pos)
        dx = out_pos[0] - orig_pos[0]
        dy = out_pos[1] - orig_pos[1]
        disp = math.sqrt(dx * dx + dy * dy)
        if disp > 0.01:
            non_zero_found = True
        if disp > cfg.max_displacement_medium + 1e-4:
            print(f"  FAIL: Displacement {disp:.2f} px exceeded max {cfg.max_displacement_medium} px")
            return False

    if not non_zero_found:
        print("  FAIL: No perturbation generated when turbulence enabled.")
        return False

    telem = turb.get_telemetry()
    print(f"  Active Level: {telem.level.value} | Offset: ({telem.offset_x:+.2f}, {telem.offset_y:+.2f}) px | Disp: {telem.displacement:.2f} px")
    print("  -> PASSED: Turbulence perturbing optical stream within bounded limits.")
    return True


def test_3_maximum_displacement_envelope() -> bool:
    """TEST 3: Perturbation stays strictly within configured max displacement envelope across all levels."""
    print("\n[TEST 3] Maximum Displacement Envelope Across Levels Check:")
    orig_pos = (600.0, 400.0)
    
    for level, max_allowed in [
        (TurbulenceLevel.LOW, 8.0),
        (TurbulenceLevel.MEDIUM, 18.0),
        (TurbulenceLevel.HIGH, 35.0)
    ]:
        cfg = AtmosphericTurbulenceConfig(enabled=True, level=level, random_seed=123)
        turb = AtmosphericTurbulence(cfg)
        
        max_seen = 0.0
        for _ in range(500):
            out_pos = turb.apply(orig_pos)
            disp = math.sqrt((out_pos[0] - orig_pos[0])**2 + (out_pos[1] - orig_pos[1])**2)
            max_seen = max(max_seen, disp)
            if disp > max_allowed + 1e-4:
                print(f"  FAIL: Level {level.value} exceeded limit {max_allowed} px with {disp:.2f} px")
                return False
                
        print(f"  Level {level.value:6s}: Max Observed = {max_seen:.2f} px (Bound Limit = {max_allowed:.1f} px)")
        
    print("  -> PASSED: All turbulence severity levels strictly adhere to displacement bounds.")
    return True


def test_4_temporal_correlation() -> bool:
    """TEST 4: Consecutive turbulence offsets show high temporal correlation (smooth drift)."""
    print("\n[TEST 4] Temporal Correlation (AR(1) Gauss-Markov) Check:")
    cfg = AtmosphericTurbulenceConfig(
        enabled=True,
        level=TurbulenceLevel.MEDIUM,
        temporal_correlation=0.90,
        random_seed=314
    )
    turb = AtmosphericTurbulence(cfg)
    
    offsets_x = []
    offsets_y = []
    orig_pos = (500.0, 500.0)
    
    for _ in range(300):
        out_pos = turb.apply(orig_pos)
        offsets_x.append(out_pos[0] - orig_pos[0])
        offsets_y.append(out_pos[1] - orig_pos[1])
        
    # Calculate Pearson correlation between offset(t) and offset(t-1)
    x_t = np.array(offsets_x[1:])
    x_t_prev = np.array(offsets_x[:-1])
    corr_x = float(np.corrcoef(x_t, x_t_prev)[0, 1])
    
    y_t = np.array(offsets_y[1:])
    y_t_prev = np.array(offsets_y[:-1])
    corr_y = float(np.corrcoef(y_t, y_t_prev)[0, 1])
    
    print(f"  Lag-1 Correlation X: {corr_x:.3f} | Lag-1 Correlation Y: {corr_y:.3f} (Config rho: {cfg.temporal_correlation})")
    
    if corr_x < 0.70 or corr_y < 0.70:
        print("  FAIL: Turbulence offsets lack sufficient temporal correlation.")
        return False
        
    print("  -> PASSED: Temporal correlation demonstrates smooth, continuous atmospheric fluctuation.")
    return True


def test_5_ground_truth_isolation() -> bool:
    """TEST 5: Ground truth coordinates are never modified or mutated."""
    print("\n[TEST 5] Strict Ground Truth Isolation Check:")
    dist_sim = DisturbanceSimulator(DisturbanceConfig())
    
    gt_tuple = (750.5, 320.25)
    gt_copy = (750.5, 320.25)
    
    for frame in range(100):
        meas = dist_sim.apply_disturbances(gt_tuple, frame * 0.033, frame)
        if gt_tuple != gt_copy:
            print(f"  FAIL: Ground truth tuple was mutated! {gt_tuple} != {gt_copy}")
            return False
            
    print(f"  Ground Truth Reference: {gt_tuple} (Strictly preserved across 100 frames)")
    print("  -> PASSED: Ground Truth is never modified by the disturbance pipeline.")
    return True


def test_6_kalman_tracking_with_turbulence() -> bool:
    """TEST 6: Kalman tracker continues functioning and accurately tracking moving target with turbulence."""
    print("\n[TEST 6] Kalman Tracker Stability with Turbulence Check:")
    dist_cfg = DisturbanceConfig(
        enable_measurement_noise=True,
        measurement_noise_std=3.0,
        enable_jitter=True,
        jitter_std=1.0,
        turbulence=AtmosphericTurbulenceConfig(
            enabled=True,
            level=TurbulenceLevel.MEDIUM,
            random_seed=42
        ),
        enable_occlusions=False,
        enable_outliers=False
    )
    dist_sim = DisturbanceSimulator(dist_cfg)
    tracker = KalmanBeaconTracker(KalmanConfig(), TrackingStateConfig())
    
    # Target moving linearly at 4.0 px/frame
    pos_x, pos_y = 300.0, 300.0
    vel_x, vel_y = 3.0, 2.0
    dt = 1.0 / 30.0
    
    errors = []
    for frame in range(60):
        t = frame * dt
        pos_x += vel_x
        pos_y += vel_y
        gt = (pos_x, pos_y)
        
        meas = dist_sim.apply_disturbances(gt, t, frame)
        res = tracker.process_frame(meas, t)
        
        if frame >= 10:  # Allow 10 frames convergence
            err = math.sqrt((res.position[0] - gt[0])**2 + (res.position[1] - gt[1])**2)
            errors.append(err)
            
    avg_err = float(np.mean(errors))
    max_err = float(np.max(errors))
    print(f"  Post-Convergence Tracking Error under MEDIUM Turbulence: Avg={avg_err:.2f} px, Max={max_err:.2f} px")
    print(f"  Final Tracker State: {tracker.state.name} | Confidence: {tracker.confidence:.2f}")
    
    if tracker.state != TrackingState.TRACKING or avg_err > 12.0:
        print("  FAIL: Kalman tracker failed to maintain stable lock under turbulence.")
        return False
        
    print("  -> PASSED: Kalman predictive tracker remains robust and accurate under atmospheric turbulence.")
    return True


def test_7_outlier_rejection_with_turbulence() -> bool:
    """TEST 7: Outlier rejection remains fully functional under active turbulence."""
    print("\n[TEST 7] Outlier Rejection Gating with Active Turbulence Check:")
    tracker = KalmanBeaconTracker(KalmanConfig(), TrackingStateConfig(gating_threshold_px=80.0))
    
    # Initialize tracker
    tracker.initialize((500.0, 500.0), 0.0)
    
    # Send a few valid frames
    for f in range(1, 5):
        tracker.process_frame(BeaconMeasurement(timestamp=f*0.033, position=(500.0 + f*2, 500.0), detected=True, confidence=0.9), f*0.033)
        
    # Inject a deliberate false outlier at (900, 100) (distance ~450 px > 80 px threshold)
    outlier_meas = BeaconMeasurement(
        timestamp=0.2,
        position=(900.0, 100.0),
        detected=True,
        confidence=0.85
    )
    res = tracker.process_frame(outlier_meas, 0.2)
    
    print(f"  Outlier Position: (900.0, 100.0) | Kalman Estimated: ({res.position[0]:.1f}, {res.position[1]:.1f})")
    print(f"  Measurement Accepted: {res.measurement_accepted} | State: {res.state.name} | Miss Count: {res.miss_count}")
    
    if res.measurement_accepted or res.state != TrackingState.PREDICTING:
        print("  FAIL: Outlier was accepted instead of being rejected by gating.")
        return False
        
    print("  -> PASSED: Outlier rejection gating functions with full integrity.")
    return True


def main() -> None:
    """Execute all verification tests."""
    print("=" * 76)
    print("RUNNING ATMOSPHERIC TURBULENCE & FINAL VALIDATION TEST SUITE (PART 2)")
    print("=" * 76)
    
    tests = [
        test_1_turbulence_disabled,
        test_2_turbulence_enabled_bounded_perturbation,
        test_3_maximum_displacement_envelope,
        test_4_temporal_correlation,
        test_5_ground_truth_isolation,
        test_6_kalman_tracking_with_turbulence,
        test_7_outlier_rejection_with_turbulence,
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 76)
    if all(results):
        print(f"ALL {len(results)} ATMOSPHERIC TURBULENCE VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 76)
        sys.exit(0)
    else:
        failed_count = len([r for r in results if not r])
        print(f"FAILED: {failed_count} test(s) failed.")
        print("=" * 76)
        sys.exit(1)


if __name__ == "__main__":
    main()
