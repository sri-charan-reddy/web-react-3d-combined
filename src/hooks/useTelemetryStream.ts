/**
 * Owns the single EventSource connection to `/api/stream`.
 *
 * Mounted once at the app root. Parsed frames go straight into the telemetry
 * store rather than React state — see state/telemetryStore.ts for why.
 */
import { useEffect } from 'react';
import { STREAM_PATH } from '@/api/endpoints';
import { apiUrl } from '@/api/client';
import { setConnection, setFrame } from '@/state/telemetryStore';
import type { TelemetryFrame } from '@/types/telemetry';

export function useTelemetryStream(): void {
  useEffect(() => {
    let source: EventSource | null = null;
    let retryTimer: number | undefined;
    let disposed = false;
    // Back off on repeated failures so a downed backend isn't hammered.
    let retryDelayMs = 1000;
    const MAX_RETRY_MS = 15_000;

    const connect = () => {
      if (disposed) return;
      source = new EventSource(apiUrl(STREAM_PATH));

      source.onopen = () => {
        retryDelayMs = 1000;
        setConnection('live');
      };

      source.onmessage = (event: MessageEvent<string>) => {
        try {
          setFrame(JSON.parse(event.data) as TelemetryFrame);
        } catch (err) {
          console.error('[telemetry] malformed SSE frame', err);
        }
      };

      source.onerror = () => {
        setConnection('reconnecting');
        // EventSource retries on its own, but only for transport hiccups. A
        // closed stream needs an explicit reconnect with our own backoff.
        if (source && source.readyState === EventSource.CLOSED) {
          source.close();
          source = null;
          retryTimer = window.setTimeout(connect, retryDelayMs);
          retryDelayMs = Math.min(retryDelayMs * 2, MAX_RETRY_MS);
        }
      };
    };

    setConnection('connecting');
    connect();

    return () => {
      disposed = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      source?.close();
    };
  }, []);
}
