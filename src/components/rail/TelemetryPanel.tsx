/** Engineering telemetry — the numeric readouts, always visible. */
import { useCallback } from 'react';
import { Icon } from '@/components/common/Icon';
import { shallowEqual, useTelemetry } from '@/hooks/useTelemetry';
import type { TelemetryFrame } from '@/types/telemetry';

interface Metrics {
  radial: string;
  angular: string;
  azimuth: string;
  confidence: string;
  missCount: number;
  covTrace: string;
  speed: string;
  heading: string;
  rssi: string;
  centroid: string;
}

const selectMetrics = (frame: TelemetryFrame | null): Metrics => {
  const t = frame?.telemetry;
  if (!t) {
    return {
      radial: '—', angular: '—', azimuth: '—', confidence: '—', missCount: 0,
      covTrace: '—', speed: '—', heading: '—', rssi: '—', centroid: '—',
    };
  }
  const speed = t.terminal_velocity ? Math.hypot(t.terminal_velocity[0], t.terminal_velocity[1]) : 0;
  // Camera azimuth free-runs past 360°; normalise so it reads as a bearing.
  const az = ((t.camera_orientation_deg % 360) + 360) % 360;

  return {
    radial: t.pointing_error_px !== null ? `${t.pointing_error_px.toFixed(1)}` : '—',
    angular: t.pointing_error_deg !== null ? `${t.pointing_error_deg.toFixed(3)}°` : '—',
    azimuth: `${az.toFixed(1)}°`,
    confidence: `${Math.round((t.tracking_confidence ?? 1) * 100)}%`,
    missCount: t.miss_count ?? 0,
    covTrace: (frame.arena.kalman_cov_trace ?? 0).toFixed(1),
    speed: `${speed.toFixed(1)}`,
    heading: `${(t.terminal_heading ?? 0).toFixed(0)}°`,
    rssi: t.rf_rssi !== null ? `${t.rf_rssi.toFixed(1)}` : '—',
    centroid: t.beacon_position
      ? `${t.beacon_position[0].toFixed(0)}, ${t.beacon_position[1].toFixed(0)}`
      : '—',
  };
};

function Metric({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return (
    <div className="metric">
      <div className="metric__k">{k}</div>
      <div className="metric__v">{v}</div>
      {sub && <div className="metric__sub">{sub}</div>}
    </div>
  );
}

export function TelemetryPanel() {
  const m = useTelemetry(useCallback(selectMetrics, []), shallowEqual);

  return (
    <section className="card panel">
      <div className="panel__head">
        <Icon name="gauge" size={14} className="text-info" />
        <h3 className="panel__title">Telemetry</h3>
      </div>
      <div className="metrics">
        <Metric k="Radial error" v={`${m.radial} px`} sub="tol 15.0 px" />
        <Metric k="Angular error" v={m.angular} sub="boresight offset" />
        <Metric k="Camera azimuth" v={m.azimuth} sub="FOV 35.0°" />
        <Metric k="Kalman conf." v={m.confidence} sub={`${m.missCount} missed`} />
        <Metric k="Cov. trace" v={m.covTrace} sub="gate 80.0 px" />
        <Metric k="RF RSSI" v={`${m.rssi} dBm`} sub="omni 360°" />
        <Metric k="Target speed" v={`${m.speed} px/s`} sub={`heading ${m.heading}`} />
        <Metric k="Centroid" v={m.centroid} sub="image px" />
      </div>
    </section>
  );
}
