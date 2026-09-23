/**
 * 2D camera for the arena viewport.
 *
 * Replaces the old "workspace zoom", which scaled the entire page with a CSS
 * transform — duplicating browser zoom, clipping content at >100% and leaving
 * dead margins at <100%. Zoom belongs to the map, not the document.
 *
 * Transform is `screen = world * scale + offset`, all in CSS pixels. The
 * renderer applies it with `ctx.setTransform`, so every draw call stays in
 * world coordinates and nothing downstream has to know about the camera.
 */

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export const MIN_SCALE = 0.4;
export const MAX_SCALE = 6;

export class Camera {
  scale = 1;
  offsetX = 0;
  offsetY = 0;

  /** Viewport size in CSS pixels. */
  viewW = 0;
  viewH = 0;

  setViewport(w: number, h: number): void {
    this.viewW = w;
    this.viewH = h;
  }

  toScreenX(worldX: number): number {
    return worldX * this.scale + this.offsetX;
  }

  toScreenY(worldY: number): number {
    return worldY * this.scale + this.offsetY;
  }

  toWorldX(screenX: number): number {
    return (screenX - this.offsetX) / this.scale;
  }

  toWorldY(screenY: number): number {
    return (screenY - this.offsetY) / this.scale;
  }

  /** Pan by a screen-space delta. */
  panBy(dx: number, dy: number): void {
    this.offsetX += dx;
    this.offsetY += dy;
  }

  /**
   * Zoom about a screen anchor, keeping the world point under it fixed —
   * the behaviour that makes wheel-zoom feel attached to the cursor rather
   * than to the centre of the canvas.
   */
  zoomAt(screenX: number, screenY: number, factor: number): void {
    const next = clamp(this.scale * factor, MIN_SCALE, MAX_SCALE);
    if (next === this.scale) return;
    const wx = this.toWorldX(screenX);
    const wy = this.toWorldY(screenY);
    this.scale = next;
    this.offsetX = screenX - wx * this.scale;
    this.offsetY = screenY - wy * this.scale;
  }

  /** Zoom about the viewport centre — used by the -/+ buttons. */
  zoomByStep(factor: number): void {
    this.zoomAt(this.viewW / 2, this.viewH / 2, factor);
  }

  /** Frame `bounds` with padding, centred in the viewport. */
  fit(bounds: Bounds, padding = 48): void {
    const w = Math.max(1, bounds.maxX - bounds.minX);
    const h = Math.max(1, bounds.maxY - bounds.minY);
    const scale = clamp(
      Math.min((this.viewW - padding * 2) / w, (this.viewH - padding * 2) / h),
      MIN_SCALE,
      MAX_SCALE,
    );
    this.scale = scale;
    this.offsetX = this.viewW / 2 - (bounds.minX + w / 2) * scale;
    this.offsetY = this.viewH / 2 - (bounds.minY + h / 2) * scale;
  }

  /**
   * Keep the world roughly on screen. Without this a hard drag can fling the
   * arena into empty space with no way back except FIT.
   */
  clampToWorld(worldW: number, worldH: number): void {
    const margin = Math.min(this.viewW, this.viewH) * 0.5;
    const scaledW = worldW * this.scale;
    const scaledH = worldH * this.scale;
    this.offsetX = clamp(this.offsetX, -scaledW + margin, this.viewW - margin);
    this.offsetY = clamp(this.offsetY, -scaledH + margin, this.viewH - margin);
  }

  /** Percentage for the zoom readout, relative to fit-to-viewport. */
  percent(worldW: number, worldH: number): number {
    const base = baseScale(this.viewW, this.viewH, worldW, worldH);
    return Math.round((this.scale / base) * 100);
  }

  snapshot(): { scale: number; offsetX: number; offsetY: number } {
    return { scale: this.scale, offsetX: this.offsetX, offsetY: this.offsetY };
  }
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Scale at which the full world exactly fits the viewport (= "100%"). */
export function baseScale(viewW: number, viewH: number, worldW: number, worldH: number): number {
  if (viewW <= 0 || viewH <= 0) return 1;
  return Math.min(viewW / worldW, viewH / worldH);
}

/** Bounding box of points with padding, used by fit-to-terminals. */
export function boundsOf(points: { x: number; y: number }[], pad = 80): Bounds | null {
  if (points.length === 0) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  return { minX: minX - pad, minY: minY - pad, maxX: maxX + pad, maxY: maxY + pad };
}
