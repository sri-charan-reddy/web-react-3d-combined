/** Real-time audit trail plus simulation playback controls. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/common/Icon';
import { pauseSim, resetSim, resumeSim, setSpeed, stepSim } from '@/api/endpoints';
import { useTelemetry } from '@/hooks/useTelemetry';
import type { TelemetryFrame } from '@/types/telemetry';

const selectEvents = (frame: TelemetryFrame | null): string[] => frame?.events ?? [];
/** The log is append-only, so length + last line is enough to detect a change. */
const eventsEqual = (a: string[], b: string[]) =>
  a.length === b.length && a[a.length - 1] === b[b.length - 1];

function partOf(event: string): string | undefined {
  const m = /\[PART (\d)\]/.exec(event);
  return m ? m[1] : undefined;
}

export function EventsTab() {
  const events = useTelemetry(useCallback(selectEvents, []), eventsEqual);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeedValue] = useState('1.0');
  // Local clear is view-only; the backend keeps its own ring buffer.
  const [clearedAt, setClearedAt] = useState(0);
  const logRef = useRef<HTMLDivElement>(null);

  const visible = events.slice(clearedAt);

  useEffect(() => {
    const box = logRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [visible.length]);

  const togglePlay = async () => {
    const next = !playing;
    setPlaying(next);
    try {
      await (next ? resumeSim() : pauseSim());
    } catch (err) {
      console.error('[sim] play/pause failed', err);
      setPlaying(!next);
    }
  };

  const changeSpeed = async (value: string) => {
    setSpeedValue(value);
    try {
      await setSpeed(parseFloat(value));
    } catch (err) {
      console.error('[sim] speed change failed', err);
    }
  };

  return (
    <div className="stack">
      <div className="row">
        <button type="button" className="btn" onClick={() => void togglePlay()}>
          <Icon name={playing ? 'pause' : 'play'} size={12} />
          {playing ? 'Pause' : 'Play'}
        </button>
        <button type="button" className="btn" onClick={() => void stepSim()} disabled={playing}>
          <Icon name="step" size={12} />
          Step
        </button>
        <button type="button" className="btn" onClick={() => void resetSim()}>
          <Icon name="reset" size={12} />
          Reset
        </button>
        <select
          className="select"
          style={{ width: 'auto' }}
          value={speed}
          onChange={(e) => void changeSpeed(e.target.value)}
          aria-label="Simulation speed"
        >
          <option value="0.5">0.5× slow</option>
          <option value="1.0">1.0× normal</option>
          <option value="2.0">2.0× fast</option>
        </select>
        <button
          type="button"
          className="btn btn--sm"
          style={{ marginLeft: 'auto' }}
          onClick={() => setClearedAt(events.length)}
        >
          Clear
        </button>
      </div>

      <div className="log" ref={logRef}>
        {visible.length === 0 ? (
          <div className="empty">No events since last clear.</div>
        ) : (
          visible.map((event, idx) => (
            <div
              key={`${clearedAt + idx}-${event}`}
              className="log__line"
              data-part={partOf(event)}
              data-alert={/failed|interrupted|lost|RECOVERY_FAILED|rejected/i.test(event)}
            >
              {event}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
