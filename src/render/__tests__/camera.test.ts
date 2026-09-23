/**
 * Camera maths.
 *
 * Worth testing directly: cursor-anchored zoom is the one piece of this UI
 * where an off-by-a-transform is invisible in code review but immediately
 * obvious — and infuriating — in use.
 */
import { describe, expect, it } from 'vitest';
import { baseScale, boundsOf, Camera, MAX_SCALE, MIN_SCALE } from '../camera';

const WORLD_W = 1280;
const WORLD_H = 720;

describe('Camera.zoomAt', () => {
  it('keeps the world point under the cursor fixed', () => {
    const cam = new Camera();
    cam.setViewport(900, 500);
    cam.scale = 0.4;
    cam.offsetX = 30;
    cam.offsetY = -12;

    for (const [sx, sy] of [
      [0, 0],
      [123, 77],
      [899, 499],
      [450, 250],
    ]) {
      const wx = cam.toWorldX(sx);
      const wy = cam.toWorldY(sy);
      for (const factor of [1.25, 0.8, 3.0, 0.33]) {
        cam.zoomAt(sx, sy, factor);
        expect(cam.toWorldX(sx)).toBeCloseTo(wx, 6);
        expect(cam.toWorldY(sy)).toBeCloseTo(wy, 6);
      }
    }
  });

  it('clamps to the scale limits', () => {
    const cam = new Camera();
    cam.setViewport(800, 600);

    for (let i = 0; i < 200; i++) cam.zoomAt(400, 300, 2);
    expect(cam.scale).toBe(MAX_SCALE);

    for (let i = 0; i < 400; i++) cam.zoomAt(400, 300, 0.5);
    expect(cam.scale).toBe(MIN_SCALE);
  });
});

describe('Camera transforms', () => {
  it('round-trips world <-> screen', () => {
    const cam = new Camera();
    cam.setViewport(1000, 700);
    cam.scale = 1.37;
    cam.offsetX = -220;
    cam.offsetY = 64;

    for (const [x, y] of [
      [0, 0],
      [1280, 720],
      [640, 360],
      [-50, 900],
    ]) {
      expect(cam.toWorldX(cam.toScreenX(x))).toBeCloseTo(x, 9);
      expect(cam.toWorldY(cam.toScreenY(y))).toBeCloseTo(y, 9);
    }
  });
});

describe('Camera.fit', () => {
  it('centres the bounds in the viewport', () => {
    const cam = new Camera();
    cam.setViewport(1000, 600);
    const b = { minX: 100, minY: 100, maxX: 500, maxY: 300 };
    cam.fit(b, 40);

    expect(cam.toScreenX((b.minX + b.maxX) / 2)).toBeCloseTo(500, 6);
    expect(cam.toScreenY((b.minY + b.maxY) / 2)).toBeCloseTo(300, 6);
  });

  it('keeps the bounds inside the viewport', () => {
    const cam = new Camera();
    cam.setViewport(1000, 600);
    const b = { minX: 0, minY: 0, maxX: WORLD_W, maxY: WORLD_H };
    cam.fit(b, 40);

    expect(cam.toScreenX(b.minX)).toBeGreaterThanOrEqual(-1e-6);
    expect(cam.toScreenX(b.maxX)).toBeLessThanOrEqual(1000 + 1e-6);
    expect(cam.toScreenY(b.minY)).toBeGreaterThanOrEqual(-1e-6);
    expect(cam.toScreenY(b.maxY)).toBeLessThanOrEqual(600 + 1e-6);
  });
});

describe('Camera.percent', () => {
  it('reads 100% when the world exactly fits', () => {
    const cam = new Camera();
    cam.setViewport(WORLD_W, WORLD_H);
    cam.scale = baseScale(WORLD_W, WORLD_H, WORLD_W, WORLD_H);
    expect(cam.percent(WORLD_W, WORLD_H)).toBe(100);
  });
});

describe('Camera.clampToWorld', () => {
  it('always leaves part of the world reachable after a hard fling', () => {
    const cam = new Camera();
    cam.setViewport(800, 600);
    cam.scale = 1;
    cam.panBy(100_000, 100_000);
    cam.clampToWorld(WORLD_W, WORLD_H);

    // Some part of the world rect must still intersect the viewport.
    expect(cam.offsetX).toBeLessThan(800);
    expect(cam.offsetX + WORLD_W).toBeGreaterThan(0);
    expect(cam.offsetY).toBeLessThan(600);
    expect(cam.offsetY + WORLD_H).toBeGreaterThan(0);
  });
});

describe('boundsOf', () => {
  it('pads the bounding box', () => {
    expect(boundsOf([{ x: 10, y: 20 }, { x: 200, y: 5 }, { x: 50, y: 300 }], 10)).toEqual({
      minX: 0,
      minY: -5,
      maxX: 210,
      maxY: 310,
    });
  });

  it('returns null for no points', () => {
    expect(boundsOf([])).toBeNull();
  });
});
