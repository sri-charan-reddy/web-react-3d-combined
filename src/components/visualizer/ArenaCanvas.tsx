/**
 * Arena canvas host.
 *
 * Owns only the elements; camera, interaction and the render loop live in
 * useArenaCanvas so none of it passes through React's render path.
 */
import { useEffect, useRef } from 'react';
import { useArenaCanvas } from '@/hooks/useArenaCanvas';
import { useTelemetry } from '@/hooks/useTelemetry';
import type { TelemetryFrame, Terminal } from '@/types/telemetry';

interface ArenaCanvasProps {
  trailEpoch: number;
  onSelectTerminal: (id: string) => void;
  onControls: (c: {
    zoomIn: () => void;
    zoomOut: () => void;
    fit: () => void;
    zoomPercent: number;
  }) => void;
}

const selectTerminals = (f: TelemetryFrame | null): Terminal[] => f?.terminals ?? [];
const byIdentity = (a: Terminal[], b: Terminal[]) =>
  a.length === b.length && a.every((t, i) => t.id === b[i].id);

export function ArenaCanvas({ trailEpoch, onSelectTerminal, onControls }: ArenaCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const terminals = useTelemetry(selectTerminals, byIdentity);

  const controls = useArenaCanvas(canvasRef, containerRef, true, trailEpoch, onSelectTerminal);

  // Publish controls upward so the toolbar can drive zoom.
  useEffect(() => {
    onControls({
      zoomIn: controls.zoomIn,
      zoomOut: controls.zoomOut,
      fit: controls.fit,
      zoomPercent: controls.zoomPercent,
    });
  }, [onControls, controls.zoomIn, controls.zoomOut, controls.fit, controls.zoomPercent]);

  const hoveredTerminal = controls.hovered
    ? terminals.find((t) => t.id === controls.hovered?.id)
    : undefined;

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      <canvas ref={canvasRef} data-panning="false" />

      {controls.hovered && hoveredTerminal && (
        <div
          className="node-tip"
          style={{ left: controls.hovered.screenX, top: controls.hovered.screenY }}
        >
          <div className="node-tip__name">{hoveredTerminal.name}</div>
          <div className="node-tip__row">
            <span>RF</span>
            <b>{hoveredTerminal.rf_status}</b>
          </div>
          <div className="node-tip__row">
            <span>Optical</span>
            <b>{hoveredTerminal.status}</b>
          </div>
          <div className="node-tip__row">
            <span>Speed</span>
            <b>{hoveredTerminal.speed.toFixed(1)} px/s</b>
          </div>
          <div className="node-tip__row">
            <span>Heading</span>
            <b>{hoveredTerminal.heading.toFixed(0)}°</b>
          </div>
          {!hoveredTerminal.is_target && <div className="node-tip__hint">Click to retarget</div>}
        </div>
      )}
    </div>
  );
}
