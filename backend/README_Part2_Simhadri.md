# Part 2: Predictive Tracking & Disturbance Handling

SIH Project module for moving optical beacon localization, Kalman filtering, occlusion coasting, and disturbance rejection.

---

## 🎯 Scope & Module Responsibility

Part 2 is responsible for maintaining an accurate, continuous estimate of a moving beacon's position and velocity, even in the presence of optical occlusions, measurement noise, and sensor disturbances.

- **Fuses optical detections from Part 1** with a 2D kinematic Kalman filter model.
- **Predicts beacon position** during temporary line-of-sight loss / camera occlusions (dead reckoning / coasting).
- **Tracks confidence and operational state** (`UNINITIALIZED`, `TRACKING_LOCKED`, `PREDICTING_COASTING`, `SEARCH_ACQUISITION`, `LOST`).
- **Filters camera sensor noise and disturbances** to prevent control instability.
- **Provides clean, standardized input/output interfaces** for seamless integration with Part 1 (Optical Detection) and Part 4 (Dynamic Controller).

> **Note on Project Boundaries:**
> - Part 1 handles optical beacon detection and feeds `BeaconMeasurement` instances.
> - Part 2 processes tracking, predictive coasting, and state management.
> - Part 4 ingests `TrackingResult` to compute flight/control commands.
> - Part 2 does *not* implement RF discovery, authentication, or physical hardware control.

---

## 📁 Project Structure

```text
part2_predictive_tracking/
├── README.md                   # Project overview, setup, and interface documentation
├── requirements.txt            # Minimal dependencies (numpy, opencv-python, matplotlib)
├── config.py                   # Central tuning parameters for filter, state machine, and sims
├── main.py                     # Standalone demonstration & simulation runner
├── src/
│   ├── __init__.py             # Package initializer exposing main tracking classes
│   ├── kalman_tracker.py       # Kalman filter tracker, prediction, and update logic
│   ├── beacon_simulator.py     # Ground-truth beacon motion trajectory generator
│   ├── disturbance_simulator.py# Measurement noise, drift, and occlusion simulator
│   ├── tracking_state.py       # FSM states, BeaconMeasurement input, and TrackingResult output
│   └── visualizer.py           # Real-time OpenCV rendering, uncertainty ellipses & HUD
├── data/
│   └── .gitkeep                # Data directory for logged trajectory traces
└── docs/
    └── architecture.md         # Detailed mathematical formulation and architecture specs
```

---

## ⚡ Integration & Interfaces

### 1. Input Interface (from Part 1)
Part 1 provides detected beacon position via `BeaconMeasurement`:
```python
from src.tracking_state import BeaconMeasurement

measurement = BeaconMeasurement(
    timestamp=12.450,
    position=(642.5, 361.2),
    detected=True,
    confidence=0.92
)
```

### 2. Output Interface (to Part 4)
Part 2 supplies filtered position, estimated velocity, and tracking status via `TrackingResult`:
```python
from src.kalman_tracker import KalmanBeaconTracker

tracker = KalmanBeaconTracker()
result = tracker.process_frame(measurement)

print("Estimated Position:", result.position)
print("Estimated Velocity:", result.velocity)
print("Tracking State:", result.state.name)
print("Confidence:", result.confidence)
```

---

## 🛠️ Installation & Setup

1. **Prerequisites**: Python 3.9+ installed.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run Standalone Demonstration**:
   ```bash
   python main.py
   ```

---

## 📖 Detailed Documentation
For the full mathematical derivation (state equations, covariance updates) and state machine transition details, see [docs/architecture.md](docs/architecture.md).
