/**
 * Canvas palette.
 *
 * Canvas2D can't read CSS custom properties, so the HUD colours are mirrored
 * here as literals. They track `styles/tokens.css` — change both together.
 */
export const palette = {
  space: '#04060c',

  teal: '#2dd4bf',
  tealPale: '#99f6e4',
  tealDeep: '#0d3b36',

  cyan: '#38bdf8',
  cyanBright: '#7dd3fc',

  amber: '#fbbf24',
  amberPale: '#fcd34d',

  rose: '#fb7185',
  violet: '#a78bfa',

  slate: '#56637a',
  slateText: '#8b97ad',
  white: '#ffffff',
} as const;

export const fonts = {
  /** Label typeface for canvas text; matches the UI stack. */
  family: "Inter, system-ui, -apple-system, sans-serif",
  mono: "'JetBrains Mono', ui-monospace, Menlo, monospace",
} as const;

/** Arena geometry, matching the simulator's 1280x720 world. */
export const geometry = {
  width: 1280,
  height: 720,
  gridSize: 80,
  coneRadius: 650,
  rfBroadcastRadius: 400,
  targetTrailLength: 90,
  otherTrailLength: 26,
} as const;
