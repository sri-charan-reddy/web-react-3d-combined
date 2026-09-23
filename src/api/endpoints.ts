/**
 * Every mission-control endpoint, named and typed.
 *
 * Components never build URLs or request bodies themselves — they call these,
 * so a backend route change is a one-file edit.
 */
import { get, post } from './client';
import type {
  ActionResult,
  DisturbanceState,
  ScenarioId,
  TelemetryFrame,
  TerminalsConfig,
  TestStatus,
} from '@/types/telemetry';

export const STREAM_PATH = '/api/stream';
export const CAMERA_FRAME_PATH = '/api/camera_frame';

export const fetchTelemetry = (signal?: AbortSignal) =>
  get<TelemetryFrame>('/api/telemetry', signal);

export const fetchTerminals = (signal?: AbortSignal) =>
  get<TerminalsConfig>('/api/terminals', signal);

export const fetchTestStatus = (signal?: AbortSignal) =>
  get<TestStatus>('/api/tests/status', signal);

export const runTests = () => post<TestStatus>('/api/tests/run');

export const updateTerminalsConfig = (numTerminals: number, targetTerminal: string) =>
  post<TerminalsConfig>('/api/terminals/config', {
    num_terminals: numTerminals,
    target_terminal: targetTerminal,
  });

/**
 * Disturbance payloads are partial — the backend merges them into the live
 * simulator and echoes the full authoritative state back.
 */
export interface DisturbancePayload {
  cloud?: boolean;
  turbulence?: string;
  vibration?: number;
  severe?: boolean;
}

export const sendDisturbance = (payload: DisturbancePayload) =>
  post<DisturbanceState>('/api/disturbance', payload);

export const sendAction = (action: string, extra?: Record<string, unknown>) =>
  post<ActionResult>('/api/action', { action, ...extra });

export const setScenario = (scenario: ScenarioId) => sendAction('scenario', { scenario });
export const pauseSim = () => sendAction('pause');
export const resumeSim = () => sendAction('resume');
export const stepSim = () => sendAction('step');
export const resetSim = () => sendAction('reset');
export const setSpeed = (speed: number) => sendAction('speed', { speed });
