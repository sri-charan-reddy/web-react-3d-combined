# FSOC PAT System Architecture & Design Specification

## System Overview

The **Free-Space Optical Communication (FSOC) Pointing, Acquisition and Tracking (PAT)** system is designed to simulate and demonstrate autonomous line-of-sight alignment between a local terminal (Terminal A) hosting a vision sensor and a remote terminal (Terminal B) emitting an optical beacon.

---

## High-Level Architecture Diagram

```
                             FSOC PAT SYSTEM
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        │                                                       │
  Simulation Layer                                      Visualization Layer
        │                                                       │
 ┌──────┼──────┐                                                │
 │      │      │                                                │
Env  Terminal Beacon                                            │
 │      │                                                       │
 │   Camera ────────────────────────────────────────────────► Renderer
 │                                                              │
 └──────────────────────────────────────────────────────────────┴──► OpenCV
```

---

## Modular Component Breakdown

The architecture strictly isolates world state, physics/geometry models, visualization, and future tracking intelligence.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            FSOC PAT PIPELINE ROADMAP                         │
├──────────────────────────────────────────────────────────────────────────────┤
│  [PHASE 1: CURRENT]                                                          │
│  FSOCEnvironment ────► VirtualCamera ────► EnvironmentRenderer (OpenCV)      │
│         │                                                                    │
│  [FUTURE PHASES]                                                             │
│         ▼                                                                    │
│  Phase 2: Perception / Beacon Detection (Centroid & Intensity Extraction)    │
│         ▼                                                                    │
│  Phase 3: Tracking & Prediction (Kalman Filter / Pointing Error Vector)       │
│         ▼                                                                    │
│  Phase 4: PAT Control Loop & RF Recovery (Acquisition Search & Fallback)     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### 1. `src/simulation/beacon.py`
- **`OpticalBeacon`**: Models x/y coordinates, optical power intensity ($I \in [0.0, 1.0]$), physical radius, and emission state (`active`).

### 2. `src/simulation/terminal.py`
- **`VirtualCamera`**: Models sensor position, orientation angle ($\theta_{deg}$), angular field-of-view ($\text{FOV}_{deg}$), image resolution, and dynamic FOV wedge polygon arc calculation.
- **`FSOCTerminal`**: Models local/remote terminal nodes, holding references to attached camera or optical beacon.

### 3. `src/simulation/environment.py`
- **`FSOCEnvironment`**: Manages canvas bounds, grid geometry, time clock, frame counters, and terminal references. Maintains pure simulation state without rendering dependencies.

### 4. `src/visualization/renderer.py`
- **`EnvironmentRenderer`**: Renders dark-mode HUD, coordinate grid, terminal icons, multi-layer glowing optical beacon, dynamic FOV wedge cone, line-of-sight baseline, and real-time system telemetry using OpenCV and NumPy.

### 5. `src/main.py`
- Application entry point. Loads `config/config.yaml`, initializes environment and renderer, and manages continuous main loop execution and user quit signals (`Q` / `ESC`).

---

## Coordinate System & Angle Convention

- **Canvas Coordinates**: 2D Screen Space where $(0, 0)$ represents top-left corner, $+X$ extends horizontally right, and $+Y$ extends vertically down.
- **Orientation Angle ($\theta_{deg}$)**:
  - $0.0^\circ$ points horizontally right ($+X$ axis towards Terminal B).
  - $+90.0^\circ$ points vertically down ($+Y$ axis).
  - $-90.0^\circ$ points vertically up ($-Y$ axis).
  - $\pm 180.0^\circ$ points horizontally left ($-X$ axis).

---

## Future Phase Roadmap

- **Phase 1 (Implemented)**: Foundation simulation canvas, terminal models, beacon model, dynamic camera FOV wedge rendering, and telemetry HUD.
- **Phase 2 (Future)**: Optical beacon visual detection, centroid extraction, and bounding box perception.
- **Phase 3 (Future)**: Pointing error calculation, target tracking, predictive filtering, and closed-loop camera orientation adjustments.
- **Phase 4 (Future)**: Autonomous acquisition search patterns (raster/spiral), RF-assisted discovery/recovery link, and integrated system demo.
