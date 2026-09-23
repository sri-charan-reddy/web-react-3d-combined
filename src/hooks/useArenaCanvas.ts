/**
 * Arena canvas: sizing, camera interaction, and the render loop.
 *
 * All of it stays outside React's render path. Pointer moves and wheel events
 * mutate the camera object directly and the next animation frame picks the
 * change up — so dragging stays smooth regardless of what the 30 Hz telemetry
 * feed is doing. The only things promoted to React state are the two values
 * the UI actually displays: the zoom percentage and the hovered node.
 */
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { baseScale, boundsOf, Camera } from '@/render/camera';
import { hitTest, lastHits, renderArena, type NodeHit } from '@/render/arena';
import { geometry } from '@/render/palette';
import { TrailStore } from '@/render/trails';
import { getFrame } from '@/state/telemetryStore';

const WHEEL_STEP = 1.0015;
const BUTTON_STEP = 1.25;
/** Pointer travel (px) above which a press counts as a drag, not a click. */
const DRAG_THRESHOLD = 4;

export interface ArenaControls {
  zoomPercent: number;
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  hovered: HoverInfo | null;
}

export interface HoverInfo {
  id: string;
  screenX: number;
  screenY: number;
}

export function useArenaCanvas(
  canvasRef: RefObject<HTMLCanvasElement | null>,
  containerRef: RefObject<HTMLDivElement | null>,
  active: boolean,
  trailEpoch: number,
  onSelectTerminal?: (id: string) => void,
): ArenaControls {
  const cameraRef = useRef(new Camera());
  const trailsRef = useRef(new TrailStore());
  const hoveredIdRef = useRef<string | null>(null);
  const dprRef = useRef(1);
  // Set once the first frame has arrived, so we auto-frame the sector.
  const framedRef = useRef(false);

  const [zoomPercent, setZoomPercent] = useState(100);
  const [hovered, setHovered] = useState<HoverInfo | null>(null);

  const selectRef = useRef(onSelectTerminal);
  selectRef.current = onSelectTerminal;

  useEffect(() => {
    trailsRef.current.clear();
    framedRef.current = false;
  }, [trailEpoch]);

  /** Frame every terminal currently on the field. */
  const fit = useCallback(() => {
    const cam = cameraRef.current;
    const frame = getFrame();
    const points: { x: number; y: number }[] = [
      { x: 0, y: 0 },
      { x: geometry.width, y: geometry.height },
    ];
    if (frame) {
      points.length = 0;
      points.push({ x: frame.arena.terminal_a.x, y: frame.arena.terminal_a.y });
      points.push({
        x: frame.arena.terminal_b.beacon_x ?? frame.arena.terminal_b.x,
        y: frame.arena.terminal_b.beacon_y ?? frame.arena.terminal_b.y,
      });
      for (const t of frame.terminals) {
        if (t.position) points.push({ x: t.position[0], y: t.position[1] });
      }
    }
    const b = boundsOf(points, 90);
    if (b) cam.fit(b);
    setZoomPercent(cam.percent(geometry.width, geometry.height));
  }, []);

  const zoomIn = useCallback(() => {
    const cam = cameraRef.current;
    cam.zoomByStep(BUTTON_STEP);
    cam.clampToWorld(geometry.width, geometry.height);
    setZoomPercent(cam.percent(geometry.width, geometry.height));
  }, []);

  const zoomOut = useCallback(() => {
    const cam = cameraRef.current;
    cam.zoomByStep(1 / BUTTON_STEP);
    cam.clampToWorld(geometry.width, geometry.height);
    setZoomPercent(cam.percent(geometry.width, geometry.height));
  }, []);

  // --- Sizing: track the container and keep the backing store at DPR ------
  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resize = () => {
      const rect = container.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      dprRef.current = dpr;
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;

      const cam = cameraRef.current;
      const hadView = cam.viewW > 0;
      cam.setViewport(rect.width, rect.height);
      if (!hadView) {
        // First measure: start at fit-to-world rather than an arbitrary 1:1.
        cam.scale = baseScale(rect.width, rect.height, geometry.width, geometry.height);
        cam.offsetX = (rect.width - geometry.width * cam.scale) / 2;
        cam.offsetY = (rect.height - geometry.height * cam.scale) / 2;
      }
      setZoomPercent(cam.percent(geometry.width, geometry.height));
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(container);
    return () => ro.disconnect();
  }, [active, containerRef, canvasRef]);

  // --- Interaction -------------------------------------------------------
  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const cam = cameraRef.current;

    let dragging = false;
    let moved = 0;
    let lastX = 0;
    let lastY = 0;
    let pointerId: number | null = null;

    const localPoint = (e: PointerEvent | WheelEvent) => {
      const r = canvas.getBoundingClientRect();
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const p = localPoint(e);
      // Exponential in deltaY so trackpads and mouse wheels both feel right.
      cam.zoomAt(p.x, p.y, Math.pow(WHEEL_STEP, -e.deltaY));
      cam.clampToWorld(geometry.width, geometry.height);
      setZoomPercent(cam.percent(geometry.width, geometry.height));
    };

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      dragging = true;
      moved = 0;
      pointerId = e.pointerId;
      lastX = e.clientX;
      lastY = e.clientY;
      canvas.setPointerCapture(e.pointerId);
      canvas.dataset.panning = 'true';
    };

    const onPointerMove = (e: PointerEvent) => {
      if (dragging) {
        const dx = e.clientX - lastX;
        const dy = e.clientY - lastY;
        moved += Math.abs(dx) + Math.abs(dy);
        lastX = e.clientX;
        lastY = e.clientY;
        cam.panBy(dx, dy);
        cam.clampToWorld(geometry.width, geometry.height);
        return;
      }
      // Hover hit-test against the node positions the last render recorded.
      const p = localPoint(e);
      const hit = hitTest(p.x, p.y);
      const id = hit && hit.id !== '__station__' ? hit.id : null;
      if (id !== hoveredIdRef.current) {
        hoveredIdRef.current = id;
        setHovered(id && hit ? { id, screenX: hit.screenX, screenY: hit.screenY } : null);
      } else if (id && hit) {
        // Node is moving under a stationary cursor — keep the tooltip attached.
        setHovered({ id, screenX: hit.screenX, screenY: hit.screenY });
      }
    };

    const endDrag = (e: PointerEvent) => {
      if (!dragging) return;
      dragging = false;
      canvas.dataset.panning = 'false';
      if (pointerId !== null && canvas.hasPointerCapture(pointerId)) {
        canvas.releasePointerCapture(pointerId);
      }
      pointerId = null;
      // A press that barely moved is a click: select the node under it.
      if (moved < DRAG_THRESHOLD) {
        const p = localPoint(e);
        const hit = hitTest(p.x, p.y);
        if (hit && hit.id !== '__station__' && !hit.isTarget) selectRef.current?.(hit.id);
      }
    };

    const onPointerLeave = () => {
      hoveredIdRef.current = null;
      setHovered(null);
    };

    const onDoubleClick = () => fit();

    canvas.addEventListener('wheel', onWheel, { passive: false });
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', endDrag);
    canvas.addEventListener('pointercancel', endDrag);
    canvas.addEventListener('pointerleave', onPointerLeave);
    canvas.addEventListener('dblclick', onDoubleClick);

    return () => {
      canvas.removeEventListener('wheel', onWheel);
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', endDrag);
      canvas.removeEventListener('pointercancel', endDrag);
      canvas.removeEventListener('pointerleave', onPointerLeave);
      canvas.removeEventListener('dblclick', onDoubleClick);
    };
  }, [active, canvasRef, fit]);

  // --- Render loop -------------------------------------------------------
  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let raf = 0;
    const tick = () => {
      const frame = getFrame();
      if (frame && cameraRef.current.viewW > 0) {
        if (!framedRef.current) {
          framedRef.current = true;
          fit();
        }
        renderArena(
          ctx,
          frame,
          {
            camera: cameraRef.current,
            trails: trailsRef.current,
            hoveredId: hoveredIdRef.current,
            dpr: dprRef.current,
          },
          performance.now() / 1000,
        );
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      lastHits.length = 0;
    };
  }, [active, canvasRef, fit]);

  return { zoomPercent, zoomIn, zoomOut, fit, hovered };
}

export type { NodeHit };
