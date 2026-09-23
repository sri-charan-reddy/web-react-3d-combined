/**
 * Selector-based subscription to the telemetry store.
 *
 * `useSyncExternalStore` re-runs the selector on every pushed frame but only
 * re-renders when the selected value actually differs, so a panel showing
 * `miss_count` stays idle while unrelated fields churn at 30 Hz.
 */
import { useCallback, useRef, useSyncExternalStore } from 'react';
import {
  getConnection,
  getFrame,
  subscribeConnection,
  subscribeFrame,
  type ConnectionState,
} from '@/state/telemetryStore';
import type { TelemetryFrame } from '@/types/telemetry';

/** Default equality: identity, widened to cover NaN. */
function is(a: unknown, b: unknown): boolean {
  return Object.is(a, b);
}

/**
 * Subscribe to a derived slice of the current frame.
 *
 * The selector must be stable (defined at module scope or wrapped in
 * `useCallback`) and pure. Returning a fresh object each call defeats the
 * memoisation — pass `equals` (e.g. a shallow compare) in that case.
 */
export function useTelemetry<T>(
  selector: (frame: TelemetryFrame | null) => T,
  equals: (a: T, b: T) => boolean = is,
): T {
  // Cache the last selected value so identical slices keep referential identity
  // across frames, which is what lets React bail out of the re-render.
  const cache = useRef<{ value: T; seeded: boolean }>({ value: undefined as T, seeded: false });

  const getSnapshot = useCallback(() => {
    const next = selector(getFrame());
    if (!cache.current.seeded || !equals(cache.current.value, next)) {
      cache.current = { value: next, seeded: true };
    }
    return cache.current.value;
  }, [selector, equals]);

  return useSyncExternalStore(subscribeFrame, getSnapshot, getSnapshot);
}

/** Current SSE connection state, for the header's LIVE / RECONNECTING pill. */
export function useConnectionState(): ConnectionState {
  return useSyncExternalStore(subscribeConnection, getConnection, getConnection);
}

/** Shallow object comparison, for selectors that build a small record. */
export function shallowEqual<T extends object>(a: T, b: T): boolean {
  if (Object.is(a, b)) return true;
  if (!a || !b) return false;
  const ka = Object.keys(a) as (keyof T)[];
  const kb = Object.keys(b);
  if (ka.length !== kb.length) return false;
  return ka.every((k) => Object.is(a[k], b[k]));
}
