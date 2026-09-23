"""Part 4: Autonomous Adaptive Recovery & Complete Integration Backend Entry Point.

Orchestrates:
- Part 1: Optical Environment, Virtual Camera Sensor & Centroid Detection
- Part 2: Kalman Predictive Tracking, Disturbance Handling & Local Spiral Reacquisition
- Part 3: Auxiliary RF Multi-Channel Discovery & HMAC-SHA256 Cryptographic Authentication
- Part 4: Central Autonomous Finite State Machine & Telemetry Provider

Usage:
    python run_part4.py
    python run_part4.py --scenario deep-loss
    python run_part4.py --scenario rogue-auth
    python run_part4.py --scenario temporary-loss
    python run_part4.py --help
"""

import argparse
import sys
import time

from src.orchestrator.states import SystemState
from src.orchestrator.controller import FSOCRecoveryOrchestrator


def run_orchestration(scenario: str = "normal", max_steps: int = 150, delay: float = 0.05) -> None:
    """Runs the integrated Part 4 recovery and control loop under specified scenario.
    
    Args:
        scenario: Test scenario: 'normal', 'temporary-loss', 'deep-loss', 'rogue-auth'
        max_steps: Maximum simulation tick steps to execute
        delay: Real-time delay between frames (seconds) for console readability
    """
    print("=" * 78)
    print("TEAM RAYNEX: PART 4 AUTONOMOUS FSOC RECOVERY & TRACKING SYSTEM")
    print("=" * 78)
    print(f"Scenario Selected : {scenario.upper()}")
    print("Subsystems Active : Part 1 (Optical) + Part 2 (Kalman) + Part 3 (RF HMAC)")
    print("-" * 78)

    target_id = "TERMINAL_02"
    target_secret = "UNAUTHORIZED_KEY_02" if scenario == "rogue-auth" else None

    orchestrator = FSOCRecoveryOrchestrator(
        target_terminal_id=target_id,
        target_secret=target_secret
    )
    orchestrator.env.camera.orientation_deg = 38.0
    orchestrator.start()

    loss_triggered = False

    try:
        for step_idx in range(max_steps):
            # Inject disturbances based on scenario
            if scenario == "temporary-loss":
                # Drops beacon at step 15 for 6 frames, then restores
                if 15 <= step_idx < 21:
                    orchestrator.env.beacon.active = False
                else:
                    orchestrator.env.beacon.active = True

            elif scenario in ("deep-loss", "rogue-auth"):
                # Drops beacon at step 15 permanently to force RF recovery
                if step_idx >= 15 and not loss_triggered:
                    orchestrator.env.beacon.active = False
                    loss_triggered = True

            # Step orchestrator state machine
            telem = orchestrator.step(dt=0.1)

            # Format status banner
            err_str = f"{telem.pointing_error_px:.1f} px" if telem.pointing_error_px is not None else "N/A"
            conf_str = f"{telem.tracking_confidence * 100:.1f}%"
            rf_dir_str = f"{telem.approximate_direction:.1f}°" if telem.approximate_direction is not None else "N/A"
            
            print(
                f"[Step {step_idx:3d}] State: {telem.current_state:<22} | "
                f"FSOC: {telem.fsoc_status:<11} | "
                f"Tracking: {telem.tracking_status:<10} | "
                f"Err: {err_str:<8} | "
                f"Conf: {conf_str:<6} | "
                f"RF Dir: {rf_dir_str}"
            )

            # Terminal conditions
            if telem.current_state == SystemState.RECOVERY_FAILED.name:
                print("\n[HALT] System reached RECOVERY_FAILED terminal safety state.")
                break

            if scenario == "normal" and telem.current_state == SystemState.FSOC_ACTIVE.name and step_idx >= 25:
                print("\n[SUCCESS] FSOC optical link established and verified stable.")
                break

            if scenario in ("temporary-loss", "deep-loss") and step_idx >= 60 and telem.current_state == SystemState.FSOC_ACTIVE.name:
                print("\n[SUCCESS] Autonomous recovery completed! FSOC optical link restored.")
                break

            if delay > 0:
                time.sleep(delay)

    except KeyboardInterrupt:
        print("\n[INFO] Demonstration interrupted by user.")

    print("=" * 78)
    print("FINAL ORCHESTRATOR TELEMETRY SUMMARY")
    print("=" * 78)
    print(f"  Final State         : {orchestrator.telemetry.current_state}")
    print(f"  FSOC Link Status    : {orchestrator.telemetry.fsoc_status}")
    print(f"  Beacon Detected     : {orchestrator.telemetry.beacon_detected}")
    print(f"  Tracking Status     : {orchestrator.telemetry.tracking_status}")
    print(f"  Target Terminal     : {orchestrator.telemetry.terminal_id}")
    print(f"  Authentication      : {orchestrator.telemetry.authentication_status}")
    print(f"  Coarse RF Direction : {orchestrator.telemetry.approximate_direction}")
    print(f"  Camera Orientation  : {orchestrator.telemetry.camera_orientation_deg:.2f}°")
    print(f"  Total Events Logged : {len(orchestrator.event_log)}")
    print("=" * 78)


def main() -> None:
    """CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Team Raynex Part 4: Autonomous FSOC Adaptive Recovery & Integration Orchestrator"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="deep-loss",
        choices=["normal", "temporary-loss", "deep-loss", "rogue-auth"],
        help="Operational scenario to simulate (default: 'deep-loss')",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=90,
        help="Maximum simulation frames to run (default: 90)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run without console sleep delay for rapid testing",
    )

    args = parser.parse_args()
    delay = 0.0 if args.fast else 0.03
    run_orchestration(scenario=args.scenario, max_steps=args.steps, delay=delay)


if __name__ == "__main__":
    main()
