/**
 * Pipeline state mapping.
 *
 * Every SystemState must light exactly one node in whichever ladder is on
 * screen, otherwise the operator sees a pipeline with nothing highlighted
 * during the state that matters most.
 */
import { describe, expect, it } from 'vitest';
import {
  activePrimarySteps,
  activeRecoveryStep,
  PRIMARY_PIPELINE,
  RECOVERY_PIPELINE,
} from '../pipelines';
import type { SystemState } from '@/types/telemetry';

const ALL_STATES: SystemState[] = [
  'IDLE',
  'RF_DISCOVERY',
  'RF_AUTHENTICATION',
  'RF_DIRECTION_RECOVERY',
  'OPTICAL_SEARCH',
  'OPTICAL_TRACKING',
  'OPTICAL_REACQUISITION',
  'PREDICTIVE_RECOVERY',
  'LOCAL_REACQUISITION',
  'FINE_ALIGNMENT',
  'FSOC_ACTIVE',
  'RECOVERY_FAILED',
];

const primaryKeys = new Set(PRIMARY_PIPELINE.map((s) => s.key));
const recoveryKeys = new Set(RECOVERY_PIPELINE.map((s) => s.key));

describe('activePrimarySteps', () => {
  it('only ever returns keys that exist in the primary pipeline', () => {
    for (const state of ALL_STATES) {
      for (const key of activePrimarySteps(state)) {
        expect(primaryKeys.has(key)).toBe(true);
      }
    }
  });

  it('lights both transmission and discovery during RF discovery', () => {
    const active = activePrimarySteps('RF_DISCOVERY');
    expect(active.has('RF_TRANSMISSION')).toBe(true);
    expect(active.has('RF_DISCOVERY')).toBe(true);
  });

  it('lights the goal node when the link is up', () => {
    expect(activePrimarySteps('FSOC_ACTIVE').has('FSOC_ACTIVE')).toBe(true);
  });
});

describe('activeRecoveryStep', () => {
  it('only ever returns a key that exists in the recovery pipeline', () => {
    for (const state of ALL_STATES) {
      const key = activeRecoveryStep(state);
      if (key !== null) expect(recoveryKeys.has(key)).toBe(true);
    }
  });

  it('rests on the base node during nominal operation', () => {
    expect(activeRecoveryStep('FSOC_ACTIVE')).toBe('FSOC_ACTIVE_BASE');
  });

  it('lights nothing before the system has started', () => {
    expect(activeRecoveryStep('IDLE')).toBeNull();
  });

  it('covers every recovery-phase state', () => {
    const recoveryStates: SystemState[] = [
      'PREDICTIVE_RECOVERY',
      'LOCAL_REACQUISITION',
      'OPTICAL_SEARCH',
      'RF_DISCOVERY',
      'RF_AUTHENTICATION',
      'RF_DIRECTION_RECOVERY',
      'OPTICAL_REACQUISITION',
      'FINE_ALIGNMENT',
      'RECOVERY_FAILED',
    ];
    for (const state of recoveryStates) {
      expect(activeRecoveryStep(state)).not.toBeNull();
    }
    expect(activeRecoveryStep('RECOVERY_FAILED')).toBe('HMAC_AUTH_REC');
  });
});
