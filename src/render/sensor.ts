/**
 * Boresight sensor view — the camera's own frame with the alignment reticle.
 *
 * Beacon coordinates arrive in image space (1280x720). The view letterboxes
 * that frame into whatever the panel is sized to, so the reticle stays centred
 * on the optical axis at any window size.
 */
import { fonts, geometry, palette } from './palette';
import type { TelemetryFrame } from '@/types/telemetry';

/** Ring radii in image pixels; the innermost is the fine-alignment margin. */
const RING_RADII = [40, 80, 140, 220] as const;
const FINE_MARGIN_PX = 40;

export interface SensorView {
  viewW: number;
  viewH: number;
  dpr: number;
}

export function renderSensor(
  ctx: CanvasRenderingContext2D,
  frame: TelemetryFrame,
  view: SensorView,
  nowSec: number,
): void {
  const { viewW, viewH, dpr } = view;
  const telem = frame.telemetry;

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, viewW, viewH);
  ctx.fillStyle = palette.space;
  ctx.fillRect(0, 0, viewW, viewH);

  // Letterbox the sensor frame into the panel.
  const scale = Math.min(viewW / geometry.width, viewH / geometry.height);
  const ox = (viewW - geometry.width * scale) / 2;
  const oy = (viewH - geometry.height * scale) / 2;
  ctx.setTransform(scale * dpr, 0, 0, scale * dpr, ox * dpr, oy * dpr);

  const cx = geometry.width / 2;
  const cy = geometry.height / 2;

  // Sensor-noise wash: sells "this is a real detector" without hurting reads.
  ctx.save();
  const wash = ctx.createRadialGradient(cx, cy, 40, cx, cy, 420);
  wash.addColorStop(0, 'rgba(45,212,191,0.05)');
  wash.addColorStop(1, 'rgba(4,6,12,0)');
  ctx.fillStyle = wash;
  ctx.fillRect(0, 0, geometry.width, geometry.height);
  ctx.restore();

  ctx.save();
  ctx.lineWidth = 1 / scale;

  // Concentric alignment rings.
  RING_RADII.forEach((r, idx) => {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = idx === 0 ? 'rgba(45,212,191,0.42)' : 'rgba(56,189,248,0.13)';
    ctx.lineWidth = (idx === 0 ? 1.4 : 1) / scale;
    ctx.stroke();
  });

  // Tick marks every 30° on the outer ring.
  ctx.strokeStyle = 'rgba(56,189,248,0.22)';
  ctx.lineWidth = 1 / scale;
  for (let a = 0; a < 360; a += 30) {
    const rad = (a * Math.PI) / 180;
    const r0 = 220;
    const r1 = a % 90 === 0 ? 236 : 229;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(rad) * r0, cy + Math.sin(rad) * r0);
    ctx.lineTo(cx + Math.cos(rad) * r1, cy + Math.sin(rad) * r1);
    ctx.stroke();
  }

  // Crosshair with a gap at the centre so it doesn't hide the beacon.
  ctx.strokeStyle = 'rgba(56,189,248,0.34)';
  ctx.beginPath();
  ctx.moveTo(cx - 300, cy);
  ctx.lineTo(cx - 14, cy);
  ctx.moveTo(cx + 14, cy);
  ctx.lineTo(cx + 300, cy);
  ctx.moveTo(cx, cy - 300);
  ctx.lineTo(cx, cy - 14);
  ctx.moveTo(cx, cy + 14);
  ctx.lineTo(cx, cy + 300);
  ctx.stroke();

  if (telem.beacon_detected && telem.beacon_position) {
    const [bx, by] = telem.beacon_position;
    const err = Math.hypot(bx - cx, by - cy);
    const inMargin = err <= FINE_MARGIN_PX;
    const accent = inMargin ? palette.teal : palette.amber;

    // Error vector from optical axis to detected centroid.
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(bx, by);
    ctx.strokeStyle = inMargin ? 'rgba(45,212,191,0.55)' : 'rgba(251,191,36,0.55)';
    ctx.setLineDash([5 / scale, 5 / scale]);
    ctx.lineWidth = 1.2 / scale;
    ctx.stroke();
    ctx.setLineDash([]);

    // Beacon glow.
    const glow = ctx.createRadialGradient(bx, by, 1, bx, by, 30);
    glow.addColorStop(0, inMargin ? 'rgba(45,212,191,0.5)' : 'rgba(251,191,36,0.5)');
    glow.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(bx, by, 30, 0, Math.PI * 2);
    ctx.fill();

    // Tracking brackets.
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1.6 / scale;
    const s = 16;
    for (const [sx, sy] of [
      [-1, -1],
      [1, -1],
      [-1, 1],
      [1, 1],
    ] as const) {
      ctx.beginPath();
      ctx.moveTo(bx + sx * s, by + sy * s - sy * 6);
      ctx.lineTo(bx + sx * s, by + sy * s);
      ctx.lineTo(bx + sx * s - sx * 6, by + sy * s);
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(bx, by, 4, 0, Math.PI * 2);
    ctx.fillStyle = palette.white;
    ctx.fill();

    // Readout pinned under the beacon.
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const lx = ox + bx * scale;
    const ly = oy + by * scale + 34;
    ctx.font = `600 10px ${fonts.mono}`;
    ctx.textAlign = 'center';
    ctx.fillStyle = accent;
    ctx.fillText(`ERR ${err.toFixed(1)} px`, lx, ly);
  } else {
    // No beacon: sweeping search arc.
    ctx.beginPath();
    const sweep = (nowSec * 0.8) % (Math.PI * 2);
    ctx.arc(cx, cy, 220, sweep, sweep + 0.6);
    ctx.strokeStyle = 'rgba(251,113,133,0.5)';
    ctx.lineWidth = 2 / scale;
    ctx.stroke();

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = `600 12px ${fonts.family}`;
    ctx.textAlign = 'center';
    ctx.fillStyle = palette.rose;
    ctx.fillText('NO BEACON — SEARCHING', viewW / 2, oy + (cy + 268) * scale);
  }

  ctx.restore();
}
