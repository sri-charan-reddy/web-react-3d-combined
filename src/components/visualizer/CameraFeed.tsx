/**
 * Raw optical sensor feed.
 *
 * The backend serves single JPEGs, so this is a polled <img> with a
 * cache-busting query. Polling only runs while the view is mounted.
 */
import { useEffect, useState } from 'react';
import { apiUrl } from '@/api/client';
import { CAMERA_FRAME_PATH } from '@/api/endpoints';
import { useTelemetry } from '@/hooks/useTelemetry';
import type { TelemetryFrame } from '@/types/telemetry';

const REFRESH_MS = 100;
const selectDetected = (f: TelemetryFrame | null) => f?.telemetry.beacon_detected ?? false;

export function CameraFeed() {
  const [src, setSrc] = useState(() => apiUrl(CAMERA_FRAME_PATH));
  const detected = useTelemetry(selectDetected);

  useEffect(() => {
    const id = window.setInterval(
      () => setSrc(`${apiUrl(CAMERA_FRAME_PATH)}?t=${Date.now()}`),
      REFRESH_MS,
    );
    return () => window.clearInterval(id);
  }, []);

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <img src={src} alt="Optical sensor feed" />
      <div className="hud hud--bl">
        <div className="hud-card">
          <span className="hud-card__k">FOV</span>
          <span className="hud-card__v">35.0°</span>
        </div>
        <div className="hud-card">
          <span className="hud-card__k">Beacon</span>
          <span className={`hud-card__v text-${detected ? 'ok' : 'fault'}`}>
            {detected ? 'Locked' : 'Unlocked'}
          </span>
        </div>
      </div>
    </div>
  );
}
