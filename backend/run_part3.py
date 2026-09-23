"""Part 3: RF-Assisted Discovery, Identification, and HMAC Authentication Launcher.

Executes:
- RF Multi-channel Scanner
- Terminal Identification by Hardware ID & RSSI
- Cryptographic HMAC-SHA256 Challenge-Response Authentication
- Coarse Direction Estimation (atan2)
- Unit & Integration Test Suite

Usage:
    python run_part3.py
"""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import test_rf_discovery_Ashish as rf_tests


def run_all_tests():
    print("=============================================================")
    print("STARTING TEST SUITE: RF-Assisted Discovery (Member 3 - Ashish)")
    print("=============================================================")

    rf_tests.test_case_1_successful_recovery()
    rf_tests.test_case_2_wrong_terminal()
    rf_tests.test_case_3_authentication_failure()
    rf_tests.test_case_4_no_terminal_found()
    rf_tests.test_case_5_dynamic_direction()
    rf_tests.test_case_6_distance_based_rssi()
    rf_tests.test_case_7_secret_not_exposed_in_discovery()

    print("\n=============================================================")
    print("ALL 7 TEST CASES PASSED SUCCESSFULLY!")
    print("=============================================================")


if __name__ == "__main__":
    run_all_tests()
