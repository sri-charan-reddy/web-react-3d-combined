/**
 * PAT lifecycle pipelines — the step lists and the state -> step mappings.
 *
 * Data, not markup: the original dashboard hard-coded ~20 pipeline nodes in
 * HTML and then queried them back out with `querySelector('[data-step=...]')`
 * to toggle classes. Declaring them here means the active node is a pure
 * function of the current system state.
 */
import type { SystemState } from '@/types/telemetry';

export interface PipelineStep {
  /** Stable key, matching the original `data-step` attribute. */
  key: string;
  num: string;
  label: string;
  /** Terminal success node, rendered with the goal accent. */
  goal?: boolean;
  /** Failure node, rendered with the alert accent. */
  alert?: boolean;
}

export const PRIMARY_PIPELINE: PipelineStep[] = [
  { key: 'DEPLOY_TERMINALS', num: '1', label: 'DEPLOY TERMINALS' },
  { key: 'RF_TRANSMISSION', num: '2', label: 'RF TRANSMISSION' },
  { key: 'RF_DISCOVERY', num: '3', label: 'RF DISCOVERY' },
  { key: 'TARGET_IDENTIFICATION', num: '4', label: 'TARGET IDENTIFIED' },
  { key: 'HMAC_AUTHENTICATION', num: '5', label: 'HMAC-SHA256 AUTH' },
  { key: 'OPTICAL_SEARCH', num: '6', label: '360° OPTICAL SCAN' },
  { key: 'OPTICAL_TRACKING', num: '7', label: 'OPTICAL TRACKING' },
  { key: 'FINE_ALIGNMENT', num: '8', label: 'FINE ALIGNMENT' },
  { key: 'FSOC_ACTIVE', num: '★', label: 'FSOC ACTIVE', goal: true },
];

export const RECOVERY_PIPELINE: PipelineStep[] = [
  { key: 'FSOC_ACTIVE_BASE', num: '1', label: 'FSOC ACTIVE' },
  { key: 'BEACON_LOST', num: '2', label: 'BEACON LOST', alert: true },
  { key: 'PREDICTIVE_RECOVERY', num: '3', label: 'PREDICTIVE RECOVERY' },
  { key: 'LOCAL_REACQUISITION', num: '4', label: 'LOCAL REACQUISITION' },
  { key: 'OPTICAL_SEARCH', num: '5', label: '360° OPTICAL SEARCH' },
  { key: 'RF_DISCOVERY_REC', num: '6', label: 'RF RECOVERY' },
  { key: 'HMAC_AUTH_REC', num: '7', label: 'HMAC AUTH' },
  { key: 'RF_DIRECTION_REC', num: '8', label: 'RF DIRECTION' },
  { key: 'OPTICAL_REACQUISITION', num: '9', label: 'OPTICAL REACQUISITION' },
  { key: 'FINE_ALIGNMENT_REC', num: '10', label: 'FINE ALIGNMENT' },
  { key: 'FSOC_ACTIVE_RESTORED', num: '★', label: 'FSOC ACTIVE', goal: true },
];

const PRIMARY_STATE_MAP: Partial<Record<SystemState, string>> = {
  IDLE: 'DEPLOY_TERMINALS',
  RF_DISCOVERY: 'RF_DISCOVERY',
  RF_AUTHENTICATION: 'HMAC_AUTHENTICATION',
  OPTICAL_SEARCH: 'OPTICAL_SEARCH',
  OPTICAL_REACQUISITION: 'OPTICAL_SEARCH',
  OPTICAL_TRACKING: 'OPTICAL_TRACKING',
  FINE_ALIGNMENT: 'FINE_ALIGNMENT',
  FSOC_ACTIVE: 'FSOC_ACTIVE',
};

const RECOVERY_STATE_MAP: Partial<Record<SystemState, string>> = {
  PREDICTIVE_RECOVERY: 'PREDICTIVE_RECOVERY',
  LOCAL_REACQUISITION: 'LOCAL_REACQUISITION',
  OPTICAL_SEARCH: 'OPTICAL_SEARCH',
  RF_DISCOVERY: 'RF_DISCOVERY_REC',
  RF_AUTHENTICATION: 'HMAC_AUTH_REC',
  RF_DIRECTION_RECOVERY: 'RF_DIRECTION_REC',
  OPTICAL_REACQUISITION: 'OPTICAL_REACQUISITION',
  FINE_ALIGNMENT: 'FINE_ALIGNMENT_REC',
  FSOC_ACTIVE: 'FSOC_ACTIVE_RESTORED',
  RECOVERY_FAILED: 'HMAC_AUTH_REC',
};

/**
 * Which primary-pipeline nodes are lit for a state. RF_DISCOVERY lights both
 * the transmission and discovery nodes, so this returns a set rather than one key.
 */
export function activePrimarySteps(state: SystemState): ReadonlySet<string> {
  const active = new Set<string>();
  if (state === 'RF_DISCOVERY') active.add('RF_TRANSMISSION');
  const mapped = PRIMARY_STATE_MAP[state];
  if (mapped) active.add(mapped);
  return active;
}

/** Which recovery-pipeline node is lit. Nominal operation lights the base node. */
export function activeRecoveryStep(state: SystemState): string | null {
  if (state === 'FSOC_ACTIVE') return 'FSOC_ACTIVE_BASE';
  if (state === 'IDLE') return null;
  return RECOVERY_STATE_MAP[state] ?? null;
}
