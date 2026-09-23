# Team Raynex — Autonomous Multimodal FSOC PAT System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/System-Multimodal%20FSOC%20PAT-orange.svg)](docs/architecture.md)

Welcome to the **Team Raynex** repository for the **Free-Space Optical Communication (FSOC) Pointing, Acquisition, and Tracking (PAT)** System.

This repository consolidates and unifies all 4 project subsystems developed across team branches:
- **Part 1 (Manoj)**: Virtual FSOC PAT Environment, Beacon Simulation & Optical Detection
- **Part 2 (Simhadri)**: Kalman-Filter Predictive Tracking, Atmospheric Turbulence & Disturbance Handling
- **Part 3 (Ashish)**: RF-Assisted Discovery, Terminal Identification & HMAC-SHA256 Cryptographic Authentication
- **Part 4 (Team Integration)**: Autonomous Adaptive Recovery State Machine & Master HUD Control

---

## 🌟 Architecture & Subsystems Overview

```
                             TEAM RAYNEX FSOC PAT SYSTEM
                                          │
    ┌─────────────────────────┬───────────┴───────────┬─────────────────────────┐
    │                         │                       │                         │
┌───▼────────────────┐ ┌──────▼──────────────┐ ┌──────▼──────────────┐ ┌────────▼────────┐
│      PART 1        │ │       PART 2        │ │       PART 3        │ │      PART 4       │
│ Virtual PAT Env    │ │ Predictive Tracking │ │ Auxiliary RF Discov │ │ Master Integration│
│ & Optical Detect   │ │ & Disturbance Rej.  │ │ & HMAC Auth         │ │ & Recovery Engine │
│ (Manoj)            │ │ (Simhadri)          │ │ (Ashish)            │ │ (Frontend & FSM)  │
└────────────────────┘ └─────────────────────┘ └─────────────────────┘ └─────────────────┘
```

For complete technical documentation, see:
- [Unified Architecture Specification](docs/architecture.md)
- [Part 1 Architecture & Specs](docs/part1_architecture.md)
- [Part 2 Architecture & Mathematical Kalman Models](docs/part2_architecture.md)
- [Part 3 RF & HMAC Protocol Details](README_Ashish.md)

---

## 📂 Repository Structure

```
Team-Raynex/
├── main.py                        # Unified multi-part CLI dispatcher (Part 4 default)
├── run_part4.py                   # Dedicated launcher for Part 4 Autonomous Orchestrator
├── run_part1.py                   # Dedicated launcher for Part 1 (Manoj)
├── run_part2.py                   # Dedicated launcher for Part 2 (Simhadri)
├── run_part3.py                   # Dedicated launcher for Part 3 (Ashish)
├── benchmark_part2.py             # Headless benchmarking suite for Part 2
│
├── config.py                      # Part 2 typed system configuration
├── config/
│   └── config.yaml                # Part 1 YAML environment configuration
│
├── src/                           # Unified source package
│   ├── __init__.py                # Package version & Part 2 exports
│   │
│   │  # --- Part 4 Modules ---
│   ├── orchestrator/              # Central FSM & Telemetry Integration Engine
│   │   ├── __init__.py
│   │   ├── controller.py          # FSOCRecoveryOrchestrator closed-loop state machine
│   │   ├── states.py              # SystemState enum (12 operational states)
│   │   └── telemetry.py           # SystemTelemetry data contract for UI / logging
│   │
│   │  # --- Part 1 Modules ---
│   ├── control/                   # PAT controller & Archimedean spiral search
│   ├── detection/                 # Classical beacon centroid detector & alignment
│   ├── simulation/                # Terminal motion, virtual camera sensor & beacon
│   ├── visualization/             # OpenCV environment renderer
│   ├── main.py                    # Part 1 standalone visual application
│   │
│   │  # --- Part 2 Modules ---
│   ├── kalman_tracker.py          # Kalman filter predictive tracker & gating
│   ├── atmospheric_turbulence.py  # Gauss-Markov atmospheric turbulence model
│   ├── beacon_simulator.py        # Ground-truth kinematic beacon simulation
│   ├── camera_controller.py       # Closed-loop Pan/Tilt servo controller
│   ├── disturbance_simulator.py   # Jitter, occlusions, and outlier injection
│   ├── local_search.py            # Bounded local search reacquisition
│   ├── tracking_state.py          # State machine, telemetry & performance metrics
│   ├── virtual_camera.py          # Moving camera FOV & arena model
│   └── visualizer.py              # Real-time multi-color OpenCV tracking HUD
│
├── rf_discovery_Ashish.py         # Part 3 RF discovery & HMAC engine
├── test_rf_discovery_Ashish.py    # Part 3 test suite (7 deterministic test cases)
├── tests/
│   └── test_part4_integration.py  # Part 4 complete integration test suite (6 scenarios)
│
├── verify_atmospheric_turbulence.py # Part 2 turbulence verification test
├── verify_camera.py                 # Part 2 virtual camera FOV verification
├── verify_camera_controller.py      # Part 2 pan/tilt servo verification
├── verify_local_search.py           # Part 2 local search pattern verification
├── verify_lost_reacquisition.py     # Part 2 recovery state machine verification
│
├── results/                       # Part 2 benchmarking telemetry (CSV & JSON)
├── docs/                          # Architecture & design documentation
│   ├── architecture.md            # Master unified system architecture
│   ├── part1_architecture.md      # Part 1 architecture document
│   └── part2_architecture.md      # Part 2 architecture document
│
├── README_Part1_Manoj.md          # Dedicated README for Part 1
├── README_Part2_Simhadri.md       # Dedicated README for Part 2
├── README_Ashish.md               # Dedicated README for Part 3
└── requirements.txt               # Unified project dependencies
```

---

## 🚀 Getting Started

### 1. Prerequisites & Installation

```bash
# Clone repository (if not already local)
git clone https://github.com/sri-charan-reddy/Team-Raynex.git
cd Team-Raynex

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

### 2. Running Subsystems

#### Unified Dispatcher (`main.py`)
```bash
# Launch Interactive Mission Control Web Dashboard
python3 main.py --dashboard
# or
python3 run_dashboard.py

# Run Master Quality & Test Evaluation Suite (All 56 Tests across Parts 1-4 & Dashboard)
python3 main.py --part all-tests
# or
python3 run_all_tests.py

# Launch Part 4 Autonomous Orchestrator [Default]
python3 main.py

# Launch Part 4 Integration Test Suite
python3 main.py --part test

# Launch Part 1 (Virtual FSOC PAT Environment)
python3 main.py --part 1

# Launch Part 2 (Predictive Tracking & Disturbance Visualizer)
python3 main.py --part 2

# Launch Part 3 (RF Discovery & HMAC Authentication Test Suite)
python3 main.py --part 3

# Execute Part 2 Headless Benchmark
python3 main.py --part benchmark
```

#### Dedicated Launchers
```bash
# Part 4 Orchestrator (with scenario options):
python3 run_part4.py --scenario deep-loss
python3 run_part4.py --scenario temporary-loss
python3 run_part4.py --scenario rogue-auth
python3 run_part4.py --scenario normal

# Part 1 (Manoj):
python3 run_part1.py

# Part 2 (Simhadri):
python3 run_part2.py

# Part 3 (Ashish):
python3 run_part3.py

# Part 2 Benchmark:
python3 benchmark_part2.py
```

---

## 🧪 Verification & Testing

### Run Part 3 RF Authentication Suite
```bash
python3 run_part3.py
# or
python3 test_rf_discovery_Ashish.py
```
*Executes all 7 test cases covering terminal match, wrong terminal, impostor authentication failure, empty RF space, dynamic direction calculation, RSSI path-loss, and shared secret protection.*

### Run Part 2 Verification Suites
```bash
python3 verify_atmospheric_turbulence.py
python3 verify_camera.py
python3 verify_camera_controller.py
python3 verify_local_search.py
python3 verify_lost_reacquisition.py
```

---

## 🌿 Git Branches

This repository maintains local tracking branches for individual contributions:
- `main`: Unified codebase integrating Part 1, Part 2, and Part 3.
- `Simhadri-part2-predictive-tracking`: Original standalone Part 2 branch.
- `monaj-part-1`: Original Part 1 branch.

To inspect or switch branches:
```bash
git checkout Simhadri-part2-predictive-tracking
git checkout monaj-part-1
git checkout main
```
