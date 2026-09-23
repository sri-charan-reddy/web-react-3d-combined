/**
 * Sector configuration drawer.
 *
 * Deploying terminals and picking a target is setup, not monitoring — it ran
 * once at the start of a session but occupied the top of the dashboard
 * permanently. Moving it behind the header's gear gives the viewport that space
 * back and keeps a destructive action (reconfiguring mid-run resets the sim)
 * behind a deliberate gesture.
 */
import { useEffect } from 'react';
import { Icon } from '@/components/common/Icon';
import { MAX_TERMINALS, MIN_TERMINALS, useTerminalConfig } from '@/hooks/useTerminalConfig';

interface ConfigDrawerProps {
  open: boolean;
  onClose: () => void;
  onApplied: () => void;
}

export function ConfigDrawer({ open, onClose, onApplied }: ConfigDrawerProps) {
  const config = useTerminalConfig(() => {
    onApplied();
    onClose();
  });

  // Escape closes — expected of any overlay, and the previous UI had no
  // dismissible surfaces at all.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} aria-hidden="true" />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Sector configuration">
        <div className="drawer__head">
          <h2 style={{ fontSize: 'var(--fs-lg)' }}>Sector configuration</h2>
          <button type="button" className="btn btn--icon" onClick={onClose} aria-label="Close">
            <Icon name="close" size={14} />
          </button>
        </div>

        <div className="drawer__body">
          <div className="field">
            <span className="label">Number of terminals</span>
            <div className="stepper">
              <button
                type="button"
                className="btn btn--icon"
                onClick={() => config.stepCount(-1)}
                disabled={config.count <= MIN_TERMINALS}
                aria-label="Fewer terminals"
              >
                <Icon name="zoomOut" size={14} />
              </button>
              <span className="stepper__value">{config.count}</span>
              <button
                type="button"
                className="btn btn--icon"
                onClick={() => config.stepCount(1)}
                disabled={config.count >= MAX_TERMINALS}
                aria-label="More terminals"
              >
                <Icon name="zoomIn" size={14} />
              </button>
            </div>
            <span className="field__hint">
              Sector density: {MIN_TERMINALS}–{MAX_TERMINALS} moving terminals
            </span>
          </div>

          <div className="field">
            <label className="label" htmlFor="target-select">
              Target terminal
            </label>
            <select
              id="target-select"
              className="select"
              value={config.target}
              onChange={(e) => config.setTarget(e.target.value)}
            >
              {config.options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
            <span className="field__hint">
              Communication endpoint to acquire and track. You can also click any terminal on the
              map to retarget.
            </span>
          </div>

          {config.error && (
            <p className="text-fault" style={{ fontSize: 'var(--fs-small)', margin: 0 }}>
              {config.error}
            </p>
          )}
        </div>

        <div className="drawer__foot">
          <button
            type="button"
            className="btn btn--primary"
            style={{ width: '100%' }}
            onClick={() => void config.apply()}
            disabled={config.applying}
          >
            <Icon name="bolt" size={13} />
            {config.applying ? 'Applying…' : 'Apply configuration'}
          </button>
          <p className="field__hint" style={{ marginTop: 'var(--s2)', marginBottom: 0 }}>
            Applying redeploys the sector and restarts acquisition.
          </p>
        </div>
      </aside>
    </>
  );
}
