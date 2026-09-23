/**
 * Derived mission status.
 *
 * The dashboard's badges are driven by a handful of booleans computed from the
 * raw frame. In the vanilla build that logic was inlined at the top of a
 * 250-line `updateUI()`; pulling it out here gives one place to read the rules
 * and keeps every panel consistent with the others.
 */
import { getConnection } from '@/state/telemetryStore';
import type { SecurityState, Telemetry, TelemetryFrame } from '@/types/telemetry';

export type Tone = 'emerald' | 'amber' | 'cyan' | 'crimson' | 'muted';

export interface MissionStatus {
  state: string;
  targetName: string;
  beaconDetected: boolean;
  /** Target matched against the authenticated RF identity. */
  identified: boolean;
  /** HMAC-SHA256 challenge/response passed. */
  authenticated: boolean;
  /** Boresight error inside the fine-alignment margin. */
  opticalAligned: boolean;
  /** Bi-directional optical link carrying traffic. */
  fsocActive: boolean;
  /** Rogue-terminal rejection — the one hard-failure state. */
  failed: boolean;
  discoveredCount: number;
  totalCount: number;
  /** True while RF discovery is still sweeping. */
  discovering: boolean;
  recoveryMechanism: string;
}

const EMPTY_STATUS: MissionStatus = {
  state: 'IDLE',
  targetName: 'Terminal-03',
  beaconDetected: false,
  identified: false,
  authenticated: false,
  opticalAligned: false,
  fsocActive: false,
  failed: false,
  discoveredCount: 0,
  totalCount: 5,
  discovering: false,
  recoveryMechanism: 'NONE',
};

/** Turn `TERMINAL_03` into `Terminal-03` when the backend omits the label. */
export function terminalLabel(id: string | null | undefined): string {
  if (!id) return 'Terminal-03';
  const [prefix, suffix] = id.split('_');
  if (!suffix) return id;
  return `${prefix.charAt(0)}${prefix.slice(1).toLowerCase()}-${suffix}`;
}

export function deriveStatus(frame: TelemetryFrame | null): MissionStatus {
  if (!frame) return EMPTY_STATUS;

  const telem: Telemetry = frame.telemetry;
  const sec: SecurityState | null | undefined = frame.security;
  const state = telem.current_state ?? 'IDLE';

  const connectionState = getConnection();
  const connected = connectionState === 'live';
  const securityValid = Boolean(sec?.valid === true || telem.security_valid === true);
  const securityStage = sec?.stage ?? telem.security_stage ?? '';
  const telemetryAuthStatus = telem.authentication_status ?? '';
  const stageAuthenticated = Boolean(
    securityStage === 'AUTHENTICATED' || telem.security_stage === 'AUTHENTICATED',
  );

  const totalCount = telem.rf_total_count || frame.terminals.length || 5;
  const discoveredCount =
    telem.rf_discovered_count ?? frame.terminals.filter((t) => t.rf_status === 'DISCOVERED').length;

  return {
    state,
    targetName: telem.target_terminal_name || terminalLabel(telem.target_terminal),
    beaconDetected: telem.beacon_detected,
    identified:
      telem.identification_status === 'IDENTIFIED' ||
      state === 'FSOC_ACTIVE' ||
      state === 'OPTICAL_TRACKING',
    authenticated:
      connected && (securityValid && (stageAuthenticated || telemetryAuthStatus === 'AUTHENTICATED')),
    opticalAligned:
      (state === 'FSOC_ACTIVE' || state === 'FINE_ALIGNMENT') && telem.beacon_detected,
    fsocActive:
      telem.fsoc_status === 'ESTABLISHED' ||
      telem.fsoc_status === 'ACTIVE' ||
      state === 'FSOC_ACTIVE',
    failed: state === 'RECOVERY_FAILED',
    discoveredCount,
    totalCount,
    discovering: state === 'RF_DISCOVERY' && discoveredCount < totalCount,
    recoveryMechanism: telem.recovery_mechanism || 'NONE',
  };
}

export function statusEquals(a: MissionStatus, b: MissionStatus): boolean {
  return (
    a.state === b.state &&
    a.targetName === b.targetName &&
    a.beaconDetected === b.beaconDetected &&
    a.identified === b.identified &&
    a.authenticated === b.authenticated &&
    a.opticalAligned === b.opticalAligned &&
    a.fsocActive === b.fsocActive &&
    a.failed === b.failed &&
    a.discoveredCount === b.discoveredCount &&
    a.totalCount === b.totalCount &&
    a.discovering === b.discovering &&
    a.recoveryMechanism === b.recoveryMechanism
  );
}

/** Label + tone pairs, matching the vanilla dashboard's wording exactly. */

export function identBadge(s: MissionStatus): [string, Tone] {
  return s.identified ? ['✓ IDENTIFIED', 'emerald'] : ['SEARCHING...', 'amber'];
}

export function authBadge(s: MissionStatus): [string, Tone] {
  if (s.failed) return ['✗ REJECTED', 'crimson'];
  return s.authenticated ? ['✓ HMAC-SHA256', 'emerald'] : ['VERIFYING', 'amber'];
}

export function opticalLinkBadge(s: MissionStatus): [string, string] {
  if (s.opticalAligned) return ['✓ ALIGNED', 'link-active'];
  return s.beaconDetected ? ['TRACKING', 'link-searching'] : ['LOST', 'link-down'];
}

export function fsocBadge(s: MissionStatus): [string, string] {
  if (s.fsocActive) return ['● ACTIVE', 'state-badge'];
  if (s.failed) return ['✗ FAILED', 'link-badge link-down'];
  return ['REACQUIRING...', 'link-badge link-searching'];
}
