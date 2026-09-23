"""Team Raynex: Unified Master Test & Quality Suite.

Executes and benchmarks all test suites across the entire repository:
1. Part 1: Optical PAT Environment, Camera Sensor, Centroid Detection & Alignment (5 checks)
2. Part 2: Kalman Predictive Tracking, Turbulence, Servoing & Local Search (31 tests)
3. Part 3: Auxiliary RF Discovery & HMAC-SHA256 Cryptographic Authentication (7 tests)
4. Part 4: Autonomous Adaptive Recovery Closed-Loop Orchestration (6 scenarios)
5. Web Dashboard: HTTP Server, SSE Stream, Actions & Disturbance APIs (7 tests)

Usage:
    python run_all_tests.py
    python run_all_tests.py --quiet
    python run_all_tests.py --verbose
"""

import argparse
import os
import subprocess
import sys
import time
from typing import Dict, List, NamedTuple, Optional

# Automatically re-execute within local .venv if running with system Python
_venv_python = os.path.abspath(os.path.join(os.path.dirname(__file__), ".venv", "bin", "python3"))
if os.path.exists(_venv_python) and sys.executable != _venv_python:
    try:
        import cv2, yaml, numpy
    except ImportError:
        os.execv(_venv_python, [_venv_python] + sys.argv)

# Ensure project root in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class SuiteResult(NamedTuple):
    name: str
    subsystem: str
    target_file: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    duration_sec: float
    success: bool
    details: str


def run_part1_verification() -> SuiteResult:
    """Runs Part 1 optical environment, sensor projection, and centroid detection."""
    start_time = time.time()
    passed = 0
    total = 5
    details = []

    try:
        from src.simulation.environment import FSOCEnvironment
        from src.simulation.camera import VirtualCameraSensor
        from src.detection.beacon_detector import ClassicalBeaconDetector
        from src.detection.alignment import AlignmentCalculator
        from src.control.pat_controller import VirtualPATController

        # 1. Environment creation
        env = FSOCEnvironment({"simulation": {"width": 1280, "height": 720}, "camera": {"orientation_deg": 0.0, "field_of_view_deg": 35.0, "image_width": 1280, "image_height": 720}})
        assert env.width == 1280 and env.height == 720
        passed += 1

        # 2. Virtual camera frame capture
        sensor = VirtualCameraSensor(env.camera)
        frame = sensor.capture_frame(env.beacon)
        assert frame is not None and frame.shape == (720, 1280, 3)
        passed += 1

        # 3. Classical beacon centroid detector
        detector = ClassicalBeaconDetector()
        det_res = detector.detect(frame)
        assert det_res.detected is True
        assert det_res.center_x is not None and det_res.center_y is not None
        passed += 1

        # 4. Pointing alignment calculator
        align_calc = AlignmentCalculator()
        align_res = align_calc.calculate(det_res)
        assert align_res.alignment_state in ("ALIGNED", "COARSE_ALIGNED", "UNALIGNED")
        passed += 1

        # 5. PAT closed-loop controller update
        pat_ctrl = VirtualPATController()
        ctrl_res = pat_ctrl.update(env.camera.orientation_deg, align_res)
        assert ctrl_res.new_orientation_deg is not None
        passed += 1

        elapsed = time.time() - start_time
        return SuiteResult(
            name="Optical PAT & Detection",
            subsystem="Part 1 (Manoj)",
            target_file="src/simulation/ & src/detection/",
            total_tests=total,
            passed_tests=passed,
            failed_tests=0,
            duration_sec=elapsed,
            success=True,
            details="All optical perception & alignment stages verified"
        )
    except Exception as exc:
        elapsed = time.time() - start_time
        return SuiteResult(
            name="Optical PAT & Detection",
            subsystem="Part 1 (Manoj)",
            target_file="src/simulation/ & src/detection/",
            total_tests=total,
            passed_tests=passed,
            failed_tests=total - passed,
            duration_sec=elapsed,
            success=False,
            details=str(exc)
        )


def run_script_suite(name: str, subsystem: str, script_relpath: str, expected_tests: int, verbose: bool = False) -> SuiteResult:
    """Executes a standalone test script as a subprocess and parses outcome."""
    start_time = time.time()
    script_path = os.path.join(PROJECT_ROOT, script_relpath)
    
    if not os.path.exists(script_path):
        return SuiteResult(
            name=name,
            subsystem=subsystem,
            target_file=script_relpath,
            total_tests=expected_tests,
            passed_tests=0,
            failed_tests=expected_tests,
            duration_sec=0.0,
            success=False,
            details="Script file not found"
        )

    cmd = [sys.executable, script_path]
    try:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60)
        elapsed = time.time() - start_time
        success = (proc.returncode == 0)
        
        if verbose and not success:
            print(f"\n[STDERR for {script_relpath}]:\n{proc.stderr}")
            print(f"[STDOUT for {script_relpath}]:\n{proc.stdout}")

        return SuiteResult(
            name=name,
            subsystem=subsystem,
            target_file=script_relpath,
            total_tests=expected_tests,
            passed_tests=expected_tests if success else 0,
            failed_tests=0 if success else expected_tests,
            duration_sec=elapsed,
            success=success,
            details="All assertions verified" if success else (proc.stderr.strip() or "Subprocess failed")
        )
    except Exception as exc:
        elapsed = time.time() - start_time
        return SuiteResult(
            name=name,
            subsystem=subsystem,
            target_file=script_relpath,
            total_tests=expected_tests,
            passed_tests=0,
            failed_tests=expected_tests,
            duration_sec=elapsed,
            success=False,
            details=str(exc)
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Team Raynex Master Test & Quality Suite")
    parser.add_argument("--verbose", action="store_true", help="Print detailed diagnostic output")
    parser.add_argument("--quiet", action="store_true", help="Print only summary table")
    args = parser.parse_args(argv)

    print("\n" + "=" * 92)
    print("           TEAM RAYNEX: FSOC PAT MASTER QUALITY & TEST EVALUATION SUITE")
    print("             Smart India Hackathon 2026 • Problem Statement: SIH26169")
    print("=" * 92)
    print(f"Executing with Python Interpreter : {sys.executable}")
    print(f"Project Workspace Directory        : {PROJECT_ROOT}")
    print("-" * 92)

    suites_to_run = [
        # Part 1
        ("Part 1: Optical PAT & Vision", "Part 1 (Manoj)", "part1_internal", 5),
        # Part 2
        ("Part 2: Atmospheric Turbulence", "Part 2 (Simhadri)", "verify_atmospheric_turbulence.py", 7),
        ("Part 2: Virtual Camera Model", "Part 2 (Simhadri)", "verify_camera.py", 6),
        ("Part 2: Camera Servoing Controller", "Part 2 (Simhadri)", "verify_camera_controller.py", 7),
        ("Part 2: Local Search Reacquisition", "Part 2 (Simhadri)", "verify_local_search.py", 7),
        ("Part 2: LOST State Controlled Recovery", "Part 2 (Simhadri)", "verify_lost_reacquisition.py", 4),
        # Part 3
        ("Part 3: RF Discovery & HMAC Security", "Part 3 (Ashish)", "test_rf_discovery_Ashish.py", 7),
        # Part 4
        ("Part 4: Autonomous Recovery Integration", "Part 4 (Orchestrator)", "tests/test_part4_integration.py", 6),
        ("Part 4: Realistic Live Closed Loop", "Part 4 (Closed-Loop)", "tests/test_live_closed_loop.py", 4),
        # Web Dashboard
        ("Frontend: Web Mission Control & APIs", "Part 4 (Dashboard)", "tests/test_dashboard_server.py", 7),
    ]

    results: List[SuiteResult] = []
    total_tests_overall = 0
    passed_tests_overall = 0
    failed_tests_overall = 0
    start_all = time.time()

    for name, subsystem, target, expected in suites_to_run:
        if not args.quiet:
            print(f"-> Running {name:<42} [{subsystem}] ...", end="", flush=True)

        if target == "part1_internal":
            res = run_part1_verification()
        else:
            res = run_script_suite(name, subsystem, target, expected, verbose=args.verbose)

        results.append(res)
        total_tests_overall += res.total_tests
        passed_tests_overall += res.passed_tests
        failed_tests_overall += res.failed_tests

        if not args.quiet:
            status_str = "PASS" if res.success else "FAIL"
            print(f" {status_str} ({res.passed_tests}/{res.total_tests}) in {res.duration_sec:.2f}s")

    total_time = time.time() - start_all

    # Format Scorecard Table
    print("\n" + "=" * 92)
    print("                               MASTER QUALITY SCORECARD")
    print("=" * 92)
    header = f"{'Subsystem / Test Suite':<40} {'Origin':<22} {'Tests':<10} {'Latency':<10} {'Status'}"
    print(header)
    print("-" * 92)

    for r in results:
        status_tag = "PASS" if r.success else "FAIL"
        test_ratio = f"{r.passed_tests}/{r.total_tests}"
        latency_str = f"{r.duration_sec:.2f}s"
        print(f"{r.name:<40} {r.subsystem:<22} {test_ratio:<10} {latency_str:<10} {status_tag}")

    print("=" * 92)
    pass_pct = (passed_tests_overall / total_tests_overall * 100) if total_tests_overall > 0 else 0.0
    print(f"OVERALL SUMMARY: {passed_tests_overall}/{total_tests_overall} Tests Passed ({pass_pct:.1f}%) in {total_time:.2f}s")
    
    if failed_tests_overall == 0:
        print("RESULT: ALL AUTOMATED SUBSYSTEM TEST SUITES PASSED WITH ZERO REGRESSIONS!")
        print("=" * 92 + "\n")
        return 0
    else:
        print(f"RESULT: {failed_tests_overall} TESTS FAILED! Check diagnostics above.")
        print("=" * 92 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
