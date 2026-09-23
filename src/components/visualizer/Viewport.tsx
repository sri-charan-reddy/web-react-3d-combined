/**
 * The viewport — the subject of this screen, so it gets the room.
 *
 * Three views over the same live simulation. Only the active one mounts, so
 * inactive canvases burn no animation frames and the camera feed stops polling
 * when it isn't on screen.
 */
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/common/Icon';
import { ArenaCanvas } from './ArenaCanvas';
/* three.js is only fetched when the operator actually opens the 3D tab. */
const OrbitCanvas = lazy(() => import('./OrbitCanvas'));
import { CameraFeed } from './CameraFeed';
import { SensorCanvas } from './SensorCanvas';
import { useTelemetry, shallowEqual } from '@/hooks/useTelemetry';
import { deriveStatus } from '@/lib/derive';
import type { ViewMode } from '@/state/WorkspaceContext';
import { useWorkspace } from '@/state/WorkspaceContext';
import type { IconName } from '@/components/common/Icon';
import type { TelemetryFrame } from '@/types/telemetry';

const TABS: { id: ViewMode; icon: IconName; label: string }[] = [
  { id: 'arena', icon: 'globe', label: 'Arena' },
  { id: 'orbit', icon: 'orbit', label: 'Orbit 3D' },
  { id: 'sensor', icon: 'crosshair', label: 'Boresight' },
  { id: 'camera', icon: 'camera', label: 'Camera' },
];

const LEGEND = [
  { color: 'var(--cyan)', label: 'Ground station' },
  { color: 'var(--amber)', label: 'Target beacon' },
  { color: 'var(--text-muted)', label: 'Remote terminals' },
  { color: 'var(--teal)', label: 'FSOC beam' },
  { color: 'var(--violet)', label: 'Kalman predict' },
];

interface HudSlice {
  targetName: string;
  fsocActive: boolean;
  opticalAligned: boolean;
  beaconDetected: boolean;
  errorPx: number | null;
  camDeg: number;
}

const selectHud = (frame: TelemetryFrame | null): HudSlice => {
  const s = deriveStatus(frame);
  return {
    targetName: s.targetName,
    fsocActive: s.fsocActive,
    opticalAligned: s.opticalAligned,
    beaconDetected: s.beaconDetected,
    errorPx: frame?.telemetry.pointing_error_px ?? null,
    camDeg: frame?.telemetry.camera_orientation_deg ?? 0,
  };
};

interface ViewportProps {
  trailEpoch: number;
  onSelectTerminal: (id: string) => void;
}

export function Viewport({ trailEpoch, onSelectTerminal }: ViewportProps) {
  const { view, setView } = useWorkspace();
  const hud = useTelemetry(useCallback(selectHud, []), shallowEqual);
  // The arena publishes its zoom controls up so the toolbar can drive them.
  const controlsRef = useRef<{ zoomIn: () => void; zoomOut: () => void; fit: () => void } | null>(null);
  const zoomLabelRef = useRef<HTMLSpanElement>(null);
  const [expanded, setExpanded] = useState(false);
  const orbitRef = useRef<{ fit: () => void } | null>(null);
  const setOrbit = useCallback((h: { fit: () => void }) => {
    orbitRef.current = h;
  }, []);

  const setControls = useCallback(
    (c: { zoomIn: () => void; zoomOut: () => void; fit: () => void; zoomPercent: number }) => {
      controlsRef.current = c;
      if (zoomLabelRef.current) zoomLabelRef.current.textContent = `${c.zoomPercent}%`;
    },
    [],
  );

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpanded(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded]);

  const isArena = view === 'arena';
  const isOrbit = view === 'orbit';

  return (
    <>
      {expanded && (
        <div className="viewport-scrim" onClick={() => setExpanded(false)} aria-hidden="true" />
      )}
      <section className={`card viewport${expanded ? ' viewport--expanded' : ''}`}>
      <div className="viewport__bar">
        <div className="segmented" role="tablist" aria-label="Viewport">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              className="segmented__item"
              aria-selected={view === tab.id}
              onClick={() => setView(tab.id)}
            >
              <Icon name={tab.icon} size={13} />
              {tab.label}
            </button>
          ))}
        </div>

        <div className="viewport__tools">
          {isOrbit && (
            <>
              <span className="label" style={{ fontSize: 'var(--fs-micro)' }}>
                Drag to orbit · scroll to zoom · right-drag to pan
              </span>
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => orbitRef.current?.fit()}
                title="Reset the camera"
              >
                <Icon name="fit" size={13} />
                Reset view
              </button>
            </>
          )}
          {isArena && (
            <>
              <span className="label" style={{ fontSize: 'var(--fs-micro)' }}>
                Scroll to zoom · drag to pan
              </span>
              <div className="zoom">
                <button
                  type="button"
                  className="btn btn--icon btn--sm"
                  onClick={() => controlsRef.current?.zoomOut()}
                  aria-label="Zoom out"
                  title="Zoom out"
                >
                  <Icon name="zoomOut" size={13} />
                </button>
                <span className="zoom__level" ref={zoomLabelRef}>
                  100%
                </span>
                <button
                  type="button"
                  className="btn btn--icon btn--sm"
                  onClick={() => controlsRef.current?.zoomIn()}
                  aria-label="Zoom in"
                  title="Zoom in"
                >
                  <Icon name="zoomIn" size={13} />
                </button>
              </div>
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => controlsRef.current?.fit()}
                title="Frame all terminals (or double-click the map)"
              >
                <Icon name="fit" size={13} />
                Fit
              </button>
            </>
          )}

          <button
            type="button"
            className="btn btn--icon btn--sm"
            onClick={() => setExpanded((v) => !v)}
            title={expanded ? 'Exit full screen (Esc)' : 'Expand to full screen'}
            aria-label={expanded ? 'Exit full screen' : 'Expand to full screen'}
          >
            <Icon name={expanded ? 'collapse' : 'expand'} size={13} />
          </button>
        </div>
      </div>

      <div className="canvas-stage">
        {view === 'arena' && (
          <ArenaCanvas
            trailEpoch={trailEpoch}
            onSelectTerminal={onSelectTerminal}
            onControls={setControls}
          />
        )}
        {view === 'orbit' && (
          <Suspense fallback={<div className="empty">Loading 3D renderer…</div>}>
            <OrbitCanvas onSelectTerminal={onSelectTerminal} onReady={setOrbit} />
          </Suspense>
        )}
        {view === 'sensor' && <SensorCanvas />}
        {view === 'camera' && <CameraFeed />}

        <div className="hud hud--tl">
          <div className="hud-card">
            <span className="hud-card__k">Target</span>
            <span className="hud-card__v text-info">{hud.targetName}</span>
          </div>
          <div className="hud-card">
            <span className="hud-card__k">Link</span>
            <span
              className={`hud-card__v text-${hud.opticalAligned ? 'ok' : hud.beaconDetected ? 'warn' : 'fault'}`}
            >
              {hud.opticalAligned ? 'Aligned' : hud.beaconDetected ? 'Tracking' : 'Lost'}
            </span>
          </div>
        </div>

        <div className="hud hud--br">
          <div className="hud-card readout">
            <span className="hud-card__k">Az</span>
            <span className="hud-card__v">{(((hud.camDeg % 360) + 360) % 360).toFixed(1)}°</span>
            <span className="hud-card__k" style={{ marginLeft: 8 }}>
              Err
            </span>
            <span className="hud-card__v">
              {hud.errorPx !== null ? `${hud.errorPx.toFixed(1)}px` : '—'}
            </span>
          </div>
        </div>

        {isOrbit && (
          <div className="hud hud--bl">
            <div className="hud-card">
              <span className="hud-card__k">Note</span>
              <span className="hud-card__v" style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>
                Altitude is illustrative — the simulator models a 2D plane
              </span>
            </div>
          </div>
        )}

        {isArena && (
          <div className="hud hud--bl">
            <div className="legend">
              {LEGEND.map((l) => (
                <span className="legend__item" key={l.label}>
                  <span className="legend__swatch" style={{ background: l.color }} />
                  {l.label}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
      </section>
    </>
  );
}
