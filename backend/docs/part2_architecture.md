# Architecture & Technical Design: Part 2 (Predictive Tracking & Disturbance Handling)

## 1. System Overview & Scope

Part 2 of the SIH project is responsible for **Predictive Tracking & Disturbance Handling** for a moving optical beacon. It bridges the raw optical detections produced by **Part 1** and the downstream control and decision systems in **Part 4**.

```
+--------------------------+
|          PART 1          |
| Optical Beacon Detection |
+------------+-------------+
             |
             | BeaconMeasurement (timestamp, pos, confidence, detected_flag)
             v
+-------------------------------------------------------+
|                        PART 2                         |
|        Predictive Tracking & Disturbance Handling      |
|                                                       |
|  +---------------------+     +---------------------+  |
|  |  Kalman Filter Core |<--->| State Machine & FSM |  |
|  |  (Predict & Update) |     | (Locked/Coast/Lost) |  |
|  +---------------------+     +---------------------+  |
|             |                           |             |
|             +-------------+-------------+             |
+---------------------------|---------------------------+
                            |
                            | TrackingResult (timestamp, pos, vel, state, confidence, cov)
                            v
               +--------------------------+
               |          PART 4          |
               | Dynamic Controller & Nav |
               +--------------------------+
```

### Key Responsibilities
1. **Kalman-Filter-Based State Estimation**: Fuse noisy optical detections with a kinematic motion model.
2. **Smooth Velocity & Trajectory Prediction**: Estimate velocity vector $(v_x, v_y)$ to enable feedforward control.
3. **Dead Reckoning / Coasting during Occlusions**: Continue predicting beacon coordinates when optical detection is intermittently lost.
4. **Disturbance & Measurement Noise Handling**: Filter camera sensor jitter and reject sudden false-positive detection spikes.
5. **Beacon Reacquisition & Gating**: Rapidly reacquire lock when the beacon reappears within predicted uncertainty bounds.
6. **Confidence & State Reporting**: Output standardized tracking states (`TRACKING_LOCKED`, `PREDICTING_COASTING`, `SEARCH_ACQUISITION`, `LOST`) with normalized confidence scores.

---

## 2. Mathematical Model (Kalman Filter)

### 2.1 State Representation
The continuous state of the optical beacon in 2D pixel/camera coordinates is modeled as:
$$\mathbf{x} = \begin{bmatrix} x \\ y \\ v_x \\ v_y \end{bmatrix}$$

### 2.2 Discrete Kinematic Transition Model
Under a constant velocity assumption with time step $\Delta t$:
$$\mathbf{x}_{k} = \mathbf{F} \mathbf{x}_{k-1} + \mathbf{w}_k, \quad \mathbf{w}_k \sim \mathcal{N}(0, \mathbf{Q})$$

$$\mathbf{F} = \begin{bmatrix} 1 & 0 & \Delta t & 0 \\ 0 & 1 & 0 & \Delta t \\ 0 & 0 & 1 & 0 \\ 0 & 0 & 0 & 1 \end{bmatrix}$$

$$\mathbf{Q} = \text{diag}(\sigma_{px}^2, \sigma_{py}^2, \sigma_{vx}^2, \sigma_{vy}^2)$$

### 2.3 Measurement Model
Optical detection from Part 1 measures 2D position $\mathbf{z}_k = [z_x, z_y]^T$:
$$\mathbf{z}_k = \mathbf{H} \mathbf{x}_k + \mathbf{v}_k, \quad \mathbf{v}_k \sim \mathcal{N}(0, \mathbf{R})$$

$$\mathbf{H} = \begin{bmatrix} 1 & 0 & 0 & 0 \\ 0 & 1 & 0 & 0 \end{bmatrix}, \quad \mathbf{R} = \begin{bmatrix} \sigma_{rx}^2 & 0 \\ 0 & \sigma_{ry}^2 \end{bmatrix}$$

### 2.4 State & Covariance Recursion
- **Prediction Phase (Every frame)**:
  $$\hat{\mathbf{x}}_{k|k-1} = \mathbf{F} \hat{\mathbf{x}}_{k-1|k-1}$$
  $$\mathbf{P}_{k|k-1} = \mathbf{F} \mathbf{P}_{k-1|k-1} \mathbf{F}^T + \mathbf{Q}$$

- **Measurement Update Phase (Only when Part 1 detects the beacon)**:
  $$\mathbf{y}_k = \mathbf{z}_k - \mathbf{H} \hat{\mathbf{x}}_{k|k-1}$$
  $$\mathbf{S}_k = \mathbf{H} \mathbf{P}_{k|k-1} \mathbf{H}^T + \mathbf{R}$$
  $$\mathbf{K}_k = \mathbf{P}_{k|k-1} \mathbf{H}^T \mathbf{S}_k^{-1}$$
  $$\hat{\mathbf{x}}_{k|k} = \hat{\mathbf{x}}_{k|k-1} + \mathbf{K}_k \mathbf{y}_k$$
  $$\mathbf{P}_{k|k} = (\mathbf{I} - \mathbf{K}_k \mathbf{H}) \mathbf{P}_{k|k-1}$$

- **Missing Measurement (Occlusion / Coasting)**:
  $$\hat{\mathbf{x}}_{k|k} = \hat{\mathbf{x}}_{k|k-1}$$
  $$\mathbf{P}_{k|k} = \mathbf{P}_{k|k-1}$$
  *(Covariance $\mathbf{P}$ naturally expands over time, reflecting increasing uncertainty).*

---

## 3. Finite State Machine (FSM)

```
       +------------------+
       |  UNINITIALIZED   |
       +--------+---------+
                | First N valid detections
                v
       +------------------+
+----->| TRACKING_LOCKED  |<----+
|      +--------+---------+     |
| Reacquired    | Missed frame  | Reacquired
| (valid gate)  v               | (in search window)
|      +------------------+     |
+------| PREDICTING_COAST |     |
       +--------+---------+     |
                | > N_coast frames
                v               |
       +------------------+     |
       |SEARCH_ACQUISITION+-----+
       +--------+---------+
                | > N_lost frames
                v
       +------------------+
       |       LOST       |
       +------------------+
```

1. **`UNINITIALIZED`**: Awaiting initial sequence of valid optical detections from Part 1 to initialize position and velocity.
2. **`TRACKING_LOCKED`**: Steady-state tracking with incoming measurements; confidence $\approx 1.0$; error ellipse remains small.
3. **`PREDICTING_COASTING`**: Optical detection is missing (occlusion/dropout). The tracker dead-reckons position using velocity estimates. Covariance grows and confidence decays linearly.
4. **`SEARCH_ACQUISITION`**: Prolonged occlusion ($N > 15$ frames). Tracker provides wide uncertainty bounds to guide search.
5. **`LOST`**: Occlusion duration exceeded timeout ($N > 60$ frames). Requires re-initialization upon new discovery.

---

## 4. Module Interface Contracts

### 4.1 Input from Part 1 (`BeaconMeasurement`)
```python
@dataclass
class BeaconMeasurement:
    timestamp: float                            # Monotonic timestamp (seconds)
    position: Optional[Tuple[float, float]]     # Measured (x, y) coordinates
    detected: bool                              # Detection flag from optical module
    confidence: float                           # Optical detector confidence [0.0, 1.0]
    raw_bbox: Optional[Tuple[float, float, float, float]] # Optional bounding box (x, y, w, h)
```

### 4.2 Output to Part 4 (`TrackingResult`)
```python
@dataclass
class TrackingResult:
    timestamp: float                    # Timestamp of current state estimate
    position: Tuple[float, float]       # Filtered / predicted (x, y)
    velocity: Tuple[float, float]       # Estimated velocity (vx, vy)
    state: TrackingState                # Current FSM state
    confidence: float                   # Overall tracking confidence [0.0, 1.0]
    is_predicted: bool                  # True if estimate is dead-reckoned without measurement
    covariance: np.ndarray              # 4x4 or 2x2 state covariance matrix
    frames_without_detection: int       # Dropout duration in frames
```

---

## 5. Standalone Simulators & Demonstration (Part 2 Testing)
To enable full development and manual verification of Part 2 without requiring physical hardware or Part 1:
- **`BeaconSimulator`**: Generates parametric ground-truth trajectories (linear, circular, figure-8).
- **`DisturbanceSimulator`**: Injects realistic Gaussian sensor noise, dynamic drift, and scheduled occlusion windows.
- **`TrackingVisualizer`**: Renders real-time OpenCV views with trajectory trails, covariance uncertainty ellipses, and HUD diagnostics.
