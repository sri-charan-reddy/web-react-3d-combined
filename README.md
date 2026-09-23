# Mission Control — React Frontend + Python Backend

A React + TypeScript rebuild of the FSOC PAT mission-control dashboard, with a
redesigned interface and a real map camera.

The Python backend lives in `backend/` and owns the simulation engine and every
`/api` route. Both applications are now in this project folder.

---

## Running it

**Development** — Vite dev server with HMR, proxying `/api` to the Python backend:

```bash
# terminal 1 — backend
npm run backend

# terminal 2 — frontend
npm install
npm run dev          # http://localhost:5173
```

Install backend dependencies once with `npm run backend:install`. The backend
listens on `http://localhost:8080`, and Vite proxies its `/api` routes there.

**Production** — build a static bundle and let the Python server host it:

```bash
npm run build
python3 backend/run_dashboard.py --ui react     # http://localhost:8080
```

`--ui legacy` (the default) still serves the original `web/` dashboard, so both
frontends remain available against the same backend. If the React build is
missing, the server warns and falls back to the legacy UI rather than 404ing.

Scripts: `npm run dev`, `backend`, `backend:install`, `build`, `preview`,
`test`, `test:watch`, `typecheck`, `lint`.

---

## Interface

```
┌────────────────────────────────────────────────────────────────┐
│ HEADER   identity · system state · target/auth/optical · live  │
├──────────────────────────────────────────┬─────────────────────┤
│ VIEWPORT  arena │ orbit 3d │ boresight │ │ RAIL                │
│           camera            …      ⤢ full│  Link status        │
│                                          │  PAT pipeline /     │
├──────────────────────────────────────────┤  recovery ladder    │
│ DOCK  terminals │ recovery │ tests │ events│ Telemetry          │
└──────────────────────────────────────────┴─────────────────────┘
```

**The viewport is the subject of the screen**, so it gets the room. The rail
holds what must stay visible. The dock holds detail one tab at a time, capped at
~32vh so it can never squeeze the map into a strip.

Sector configuration (terminal count, target selection) lives behind the header's
gear. It is setup, not monitoring — it ran once per session but used to occupy
the top of the dashboard permanently.

### Views

| Tab | What it is |
|---|---|
| **Arena** | 2D plan view. Undistorted bearings and FOV cone — the one to read angles from. |
| **Orbit 3D** | three.js scene you can orbit, zoom and pan. Spatial sense and demo piece. |
| **Boresight** | The camera's own frame with the alignment reticle and error vector. |
| **Camera** | Raw optical sensor feed from the backend. |

The **⤢ expand** button (or `Esc` to leave) lifts the viewport to a full-window
overlay. Both canvases resize through their own `ResizeObserver`, so nothing is
re-initialised on the way in or out — worth having for the 3D view especially,
which is cramped in the docked panel.

### Map camera

Zoom belongs to the map, not the document.

| Gesture | Action |
|---|---|
| Scroll / trackpad | Zoom about the cursor |
| Drag | Pan |
| Double-click, or **Fit** | Frame all terminals |
| Hover a terminal | Tooltip: RF, optical, speed, heading |
| Click a terminal | Retarget acquisition to it |

100% means "the 1280×720 world exactly fits the panel"; the range is 0.4×–6×.
The camera clamps so a hard drag can't fling the arena somewhere unrecoverable.

Page scale is left to the browser (`Cmd +/−`), which already does it correctly.

### Orbit 3D

Drag to orbit, scroll to zoom, right-drag to pan, **Reset view** to reframe. The
camera is polar-clamped so it can't drop below the ground plane, and the framing
solves for the current aspect ratio rather than sitting at a fixed pose that only
looks right in one panel shape. Hover highlights a terminal; click retargets, the
same as in 2D.

three.js is **lazy-loaded** — it is not fetched until the tab is first opened, so
the initial page stays ~66 kB gzipped and sessions that never open 3D never pay
for it. If WebGL is unavailable the tab explains itself and points at the 2D view
rather than showing a blank panel.

> **On altitude.** The simulator is strictly 2D — terminals are `[x, y]` on a
> 1280×720 plane and `camera_tilt` is always `0`. The heights in the 3D view are
> a deliberate display convention (a ground station firing up at airborne
> terminals, the usual FSOC geometry), derived deterministically from each
> terminal's id so a node holds its height rather than shimmering between
> frames. The view labels them as illustrative. **No axis encodes a value the
> backend computes.** To make elevation real, the Python simulator would need a
> Z coordinate and a true elevation angle.

---

## Why it is structured this way

### Telemetry does not flow through React state

The backend pushes a full frame at **~30 Hz**. Putting that in state or context
would re-render every panel 30 times a second.

Instead the frame lives in a small external store (`state/telemetryStore.ts`).
Components subscribe through `useTelemetry(selector)`, built on
`useSyncExternalStore`, and re-render **only when their own slice changes value**.

Measured against the original vanilla dashboard, same backend, same view:

| | DOM mutations/sec |
|---|---|
| Original `web/` | ~4,740 |
| This build | ~66 |

The original's `updateUI()` wrote `textContent` and `className` onto ~60 cached
nodes every frame unconditionally, including the five collapsed panels nobody
could see.

### Canvases bypass React entirely

`useArenaCanvas` runs the camera, pointer interaction and a `requestAnimationFrame`
loop that reads `getFrame()` straight from the store. Dragging stays smooth no
matter what the telemetry feed is doing, because panning never touches React.
Only two values are promoted to React state: the zoom percentage and the hovered
node.

Renderers (`render/arena.ts`, `render/sensor.ts`) are pure functions of
`(ctx, frame, view, clock)` — no DOM lookups, no framework coupling.

### The backend contract is typed once

`types/telemetry.ts` mirrors the Python `SystemTelemetry` payload exactly,
including `null`-vs-absent distinctions. A backend field rename surfaces as a
compile error instead of an `undefined` on screen.

### Pipelines and test categories are data, not markup

The lifecycle steps are arrays in `lib/pipelines.ts` and the active node is a
pure function of the system state. Test categories come from
`/api/tests/status`, so adding a suite on the Python side surfaces automatically.

The rail swaps the PAT pipeline for the recovery ladder on its own whenever a
recovery mechanism engages — during a fault that is the chain you actually need.

---

## Design

**Colour means state; chrome is neutral.** Greys carry the interface. Each accent
has a `-dim` value for fills and resting states, with full strength reserved for
live and alert conditions — that is what keeps a six-accent HUD from becoming
noise. Tokens live in `styles/tokens.css`.

**Caps are for labels only.** Everything used to be ALL-CAPS letterspaced, so
nothing stood out. Now small labels are capped; values and body text are normal
case, and numeric readouts are tabular-figure mono so digits don't jitter at 30 Hz.

**Icons are inline SVG** (`components/common/Icon.tsx`), stroked on a 16px grid
and inheriting `currentColor`. The emoji they replace rendered differently on
every OS and couldn't take a colour.

**Two views, each honest about what it is for.** The Arena stays a true plan
view: a tilted projection would look showier but distorts the camera azimuth and
FOV cone against real bearings, which is the whole point of that view. Depth
there comes from lighting instead — a parallaxed starfield, a subdividing grid,
cast shadows under nodes, volumetric bloom on the beam with travelling data
pulses, and a lock reticle once the link is established. Orbit 3D is where actual
perspective lives, and it is a separate tab precisely so neither view has to
compromise.

Canvas colours are mirrored as literals in `render/palette.ts` because Canvas2D
cannot read CSS custom properties. Change both together.

---

## Layout

```
src/
├── api/            HTTP transport + one named function per endpoint
├── types/          Backend wire contract (single source of truth)
├── state/          telemetryStore (external, 30 Hz) · WorkspaceContext (active tab)
├── hooks/          useTelemetry (selectors) · useTelemetryStream (SSE + backoff)
│                   useArenaCanvas (camera + interaction + render loop)
│                   useTestRunner · useDisturbance · useTerminalConfig
├── lib/            derive.ts (mission status) · pipelines.ts (lifecycle steps)
├── render/         camera.ts · arena.ts · sensor.ts · scene3d.ts · palette · trails
├── components/
│   ├── common/     Icon · ErrorBoundary
│   ├── layout/     Header
│   ├── visualizer/ Viewport · ArenaCanvas · OrbitCanvas · SensorCanvas · CameraFeed
│   ├── rail/       LinkPanel · PipelinePanel · TelemetryPanel
│   ├── dock/       Dock · TerminalsTab · RecoveryTab · TestsTab · EventsTab
│   └── config/     ConfigDrawer
└── styles/         tokens · base · layout · panels
```

---

## Verification

- `npm run typecheck`, `npm run lint` — clean, `strict: true`, no warnings.
- `npm run test` — 16 unit tests covering the camera maths (cursor anchoring is
  exact at every anchor point and zoom factor, scale clamping, fit centring,
  world↔screen round-trip, pan clamping) and the pipeline state mapping.
- Interaction paths exercised against the live backend: wheel zoom, drag pan,
  fit, hover tooltips, click-to-retarget (verified the backend target actually
  changed), tab switching, disturbance toggles, scenario triggers, test runner,
  full-screen expand and `Esc`.
- 3D specifically: WebGL context is created and disposed with the tab — twelve
  rapid tab switches leave exactly one canvas and no context warnings. Verified
  the `three` chunk is absent from the network log until the tab is opened.

---

## Known differences from the original

All deliberate:

1. **Page zoom is gone**, replaced by the map camera. The old control scaled the
   whole document with a CSS transform: at 150% it clipped content 664px off the
   right behind a sticky header, at 50% it left 320px of dead space each side,
   and it duplicated the browser's own zoom. Use `Cmd +/−` for page scale.
2. **Six accordions became a four-tab dock.** They were all collapsed by default,
   so the operator had to guess which one held what, and opening two pushed the
   viewport off screen.
3. **Sector config moved behind the gear.** Reconfiguring restarts acquisition,
   so it now sits behind a deliberate gesture rather than at the top of a live
   monitoring view.
4. **Clearing the event log is local to the view.** The backend keeps its own
   ring buffer; the original cleared the DOM and let the next frame repopulate
   it, which made the button look broken.
5. **Hidden panels are unmounted**, so they cost nothing per telemetry frame.
