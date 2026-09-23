/** Multi-terminal registry with live RF discovery and motion state. */
import { memo, useCallback } from 'react';
import { Icon } from '@/components/common/Icon';
import { useTelemetry } from '@/hooks/useTelemetry';
import type { TelemetryFrame, Terminal } from '@/types/telemetry';

interface Slice {
  terminals: Terminal[];
  targetId: string;
  /** Cheap change-detector: only the fields the table actually draws. */
  signature: string;
}

const selectTerminals = (frame: TelemetryFrame | null): Slice => {
  const terminals = frame?.terminals ?? [];
  const targetId = frame?.target_terminal ?? '';
  return {
    terminals,
    targetId,
    signature:
      terminals.map((t) => `${t.id}:${t.status}:${t.rf_status}`).join('|') + `|${targetId}`,
  };
};

/**
 * Positions update every frame but the table shows discrete status only, so it
 * re-renders on the signature alone.
 */
const sigEqual = (a: Slice, b: Slice) => a.signature === b.signature;

const Row = memo(function Row({ t, isTarget }: { t: Terminal; isTarget: boolean }) {
  const discovered = t.rf_status === 'DISCOVERED';
  const detected = String(t.status ?? '').toLowerCase() === 'detected';
  return (
    <tr data-target={isTarget}>
      <td>
        <span className="table__name">
          <Icon
            name={isTarget ? 'target' : 'satellite'}
            size={12}
            className={isTarget ? 'text-ok' : 'text-muted'}
          />
          {t.name}
        </span>
      </td>
      <td>
        <span className={`chip ${discovered ? 'chip--ok' : 'chip--warn'}`}>
          {discovered ? 'Discovered' : 'Transmitting'}
        </span>
      </td>
      <td>
        <span className={`chip ${detected ? 'chip--info' : ''}`}>
          {detected ? 'Detected' : 'Unseen'}
        </span>
      </td>
      <td className="readout text-muted">{t.speed.toFixed(1)} px/s</td>
      <td className="readout text-muted">{t.heading.toFixed(0)}°</td>
      <td>{isTarget ? <span className="chip chip--ok">Target</span> : <span className="text-muted">—</span>}</td>
    </tr>
  );
});

export function TerminalsTab() {
  const s = useTelemetry(useCallback(selectTerminals, []), sigEqual);

  if (s.terminals.length === 0) {
    return <div className="empty">Awaiting terminal registry…</div>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Terminal</th>
          <th>RF discovery</th>
          <th>Optical</th>
          <th>Speed</th>
          <th>Heading</th>
          <th>Role</th>
        </tr>
      </thead>
      <tbody>
        {s.terminals.map((t) => (
          <Row key={t.id} t={t} isTarget={t.id === s.targetId || t.is_target} />
        ))}
      </tbody>
    </table>
  );
}
