# Free-Space Optical Communication (FSOC) PAT System Architecture

## 1. End-to-End System Architecture

The **Team Raynex FSOC PAT (Pointing, Acquisition, and Tracking)** system provides an end-to-end resilient optical communication alignment stack designed to handle optical turbulence, mechanical platform vibration, transient occlusions, and deep link loss using multimodal AI and auxiliary RF telemetry.

```
                             TEAM RAYNEX FSOC PAT SYSTEM
                                          │
    ┌─────────────────────────┬───────────┴───────────┬─────────────────────────┐
    │                         │                       │                         │
┌───▼────────────────┐ ┌──────▼──────────────┐ ┌──────▼──────────────┐ ┌────────▼────────┐
│      PART 1        │ │       PART 2        │ │       PART 3        │ │      PART 4       │
│ Virtual Environment│ │ Predictive Tracking │ │ Auxiliary RF Discov │ │ Adaptive Recovery │
│ & Optical Detect   │ │ & Disturbance Rej.  │ │ & HMAC Auth         │ │ & Master Control  │
└────────┬───────────┘ └──────┬──────────────┘ └──────┬──────────────┘ └────────▲───────────┘
         │                    │                       │                         │
         │ Optical Detection  │ Kalman State & Track  │ Coarse Bearing & Auth   │ State Machine
         └───────────────────►┼──────────────────────►┼─────────────────────────┘
                              │                       │
                              └───────────────────────┴──────────────► Actuator / Gimbal
```

---

## 2. Subsystem Breakdown

### 2.1 Part 1: Virtual FSOC PAT Environment (Manoj)
*Full specification: [docs/part1_architecture.md](part1_architecture.md)*
- **Optical Simulation**: Terminal A (RX) and Terminal B (TX) in 2D/3D kinematic motion.
- **Sensor Modeling**: Virtual Camera with configurable FOV, optical distortion, sensor noise, and Gaussian intensity profiles.
- **Classical Detection**: Thresholding, connected component centroid extraction, and spot brightness validation.
- **Search Logic**: Archimedean spiral and raster search patterns for initial blind acquisition.

### 2.2 Part 2: Predictive Tracking & Disturbance Handling (Simhadri)
*Full specification: [docs/part2_architecture.md](part2_architecture.md)*
- **Kinematic State Estimation**: Constant-velocity Kalman filter tracking $\mathbf{x} = [x, y, v_x, v_y]^T$.
- **Disturbance Modeling**: Atmospheric turbulence (Gauss-Markov scintillation / beam wander), mechanical platform vibration, and Gaussian sensor noise.
- **Outlier Rejection**: Statistical Mahalanobis gating ($\chi^2$-distribution gating) to ignore rogue optical reflections or sensor anomalies.
- **Reacquisition**: Bounded local spiral search around Kalman covariance prediction during short optical drops.

### 2.3 Part 3: RF-Assisted Auxiliary Discovery & HMAC Authentication (Ashish)
*Full specification: [README_Ashish.md](../README_Ashish.md)*
- **RF Beacon Broadcast**: Multi-channel wireless discovery broadcasting terminal identifiers and RSSI indicators.
- **HMAC-SHA256 Cryptographic Authentication**: Challenge-response handshake preventing rogue node spoofing.
- **Coarse Bearing Estimation**: Angle calculation (`atan2`) from RF antenna geometry to orient optical actuators within optical FOV.

### 2.4 Part 4: Adaptive Recovery & Complete Integration (Frontend & Master FSM)
- **Hierarchical 11-Stage Decision Engine**:
  1. 360° Initial Optical Search
  2. Beacon Detection & Centroid Locking
  3. Continuous Kalman Prediction & State Tracking
  4. Closed-Loop Fine PAT Alignment
  5. FSOC Data Link Maintenance
  6. Disturbance Injection & Detection Loss Detection
  7. Kalman Dead-Reckoning (Coast Phase)
  8. Bounded Local Search around Uncertainty Bounds
  9. Complete Optical Loss Escalation -> Auxiliary RF Scan
  10. Cryptographic Terminal Identification & HMAC Verification
  11. Actuator Slew to Coarse Bearing & Optical Reacquisition

---

## 3. Data Flow & Interfaces

| From | To | Payload | Interface |
| :--- | :--- | :--- | :--- |
| **Part 1** | **Part 2** | `BeaconMeasurement(timestamp, pos, confidence, detected)` | Direct Function / Pipeline |
| **Part 2** | **Part 4** | `TrackingResult(timestamp, pos, vel, state, confidence, P)` | Telemetry / State Machine |
| **Part 3** | **Part 4** | `RFResult(terminal_id, rssi, direction, authenticated)` | RF Bridge |
| **Part 4** | **Hardware/Sim** | `PanTiltCommand(pan_deg, tilt_deg, slew_rate)` | Actuator Controller |
