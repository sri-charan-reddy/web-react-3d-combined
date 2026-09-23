/**
 * Icon set.
 *
 * Inline SVG rather than emoji: emoji render differently on every OS, can't
 * take a colour, and sit at the wrong optical weight next to a HUD typeface.
 * These are stroked on a 16px grid, inherit `currentColor`, and stay crisp at
 * any zoom.
 */
import type { SVGProps } from 'react';

export type IconName =
  | 'satellite'
  | 'target'
  | 'recovery'
  | 'flask'
  | 'gauge'
  | 'terminal'
  | 'globe'
  | 'orbit'
  | 'camera'
  | 'crosshair'
  | 'settings'
  | 'play'
  | 'pause'
  | 'step'
  | 'reset'
  | 'zoomIn'
  | 'zoomOut'
  | 'fit'
  | 'expand'
  | 'collapse'
  | 'check'
  | 'cross'
  | 'alert'
  | 'spinner'
  | 'chevron'
  | 'close'
  | 'bolt';

/** Path data only — the wrapper supplies sizing, stroke and colour. */
const PATHS: Record<IconName, JSX.Element> = {
  satellite: (
    <>
      <path d="M5.5 8 8 5.5m-4.4.8 2.1-2.1a1 1 0 0 1 1.4 0l1.6 1.6a1 1 0 0 1 0 1.4L6.6 9.3a1 1 0 0 1-1.4 0L3.6 7.7a1 1 0 0 1 0-1.4Z" />
      <path d="m9.3 12.4 2.1-2.1a1 1 0 0 0 0-1.4L9.8 7.3a1 1 0 0 0-1.4 0l-2.1 2.1a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0Z" />
      <path d="M11 5a3 3 0 0 1 0 6M12.2 2.8a5.5 5.5 0 0 1 0 10.4" />
    </>
  ),
  target: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <circle cx="8" cy="8" r="2.2" />
      <path d="M8 .8v2.4M8 12.8v2.4M.8 8h2.4M12.8 8h2.4" />
    </>
  ),
  recovery: (
    <>
      <path d="M13.5 8a5.5 5.5 0 1 1-1.7-4" />
      <path d="M13.6 1.4v3.1h-3.1" />
    </>
  ),
  flask: (
    <>
      <path d="M6.2 1.8v3.9L2.6 12a1.4 1.4 0 0 0 1.2 2.2h8.4a1.4 1.4 0 0 0 1.2-2.2L9.8 5.7V1.8" />
      <path d="M5.2 1.8h5.6M4.4 9.8h7.2" />
    </>
  ),
  gauge: (
    <>
      <path d="M2.4 12a6.5 6.5 0 1 1 11.2 0" />
      <path d="M8 12 10.6 7" />
      <circle cx="8" cy="12" r="0.9" fill="currentColor" stroke="none" />
    </>
  ),
  terminal: (
    <>
      <rect x="1.8" y="2.8" width="12.4" height="10.4" rx="1.6" />
      <path d="M4.6 6.4 6.6 8l-2 1.6M8.4 10h3" />
    </>
  ),
  globe: (
    <>
      <circle cx="8" cy="8" r="6.2" />
      <path d="M1.8 8h12.4" />
      <path d="M8 1.8a9.6 9.6 0 0 1 0 12.4 9.6 9.6 0 0 1 0-12.4Z" />
    </>
  ),
  orbit: (
    <>
      <circle cx="8" cy="8" r="3.1" />
      <ellipse cx="8" cy="8" rx="7" ry="3.1" transform="rotate(-28 8 8)" />
    </>
  ),
  camera: (
    <>
      <path d="M2.6 4.8h2.2l1-1.6h4.4l1 1.6h2.2a1.2 1.2 0 0 1 1.2 1.2v5.6a1.2 1.2 0 0 1-1.2 1.2H2.6a1.2 1.2 0 0 1-1.2-1.2V6a1.2 1.2 0 0 1 1.2-1.2Z" />
      <circle cx="8" cy="8.8" r="2.4" />
    </>
  ),
  crosshair: (
    <>
      <circle cx="8" cy="8" r="6.2" />
      <path d="M8 1.8v4M8 10.2v4M1.8 8h4M10.2 8h4" />
    </>
  ),
  settings: (
    <>
      <circle cx="8" cy="8" r="2.3" />
      <path d="M12.9 9.8a1.1 1.1 0 0 0 .2 1.2l.1.1a1.3 1.3 0 1 1-1.9 1.9l-.1-.1a1.1 1.1 0 0 0-1.2-.2 1.1 1.1 0 0 0-.7 1v.2a1.3 1.3 0 1 1-2.6 0v-.1a1.1 1.1 0 0 0-.7-1 1.1 1.1 0 0 0-1.2.2l-.1.1a1.3 1.3 0 1 1-1.9-1.9l.1-.1a1.1 1.1 0 0 0 .2-1.2 1.1 1.1 0 0 0-1-.7h-.2a1.3 1.3 0 1 1 0-2.6h.1a1.1 1.1 0 0 0 1-.7 1.1 1.1 0 0 0-.2-1.2l-.1-.1a1.3 1.3 0 1 1 1.9-1.9l.1.1a1.1 1.1 0 0 0 1.2.2h.1a1.1 1.1 0 0 0 .7-1v-.2a1.3 1.3 0 1 1 2.6 0v.1a1.1 1.1 0 0 0 .7 1 1.1 1.1 0 0 0 1.2-.2l.1-.1a1.3 1.3 0 1 1 1.9 1.9l-.1.1a1.1 1.1 0 0 0-.2 1.2v.1a1.1 1.1 0 0 0 1 .7h.2a1.3 1.3 0 1 1 0 2.6h-.1a1.1 1.1 0 0 0-1 .7Z" />
    </>
  ),
  play: <path d="M4.8 2.9v10.2L13.2 8Z" fill="currentColor" stroke="none" />,
  pause: <path d="M5.4 3.2h1.9v9.6H5.4zM8.7 3.2h1.9v9.6H8.7z" fill="currentColor" stroke="none" />,
  step: (
    <>
      <path d="M3.6 3.4 9.8 8l-6.2 4.6Z" fill="currentColor" stroke="none" />
      <path d="M11.8 3.4v9.2" />
    </>
  ),
  reset: (
    <>
      <path d="M2.5 8a5.5 5.5 0 1 0 1.7-4" />
      <path d="M2.4 1.4v3.1h3.1" />
    </>
  ),
  zoomIn: (
    <>
      <circle cx="7.2" cy="7.2" r="4.6" />
      <path d="M10.6 10.6 14 14M7.2 5.4v3.6M5.4 7.2h3.6" />
    </>
  ),
  zoomOut: (
    <>
      <circle cx="7.2" cy="7.2" r="4.6" />
      <path d="M10.6 10.6 14 14M5.4 7.2h3.6" />
    </>
  ),
  fit: (
    <>
      <path d="M2.4 5.8V3.2a.8.8 0 0 1 .8-.8h2.6M13.6 5.8V3.2a.8.8 0 0 0-.8-.8h-2.6" />
      <path d="M2.4 10.2v2.6a.8.8 0 0 0 .8.8h2.6M13.6 10.2v2.6a.8.8 0 0 1-.8.8h-2.6" />
    </>
  ),
  expand: (
    <>
      <path d="M9.6 2.4h4v4M13.6 2.4 9.2 6.8" />
      <path d="M6.4 13.6h-4v-4M2.4 13.6l4.4-4.4" />
    </>
  ),
  collapse: (
    <>
      <path d="M13.2 6.4h-4v-4M9.2 6.4l4.4-4.4" />
      <path d="M2.8 9.6h4v4M6.8 9.6l-4.4 4.4" />
    </>
  ),
  check: <path d="m2.8 8.4 3.2 3.2 7.2-7.2" />,
  cross: <path d="m3.6 3.6 8.8 8.8M12.4 3.6l-8.8 8.8" />,
  alert: (
    <>
      <path d="M8 2.2 14.6 13H1.4Z" />
      <path d="M8 6.4v3M8 11.2h.01" />
    </>
  ),
  spinner: <path d="M8 1.6a6.4 6.4 0 1 1-6.4 6.4" />,
  chevron: <path d="m4.4 6.2 3.6 3.6 3.6-3.6" />,
  close: <path d="m4 4 8 8M12 4l-8 8" />,
  bolt: <path d="M8.8 1.4 3.4 9h3.6l-.6 5.6L12.6 7H9Z" />,
};

interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName;
  /** Rendered size in px. Defaults to 14, the inline-with-text size. */
  size?: number;
}

export function Icon({ name, size = 14, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      style={{ flex: 'none', display: 'block' }}
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}
