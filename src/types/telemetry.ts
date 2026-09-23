/**
 * Wire contract for the Python mission-control backend (`src/web/server.py`).
 *
 * These types mirror the JSON emitted by `/api/telemetry` and `/api/stream`
 * exactly. Fields the simulator leaves unset arrive as `null` rather than being
 * omitted, so they are typed `T | null` instead of optional.
 */

/** Cartesian pair in arena world pixels (1280x720). */
export type Vec2 = readonly [number, number];

/** Operational states of the Part 4 recovery state machine. */
export type SystemState =
  | 'IDLE'
  | 'RF_DISCOVERY'
  | 'RF_AUTHENTICATION'
  | 'RF_DIRECTION_RECOVERY'
  | 'OPTICAL_SEARCH'
  | 'OPTICAL_TRACKING'
  | 'OPTICAL_REACQUISITION'
  | 'PREDICTIVE_RECOVERY'
  | 'LOCAL_REACQUISITION'
  | 'FINE_ALIGNMENT'
  | 'FSOC_ACTIVE'
  | 'RECOVERY_FAILED';

export type TurbulenceLevel = 'OFF' | 'LOW' | 'MEDIUM' | 'HIGH';
export type RfStatus = 'TRANSMITTING' | 'DISCOVERED' | 'IDLE';
export type TerminalRole = 'Target' | 'Other';
export type ScenarioId = 'normal' | 'temporary-loss' | 'deep-loss' | 'rogue-auth';

/** One remote terminal in the sector, as tracked by the simulator. */
export interface Terminal {
  id: string;
  name: string;
  /** "Detected" once the optical scan has swept over it. */
  status: string;
  rf_status: RfStatus;
  role: TerminalRole;
  position: Vec2;
  velocity: Vec2;
  heading: number;
  speed: number;
  trajectory: string;
  is_target: boolean;
}

/** Local ground station (Terminal A) pose and camera cone. */
export interface TerminalAState {
  x: number;
  y: number;
  orientation_deg: number;
  fov_deg: number;
}

/** Remote target terminal (Terminal B) pose and beacon. */
export interface TerminalBState {
  x: number;
  y: number;
  beacon_active: boolean;
  beacon_x: number;
  beacon_y: number;
}

/** World-space simulation snapshot used by the arena renderer. */
export interface ArenaState {
  terminal_a: TerminalAState;
  terminal_b: TerminalBState;
  terminals_list: Terminal[];
  world_width: number;
  world_height: number;
  kalman_pred: Vec2 | null;
  kalman_cov_trace: number;
  sim_step: number;
  scenario: ScenarioId;
  is_running: boolean;
  cloud_occlusion: boolean;
  vibration: number;
  turbulence: TurbulenceLevel;
}

/** HMAC-SHA256 challenge/response audit block (Part 3). */
export interface SecurityState {
  algorithm: string;
  challenge_nonce: string;
  hmac_sample: string;
  replay_protected: boolean;
  valid: boolean;
  stage: string;
  identification_status: string;
  target_terminal: string;
  target_terminal_name: string;
}

/** The full per-frame telemetry contract (`SystemTelemetry` on the Python side). */
export interface Telemetry {
  timestamp: number;
  current_state: SystemState;
  beacon_detected: boolean;
  beacon_position: Vec2 | null;
  tracking_status: string;
  prediction_status: string;
  optical_recovery_status: string;
  rf_status: string;
  terminal_id: string;
  authentication_status: string;
  approximate_direction: string | null;
  alignment_status: string;
  fsoc_status: string;
  error_status: string | null;
  camera_orientation_deg: number;
  camera_pan: number;
  camera_tilt: number;
  pointing_error_px: number | null;
  pointing_error_deg: number | null;
  tracking_error: number | null;
  rf_rssi: number | null;
  rf_direction: string | null;
  tracking_confidence: number;
  miss_count: number;
  recovery_attempt: number;
  terminal_world_position: Vec2 | null;
  terminal_velocity: Vec2 | null;
  terminal_heading: number;
  beacon_image_position: Vec2 | null;
  predicted_beacon_position: Vec2 | null;
  optical_signal_strength: number;
  optical_link_status: string;
  turbulence_level: TurbulenceLevel;
  vibration_level: number;
  cloud_occlusion: boolean;
  num_terminals: number;
  target_terminal: string;
  target_terminal_name: string;
  identification_status: string;
  security_algorithm: string;
  security_challenge_nonce: string;
  security_hmac_sample: string;
  security_replay_protected: boolean;
  security_valid: boolean;
  security_stage: string;
  recovery_mechanism: string;
  rf_discovery_state: string;
  rf_discovered_count: number;
  rf_total_count: number;
  rf_wave_active: boolean;
  optical_search_state: string;
  optical_tracking_state: string;
  fsoc_state: string;
  terminals_overview: Terminal[];
  recent_events: string[];
}

/** One SSE frame — the root object pushed on `/api/stream` at ~30 Hz. */
export interface TelemetryFrame {
  telemetry: Telemetry;
  arena: ArenaState;
  terminals: Terminal[];
  target_terminal: string;
  target_terminal_name: string;
  num_terminals: number;
  security: SecurityState;
  recovery_mechanism: string;
  events: string[];
  timestamp: number;
}

/** `/api/terminals` and `/api/terminals/config` response. */
export interface TerminalsConfig {
  num_terminals: number;
  target_terminal: string;
  available_pool: { id: string; name: string }[];
  overview: Terminal[];
}

/** `/api/disturbance` response — the simulator's authoritative echo. */
export interface DisturbanceState {
  cloud: boolean;
  cloud_occlusion: boolean;
  cloud_transit_frames: number;
  turbulence: TurbulenceLevel;
  turbulence_level: TurbulenceLevel;
  is_turbulent: boolean;
  vibration: number;
  vibration_amplitude: number;
  is_vibrating: boolean;
  severe: boolean;
}

export interface TestItem {
  name: string;
  status: 'PASSED' | 'FAILED' | 'PENDING' | 'RUNNING';
}

export interface TestCategory {
  id: string;
  title: string;
  passed: number;
  total: number;
  status: 'PASSED' | 'FAILED' | 'PENDING' | 'RUNNING';
  items: TestItem[];
}

/** `/api/tests/status` and `/api/tests/run` response. */
export interface TestStatus {
  is_running: boolean;
  current_step: string;
  progress_pct: number;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  success: boolean;
  duration_sec: number;
  last_run_time: number;
  categories: TestCategory[];
}

/** `/api/action` response. */
export interface ActionResult {
  success: boolean;
  action: string;
  is_running: boolean;
  scenario: ScenarioId;
}
