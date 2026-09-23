/**
 * Terminal deployment form: count + target selection, applied as one action.
 *
 * The form is intentionally local-draft state — nothing is sent until the
 * operator presses APPLY, so a mid-edit count never reconfigures the sim.
 */
import { useCallback, useEffect, useState } from 'react';
import { fetchTerminals, updateTerminalsConfig } from '@/api/endpoints';
import type { TerminalsConfig } from '@/types/telemetry';

export const MIN_TERMINALS = 2;
export const MAX_TERMINALS = 12;

export function terminalId(index: number): string {
  return `TERMINAL_${String(index).padStart(2, '0')}`;
}

export function terminalName(index: number): string {
  return `Terminal-${String(index).padStart(2, '0')}`;
}

interface UseTerminalConfig {
  count: number;
  target: string;
  options: { id: string; name: string }[];
  applying: boolean;
  error: string | null;
  stepCount: (delta: number) => void;
  setTarget: (id: string) => void;
  apply: () => Promise<void>;
}

export function useTerminalConfig(onApplied?: () => void): UseTerminalConfig {
  const [count, setCount] = useState(5);
  const [target, setTarget] = useState('TERMINAL_03');
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const adopt = useCallback((cfg: TerminalsConfig) => {
    setCount(cfg.num_terminals);
    setTarget(cfg.target_terminal);
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    fetchTerminals(ac.signal)
      .then(adopt)
      .catch((err) => {
        if (!ac.signal.aborted) console.warn('[config] initial fetch failed', err);
      });
    return () => ac.abort();
  }, [adopt]);

  const stepCount = useCallback((delta: number) => {
    setCount((c) => Math.max(MIN_TERMINALS, Math.min(MAX_TERMINALS, c + delta)));
  }, []);

  // Options track the count; a target outside the new range is appended so the
  // select never shows a blank value mid-edit.
  const options = Array.from({ length: Math.max(count, MIN_TERMINALS) }, (_, i) => ({
    id: terminalId(i + 1),
    name: terminalName(i + 1),
  }));
  if (!options.some((o) => o.id === target)) {
    options.push({ id: target, name: target.replace('_', '-') });
  }

  const apply = useCallback(async () => {
    setApplying(true);
    setError(null);
    try {
      const cfg = await updateTerminalsConfig(count, target);
      adopt(cfg);
      onApplied?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply configuration');
    } finally {
      setApplying(false);
    }
  }, [count, target, adopt, onApplied]);

  return { count, target, options, applying, error, stepCount, setTarget, apply };
}
