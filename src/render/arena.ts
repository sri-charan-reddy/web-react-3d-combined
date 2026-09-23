/**
 * 2D kinematic arena renderer.
 *
 * A pure function of (context, frame, view-state, clock) — no DOM lookups, no
 * React. Driven from a requestAnimationFrame loop so the 30 Hz telemetry feed
 * moves pixels without ever re-rendering a component.
 *
 * The view stays a true plan view. A tilted/perspective projection would look
 * showier but would distort exactly the thing this view exists to show — the
 * camera's azimuth and FOV cone against real bearings. Depth instead comes
 * from lighting: a layered starfield, range haze, bloom on emissive elements
 * and cast shadows under the nodes.
 *
 * Draw order is back-to-front; layers are numbered.
 */
import { Camera } from './camera';
import { fonts, geometry, palette } from './palette';
import { TARGET_TRAIL, type Point, type TrailStore } from './trails';
import type { TelemetryFrame, Terminal } from '@/types/telemetry';

export interface ArenaView {
  camera: Camera;
  trails: TrailStore;
  /** Terminal id under the pointer, if any. */
  hoveredId: string | null;
  /** Device pixel ratio of the backing store. */
  dpr: number;
}

/** Screen-space position and radius of a node, for hit-testing and tooltips. */
export interface NodeHit {
  id: string;
  worldX: number;
  worldY: number;
  screenX: number;
  screenY: number;
  radius: number;
  isTarget: boolean;
}

/** Populated on every render so the interaction layer can hit-test cheaply. */
export const lastHits: NodeHit[] = [];

/* ------------------------------------------------------------------------ */
/* Background                                                               */
/* ------------------------------------------------------------------------ */

/** Deterministic star field — same layout every frame, parallaxed by the camera. */
const STARS = Array.from({ length: 220 }, (_, i) => {
  // Cheap hash so the field is stable across reloads without storing a table.
  const a = Math.sin(i * 12.9898) * 43758.5453;
  const b = Math.sin(i * 78.233) * 21982.331;
  const c = Math.sin(i * 39.425) * 11233.77;
  return {
    x: (a - Math.floor(a)) * geometry.width,
    y: (b - Math.floor(b)) * geometry.height,
    r: 0.4 + (c - Math.floor(c)) * 1.1,
    /** Depth 0..1 — nearer stars are brighter and parallax further. */
    depth: 0.25 + (c - Math.floor(c)) * 0.75,
  };
});

function drawStarfield(ctx: CanvasRenderingContext2D, cam: Camera, nowSec: number): void {
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  for (let i = 0; i < STARS.length; i++) {
    const s = STARS[i];
    // Parallax: distant stars move less than the world.
    const p = 0.35 + s.depth * 0.5;
    const x = s.x * cam.scale * p + cam.offsetX * p;
    const y = s.y * cam.scale * p + cam.offsetY * p;
    if (x < -20 || y < -20 || x > cam.viewW + 20 || y > cam.viewH + 20) continue;
    const twinkle = 0.6 + 0.4 * Math.sin(nowSec * 0.7 + i);
    ctx.globalAlpha = 0.10 + s.depth * 0.35 * twinkle;
    ctx.fillStyle = i % 7 === 0 ? palette.cyanBright : '#ffffff';
    ctx.beginPath();
    ctx.arc(x, y, s.r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/** Grid that subdivides as you zoom in, so it never turns into a grey wash. */
function drawGrid(ctx: CanvasRenderingContext2D, cam: Camera): void {
  const w = geometry.width;
  const h = geometry.height;

  // Pick a spacing that stays 30-120 screen px regardless of zoom.
  let step = geometry.gridSize;
  while (step * cam.scale > 120) step /= 2;
  while (step * cam.scale < 30) step *= 2;

  ctx.save();
  ctx.lineWidth = 1 / cam.scale;

  for (let i = 0, x = 0; x <= w; x += step, i++) {
    // Every 4th line is a major division.
    ctx.strokeStyle = i % 4 === 0 ? 'rgba(148,176,220,0.09)' : 'rgba(148,176,220,0.035)';
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let i = 0, y = 0; y <= h; y += step, i++) {
    ctx.strokeStyle = i % 4 === 0 ? 'rgba(148,176,220,0.09)' : 'rgba(148,176,220,0.035)';
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // World boundary.
  ctx.strokeStyle = 'rgba(148,176,220,0.16)';
  ctx.lineWidth = 1.5 / cam.scale;
  ctx.strokeRect(0, 0, w, h);
  ctx.restore();
}

/** Range rings around the ground station, labelled in world units. */
function drawRangeRings(ctx: CanvasRenderingContext2D, cam: Camera, ax: number, ay: number): void {
  ctx.save();
  ctx.lineWidth = 1 / cam.scale;
  ctx.setLineDash([4 / cam.scale, 6 / cam.scale]);
  for (const r of [200, 400, 600]) {
    ctx.strokeStyle = 'rgba(56,189,248,0.10)';
    ctx.beginPath();
    ctx.arc(ax, ay, r, 0, Math.PI * 2);
    ctx.stroke();

    // Labels only once the ring is big enough on screen to be worth reading.
    if (r * cam.scale > 70) {
      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(126,141,166,0.55)';
      ctx.font = `${9 / cam.scale}px ${fonts.family}`;
      ctx.textAlign = 'left';
      ctx.fillText(`${r}`, ax + r + 4 / cam.scale, ay - 3 / cam.scale);
      ctx.setLineDash([4 / cam.scale, 6 / cam.scale]);
    }
  }
  ctx.restore();
}

/* ------------------------------------------------------------------------ */
/* Elements                                                                  */
/* ------------------------------------------------------------------------ */

function drawTrail(
  ctx: CanvasRenderingContext2D,
  cam: Camera,
  trail: readonly Point[],
  rgb: string,
  peak: number,
  width: number,
): void {
  if (trail.length < 2) return;
  ctx.save();
  ctx.lineCap = 'round';
  for (let i = 1; i < trail.length; i++) {
    const p0 = trail[i - 1];
    const p1 = trail[i];
    const t = i / trail.length;
    ctx.beginPath();
    ctx.moveTo(p0.x, p0.y);
    ctx.lineTo(p1.x, p1.y);
    ctx.strokeStyle = `rgba(${rgb}, ${t * peak})`;
    // Trail tapers toward the tail, which reads as direction of travel.
    ctx.lineWidth = ((0.3 + t * 0.7) * width) / cam.scale;
    ctx.stroke();
  }
  ctx.restore();
}

/** Camera field-of-view cone with a soft leading edge. */
function drawFovCone(
  ctx: CanvasRenderingContext2D,
  cam: Camera,
  ax: number,
  ay: number,
  angle: number,
  halfWidth: number,
): void {
  const R = geometry.coneRadius;
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  ctx.arc(ax, ay, R, angle - halfWidth, angle + halfWidth);
  ctx.closePath();

  const grad = ctx.createRadialGradient(ax, ay, 20, ax, ay, R);
  grad.addColorStop(0, 'rgba(56,189,248,0.20)');
  grad.addColorStop(0.55, 'rgba(56,189,248,0.06)');
  grad.addColorStop(1, 'rgba(56,189,248,0)');
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.strokeStyle = 'rgba(56,189,248,0.30)';
  ctx.lineWidth = 1 / cam.scale;
  ctx.stroke();

  // Boresight axis.
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  ctx.lineTo(ax + Math.cos(angle) * R, ay + Math.sin(angle) * R);
  ctx.strokeStyle = 'rgba(56,189,248,0.42)';
  ctx.setLineDash([5 / cam.scale, 5 / cam.scale]);
  ctx.lineWidth = 1 / cam.scale;
  ctx.stroke();
  ctx.restore();
}

/** Expanding RF rings from a transmitting terminal. */
function drawRfWaves(
  ctx: CanvasRenderingContext2D,
  cam: Camera,
  x: number,
  y: number,
  nowSec: number,
  index: number,
  isTarget: boolean,
  isDiscovered: boolean,
): void {
  ctx.save();
  for (let k = 0; k < 3; k++) {
    const prog = (nowSec * 1.2 + k / 3 + index * 0.17) % 1;
    const radius = 12 + prog * 46;
    const alpha = (1 - prog) * (isDiscovered ? 0.28 : isTarget ? 0.6 : 0.42);
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.strokeStyle = isDiscovered
      ? `rgba(45,212,191,${alpha})`
      : isTarget
        ? `rgba(56,189,248,${alpha})`
        : `rgba(126,141,166,${alpha})`;
    ctx.lineWidth = 1.3 / cam.scale;
    ctx.stroke();
  }
  ctx.restore();
}

/**
 * Optical beam with volumetric bloom and travelling data pulses.
 * The pulses are what make an established link read as *carrying traffic*
 * rather than just being a drawn line.
 */
function drawBeam(
  ctx: CanvasRenderingContext2D,
  cam: Camera,
  ax: number,
  ay: number,
  bx: number,
  by: number,
  nowSec: number,
): void {
  ctx.save();
  ctx.lineCap = 'round';

  // Outer glow, then core — cheaper and more controllable than shadowBlur.
  ctx.strokeStyle = 'rgba(45,212,191,0.13)';
  ctx.lineWidth = 9 / cam.scale;
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  ctx.lineTo(bx, by);
  ctx.stroke();

  ctx.strokeStyle = 'rgba(45,212,191,0.55)';
  ctx.lineWidth = 2.6 / cam.scale;
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  ctx.lineTo(bx, by);
  ctx.stroke();

  ctx.strokeStyle = 'rgba(230,255,250,0.95)';
  ctx.lineWidth = 0.9 / cam.scale;
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  ctx.lineTo(bx, by);
  ctx.stroke();

  // Data pulses travelling A -> B.
  const dx = bx - ax;
  const dy = by - ay;
  for (let i = 0; i < 3; i++) {
    const t = (nowSec * 0.55 + i / 3) % 1;
    const px = ax + dx * t;
    const py = ay + dy * t;
    const fade = Math.sin(t * Math.PI);
    ctx.beginPath();
    ctx.arc(px, py, 2.6 / cam.scale, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${0.85 * fade})`;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(px, py, 6 / cam.scale, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(45,212,191,${0.22 * fade})`;
    ctx.fill();
  }
  ctx.restore();
}

/** Soft elliptical shadow that lifts a node off the plane. */
function drawNodeShadow(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
  ctx.save();
  const g = ctx.createRadialGradient(x, y + r * 0.5, 0, x, y + r * 0.5, r * 1.9);
  g.addColorStop(0, 'rgba(0,0,0,0.55)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.ellipse(x, y + r * 0.45, r * 1.9, r * 1.0, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function isTargetTerminal(t: Terminal, targetId: string): boolean {
  return t.id === targetId || t.role === 'Target' || t.is_target;
}

/* ------------------------------------------------------------------------ */
/* Main                                                                      */
/* ------------------------------------------------------------------------ */

export function renderArena(
  ctx: CanvasRenderingContext2D,
  frame: TelemetryFrame,
  view: ArenaView,
  nowSec: number,
): void {
  const { camera: cam, trails, hoveredId } = view;
  const { arena, telemetry: telem, terminals } = frame;
  const targetId = frame.target_terminal;

  lastHits.length = 0;

  // --- Clear in device space -------------------------------------------
  ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
  ctx.clearRect(0, 0, cam.viewW, cam.viewH);
  ctx.fillStyle = palette.space;
  ctx.fillRect(0, 0, cam.viewW, cam.viewH);

  drawStarfield(ctx, cam, nowSec);

  // --- Enter world space ------------------------------------------------
  ctx.setTransform(
    cam.scale * view.dpr,
    0,
    0,
    cam.scale * view.dpr,
    cam.offsetX * view.dpr,
    cam.offsetY * view.dpr,
  );

  const termA = arena.terminal_a;
  const termB = arena.terminal_b;
  const ax = termA.x;
  const ay = termA.y;
  const bx = termB.beacon_x ?? termB.x;
  const by = termB.beacon_y ?? termB.y;
  const camAngle = (termA.orientation_deg * Math.PI) / 180;
  const fovHalf = ((termA.fov_deg / 2) * Math.PI) / 180;

  drawGrid(ctx, cam);
  drawRangeRings(ctx, cam, ax, ay);

  // 1. RF omni-broadcast radius.
  ctx.save();
  ctx.beginPath();
  ctx.arc(ax, ay, geometry.rfBroadcastRadius, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(45,212,191,0.10)';
  ctx.lineWidth = 1 / cam.scale;
  ctx.setLineDash([6 / cam.scale, 7 / cam.scale]);
  ctx.stroke();
  ctx.restore();

  // 2. Camera FOV cone + boresight.
  drawFovCone(ctx, cam, ax, ay, camAngle, fovHalf);

  // 3. Target flight trail.
  if (bx && by) {
    drawTrail(ctx, cam, trails.push(TARGET_TRAIL, bx, by, geometry.targetTrailLength), '251,191,36', 0.5, 2.4);
  }

  // 4. RF discovery waves.
  const rfActive = Boolean(
    telem.rf_wave_active ||
      telem.rf_discovery_state === 'IN_PROGRESS' ||
      telem.current_state === 'RF_DISCOVERY' ||
      terminals.some((t) => t.rf_status === 'TRANSMITTING'),
  );
  if (rfActive) {
    terminals.forEach((t, idx) => {
      const isTarget = isTargetTerminal(t, targetId);
      const x = isTarget ? bx : t.position?.[0];
      const y = isTarget ? by : t.position?.[1];
      if (x === undefined || y === undefined) return;
      drawRfWaves(ctx, cam, x, y, nowSec, idx, isTarget, t.rf_status === 'DISCOVERED');
    });
  }

  // 5. Non-target terminals.
  terminals.forEach((t) => {
    if (t.id === targetId || !t.position) return;
    const [tx, ty] = t.position;
    const detected = String(t.status ?? '').toLowerCase() === 'detected';
    const discovered = t.rf_status === 'DISCOVERED';
    const hovered = hoveredId === t.id;

    drawTrail(
      ctx,
      cam,
      trails.push(t.id, tx, ty, geometry.otherTrailLength),
      detected ? '45,212,191' : '126,141,166',
      detected ? 0.32 : 0.2,
      1.6,
    );

    drawNodeShadow(ctx, tx, ty, 7);

    ctx.save();
    const accent = detected ? palette.teal : discovered ? palette.cyan : palette.slate;

    if (hovered) {
      ctx.beginPath();
      ctx.arc(tx, ty, 17, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.45)';
      ctx.lineWidth = 1.2 / cam.scale;
      ctx.stroke();
    }

    if (detected) {
      ctx.beginPath();
      ctx.arc(tx, ty, 13, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(45,212,191,0.40)';
      ctx.lineWidth = 1.2 / cam.scale;
      ctx.stroke();
    }

    // Body with a light-from-above gradient.
    const body = ctx.createLinearGradient(tx, ty - 7, tx, ty + 7);
    body.addColorStop(0, detected ? '#12352f' : '#1a2130');
    body.addColorStop(1, detected ? '#081f1c' : '#0d121c');
    ctx.beginPath();
    ctx.arc(tx, ty, 7, 0, Math.PI * 2);
    ctx.fillStyle = body;
    ctx.fill();
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1.6 / cam.scale;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(tx - 1.6, ty - 1.8, 1.8, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.fill();
    ctx.restore();

    // Labels are drawn in screen space so they never scale or overlap.
    lastHits.push({
      id: t.id,
      worldX: tx,
      worldY: ty,
      screenX: cam.toScreenX(tx),
      screenY: cam.toScreenY(ty),
      radius: 11,
      isTarget: false,
    });
  });

  trails.retain([TARGET_TRAIL, ...terminals.map((t) => t.id)]);

  // 6. Optical FSOC beam.
  const beamActive =
    telem.fsoc_status === 'ESTABLISHED' ||
    telem.fsoc_status === 'ACTIVE' ||
    telem.current_state === 'FSOC_ACTIVE';
  if (beamActive && termB.beacon_active) {
    drawBeam(ctx, cam, ax, ay, bx, by, nowSec);
  }

  // 7. Kalman dead-reckoning marker.
  if (arena.kalman_pred && telem.tracking_status === 'PREDICTING') {
    const [kx, ky] = arena.kalman_pred;
    ctx.save();
    ctx.beginPath();
    ctx.arc(kx, ky, 10, 0, Math.PI * 2);
    ctx.strokeStyle = palette.violet;
    ctx.lineWidth = 1.6 / cam.scale;
    ctx.setLineDash([3 / cam.scale, 3 / cam.scale]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(kx - 4, ky);
    ctx.lineTo(kx + 4, ky);
    ctx.moveTo(kx, ky - 4);
    ctx.lineTo(kx, ky + 4);
    ctx.stroke();
    ctx.restore();
  }

  // 8. Ground station (Terminal A).
  drawNodeShadow(ctx, ax, ay, 13);
  ctx.save();
  const pulse = 0.5 + 0.5 * Math.sin(nowSec * 1.6);
  ctx.beginPath();
  ctx.arc(ax, ay, 15 + pulse * 3, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(56,189,248,${0.18 + pulse * 0.14})`;
  ctx.lineWidth = 1 / cam.scale;
  ctx.stroke();

  const dish = ctx.createLinearGradient(ax, ay - 13, ax, ay + 13);
  dish.addColorStop(0, '#1b2b42');
  dish.addColorStop(1, '#0a1220');
  ctx.beginPath();
  ctx.arc(ax, ay, 13, 0, Math.PI * 2);
  ctx.fillStyle = dish;
  ctx.fill();
  ctx.strokeStyle = palette.cyan;
  ctx.lineWidth = 2 / cam.scale;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(ax, ay, 4, 0, Math.PI * 2);
  ctx.fillStyle = '#ffffff';
  ctx.fill();
  ctx.restore();

  lastHits.push({
    id: '__station__',
    worldX: ax,
    worldY: ay,
    screenX: cam.toScreenX(ax),
    screenY: cam.toScreenY(ay),
    radius: 16,
    isTarget: false,
  });

  // 9. Target terminal (Terminal B).
  drawNodeShadow(ctx, bx, by, 10);
  ctx.save();
  if (termB.beacon_active) {
    const halo = ctx.createRadialGradient(bx, by, 2, bx, by, 26);
    halo.addColorStop(0, 'rgba(251,191,36,0.75)');
    halo.addColorStop(0.45, 'rgba(251,191,36,0.22)');
    halo.addColorStop(1, 'rgba(251,191,36,0)');
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(bx, by, 26, 0, Math.PI * 2);
    ctx.fill();
  }

  // Lock reticle: rotating brackets once the link is established.
  const locked = telem.current_state === 'FSOC_ACTIVE' || telem.current_state === 'FINE_ALIGNMENT';
  if (locked) {
    ctx.save();
    ctx.translate(bx, by);
    ctx.rotate(nowSec * 0.5);
    ctx.strokeStyle = 'rgba(45,212,191,0.75)';
    ctx.lineWidth = 1.4 / cam.scale;
    for (let q = 0; q < 4; q++) {
      ctx.beginPath();
      ctx.arc(0, 0, 19, q * (Math.PI / 2) + 0.25, q * (Math.PI / 2) + Math.PI / 2 - 0.25);
      ctx.stroke();
    }
    ctx.restore();
  }

  if (hoveredId === targetId) {
    ctx.beginPath();
    ctx.arc(bx, by, 23, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.45)';
    ctx.lineWidth = 1.2 / cam.scale;
    ctx.stroke();
  }

  ctx.beginPath();
  ctx.arc(bx, by, 14, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(56,189,248,0.55)';
  ctx.lineWidth = 1.2 / cam.scale;
  ctx.stroke();

  const core = ctx.createLinearGradient(bx, by - 9, bx, by + 9);
  core.addColorStop(0, termB.beacon_active ? '#ffd97a' : '#3a4353');
  core.addColorStop(1, termB.beacon_active ? '#d97706' : '#222a38');
  ctx.beginPath();
  ctx.arc(bx, by, 9, 0, Math.PI * 2);
  ctx.fillStyle = core;
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1.6 / cam.scale;
  ctx.stroke();
  ctx.restore();

  lastHits.push({
    id: targetId,
    worldX: bx,
    worldY: by,
    screenX: cam.toScreenX(bx),
    screenY: cam.toScreenY(by),
    radius: 16,
    isTarget: true,
  });

  // --- Screen-space labels ---------------------------------------------
  // Drawn last, unscaled, so text stays the same size at any zoom and never
  // inherits the camera's transform.
  ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
  ctx.textAlign = 'center';
  placedLabels.length = 0;

  // Target first so it wins the contested position and others move around it.
  const targetObj = terminals.find((t) => t.id === targetId);
  const tsx = cam.toScreenX(bx);
  const tsy = cam.toScreenY(by);
  drawLabel(ctx, tsx, tsy - 26, `${targetObj ? targetObj.name : targetId} · TARGET`, palette.cyanBright, true);
  if (cam.scale > 0.42) {
    const targetDiscovered =
      targetObj?.rf_status === 'DISCOVERED' || telem.rf_discovery_state === 'COMPLETE';
    drawLabel(
      ctx,
      tsx,
      tsy + 30,
      telem.current_state === 'FSOC_ACTIVE' ? 'FSOC ACTIVE' : targetDiscovered ? 'ACQUIRED' : 'TRANSMITTING',
      locked ? palette.teal : targetDiscovered ? palette.cyanBright : palette.amberPale,
      false,
      true,
    );
  }

  drawLabel(
    ctx,
    cam.toScreenX(ax),
    cam.toScreenY(ay) + 30,
    'TERMINAL A · RX',
    palette.cyanBright,
    true,
  );

  terminals.forEach((t) => {
    if (t.id === targetId || !t.position) return;
    const sx = cam.toScreenX(t.position[0]);
    const sy = cam.toScreenY(t.position[1]);
    if (sx < -80 || sy < -40 || sx > cam.viewW + 80 || sy > cam.viewH + 40) return;
    const detected = String(t.status ?? '').toLowerCase() === 'detected';
    const discovered = t.rf_status === 'DISCOVERED';
    drawLabel(ctx, sx, sy - 18, t.name, detected ? palette.tealPale : palette.slateText, false);
    if (cam.scale > 0.42) {
      drawLabel(
        ctx,
        sx,
        sy + 26,
        detected ? 'DETECTED' : discovered ? 'DISCOVERED' : 'TRANSMITTING',
        detected ? palette.teal : discovered ? palette.cyan : palette.amberPale,
        false,
        true,
      );
    }
  });

}

/**
 * Screen-space label placement.
 *
 * Terminals drift past each other constantly, and two labels landing on the
 * same pixels made both unreadable. Each label is tested against the ones
 * already placed this frame and nudged vertically until it clears — nearest
 * free slot, so a label only moves as far as it has to.
 */
interface LabelBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

const placedLabels: LabelBox[] = [];

function overlaps(a: LabelBox, b: LabelBox): boolean {
  return (
    Math.abs(a.x - b.x) * 2 < a.w + b.w + 4 && Math.abs(a.y - b.y) * 2 < a.h + b.h + 3
  );
}

/** Text with a dark plate behind it, so labels stay readable over any layer. */
function drawLabel(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  text: string,
  color: string,
  bold: boolean,
  small = false,
): void {
  const size = small ? 9 : bold ? 11 : 10;
  ctx.font = `${bold ? 700 : 600} ${size}px ${fonts.family}`;
  const w = ctx.measureText(text).width + 10;
  const h = size + 5;

  // Search outward from the requested position for a free slot.
  let box: LabelBox = { x, y, w, h };
  for (let attempt = 0; attempt < 12; attempt++) {
    if (!placedLabels.some((p) => overlaps(box, p))) break;
    // Alternate above/below, growing the offset each round.
    const step = Math.ceil((attempt + 1) / 2) * (h + 2);
    box = { x, y: y + (attempt % 2 === 0 ? -step : step), w, h };
  }
  placedLabels.push(box);

  ctx.save();
  ctx.fillStyle = 'rgba(4,6,12,0.72)';
  roundRect(ctx, box.x - w / 2, box.y - h / 2, w, h, 3);
  ctx.fill();

  ctx.fillStyle = color;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'center';
  ctx.fillText(text, box.x, box.y + 0.5);
  ctx.restore();
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** Nearest node within its hit radius, for hover and click. */
export function hitTest(screenX: number, screenY: number): NodeHit | null {
  let best: NodeHit | null = null;
  let bestDist = Infinity;
  for (const h of lastHits) {
    const d = Math.hypot(h.screenX - screenX, h.screenY - screenY);
    if (d <= h.radius && d < bestDist) {
      best = h;
      bestDist = d;
    }
  }
  return best;
}
