/**
 * System test suite: kick off a run and poll until it settles.
 *
 * Polling (not SSE) matches the backend, which exposes test progress on a plain
 * `/api/tests/status` endpoint. The interval is cleared on unmount and whenever
 * the run finishes, so no timer outlives the panel.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchTestStatus, runTests } from '@/api/endpoints';
import type { TestStatus } from '@/types/telemetry';

const POLL_INTERVAL_MS = 300;

export function useTestRunner() {
  const [status, setStatus] = useState<TestStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | undefined>(undefined);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== undefined) {
      window.clearInterval(pollRef.current);
      pollRef.current = undefined;
    }
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    fetchTestStatus(ac.signal)
      .then(setStatus)
      .catch((err) => {
        if (!ac.signal.aborted) console.warn('[tests] initial status failed', err);
      });
    return () => {
      ac.abort();
      stopPolling();
    };
  }, [stopPolling]);

  const start = useCallback(async () => {
    setError(null);
    try {
      setStatus(await runTests());
      stopPolling();
      pollRef.current = window.setInterval(async () => {
        try {
          const next = await fetchTestStatus();
          setStatus(next);
          if (!next.is_running) stopPolling();
        } catch (err) {
          console.warn('[tests] poll failed', err);
          stopPolling();
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start tests');
    }
  }, [stopPolling]);

  return { status, error, isRunning: status?.is_running ?? false, start };
}
