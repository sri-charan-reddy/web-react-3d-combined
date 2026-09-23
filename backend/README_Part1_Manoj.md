# Free-Space Optical Communication (FSOC) PAT System

## Phase 1 — Virtual FSOC Environment & FOV Visualization

A modular Python simulation prototype for a college project evaluating **Pointing, Acquisition and Tracking (PAT)** in **Free-Space Optical Communication (FSOC)** terminals.

---

## Technical Background

### What is FSOC?
**Free-Space Optical Communication (FSOC)** is a high-bandwidth optical communication technology that transmits data through unguided free space (atmosphere or space vacuum) using modulated laser beams instead of traditional radio frequencies (RF). FSOC offers extremely high data rates (Gbps/Tbps) and immunity to RF interference, but requires line-of-sight optical alignment.

### What is PAT?
Because laser beams have extremely narrow beam divergence angles (often milliradians or less), maintaining link connection requires a high-precision **Pointing, Acquisition and Tracking (PAT)** system:
1. **Pointing**: Directing the optical terminal toward the target location.
2. **Acquisition**: Visually detecting and locking onto the optical beacon from the remote terminal.
3. **Tracking**: Continuously measuring alignment error and driving gimbal/steering actuators to compensate for relative motion.

---

## Phase 1 Scope & Implementation

Phase 1 provides the foundational visual simulation environment representing two optical communication nodes:
- **Terminal A (Local Terminal)**: Hosts the virtual vision camera and optical tracking subsystem.
- **Terminal B (Remote Terminal)**: Hosts the optical beacon target.
- **Virtual Camera**: Features configurable position, orientation angle, image resolution, and dynamic Field of View (FOV) cone geometry.
- **Optical Beacon**: Simulated high-intensity circular beacon with radial glow.
- **OpenCV Renderer**: Real-time dark-mode visual interface with baseline line-of-sight, grid overlay, and real-time telemetry HUD.

### Explicitly Excluded from Phase 1
To maintain clean modular progression, Phase 1 deliberately **does not** include:
- Machine Learning / YOLO / Object detection algorithms
- Computer vision centroid extraction
- Kalman filtering / Predictive tracking
- Automated closed-loop camera orientation control
- RF fallback communication or hardware interfacing

---

## Project Directory Structure

```
fsoc-pat-system/
├── README.md                 # Project documentation & instructions
├── requirements.txt          # Python library dependencies
├── .gitignore                # Git ignore configuration
├── config/
│   └── config.yaml           # Centralized simulation configuration
├── src/
│   ├── __init__.py
│   ├── main.py               # Application entry point & render loop
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── environment.py    # World state, bounds, & time clock
│   │   ├── terminal.py       # Virtual camera & FSOC terminal models
│   │   └── beacon.py         # Optical beacon model
│   └── visualization/
│       ├── __init__.py
│       └── renderer.py       # OpenCV dark-mode interface renderer
└── docs/
    └── architecture.md       # Architecture diagram & design specs
```

---

## Setup & Installation

### Prerequisites
- Python 3.8 or higher installed.

### Step 1: Install Dependencies
Open a command prompt or terminal inside the `fsoc-pat-system` directory:

```bash
pip install -r requirements.txt
```

---

## Running the Application

To launch the FSOC simulation window:

```bash
python src/main.py
```

### Controls & Navigation
- **Exit Simulation**: Press `Q`, `q`, or `ESC` key while the OpenCV window is focused.

---

## Expected Visual Output

Upon running `python src/main.py`, an OpenCV window titled **"FSOC PAT System - Phase 1: Virtual Environment"** will display:

1. **Dark Background & Grid**: Sleek slate background with coordinate grid lines.
2. **Terminal A (Local)**: Cyan box node on the left hosting the camera aperture.
3. **Terminal B (Remote)**: Gold box node on the right hosting the optical beacon.
4. **Optical Beacon**: Bright glowing multi-layer optical beam core at Terminal B.
5. **Camera FOV Wedge**: Semi-transparent cyan sector cone projecting from Terminal A in the direction of the camera orientation ($0.0^\circ$).
6. **Line of Sight (LOS)**: Dashed baseline path connecting Terminal A to Terminal B.
7. **Telemetry HUD**: Top-left panel displaying real-time node coordinates, camera angle ($0.0^\circ$), FOV ($35.0^\circ$), beacon status, baseline distance, and simulation time.

---

## Future Phase Roadmap

- **Phase 1 (Completed)**: Virtual environment, terminal models, camera FOV geometry, beacon rendering, and OpenCV telemetry interface.
- **Phase 2**: Optical beacon visual detection, thresholding, and centroid coordinate extraction.
- **Phase 3**: Pointing error calculation, Kalman filtering, and closed-loop camera alignment tracking.
- **Phase 4**: Autonomous acquisition search patterns (raster/spiral) and integrated end-to-end system demonstration.
