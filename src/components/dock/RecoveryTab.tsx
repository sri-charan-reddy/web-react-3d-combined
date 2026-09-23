/**
 * Disturbance injection and scenario triggers.
 *
 * The operator's live controls: force a fault, watch the recovery ladder in the
 * rail respond. Toggles post a partial payload and adopt whatever the simulator
 * echoes back — "severe" switches on three others server-side, and mirroring
 * that locally would drift from the truth.
 */
import { useCallback } from 'react';
import { Icon } from '@/components/common/Icon';
import { setScenario } from '@/api/endpoints';
import { useDisturbance } from '@/hooks/useDisturbance';
import { shallowEqual, useTelemetry } from '@/hooks/useTelemetry';
import type { ScenarioId, TelemetryFrame } from '@/types/telemetry';

const SCENARIOS: { id: ScenarioId; n: string; title: string; detail: string }[] = [
  { id: 'normal', n: '01', title: 'Standard PAT', detail: 'Optical search & fine tracking' },
  { id: 'temporary-loss', n: '02', title: 'Cloud occlusion', detail: 'Predictive Kalman recovery' },
  { id: 'deep-loss', n: '03', title: 'Deep loss → RF', detail: 'Auxiliary RF & HMAC handshake' },
  { id: 'rogue-auth', n: '04', title: 'Rogue RF spoof', detail: 'Cryptographic rejection' },
];

interface Slice {
  scenario: ScenarioId;
  mechanism: string;
  turbulence: string;
  cloud: boolean;
  vibration: number;
}

const selectRecovery = (f: TelemetryFrame | null): Slice => ({
  scenario: f?.arena.scenario ?? 'normal',
  mechanism: f?.telemetry.recovery_mechanism || 'NONE',
  turbulence: f?.arena.turbulence ?? 'OFF',
  cloud: f?.arena.cloud_occlusion ?? false,
  vibration: f?.arena.vibration ?? 0,
});

function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="field">
      <span className="label">{label}</span>
      <div className="segmented">
        <button
          type="button"
          className="segmented__item"
          aria-pressed={!value}
          onClick={() => onChange(false)}
        >
          Off
        </button>
        <button
          type="button"
          className="segmented__item"
          aria-pressed={value}
          onClick={() => onChange(true)}
        >
          On
        </button>
      </div>
    </div>
  );
}

export function RecoveryTab() {
  const s = useTelemetry(useCallback(selectRecovery, []), shallowEqual);
  const d = useDisturbance();

  const trigger = async (id: ScenarioId) => {
    try {
      await setScenario(id);
    } catch (err) {
      console.error('[scenario] trigger failed', err);
    }
  };

  return (
    <div className="grid-2">
      <div className="stack">
        <div className="row">
          <span className="label">Disturbance injection</span>
          {s.mechanism !== 'NONE' && (
            <span
              className={`chip ${s.mechanism === 'FAILED' ? 'chip--fault' : 'chip--warn'}`}
              style={{ marginLeft: 'auto' }}
            >
              <Icon name={s.mechanism === 'FAILED' ? 'cross' : 'recovery'} size={11} />
              {s.mechanism.replace(/_/g, ' ')}
            </span>
          )}
        </div>

        <div className="row" style={{ gap: 'var(--s4)', alignItems: 'flex-start' }}>
          <Toggle label="Cloud" value={d.toggles.cloud} onChange={(v) => void d.setCloud(v)} />
          <Toggle
            label="Turbulence"
            value={d.toggles.turbulence}
            onChange={(v) => void d.setTurbulence(v)}
          />
          <Toggle
            label="Vibration"
            value={d.toggles.vibration}
            onChange={(v) => void d.setVibration(v)}
          />
          <Toggle label="Severe" value={d.toggles.severe} onChange={(v) => void d.setSevere(v)} />
        </div>

        <div className="kv">
          <div className="kv__row">
            <span className="kv__k">Turbulence level</span>
            <span className="kv__v readout">{s.turbulence}</span>
          </div>
          <div className="kv__row">
            <span className="kv__k">Vibration amplitude</span>
            <span className="kv__v readout">{s.vibration.toFixed(1)} px</span>
          </div>
          <div className="kv__row">
            <span className="kv__k">Cloud occlusion</span>
            <span className={`kv__v text-${s.cloud ? 'warn' : 'muted'}`}>
              {s.cloud ? 'Active' : 'Clear'}
            </span>
          </div>
        </div>
      </div>

      <div className="stack">
        <span className="label">Scenario demonstrations</span>
        <div className="scenarios">
          {SCENARIOS.map((sc) => (
            <button
              key={sc.id}
              type="button"
              className="scenario"
              aria-pressed={s.scenario === sc.id}
              onClick={() => void trigger(sc.id)}
            >
              <span className="scenario__n">Scenario {sc.n}</span>
              <span className="scenario__t">{sc.title}</span>
              <span className="scenario__d">{sc.detail}</span>
            </button>
          ))}
        </div>
        <span className="field__hint">
          All remote terminals keep moving during recovery — the ladder in the rail tracks progress.
        </span>
      </div>
    </div>
  );
}
