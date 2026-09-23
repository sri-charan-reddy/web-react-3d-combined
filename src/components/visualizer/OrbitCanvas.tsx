/**
 * Orbital 3D view host.
 *
 * Mirrors the 2D arena's arrangement: the scene lives outside React and reads
 * the telemetry store directly from a requestAnimationFrame loop, so orbiting
 * stays smooth regardless of the 30 Hz feed. WebGL context is created on mount
 * and disposed on unmount — the tab is only mounted while it is selected, so an
 * unused 3D view costs nothing.
 */
import { useEffect, useRef, useState } from 'react';
import { createScene3D, type Scene3DHandle } from '@/render/scene3d';
import { getFrame } from '@/state/telemetryStore';

interface OrbitCanvasProps {
  onSelectTerminal: (id: string) => void;
  onReady: (handle: { fit: () => void }) => void;
}

function OrbitCanvas({ onSelectTerminal, onReady }: OrbitCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<Scene3DHandle | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const selectRef = useRef(onSelectTerminal);
  selectRef.current = onSelectTerminal;
  const readyRef = useRef(onReady);
  readyRef.current = onReady;

  useEffect(() => {
    const container = containerRef.current;
    const labels = labelsRef.current;
    if (!container || !labels) return;

    let scene: Scene3DHandle;
    try {
      scene = createScene3D(container, labels);
    } catch (err) {
      // A machine without WebGL should get an explanation, not a blank panel.
      console.error('[orbit] scene init failed', err);
      setFailed(err instanceof Error ? err.message : 'WebGL unavailable');
      return;
    }
    sceneRef.current = scene;
    readyRef.current({ fit: scene.fit });

    const ro = new ResizeObserver(() => scene.resize());
    ro.observe(container);

    let raf = 0;
    const tick = () => {
      const frame = getFrame();
      if (frame) scene.update(frame, performance.now() / 1000);
      scene.render();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    // Hover + click. A drag that ends far from where it started is an orbit,
    // not a selection.
    let downX = 0;
    let downY = 0;
    const el = container;

    const onMove = (e: PointerEvent) => {
      const id = scene.pick(e.clientX, e.clientY);
      el.style.cursor = id ? 'pointer' : 'grab';
    };
    const onDown = (e: PointerEvent) => {
      downX = e.clientX;
      downY = e.clientY;
    };
    const onUp = (e: PointerEvent) => {
      if (Math.abs(e.clientX - downX) + Math.abs(e.clientY - downY) > 5) return;
      const id = scene.pick(e.clientX, e.clientY);
      if (id) selectRef.current(id);
    };

    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerdown', onDown);
    el.addEventListener('pointerup', onUp);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerdown', onDown);
      el.removeEventListener('pointerup', onUp);
      scene.dispose();
      sceneRef.current = null;
    };
  }, []);

  if (failed) {
    return (
      <div className="empty" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
        <div>
          <p style={{ margin: 0, color: 'var(--warn)' }}>3D view unavailable</p>
          <p style={{ margin: '6px 0 0' }}>{failed}</p>
          <p style={{ margin: '6px 0 0' }}>Use the Arena tab for the 2D plan view.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <div ref={containerRef} style={{ position: 'absolute', inset: 0, cursor: 'grab' }} />
      <div ref={labelsRef} />
    </div>
  );
}

// Default export so the view can be code-split with React.lazy — three.js is
// ~165 kB gzipped and most sessions never open this tab.
export default OrbitCanvas;
