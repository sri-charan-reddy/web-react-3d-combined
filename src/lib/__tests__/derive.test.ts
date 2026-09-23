import { afterEach, describe, expect, it } from 'vitest';
import { deriveStatus } from '../derive';
import { resetStore, setConnection } from '@/state/telemetryStore';
import type { TelemetryFrame } from '@/types/telemetry';

function makeFrame(overrides: Partial<TelemetryFrame> = {}): TelemetryFrame {
  const base: TelemetryFrame = {
    telemetry: {
      timestamp: 0,
      current_state: 'IDLE',
      beacon_detected: false,
      beacon_position: null,
      tracking_status: 'IDLE',
      prediction_status: 'IDLE',
      optical_recovery_status: 'IDLE',
      rf_status: 'IDLE',
      terminal_id: 'A',
      authentication_status: 'PENDING',
      approximate_direction: null,
      alignment_status: 'NONE',
      fsoc_status: 'DOWN',
      error_status: null,
      camera_orientation_deg: 0,
      camera_pan: 0,
      camera_tilt: 0,
      pointing_error_px: null,
      pointing_error_deg: null,
      tracking_error: null,
      rf_rssi: null,
      rf_direction: null,
      tracking_confidence: 0,
      miss_count: 0,
      recovery_attempt: 0,
      terminal_world_position: null,
      terminal_velocity: null,
      terminal_heading: 0,
      beacon_image_position: null,
      predicted_beacon_position: null,
      optical_signal_strength: 0,
      optical_link_status: 'DOWN',
      turbulence_level: 'OFF',
      vibration_level: 0,
      cloud_occlusion: false,
      num_terminals: 1,
      target_terminal: 'T1',
      target_terminal_name: 'Terminal-01',
      identification_status: 'SEARCHING',
      security_algorithm: 'HMAC-SHA256',
      security_challenge_nonce: 'nonce',
      security_hmac_sample: 'sample',
      security_replay_protected: true,
      security_valid: false,
      security_stage: 'PENDING',
      recovery_mechanism: 'NONE',
      rf_discovery_state: 'IDLE',
      rf_discovered_count: 0,
      rf_total_count: 1,
      rf_wave_active: false,
      optical_search_state: 'IDLE',
      optical_tracking_state: 'IDLE',
      fsoc_state: 'DOWN',
      terminals_overview: [],
      recent_events: [],
    },
    arena: {
      terminal_a: { x: 0, y: 0, orientation_deg: 0, fov_deg: 0 },
      terminal_b: { x: 0, y: 0, beacon_active: false, beacon_x: 0, beacon_y: 0 },
      terminals_list: [],
      world_width: 1280,
      world_height: 720,
      kalman_pred: null,
      kalman_cov_trace: 0,
      sim_step: 0,
      scenario: 'normal',
      is_running: true,
      cloud_occlusion: false,
      vibration: 0,
      turbulence: 'OFF',
    },
    terminals: [],
    target_terminal: 'T1',
    target_terminal_name: 'Terminal-01',
    num_terminals: 1,
    security: {
      algorithm: 'HMAC-SHA256',
      challenge_nonce: 'nonce',
      hmac_sample: 'sample',
      replay_protected: true,
      valid: false,
      stage: 'PENDING',
      identification_status: 'SEARCHING',
      target_terminal: 'T1',
      target_terminal_name: 'Terminal-01',
    },
    recovery_mechanism: 'NONE',
    events: [],
    timestamp: 0,
    ...overrides,
  };

  return base;
}

describe('deriveStatus', () => {
  afterEach(() => {
    resetStore();
  });

  it('does not mark the stream as authenticated before the SSE connection is live', () => {
    setConnection('connecting');
    const frame = makeFrame({
      telemetry: {
        ...makeFrame().telemetry,
        authentication_status: 'AUTHENTICATED',
        security_valid: true,
        security_stage: 'AUTHENTICATED',
      },
    });

    expect(deriveStatus(frame).authenticated).toBe(false);
  });

  it('only accepts an explicit backend auth signal after the stream is live', () => {
    setConnection('live');
    const frame = makeFrame({
      security: {
        ...makeFrame().security,
        valid: false,
        stage: 'PENDING',
      },
      telemetry: {
        ...makeFrame().telemetry,
        security_valid: true,
        security_stage: 'AUTHENTICATED',
        authentication_status: 'AUTHENTICATED',
      },
    });

    expect(deriveStatus(frame).authenticated).toBe(true);
  });
});
