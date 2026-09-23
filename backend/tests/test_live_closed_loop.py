"""
Team Raynex: Autonomous FSOC PAT Closed-Loop Simulation Test Suite
=================================================================
Validates the complete closed-loop dynamics:
1. Continuous dynamic flight trajectory of the moving terminal (never stationary).
2. Closed-loop optical servoing of the camera tracking the moving beacon.
3. Multi-tier autonomous recovery hierarchy:
   Optical loss -> PREDICTIVE_RECOVERY -> LOCAL_REACQUISITION -> OPTICAL_SEARCH
   -> RF_DISCOVERY -> RF_AUTHENTICATION -> RF_DIRECTION_RECOVERY
   -> OPTICAL_REACQUISITION -> FINE_ALIGNMENT -> FSOC_ACTIVE.
4. Position continuity: terminal coordinates change continuously throughout.
5. Cryptographic rejection of rogue RF beacon.
"""

import math
import os
import sys
import time
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.simulation.environment import FSOCEnvironment
from src.orchestrator.controller import FSOCRecoveryOrchestrator, SystemState


def test_dynamic_motion_trajectory_kinematics():
    """Verify that dynamic flight creates continuous curved motion with valid velocity & heading."""
    print("Testing dynamic motion trajectory kinematics...")
    orchestrator = FSOCRecoveryOrchestrator()
    orchestrator.enable_motion("dynamic_flight")
    env = orchestrator.env
    
    initial_pos = (env.terminal_b.x, env.terminal_b.y)
    positions = [initial_pos]
    
    # Step simulation across 50 frames
    for _ in range(50):
        env.update(dt=0.05)
        positions.append((env.terminal_b.x, env.terminal_b.y))
        
        vel = env.get_terminal_velocity()
        speed = env.get_terminal_speed()
        heading = env.get_terminal_heading_deg()
        
        assert speed > 0.0, "Terminal must have non-zero speed during dynamic flight"
        assert 0.0 <= heading <= 360.0, f"Heading must be in [0, 360], got {heading}"
        assert math.isclose(speed, math.hypot(vel[0], vel[1]), rel_tol=1e-3)
        
    # Verify terminal moved continuously and did not stay frozen
    final_pos = positions[-1]
    assert final_pos != initial_pos, "Terminal position must change over time"
    # Verify positions are all distinct successive frames
    for i in range(len(positions) - 1):
        assert positions[i] != positions[i + 1], f"Frame {i} to {i+1} terminal was stationary!"
    print("  -> PASS: Continuous curved flight trajectory verified.")


def test_closed_loop_tracking_under_continuous_motion():
    """Verify camera closed-loop optical servoing follows moving terminal."""
    print("Testing closed-loop tracking under continuous motion...")
    orchestrator = FSOCRecoveryOrchestrator()
    orchestrator.env.camera.orientation_deg = 38.0
    orchestrator.enable_motion("dynamic_flight")
    orchestrator.start()
    
    # Run until FSOC_ACTIVE is reached
    active = False
    for _ in range(100):
        telem = orchestrator.step(dt=0.05)
        if telem.current_state == "FSOC_ACTIVE":
            active = True
            break
            
    assert active, f"System should reach FSOC_ACTIVE, got {orchestrator.state.name}"
    
    # Record tracking errors over 30 steps of active flight
    tracking_errors = []
    positions = []
    for _ in range(30):
        telem = orchestrator.step(dt=0.05)
        assert telem.current_state == "FSOC_ACTIVE"
        assert telem.terminal_world_position is not None
        positions.append(telem.terminal_world_position)
        if telem.pointing_error_px is not None:
            tracking_errors.append(telem.pointing_error_px)
            
    # Verify terminal moved continuously
    assert len(set(positions)) == len(positions), "Terminal must move every frame"
    # Verify camera servo kept pointing error small (< 60 px in sensor coordinates under high-speed flight)
    assert len(tracking_errors) > 20
    assert np.mean(tracking_errors) < 60.0, f"Average tracking error too high: {np.mean(tracking_errors)}"
    print(f"  -> PASS: Closed-loop tracking lock maintained (mean error: {np.mean(tracking_errors):.2f} px).")


def test_complete_multi_tier_recovery_under_motion():
    """
    Verify complete multi-tier recovery sequence while terminal continuously moves:
    FSOC_ACTIVE -> Loss -> PREDICTIVE -> LOCAL -> OPTICAL_SEARCH -> RF_DISCOVERY
    -> RF_AUTH -> RF_DIRECTION -> OPTICAL_REACQUISITION -> FINE_ALIGNMENT -> FSOC_ACTIVE.
    """
    print("Testing complete multi-tier recovery sequence under flight...")
    orchestrator = FSOCRecoveryOrchestrator()
    orchestrator.env.camera.orientation_deg = 38.0
    orchestrator.enable_motion("dynamic_flight")
    orchestrator.start()
    
    # 1. Establish FSOC_ACTIVE
    for _ in range(100):
        telem = orchestrator.step(dt=0.05)
        if telem.current_state == "FSOC_ACTIVE":
            break
    assert orchestrator.state == SystemState.FSOC_ACTIVE
    
    # 2. Induce cloud occlusion (turn off optical beacon)
    orchestrator.env.beacon.active = False
    
    visited_states = []
    terminal_coords = []
    
    # Step through recovery
    reacquired = False
    for step_i in range(250):
        # When entering OPTICAL_REACQUISITION, clear the cloud occlusion so beacon is visible
        if orchestrator.state == SystemState.OPTICAL_REACQUISITION:
            orchestrator.env.beacon.active = True
            
        telem = orchestrator.step(dt=0.05)
        state_name = orchestrator.state.name
        if state_name not in visited_states:
            visited_states.append(state_name)
            
        terminal_coords.append((orchestrator.env.terminal_b.x, orchestrator.env.terminal_b.y))
        
        if orchestrator.state == SystemState.FSOC_ACTIVE and "RF_DIRECTION_RECOVERY" in visited_states:
            reacquired = True
            break
            
    # Verify complete recovery path was traversed
    expected_order = [
        "FSOC_ACTIVE",
        "PREDICTIVE_RECOVERY",
        "LOCAL_REACQUISITION",
        "OPTICAL_SEARCH",
        "RF_DISCOVERY",
        "RF_AUTHENTICATION",
        "RF_DIRECTION_RECOVERY",
        "OPTICAL_REACQUISITION",
        "FINE_ALIGNMENT",
    ]
    for exp_state in expected_order:
        assert exp_state in visited_states, f"State {exp_state} missing from recovery sequence: {visited_states}"
        
    assert reacquired, f"System failed to reacquire FSOC_ACTIVE, ended in {orchestrator.state.name}"
    
    # Verify terminal moved during EVERY single step of recovery
    for i in range(len(terminal_coords) - 1):
        assert terminal_coords[i] != terminal_coords[i + 1], f"Terminal was stationary at step {i}!"
    print(f"  -> PASS: Complete recovery sequence verified through states: {visited_states}")


def test_rogue_rf_authentication_rejection():
    """Verify that a rogue RF beacon with invalid cryptographic signature is rejected."""
    print("Testing rogue RF authentication rejection...")
    orchestrator = FSOCRecoveryOrchestrator()
    orchestrator.enable_motion("dynamic_flight")
    
    # Fast forward to RF_AUTHENTICATION
    orchestrator.state = SystemState.RF_AUTHENTICATION
    # Configure unauthenticated rogue terminal
    orchestrator.target_terminal_id = "TERMINAL_ROGUE_UNKNOWN"
    
    for _ in range(5):
        telem = orchestrator.step(dt=0.05)
        
    assert orchestrator.state == SystemState.RECOVERY_FAILED
    assert telem.authentication_status == "REJECTED"
    print("  -> PASS: Rogue RF beacon correctly rejected with HMAC failure.")


def main():
    print("\n" + "=" * 80)
    print("       TEAM RAYNEX: REALISTIC LIVE CLOSED-LOOP SIMULATION TEST SUITE")
    print("=" * 80)
    start_time = time.time()
    
    test_dynamic_motion_trajectory_kinematics()
    test_closed_loop_tracking_under_continuous_motion()
    test_complete_multi_tier_recovery_under_motion()
    test_rogue_rf_authentication_rejection()
    
    elapsed = time.time() - start_time
    print("-" * 80)
    print(f"ALL 4 LIVE CLOSED-LOOP TESTS PASSED in {elapsed:.2f}s!")
    print("=" * 80 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
