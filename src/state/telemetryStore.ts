/**
 * Telemetry store — the backbone of the dashboard's render performance.
 *
 * The backend pushes a full frame at ~30 Hz. Holding that in React state and
 * letting it flow down through context would re-render every panel 30 times a
 * second; the original vanilla dashboard sidestepped the problem by poking
 * `textContent` on ~60 cached DOM nodes by hand.
 *
 * Instead the frame lives outside React in a mutable slot. Components subscribe
 * through `useTelemetry(selector)` (see hooks/useTelemetry.ts) and re-render
 * only when *their own slice* changes value. Canvas renderers skip React
 * altogether and read `getFrame()` from inside a requestAnimationFrame loop.
 */
import type { TelemetryFrame } from '@/types/telemetry';

export type ConnectionState = 'connecting' | 'live' | 'reconnecting';

type Listener = () => void;

let frame: TelemetryFrame | null = null;
let connection: ConnectionState = 'connecting';

const frameListeners = new Set<Listener>();
const connectionListeners = new Set<Listener>();

function emit(listeners: Set<Listener>): void {
  for (const listener of listeners) listener();
}

/** Latest frame, or null before the first one arrives. */
export function getFrame(): TelemetryFrame | null {
  return frame;
}

export function setFrame(next: TelemetryFrame): void {
  frame = next;
  emit(frameListeners);
}

export function subscribeFrame(listener: Listener): () => void {
  frameListeners.add(listener);
  return () => frameListeners.delete(listener);
}

export function getConnection(): ConnectionState {
  return connection;
}

export function setConnection(next: ConnectionState): void {
  if (connection === next) return;
  connection = next;
  emit(connectionListeners);
}

export function subscribeConnection(listener: Listener): () => void {
  connectionListeners.add(listener);
  return () => connectionListeners.delete(listener);
}

/** Test seam — drops all state and listeners. */
export function resetStore(): void {
  frame = null;
  connection = 'connecting';
  frameListeners.clear();
  connectionListeners.clear();
}
