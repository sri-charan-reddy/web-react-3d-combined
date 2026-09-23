"""
Unit Test Suite for RF-Assisted Discovery Module
SIH 2026 - Problem Statement ID: SIH26169 (ISRO)
Member 3: Ashish

Tests dynamic direction, distance-based RSSI, and challenge-response authentication:
1. Successful recovery (Valid terminal + correct trusted secret)
2. Wrong terminal (Requested terminal ID not present in RF field)
3. Authentication failure (Mismatched / impostor shared secret)
4. No terminal found (Empty RF environment)
5. Dynamic direction calculation (Coordinate geometry atan2 verification)
6. Distance-based RSSI simulation (Farther terminals produce weaker RSSI)
7. Information privacy (Shared secrets not exposed in discovery output)
"""

from rf_discovery_Ashish import (
    recover_terminal,
    discover_rf_terminals,
    calculate_rf_direction,
    calculate_simulated_rssi,
    DEFAULT_SIMULATED_TERMINALS,
    DEFAULT_LOCAL_TERMINAL_POSITION
)


def test_case_1_successful_recovery():
    print("\n-------------------------------------------------------------")
    print("TEST CASE 1: Correct Terminal + Successful Authentication")
    print("-------------------------------------------------------------")
    result = recover_terminal("TERMINAL_02")
    print("\nResult Dictionary:")
    print(result)

    assert result["success"] is True
    assert result["terminal_id"] == "TERMINAL_02"
    assert result["authenticated"] is True
    assert result["rssi"] is not None
    assert result["direction"] is not None
    assert 0.0 <= result["direction"] < 360.0
    print(">>> PASS: Test Case 1 passed.")


def test_case_2_wrong_terminal():
    print("\n-------------------------------------------------------------")
    print("TEST CASE 2: Wrong Terminal / Terminal Mismatch")
    print("-------------------------------------------------------------")
    only_terminal_03 = {
        "TERMINAL_03": DEFAULT_SIMULATED_TERMINALS["TERMINAL_03"]
    }
    result = recover_terminal("TERMINAL_01", available_terminals=only_terminal_03)
    print("\nResult Dictionary:")
    print(result)

    assert result["success"] is False
    assert result["authenticated"] is False
    assert result["direction"] is None
    print(">>> PASS: Test Case 2 passed.")


def test_case_3_authentication_failure():
    print("\n-------------------------------------------------------------")
    print("TEST CASE 3: Authentication Failure (Wrong / Impostor Secret)")
    print("-------------------------------------------------------------")
    # Caller supplies an unauthorized expected secret
    result = recover_terminal("TERMINAL_02", expected_secret="WRONG_IMPOSTOR_KEY_99")
    print("\nResult Dictionary:")
    print(result)

    assert result["success"] is False
    assert result["authenticated"] is False
    assert result["direction"] is None
    print(">>> PASS: Test Case 3 passed.")


def test_case_4_no_terminal_found():
    print("\n-------------------------------------------------------------")
    print("TEST CASE 4: No Terminals in Range (Empty RF Environment)")
    print("-------------------------------------------------------------")
    empty_environment = {}
    result = recover_terminal("TERMINAL_02", available_terminals=empty_environment)
    print("\nResult Dictionary:")
    print(result)

    assert result["success"] is False
    assert result["terminal_id"] is None
    assert result["direction"] is None
    assert result["authenticated"] is False
    print(">>> PASS: Test Case 4 passed.")


def test_case_5_dynamic_direction():
    print("\n-------------------------------------------------------------")
    print("TEST CASE 5: Dynamic RF Direction Calculation (atan2)")
    print("-------------------------------------------------------------")
    local = (0, 0)

    # 0 deg: positive X
    dir_0 = calculate_rf_direction(local, (10, 0))
    # 90 deg: positive Y
    dir_90 = calculate_rf_direction(local, (0, 10))
    # 180 deg: negative X
    dir_180 = calculate_rf_direction(local, (-10, 0))
    # 270 deg: negative Y
    dir_270 = calculate_rf_direction(local, (0, -10))

    print(f"Angle for (10, 0)   : {dir_0} deg (Expected: 0.0 deg)")
    print(f"Angle for (0, 10)   : {dir_90} deg (Expected: 90.0 deg)")
    print(f"Angle for (-10, 0)  : {dir_180} deg (Expected: 180.0 deg)")
    print(f"Angle for (0, -10)  : {dir_270} deg (Expected: 270.0 deg)")

    assert abs(dir_0 - 0.0) < 0.1
    assert abs(dir_90 - 90.0) < 0.1
    assert abs(dir_180 - 180.0) < 0.1
    assert abs(dir_270 - 270.0) < 0.1
    print(">>> PASS: Test Case 5 passed.")


def test_case_6_distance_based_rssi():
    print("\n-------------------------------------------------------------")
    print("TEST CASE 6: Distance-Based Simulated RSSI")
    print("-------------------------------------------------------------")
    rssi_near = calculate_simulated_rssi(distance=2.0)
    rssi_far = calculate_simulated_rssi(distance=50.0)
    rssi_zero = calculate_simulated_rssi(distance=0.0)

    print(f"Simulated RSSI at distance 2m  : {rssi_near} dBm")
    print(f"Simulated RSSI at distance 50m : {rssi_far} dBm")
    print(f"Simulated RSSI at distance 0m  : {rssi_zero} dBm (safely clamped)")

    # Farther distance must yield weaker (more negative) RSSI
    assert rssi_far < rssi_near
    # Safe handling of zero distance must not crash and produce valid float
    assert rssi_zero is not None
    print(">>> PASS: Test Case 6 passed.")


def test_case_7_secret_not_exposed_in_discovery():
    print("\n-------------------------------------------------------------")
    print("TEST CASE 7: Shared Secret Privacy during RF Discovery")
    print("-------------------------------------------------------------")
    discovered = discover_rf_terminals()
    for terminal in discovered:
        assert "shared_secret" not in terminal
        assert "terminal_id" in terminal
        assert "direction" in terminal
        assert "rssi" in terminal

    print(f"Verified {len(discovered)} discovered terminals: none expose 'shared_secret'.")
    print(">>> PASS: Test Case 7 passed.")


if __name__ == "__main__":
    print("=============================================================")
    print("STARTING TEST SUITE: RF-Assisted Discovery (Member 3 - Ashish)")
    print("=============================================================")

    test_case_1_successful_recovery()
    test_case_2_wrong_terminal()
    test_case_3_authentication_failure()
    test_case_4_no_terminal_found()
    test_case_5_dynamic_direction()
    test_case_6_distance_based_rssi()
    test_case_7_secret_not_exposed_in_discovery()

    print("\n=============================================================")
    print("ALL 7 TEST CASES PASSED SUCCESSFULLY!")
    print("=============================================================")
