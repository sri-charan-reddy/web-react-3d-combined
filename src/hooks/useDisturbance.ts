/**
 * Live disturbance injection toggles.
 *
 * Each toggle posts a partial payload; the backend replies with the full
 * authoritative disturbance state, which we adopt verbatim. That matters for
 * "severe", which switches on cloud, turbulence and vibration server-side —
 * mirroring that locally would drift from the simulator.
 */
import { useCallback, useState } from 'react';
import { sendDisturbance, type DisturbancePayload } from '@/api/endpoints';
import type { DisturbanceState } from '@/types/telemetry';

export interface DisturbanceToggles {
  cloud: boolean;
  turbulence: boolean;
  vibration: boolean;
  severe: boolean;
}

const INITIAL: DisturbanceToggles = {
  cloud: false,
  turbulence: false,
  vibration: false,
  severe: false,
};

/** Vibration amplitude in px used when the toggle is switched on. */
const VIBRATION_ON = 3.5;

export function useDisturbance() {
  const [toggles, setToggles] = useState<DisturbanceToggles>(INITIAL);

  const send = useCallback(async (payload: DisturbancePayload, optimistic: Partial<DisturbanceToggles>) => {
    setToggles((t) => ({ ...t, ...optimistic }));
    try {
      const state: DisturbanceState = await sendDisturbance(payload);
      setToggles({
        cloud: state.cloud,
        turbulence: state.is_turbulent,
        vibration: state.is_vibrating,
        severe: state.severe,
      });
    } catch (err) {
      console.error('[disturbance] request failed', err);
    }
  }, []);

  return {
    toggles,
    setCloud: (on: boolean) => send({ cloud: on }, { cloud: on }),
    setTurbulence: (on: boolean) => send({ turbulence: on ? 'HIGH' : 'OFF' }, { turbulence: on }),
    setVibration: (on: boolean) =>
      send({ vibration: on ? VIBRATION_ON : 0.0 }, { vibration: on }),
    setSevere: (on: boolean) =>
      send(
        { severe: on },
        on ? { severe: true, cloud: true, turbulence: true, vibration: true } : { severe: false },
      ),
  };
}
