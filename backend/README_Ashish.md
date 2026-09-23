# SIH 2026 - Problem Statement ID: SIH26169
## Development of an AI-Based Virtual Camera Tracking System for Coarse Alignment of Mobile Free Space Optical Communication (FSOC) Terminals
**Organization:** ISRO | **Category:** Software

---

### Assigned Contribution: Member 3 (Ashish)
**Module:** `RF-Assisted Discovery, Terminal Identification and Authentication`

---

## 1. Module Overview & Purpose

In mobile Free Space Optical Communication (FSOC), optical transmission links depend on very narrow laser beams with divergence angles on the order of milliradians. If tracking is lost due to vehicle motion, platform vibration, or sudden obstruction, scanning the entire sky optically is slow and computationally heavy.

When optical beacon acquisition fails, this module provides an **auxiliary RF-based discovery and recovery mechanism** to identify the intended terminal and supply its approximate bearing so that coarse optical tracking can reacquire the beacon.

### Crucial Architectural Clarification
- **FSOC is the primary optical communication channel.**
- **RF is strictly an auxiliary discovery/recovery channel.**
- **The RF module does NOT replace FSOC.** It only provides coarse direction to assist optical reacquisition when the optical beam is lost.

---

## 2. End-to-End Recovery Flow

```text
Optical tracking fails
        ↓
RF discovery (Scan nearby terminals)
        ↓
Terminal ID identification (Match expected terminal)
        ↓
HMAC challenge-response authentication (Verify identity via shared secret)
        ↓
Approximate RF direction (Calculate angle from 2D coordinates)
        ↓
Return recovery information (Dictionary with direction, RSSI, and status)
        ↓
Future camera points toward approximate direction
        ↓
Optical beacon reacquisition (FSOC optical tracking resumes)
```

---

## 3. Simulation Details (No Hardware Required)

This module is a **software simulation** designed to demonstrate the recovery logic without requiring physical RF transceivers:

1. **Terminal Positions**:
   - Both the local terminal and candidate target terminals are represented in a simple 2D coordinate system `(x, y)`.
   - Default local terminal position is `(0, 0)`.
   - Simulated field terminals:
     - `TERMINAL_01`: `(10, 8)`
     - `TERMINAL_02`: `(7.88, 6.15)`
     - `TERMINAL_03`: `(-5, 10)`

2. **Dynamic RF Direction Calculation**:
   - RF bearing is dynamically calculated using Cartesian trigonometry:
     $$\Delta x = x_2 - x_1, \quad \Delta y = y_2 - y_1$$
     $$\theta = \text{atan2}(\Delta y, \Delta x) \pmod{360^\circ}$$
   - **Angle Convention:**
     - **0°**: Positive X direction `(+X)`
     - **90°**: Positive Y direction `(+Y)`
     - **180°**: Negative X direction `(-X)`
     - **270°**: Negative Y direction `(-Y)`

3. **Distance-Based RSSI Simulation**:
   - Euclidean distance: $d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}$.
   - RSSI is simulated via a standard logarithmic path-loss model:
     $$\text{RSSI} = \text{reference\_rssi} - 20 \times \log_{10}(\max(d, 1.0))$$
   - Zero distance is safely clamped to $1.0\text{ m}$ to avoid logarithmic singularities.
   - *Note:* This is a software demonstration of the principle that greater distance results in weaker signal strength; it is not a complex propagation model.

4. **Cryptographic Authentication**:
   - Uses standard library `hmac`, `hashlib.sha256`, and `secrets.token_hex(16)`.
   - Mutual challenge-response ensures rogue transmitters cannot spoof friendly terminals.
   - Shared secrets are **never exposed** in the public discovery output.
   - The verifier validates against an internal `TRUSTED_TERMINALS_REGISTRY`.

---

## 4. Files in this Contribution

Every file for this contribution strictly ends with `_Ashish`:

| File Name | Role |
| :--- | :--- |
| `rf_discovery_Ashish.py` | Dynamic RF discovery, distance-based RSSI, HMAC authentication, and terminal recovery logic |
| `test_rf_discovery_Ashish.py` | Standalone test suite covering all 7 success, mismatch, failure, coordinate, and privacy tests |
| `README_Ashish.md` | Full documentation, coordinate conventions, API usage, and viva notes |

---

## 5. Dependencies & Requirements

- **Python Version:** Python 3.8+
- **External Dependencies:** **None** (Only standard library: `math`, `hmac`, `hashlib`, `secrets`).
- No external packages (NumPy, OpenCV, PyTorch, Streamlit) or physical RF hardware are needed.

---

## 6. How to Run the Unit Tests

Execute the standalone test suite from PowerShell / terminal:

```bash
python test_rf_discovery_Ashish.py
```

### Verified Test Cases:
1. **Case 1: Successful Recovery** — Target terminal exists, passes challenge-response authentication, returns valid RSSI and direction in $[0^\circ, 360^\circ)$.
2. **Case 2: Wrong Terminal** — Requested terminal ID is not active in the RF environment.
3. **Case 3: Authentication Failure** — Terminal ID exists, but secret does not match (impostor detection).
4. **Case 4: No Terminal Found** — Empty RF environment where no beacons are received.
5. **Case 5: Dynamic Direction** — Verifies `calculate_rf_direction` computes correct angles for cardinal coordinates (0°, 90°, 180°, 270°).
6. **Case 6: Distance-Based RSSI** — Verifies farther terminals produce weaker (more negative) RSSI values.
7. **Case 7: Secret Privacy** — Confirms that `discover_rf_terminals()` does not leak `shared_secret` in the public discovery result.

---

## 7. Integration Guide for Member 4 (Main Controller)

When the optical tracking module loses sight of the target beacon, the main controller invokes `recover_terminal()`:

```python
from rf_discovery_Ashish import recover_terminal

# Attempt to locate and authenticate the target terminal
result = recover_terminal("TERMINAL_02")

if result["success"]:
    target_bearing = result["direction"]
    signal_strength = result["rssi"]
    print(f"Terminal verified! Repointing virtual camera toward {target_bearing} deg (RSSI: {signal_strength} dBm)...")
    # Repoint camera coarse gimbal to target_bearing degrees
    # Re-enable optical AI tracking (Member 1 & Member 2 modules)
else:
    print(f"Recovery failed: {result['message']}")
```

### Return Data Structure:
```python
# On Success:
{
    "success": True,
    "terminal_id": "TERMINAL_02",
    "rssi": -45.0,
    "direction": 38.0,
    "authenticated": True,
    "message": "Terminal discovered, identified and authenticated successfully."
}

# On Failure:
{
    "success": False,
    "terminal_id": None,
    "rssi": None,
    "direction": None,
    "authenticated": False,
    "message": "Expected terminal 'TERMINAL_05' not found..."
}
```

---

## 8. SIH Viva & Presentation Questions

1. **Why is an RF subsystem needed if this is an Optical (FSOC) project?**
   - FSOC laser beams have narrow beam divergence. If high-speed mobility or vibration breaks optical line-of-sight, blind optical scanning takes too long. Auxiliary RF provides an omnidirectional coarse compass, allowing the camera to immediately re-point in the right direction.

2. **Why challenge-response instead of a static password?**
   - A static password sent over the air can be intercepted and replayed. A random challenge nonce generated via `secrets.token_hex(16)` ensures every exchange is unique and immune to replay attacks.

3. **How is the RF direction determined?**
   - In real-world systems, RF direction is determined using antenna arrays (AoA / direction finding). In this software simulation, it is dynamically computed using the 2D Cartesian coordinates of the tracking terminal and target terminal via `atan2(dy, dx)`.
