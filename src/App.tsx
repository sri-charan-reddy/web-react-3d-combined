/**
 * Dashboard composition root.
 *
 * Layout is header / (viewport + rail) / dock. The viewport is the subject of
 * the screen and gets the space; the rail carries what must stay visible; the
 * dock holds detail one tab at a time. Every panel pulls its own slice from the
 * telemetry store, so nothing is threaded through props here.
 */
import { useCallback, useState } from 'react';
import { ConfigDrawer } from '@/components/config/ConfigDrawer';
import { Dock } from '@/components/dock/Dock';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { Header } from '@/components/layout/Header';
import { LinkPanel } from '@/components/rail/LinkPanel';
import { PipelinePanel } from '@/components/rail/PipelinePanel';
import { TelemetryPanel } from '@/components/rail/TelemetryPanel';
import { Viewport } from '@/components/visualizer/Viewport';
import { updateTerminalsConfig } from '@/api/endpoints';
import { useTelemetryStream } from '@/hooks/useTelemetryStream';
import { getFrame } from '@/state/telemetryStore';
import { WorkspaceProvider } from '@/state/WorkspaceContext';

function Dashboard() {
  useTelemetryStream();

  const [configOpen, setConfigOpen] = useState(false);
  // Reconfiguring the sector invalidates every motion trail; bumping this epoch
  // tells the arena to drop its history instead of drawing a jump.
  const [trailEpoch, setTrailEpoch] = useState(0);
  const resetTrails = useCallback(() => setTrailEpoch((e) => e + 1), []);

  /** Click a terminal on the map to make it the tracking target. */
  const selectTerminal = useCallback(
    (id: string) => {
      const frame = getFrame();
      if (!frame || id === frame.target_terminal) return;
      updateTerminalsConfig(frame.num_terminals, id)
        .then(resetTrails)
        .catch((err) => console.error('[retarget] failed', err));
    },
    [resetTrails],
  );

  return (
    <div className="app">
      <Header onOpenConfig={() => setConfigOpen(true)} />

      <div className="body">
        <div className="stage">
          <Viewport trailEpoch={trailEpoch} onSelectTerminal={selectTerminal} />
          <Dock />
        </div>

        <aside className="rail">
          <LinkPanel />
          <PipelinePanel />
          <TelemetryPanel />
        </aside>
      </div>

      <ConfigDrawer
        open={configOpen}
        onClose={() => setConfigOpen(false)}
        onApplied={resetTrails}
      />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <WorkspaceProvider>
        <Dashboard />
      </WorkspaceProvider>
    </ErrorBoundary>
  );
}
