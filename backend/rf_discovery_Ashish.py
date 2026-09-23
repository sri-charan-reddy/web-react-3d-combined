"""
RF-Assisted Discovery, Terminal Identification and Authentication Module
SIH 2026 - Problem Statement ID: SIH26169 (ISRO)
Member 3: Ashish

Role: Auxiliary RF recovery when optical beacon acquisition fails.
Provides approximate direction and terminal verification for coarse optical reacquisition.
"""

import math
import hmac
import hashlib
import secrets

# Reference position for the local terminal (observer / FSOC tracking platform)
DEFAULT_LOCAL_TERMINAL_POSITION = (0, 0)

# Simulated RF environment with 2D positions (x, y) and private shared secrets
DEFAULT_SIMULATED_TERMINALS = {
    "TERMINAL_01": {"terminal_id": "TERMINAL_01", "position": (10, 8), "shared_secret": "ISRO_FSOC_KEY_01"},
    "TERMINAL_02": {"terminal_id": "TERMINAL_02", "position": (7.88, 6.15), "shared_secret": "ISRO_FSOC_KEY_02"},
    "TERMINAL_03": {"terminal_id": "TERMINAL_03", "position": (-5, 10), "shared_secret": "ISRO_FSOC_KEY_03"},
    "TERMINAL_04": {"terminal_id": "TERMINAL_04", "position": (14.2, -6.5), "shared_secret": "ISRO_FSOC_KEY_04"},
    "TERMINAL_05": {"terminal_id": "TERMINAL_05", "position": (-8.5, -7.0), "shared_secret": "ISRO_FSOC_KEY_05"},
    "TERMINAL_06": {"terminal_id": "TERMINAL_06", "position": (18.0, 4.0), "shared_secret": "ISRO_FSOC_KEY_06"},
    "TERMINAL_07": {"terminal_id": "TERMINAL_07", "position": (-12.0, 5.0), "shared_secret": "ISRO_FSOC_KEY_07"},
    "TERMINAL_08": {"terminal_id": "TERMINAL_08", "position": (6.0, -12.0), "shared_secret": "ISRO_FSOC_KEY_08"},
    "TERMINAL_09": {"terminal_id": "TERMINAL_09", "position": (11.5, 15.0), "shared_secret": "ISRO_FSOC_KEY_09"},
    "TERMINAL_10": {"terminal_id": "TERMINAL_10", "position": (-15.0, -4.0), "shared_secret": "ISRO_FSOC_KEY_10"},
    "TERMINAL_11": {"terminal_id": "TERMINAL_11", "position": (5.0, 18.0), "shared_secret": "ISRO_FSOC_KEY_11"},
    "TERMINAL_12": {"terminal_id": "TERMINAL_12", "position": (16.0, -14.0), "shared_secret": "ISRO_FSOC_KEY_12"},
    "TERMINAL_13": {"terminal_id": "TERMINAL_13", "position": (-9.0, 16.0), "shared_secret": "ISRO_FSOC_KEY_13"},
    "TERMINAL_14": {"terminal_id": "TERMINAL_14", "position": (20.0, -8.0), "shared_secret": "ISRO_FSOC_KEY_14"},
    "TERMINAL_15": {"terminal_id": "TERMINAL_15", "position": (-14.0, 12.0), "shared_secret": "ISRO_FSOC_KEY_15"},
}

# Verifier's trusted registry containing expected shared secrets for known terminals
TRUSTED_TERMINALS_REGISTRY = {
    f"TERMINAL_{i:02d}": f"ISRO_FSOC_KEY_{i:02d}" for i in range(1, 21)
}


def calculate_rf_direction(local_pos, target_pos):
    """
    Calculates dynamic RF bearing angle from local_pos to target_pos in degrees.
    Convention:
      0 deg   = +X direction
      90 deg  = +Y direction
      180 deg = -X direction
      270 deg = -Y direction
    """
    dx = target_pos[0] - local_pos[0]
    dy = target_pos[1] - local_pos[1]
    angle_deg = math.degrees(math.atan2(dy, dx))
    return round(angle_deg % 360.0, 1)


def calculate_simulated_rssi(distance, reference_rssi=-25.0):
    """
    Simulates RSSI (in dBm) using a simple logarithmic distance model:
        RSSI = reference_rssi - 20 * log10(distance)
    Clamps distance to minimum 1.0 unit to safely handle distance = 0.
    """
    safe_distance = max(distance, 1.0)
    rssi = reference_rssi - 20.0 * math.log10(safe_distance)
    return round(rssi, 1)


def discover_rf_terminals(available_terminals=None, local_position=DEFAULT_LOCAL_TERMINAL_POSITION):
    """
    Simulates RF scanning to discover nearby terminals.
    Calculates dynamic direction and RSSI based on coordinates.
    Shared secrets are kept private and never exposed in discovery output.
    """
    print("[RF Discovery] Scanning RF channels for beacon signals...")

    terminals_pool = DEFAULT_SIMULATED_TERMINALS if available_terminals is None else available_terminals

    discovered = []
    for term_id, info in terminals_pool.items():
        if "position" in info:
            target_pos = info["position"]
            dx = target_pos[0] - local_position[0]
            dy = target_pos[1] - local_position[1]
            dist = math.sqrt(dx * dx + dy * dy)
            direction = calculate_rf_direction(local_position, target_pos)
            rssi = calculate_simulated_rssi(dist)
        else:
            target_pos = info.get("position", (0, 0))
            direction = info.get("direction", 0.0)
            rssi = info.get("rssi", -50.0)

        # Public discovery information only (shared_secret is omitted)
        discovered.append({
            "terminal_id": info.get("terminal_id", term_id),
            "rssi": rssi,
            "direction": direction,
            "position": target_pos
        })

    if discovered:
        print(f"[RF Discovery] Discovered {len(discovered)} active terminal(s).")
    else:
        print("[RF Discovery] No RF beacons detected in range.")

    return discovered


def authenticate_terminal(target_terminal, expected_secret):
    """
    Performs challenge-response HMAC-SHA256 authentication:
    1. Generates a random cryptographic nonce challenge.
    2. Target terminal computes HMAC response using its private secret.
    3. Verifier checks response matches expected HMAC using trusted secret.
    """
    challenge = secrets.token_hex(16)

    # Resolve target terminal's internal secret
    if isinstance(target_terminal, dict):
        terminal_secret = target_terminal.get("shared_secret")
        if terminal_secret is None:
            term_id = target_terminal.get("terminal_id")
            terminal_secret = DEFAULT_SIMULATED_TERMINALS.get(term_id, {}).get("shared_secret", "")
    elif isinstance(target_terminal, str):
        terminal_secret = target_terminal
    else:
        terminal_secret = ""

    # Target computes response HMAC
    response = hmac.new(
        terminal_secret.encode(),
        challenge.encode(),
        hashlib.sha256
    ).hexdigest()

    # Verifier computes expected HMAC with trusted secret
    expected_response = hmac.new(
        expected_secret.encode(),
        challenge.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(response, expected_response)


def recover_terminal(expected_terminal_id, available_terminals=None, expected_secret=None, local_position=DEFAULT_LOCAL_TERMINAL_POSITION):
    """
    Main integration function for Member 4 / Main Controller.
    Recovers target terminal via auxiliary RF channel and returns coarse direction.
    """
    print(f"\n==========================================")
    print(f"[RF Recovery] Initiating recovery for target: {expected_terminal_id}")
    print(f"==========================================")

    # Step 1: RF Discovery
    discovered_list = discover_rf_terminals(available_terminals, local_position=local_position)

    if not discovered_list:
        return {
            "success": False,
            "terminal_id": None,
            "rssi": None,
            "direction": None,
            "authenticated": False,
            "message": "No terminals found in RF coverage area."
        }

    # Step 2: Terminal Identification
    matched_terminal = None
    for candidate in discovered_list:
        if candidate["terminal_id"] == expected_terminal_id:
            matched_terminal = candidate
            break

    if not matched_terminal:
        discovered_ids = [t["terminal_id"] for t in discovered_list]
        return {
            "success": False,
            "terminal_id": None,
            "rssi": None,
            "direction": None,
            "authenticated": False,
            "message": f"Expected terminal '{expected_terminal_id}' not found. Discovered IDs: {discovered_ids}"
        }

    print(f"[Terminal Identification] Match found: {matched_terminal['terminal_id']} (RSSI: {matched_terminal['rssi']} dBm)")

    # Step 3: Obtain Trusted Expected Secret
    if expected_secret is None:
        trusted_secret = TRUSTED_TERMINALS_REGISTRY.get(expected_terminal_id)
        if not trusted_secret:
            return {
                "success": False,
                "terminal_id": None,
                "rssi": None,
                "direction": None,
                "authenticated": False,
                "message": f"No trusted secret registered for terminal '{expected_terminal_id}'."
            }
    else:
        trusted_secret = expected_secret

    # Step 4: Challenge-Response Authentication
    terminals_pool = DEFAULT_SIMULATED_TERMINALS if available_terminals is None else available_terminals
    target_device = terminals_pool.get(expected_terminal_id, {})
    auth_success = authenticate_terminal(target_device, trusted_secret)

    if not auth_success:
        print("[Authentication] Challenge-response verification FAILED! Unauthorized terminal.")
        return {
            "success": False,
            "terminal_id": None,
            "rssi": None,
            "direction": None,
            "authenticated": False,
            "message": "Authentication failed: Invalid shared secret response."
        }

    print("[Authentication] Challenge-response verification SUCCESSFUL. Terminal authenticated.")

    # Step 5: Approximate RF Direction for coarse optical reacquisition
    direction = matched_terminal["direction"]
    rssi = matched_terminal["rssi"]
    print(f"[Direction Estimation] Approximate target direction: {direction} deg")

    return {
        "success": True,
        "terminal_id": expected_terminal_id,
        "rssi": rssi,
        "direction": direction,
        "authenticated": True,
        "message": "Terminal discovered, identified and authenticated successfully."
    }
