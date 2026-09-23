/**
 * Link status — the acquisition chain, always visible.
 *
 * These four values were previously spread across five bordered boxes inside
 * the discovery card plus duplicated in the header. Here they are one list of
 * key/value rows: same information, a quarter of the ink.
 */
import { useCallback } from 'react';
import { Icon } from '@/components/common/Icon';
import { useTelemetry } from '@/hooks/useTelemetry';
import { deriveStatus, statusEquals, type MissionStatus } from '@/lib/derive';
import type { TelemetryFrame } from '@/types/telemetry';

const selectStatus = (frame: TelemetryFrame | null): MissionStatus => deriveStatus(frame);

type Tone = 'ok' | 'warn' | 'fault' | 'muted';

function Row({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  const icon = tone === 'ok' ? 'check' : tone === 'fault' ? 'cross' : 'spinner';
  return (
    <div className="kv__row">
      <span className="kv__k">{label}</span>
      <span className={`kv__v text-${tone}`}>
        <span className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
          <Icon
            name={icon}
            size={11}
            className={tone === 'warn' ? 'spin' : undefined}
            style={tone === 'muted' ? { opacity: 0.5 } : undefined}
          />
          {value}
        </span>
      </span>
    </div>
  );
}

function scanTone(state: string): Tone {
  if (state === 'OPTICAL_SEARCH') return 'warn';
  if (state === 'RF_DISCOVERY' || state === 'RF_AUTHENTICATION' || state === 'IDLE') return 'muted';
  return 'ok';
}

function scanLabel(state: string): string {
  if (state === 'OPTICAL_SEARCH') return 'Scanning 360°';
  if (state === 'RF_DISCOVERY' || state === 'RF_AUTHENTICATION' || state === 'IDLE') return 'Standby';
  return 'Acquired';
}

export function LinkPanel() {
  const s = useTelemetry(useCallback(selectStatus, []), statusEquals);

  const overallTone = s.fsocActive ? 'ok' : s.failed ? 'fault' : 'warn';
  const overallLabel = s.fsocActive ? 'Nominal' : s.failed ? 'Alert' : 'Recovering';

  return (
    <section className="card panel">
      <div className="panel__head">
        <Icon name="satellite" size={14} className="text-info" />
        <h3 className="panel__title">Link Status</h3>
        <div className="panel__tools">
          <span className={`chip chip--${overallTone}`}>
            <span className={`dot ${s.fsocActive || s.failed ? 'dot--pulse' : ''}`} />
            {overallLabel}
          </span>
        </div>
      </div>

      <div className="panel__body">
        <div className="kv">
          <Row
            label="RF discovery"
            value={`${s.discoveredCount} / ${s.totalCount}`}
            tone={s.discovering ? 'warn' : 'ok'}
          />
          <Row
            label="Identification"
            value={s.identified ? 'Identified' : 'Scanning'}
            tone={s.identified ? 'ok' : 'warn'}
          />
          <Row
            label="HMAC-SHA256"
            value={s.failed ? 'Rejected' : s.authenticated ? 'Authenticated' : 'Verifying'}
            tone={s.failed ? 'fault' : s.authenticated ? 'ok' : 'warn'}
          />
          <Row label="Optical search" value={scanLabel(s.state)} tone={scanTone(s.state)} />
          <Row
            label="Fine alignment"
            value={s.opticalAligned ? 'Aligned' : s.beaconDetected ? 'Tracking' : 'Lost'}
            tone={s.opticalAligned ? 'ok' : s.beaconDetected ? 'warn' : 'fault'}
          />
          <Row
            label="FSOC link"
            value={s.fsocActive ? 'Active' : s.failed ? 'Halted' : 'Reacquiring'}
            tone={s.fsocActive ? 'ok' : s.failed ? 'fault' : 'warn'}
          />
        </div>
      </div>
    </section>
  );
}
