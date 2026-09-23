/**
 * Orbital 3D view of the sector.
 *
 * A companion to the 2D plan view, not a replacement: the plan view is where
 * bearings and the FOV cone are read without perspective distortion, this one
 * is for spatial sense — where things are relative to each other, and what the
 * link geometry actually looks like.
 *
 * ── On altitude ────────────────────────────────────────────────────────────
 * The simulator is strictly 2D: terminals are [x, y] on a 1280x720 plane and
 * `camera_tilt` is always 0. The heights here are a deliberate display
 * convention, not telemetry — a ground station firing up at airborne terminals,
 * which is the usual FSOC geometry. They are derived deterministically from each
 * terminal's id (see `altitudeFor`) so a node keeps the same height for its
 * whole life instead of jittering between frames, and the view labels them as
 * illustrative. Nothing here encodes a value the backend computes.
 *
 * Everything is preallocated and reused; the per-frame `update` only writes
 * transforms and colours, so there is no allocation in the render loop.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import { geometry as geo } from './palette';
import type { TelemetryFrame, Terminal } from '@/types/telemetry';

const WORLD_W = geo.width;
const WORLD_H = geo.height;
const HALF_W = WORLD_W / 2;
const HALF_H = WORLD_H / 2;

/** Display-only altitude band for airborne terminals, in world units. */
const ALT_MIN = 70;
const ALT_MAX = 190;
/** Ground station sits on the plane. */
const STATION_ALT = 8;

/** World (x, y) -> scene (x, z), centred on the origin. */
function sx(worldX: number): number {
  return worldX - HALF_W;
}
function sz(worldY: number): number {
  return worldY - HALF_H;
}

/**
 * Stable pseudo-random altitude from the terminal id.
 *
 * Deterministic so a terminal holds its height across frames and reloads —
 * a per-frame random would make the whole sector shimmer vertically.
 */
export function altitudeFor(id: string): number {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const t = ((h >>> 0) % 1000) / 1000;
  return ALT_MIN + t * (ALT_MAX - ALT_MIN);
}

interface TerminalNode {
  group: THREE.Group;
  core: THREE.Mesh;
  halo: THREE.Sprite;
  mast: THREE.Line;
  rings: THREE.Mesh[];
  label: CSS2DObject;
  labelEl: HTMLDivElement;
  baseAltitude: number;
}

export interface Scene3DHandle {
  resize(): void;
  update(frame: TelemetryFrame, nowSec: number): void;
  render(): void;
  fit(): void;
  dispose(): void;
  /** Terminal id under the pointer, or null. */
  pick(clientX: number, clientY: number): string | null;
}

export function createScene3D(
  container: HTMLDivElement,
  labelHost: HTMLDivElement,
): Scene3DHandle {
  // ── Renderer ────────────────────────────────────────────────────────────
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x04060c, 1);
  renderer.domElement.style.display = 'block';
  renderer.domElement.style.width = '100%';
  renderer.domElement.style.height = '100%';
  container.appendChild(renderer.domElement);

  const labelRenderer = new CSS2DRenderer({ element: labelHost });
  labelHost.style.position = 'absolute';
  labelHost.style.inset = '0';
  labelHost.style.pointerEvents = 'none';
  labelHost.style.overflow = 'hidden';

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x04060c, 900, 2600);

  const camera = new THREE.PerspectiveCamera(46, 1, 1, 6000);
  camera.position.set(-520, 620, 900);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = false;
  controls.minDistance = 180;
  controls.maxDistance = 2600;
  // Stop the camera going under the ground plane — disorienting and shows
  // the grid from behind.
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.target.set(0, 60, 0);

  // Once the operator has moved the camera, stop re-framing on resize —
  // silently yanking their view back would be worse than a loose fit.
  let userHasOrbited = false;
  controls.addEventListener('start', () => {
    userHasOrbited = true;
  });

  // ── Lighting ────────────────────────────────────────────────────────────
  scene.add(new THREE.AmbientLight(0x2a3a55, 1.4));
  const key = new THREE.DirectionalLight(0x6fb7ff, 0.7);
  key.position.set(-400, 800, 500);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x2dd4bf, 0.35);
  rim.position.set(600, 300, -500);
  scene.add(rim);

  // ── Ground plane + grid ────────────────────────────────────────────────
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(WORLD_W, WORLD_H),
    new THREE.MeshBasicMaterial({ color: 0x070d18, transparent: true, opacity: 0.92 }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.5;
  scene.add(ground);

  const grid = new THREE.GridHelper(WORLD_W, WORLD_W / 80, 0x3d6490, 0x1d2f4a);
  scene.add(grid);

  // World boundary outline.
  const boundary = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.PlaneGeometry(WORLD_W, WORLD_H)),
    new THREE.LineBasicMaterial({ color: 0x2dd4bf, transparent: true, opacity: 0.45 }),
  );
  boundary.rotation.x = -Math.PI / 2;
  scene.add(boundary);

  // ── Ground station ──────────────────────────────────────────────────────
  const station = new THREE.Group();
  const dish = new THREE.Mesh(
    new THREE.CylinderGeometry(20, 28, 12, 24),
    new THREE.MeshStandardMaterial({
      color: 0x16283f,
      emissive: 0x0d3550,
      emissiveIntensity: 0.6,
      metalness: 0.6,
      roughness: 0.4,
    }),
  );
  dish.position.y = STATION_ALT;
  station.add(dish);

  const aperture = new THREE.Mesh(
    new THREE.SphereGeometry(6.5, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffffff }),
  );
  aperture.position.y = STATION_ALT + 7;
  station.add(aperture);

  // Base pad ring.
  const pad = new THREE.Mesh(
    new THREE.RingGeometry(34, 40, 40),
    new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.35, side: THREE.DoubleSide }),
  );
  pad.rotation.x = -Math.PI / 2;
  pad.position.y = 0.6;
  station.add(pad);
  scene.add(station);

  const stationLabelEl = makeLabel('TERMINAL A · RX', '#7dd3fc', true);
  const stationLabel = new CSS2DObject(stationLabelEl);
  stationLabel.position.set(0, STATION_ALT + 34, 0);
  station.add(stationLabel);

  // ── FOV wedge: flat on the ground, where the bearing stays readable ─────
  const fovMat = new THREE.MeshBasicMaterial({
    color: 0x38bdf8,
    transparent: true,
    opacity: 0.1,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const fovMesh = new THREE.Mesh(new THREE.BufferGeometry(), fovMat);
  fovMesh.position.y = 1.2;
  scene.add(fovMesh);

  const boresight = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineDashedMaterial({ color: 0x38bdf8, dashSize: 18, gapSize: 12, transparent: true, opacity: 0.5 }),
  );
  scene.add(boresight);

  // ── Optical beam ────────────────────────────────────────────────────────
  const beamGroup = new THREE.Group();
  const beamCore = new THREE.Mesh(
    new THREE.CylinderGeometry(1.4, 1.4, 1, 8, 1, true),
    new THREE.MeshBasicMaterial({ color: 0xeafff9, transparent: true, opacity: 0.95 }),
  );
  const beamGlow = new THREE.Mesh(
    new THREE.CylinderGeometry(6.5, 6.5, 1, 12, 1, true),
    new THREE.MeshBasicMaterial({
      color: 0x2dd4bf,
      transparent: true,
      opacity: 0.16,
      depthWrite: false,
      side: THREE.DoubleSide,
    }),
  );
  beamGroup.add(beamCore, beamGlow);
  scene.add(beamGroup);

  // Data pulses travelling along the beam.
  const pulses = Array.from({ length: 4 }, () => {
    const m = new THREE.Mesh(
      new THREE.SphereGeometry(4, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true }),
    );
    scene.add(m);
    return m;
  });

  // ── Kalman prediction marker ────────────────────────────────────────────
  const kalman = new THREE.Mesh(
    new THREE.OctahedronGeometry(12),
    new THREE.MeshBasicMaterial({ color: 0xa78bfa, wireframe: true, transparent: true, opacity: 0.9 }),
  );
  kalman.visible = false;
  scene.add(kalman);

  // ── Terminals (rebuilt when the roster changes) ─────────────────────────
  const nodes = new Map<string, TerminalNode>();
  const terminalRoot = new THREE.Group();
  scene.add(terminalRoot);

  const haloTexture = makeGlowTexture();

  function buildNode(t: Terminal): TerminalNode {
    const group = new THREE.Group();

    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(16, 1),
      new THREE.MeshStandardMaterial({
        color: 0x1a2740,
        emissive: 0x0f3a35,
        emissiveIntensity: 0.7,
        metalness: 0.5,
        roughness: 0.35,
        flatShading: true,
      }),
    );
    group.add(core);

    const halo = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: haloTexture,
        color: 0x2dd4bf,
        transparent: true,
        opacity: 0.5,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    halo.scale.set(95, 95, 1);
    group.add(halo);

    // Mast down to the ground plane, so the altitude reads as a position
    // rather than the node floating ambiguously in space.
    const mast = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ color: 0x2dd4bf, transparent: true, opacity: 0.22 }),
    );
    group.add(mast);

    // RF rings that rise up the mast.
    const rings = Array.from({ length: 3 }, () => {
      const r = new THREE.Mesh(
        new THREE.RingGeometry(10, 12, 32),
        new THREE.MeshBasicMaterial({
          color: 0x38bdf8,
          transparent: true,
          opacity: 0.5,
          side: THREE.DoubleSide,
          depthWrite: false,
        }),
      );
      r.rotation.x = -Math.PI / 2;
      group.add(r);
      return r;
    });

    const labelEl = makeLabel(t.name, '#8b97ad', false);
    const label = new CSS2DObject(labelEl);
    label.position.set(0, 26, 0);
    group.add(label);

    terminalRoot.add(group);
    return { group, core, halo, mast, rings, label, labelEl, baseAltitude: altitudeFor(t.id) };
  }

  function syncRoster(terminals: Terminal[]): void {
    const live = new Set(terminals.map((t) => t.id));
    for (const [id, node] of nodes) {
      if (!live.has(id)) {
        terminalRoot.remove(node.group);
        disposeGroup(node.group);
        node.labelEl.remove();
        nodes.delete(id);
      }
    }
    for (const t of terminals) {
      if (!nodes.has(t.id)) nodes.set(t.id, buildNode(t));
    }
  }

  // ── Picking ─────────────────────────────────────────────────────────────
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();

  function pick(clientX: number, clientY: number): string | null {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);

    const meshes: THREE.Object3D[] = [];
    for (const node of nodes.values()) meshes.push(node.core);
    const hits = raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return null;

    for (const [id, node] of nodes) {
      if (node.core === hits[0].object) return id;
    }
    return null;
  }

  // ── Per-frame update ────────────────────────────────────────────────────
  const tmpA = new THREE.Vector3();
  const tmpB = new THREE.Vector3();
  const tmpDir = new THREE.Vector3();
  const UP = new THREE.Vector3(0, 1, 0);

  let hoveredId: string | null = null;

  function update(frame: TelemetryFrame, nowSec: number): void {
    const { arena, telemetry: telem, terminals } = frame;
    const targetId = frame.target_terminal;

    syncRoster(terminals);

    // Ground station.
    const ax = sx(arena.terminal_a.x);
    const az = sz(arena.terminal_a.y);
    station.position.set(ax, 0, az);

    // FOV wedge on the ground.
    const angle = (arena.terminal_a.orientation_deg * Math.PI) / 180;
    const half = ((arena.terminal_a.fov_deg / 2) * Math.PI) / 180;
    updateWedge(fovMesh, ax, az, angle, half, geo.coneRadius);

    const bsEnd = boresight.geometry.attributes.position;
    bsEnd.setXYZ(0, ax, 2, az);
    bsEnd.setXYZ(
      1,
      ax + Math.cos(angle) * geo.coneRadius,
      2,
      az + Math.sin(angle) * geo.coneRadius,
    );
    bsEnd.needsUpdate = true;
    boresight.computeLineDistances();

    // Terminals.
    for (const t of terminals) {
      const node = nodes.get(t.id);
      if (!node || !t.position) continue;

      const isTarget = t.id === targetId || t.is_target;
      const detected = String(t.status ?? '').toLowerCase() === 'detected';
      const discovered = t.rf_status === 'DISCOVERED';

      // Gentle bob so the scene has life without the height reading as data.
      const alt = node.baseAltitude + Math.sin(nowSec * 0.6 + node.baseAltitude) * 4;
      const px = sx(t.position[0]);
      const pz = sz(t.position[1]);
      node.group.position.set(px, alt, pz);
      node.core.rotation.y += 0.004;
      node.core.rotation.x = Math.sin(nowSec * 0.3) * 0.15;

      const accent = detected ? 0x2dd4bf : discovered ? 0x38bdf8 : 0x56637a;
      const mat = node.core.material as THREE.MeshStandardMaterial;
      mat.emissive.setHex(isTarget ? 0xd97706 : accent);
      mat.emissiveIntensity = isTarget ? 1.2 : detected ? 0.8 : 0.35;

      const haloMat = node.halo.material as THREE.SpriteMaterial;
      haloMat.color.setHex(isTarget ? 0xfbbf24 : accent);
      haloMat.opacity = hoveredId === t.id ? 0.8 : isTarget ? 0.65 : detected ? 0.4 : 0.2;
      const haloScale = isTarget ? 150 : 95;
      node.halo.scale.set(haloScale, haloScale, 1);

      node.core.scale.setScalar(isTarget ? 1.35 : 1);

      // Mast to the ground.
      const mp = node.mast.geometry.attributes.position;
      mp.setXYZ(0, 0, 0, 0);
      mp.setXYZ(1, 0, -alt, 0);
      mp.needsUpdate = true;
      const mm = node.mast.material as THREE.LineBasicMaterial;
      mm.color.setHex(accent);
      mm.opacity = isTarget ? 0.5 : 0.28;

      // RF rings rising along the mast.
      const transmitting = !discovered || telem.current_state === 'RF_DISCOVERY';
      node.rings.forEach((ring, k) => {
        ring.visible = transmitting;
        if (!transmitting) return;
        const prog = (nowSec * 0.7 + k / 3) % 1;
        ring.position.y = -alt + prog * alt;
        const s = 0.6 + prog * 2.2;
        ring.scale.set(s, s, 1);
        const rm = ring.material as THREE.MeshBasicMaterial;
        rm.opacity = (1 - prog) * 0.45;
        rm.color.setHex(isTarget ? 0x38bdf8 : 0x2dd4bf);
      });

      node.labelEl.textContent = isTarget ? `${t.name} · TARGET` : t.name;
      node.labelEl.style.color = isTarget ? '#7dd3fc' : detected ? '#99f6e4' : '#8b97ad';
      node.labelEl.style.fontWeight = isTarget ? '700' : '600';
      node.labelEl.style.opacity = isTarget || detected || hoveredId === t.id ? '1' : '0.65';
    }

    // Optical beam: station -> target beacon.
    const targetNode = nodes.get(targetId);
    const beamActive =
      (telem.fsoc_status === 'ESTABLISHED' ||
        telem.fsoc_status === 'ACTIVE' ||
        telem.current_state === 'FSOC_ACTIVE') &&
      arena.terminal_b.beacon_active &&
      Boolean(targetNode);

    beamGroup.visible = beamActive;
    for (const p of pulses) p.visible = beamActive;

    if (beamActive && targetNode) {
      tmpA.set(ax, STATION_ALT + 7, az);
      tmpB.copy(targetNode.group.position);
      const len = tmpA.distanceTo(tmpB);
      tmpDir.subVectors(tmpB, tmpA).normalize();

      beamGroup.position.copy(tmpA).addScaledVector(tmpDir, len / 2);
      beamGroup.quaternion.setFromUnitVectors(UP, tmpDir);
      beamCore.scale.set(1, len, 1);
      beamGlow.scale.set(1, len, 1);

      pulses.forEach((p, i) => {
        const t = (nowSec * 0.45 + i / pulses.length) % 1;
        p.position.copy(tmpA).addScaledVector(tmpDir, len * t);
        const fade = Math.sin(t * Math.PI);
        (p.material as THREE.MeshBasicMaterial).opacity = fade;
        p.scale.setScalar(0.6 + fade * 0.9);
      });
    }

    // Kalman prediction.
    if (arena.kalman_pred && telem.tracking_status === 'PREDICTING') {
      kalman.visible = true;
      const alt = targetNode ? targetNode.group.position.y : 120;
      kalman.position.set(sx(arena.kalman_pred[0]), alt, sz(arena.kalman_pred[1]));
      kalman.rotation.y += 0.02;
    } else {
      kalman.visible = false;
    }

    controls.update();
  }

  function resize(): void {
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (w === 0 || h === 0) return;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
    labelRenderer.setSize(w, h);
    if (!userHasOrbited) fit();
  }

  /**
   * Frame the whole sector for the current aspect ratio.
   *
   * A fixed camera position looked correct in one panel shape and lost in
   * every other, so the distance is solved from the world's bounding radius
   * against both the vertical and horizontal field of view.
   */
  function fit(): void {
    const radius = Math.hypot(WORLD_W / 2, WORLD_H / 2);
    const vFov = (camera.fov * Math.PI) / 180;
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect);

    // Three-quarter view: high enough to read the layout, low enough to feel 3D.
    const dir = new THREE.Vector3(-0.42, 0.6, 0.68).normalize();
    // Foreshortening: at elevation `dir.y` the plane's depth occupies far less
    // vertical screen space than its true radius.
    const apparentDepth = radius * Math.max(0.45, dir.y);
    const dist =
      Math.max(apparentDepth / Math.tan(vFov / 2), radius / Math.tan(hFov / 2)) * 0.95;

    camera.position.copy(dir.clone().multiplyScalar(dist));
    controls.target.set(0, 70, 0);
    controls.update();
  }

  function render(): void {
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
  }

  function dispose(): void {
    controls.dispose();
    for (const node of nodes.values()) {
      disposeGroup(node.group);
      node.labelEl.remove();
    }
    nodes.clear();
    stationLabelEl.remove();
    disposeGroup(scene as unknown as THREE.Group);
    renderer.dispose();
    renderer.domElement.remove();
  }

  resize();
  fit();

  return {
    resize,
    update,
    render,
    fit,
    dispose,
    pick(clientX, clientY) {
      hoveredId = pick(clientX, clientY);
      return hoveredId;
    },
  };
}

/* ------------------------------------------------------------------------ */
/* Helpers                                                                   */
/* ------------------------------------------------------------------------ */

function makeLabel(text: string, color: string, bold: boolean): HTMLDivElement {
  const el = document.createElement('div');
  el.textContent = text;
  el.style.cssText = `
    font: ${bold ? 700 : 600} ${bold ? 11 : 10}px Inter, system-ui, sans-serif;
    color: ${color};
    background: rgba(4,6,12,0.72);
    padding: 2px 7px;
    border-radius: 3px;
    white-space: nowrap;
    pointer-events: none;
    transform: translateY(-50%);
  `;
  return el;
}

/** Soft radial glow sprite, generated once and shared by every node. */
function makeGlowTexture(): THREE.Texture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0, 'rgba(255,255,255,0.9)');
    g.addColorStop(0.35, 'rgba(255,255,255,0.22)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

/** Rebuild the FOV wedge as a fan on the ground plane. */
function updateWedge(
  mesh: THREE.Mesh,
  cx: number,
  cz: number,
  angle: number,
  half: number,
  radius: number,
): void {
  const SEGMENTS = 24;
  const verts = new Float32Array((SEGMENTS + 2) * 3);
  verts[0] = cx;
  verts[1] = 0;
  verts[2] = cz;
  for (let i = 0; i <= SEGMENTS; i++) {
    const a = angle - half + (i / SEGMENTS) * half * 2;
    verts[(i + 1) * 3] = cx + Math.cos(a) * radius;
    verts[(i + 1) * 3 + 1] = 0;
    verts[(i + 1) * 3 + 2] = cz + Math.sin(a) * radius;
  }
  const idx: number[] = [];
  for (let i = 1; i <= SEGMENTS; i++) idx.push(0, i, i + 1);

  mesh.geometry.dispose();
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(verts, 3));
  g.setIndex(idx);
  mesh.geometry = g;
}

function disposeGroup(root: THREE.Object3D): void {
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
    if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
    else mat?.dispose();
  });
}
