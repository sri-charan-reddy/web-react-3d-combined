"""Part 1: Virtual FSOC PAT Environment & Optical Detection Launcher.

Coordinates:
- FSOCEnvironment (Terminal A & Terminal B)
- VirtualCameraSensor
- ClassicalBeaconDetector & AlignmentCalculator
- VirtualPATController & SearchController
- EnvironmentRenderer (OpenCV Visualization)

Usage:
    python run_part1.py
"""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.main import main as run_part1_main

if __name__ == "__main__":
    run_part1_main()
