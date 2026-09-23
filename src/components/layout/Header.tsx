/**
 * Command bar.
 *
 * Carries only what must be visible at all times: identity, the state machine's
 * current node, the target, link health and feed status. Everything else moved
 * into the rail or the config drawer — the previous header tried to hold five
 * stacked key/value pairs plus a zoom widget and wrapped mid-token because of it.
 */
import { useCallback } from 'react';
import { Icon } from '@/components/common/Icon';
import { useConnectionState, useTelemetry } from '@/hooks/useTelemetry';
import { deriveStatus, statusEquals, type MissionStatus } from '@/lib/derive';
import type { TelemetryFrame } from '@/types/telemetry';

const selectStatus = (frame: TelemetryFrame | null): MissionStatus => deriveStatus(frame);

/** Tone for the state chip — the one coloured surface in the header. */
function stateTone(s: MissionStatus): 'ok' | 'warn' | 'fault' | 'idle' {
  if (s.failed) return 'fault';
  if (s.fsocActive) return 'ok';
  if (s.state === 'IDLE') return 'idle';
  return 'warn';
}

interface HeaderProps {
  onOpenConfig: () => void;
}

export function Header({ onOpenConfig }: HeaderProps) {
  const status = useTelemetry(useCallback(selectStatus, []), statusEquals);
  const connection = useConnectionState();
  const live = connection === 'live';

  const linkLabel = status.opticalAligned
    ? 'Aligned'
    : status.beaconDetected
      ? 'Tracking'
      : 'Lost';
  const linkTone = status.opticalAligned ? 'ok' : status.beaconDetected ? 'warn' : 'fault';

  const authLabel = status.failed
    ? 'Rejected'
    : status.authenticated
      ? 'HMAC-SHA256'
      : 'Verifying';
  const authTone = status.failed ? 'fault' : status.authenticated ? 'ok' : 'warn';

  return (
    <header className="header" data-live={live}>
      <div className="brand">
        <div className="brand__mark">
          <span className="brand__sweep" />
        </div>
        <div>
          <div className="brand__name">FSOC Adaptive Link</div>
          <div className="brand__sub">Raynex PAT Mission Control</div>
        </div>
      </div>

      <div className="state-chip" data-tone={stateTone(status)}>
        <span className="state-chip__label">State</span>
        <span className="state-chip__value">{status.state.replace(/_/g, ' ')}</span>
      </div>

      <div className="header__status">
        <div className="stat">
          <span className="stat__k">Target</span>
          <span className="stat__v text-info">{status.targetName}</span>
        </div>
        <div className="stat">
          <span className="stat__k">Auth</span>
          <span className={`stat__v text-${authTone}`}>{authLabel}</span>
        </div>
        <div className="stat">
          <span className="stat__k">Optical</span>
          <span className={`stat__v text-${linkTone}`}>{linkLabel}</span>
        </div>

        <div className="link-state" data-live={live}>
          <span className={`dot ${live ? 'dot--pulse' : ''}`} />
          {live ? 'Live 30 Hz' : 'Reconnecting'}
        </div>

        <button
          type="button"
          className="btn btn--icon"
          onClick={onOpenConfig}
          title="Sector configuration"
          aria-label="Sector configuration"
        >
          <Icon name="settings" size={15} />
        </button>
      </div>
    </header>
  );
}
