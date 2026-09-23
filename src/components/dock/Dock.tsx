/**
 * Detail dock.
 *
 * Replaces six stacked accordions that were all collapsed by default — which
 * meant the operator had to guess which one held what, and opening two pushed
 * the viewport off screen. One tab is open at a time, the choice persists, and
 * the whole dock can be folded away when the map is all you want.
 *
 * Only the selected tab's content mounts, so hidden panels cost nothing per
 * telemetry frame.
 */
import { useCallback, useState } from 'react';
import { Icon, type IconName } from '@/components/common/Icon';
import { EventsTab } from './EventsTab';
import { RecoveryTab } from './RecoveryTab';
import { TerminalsTab } from './TerminalsTab';
import { TestsTab } from './TestsTab';
import { useTelemetry } from '@/hooks/useTelemetry';
import type { TelemetryFrame } from '@/types/telemetry';

type TabId = 'terminals' | 'recovery' | 'tests' | 'events';

const TABS: { id: TabId; icon: IconName; label: string }[] = [
  { id: 'terminals', icon: 'satellite', label: 'Terminals' },
  { id: 'recovery', icon: 'recovery', label: 'Recovery & Scenarios' },
  { id: 'tests', icon: 'flask', label: 'System Tests' },
  { id: 'events', icon: 'terminal', label: 'Event Log' },
];

const selectCount = (f: TelemetryFrame | null) => f?.terminals.length ?? 0;

export function Dock() {
  const [tab, setTab] = useState<TabId>('terminals');
  const [collapsed, setCollapsed] = useState(false);
  const terminalCount = useTelemetry(useCallback(selectCount, []));

  return (
    <section className="card dock" data-collapsed={collapsed}>
      <div className="dock__bar">
        <div className="dock__tabs" role="tablist" aria-label="Detail panels">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              className="dock__tab"
              aria-selected={!collapsed && tab === t.id}
              onClick={() => {
                setTab(t.id);
                setCollapsed(false);
              }}
            >
              <Icon name={t.icon} size={13} />
              {t.label}
              {t.id === 'terminals' && terminalCount > 0 && (
                <span className="dock__tab-badge">{terminalCount}</span>
              )}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="btn btn--icon btn--sm"
          style={{ marginLeft: 'auto' }}
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? 'Expand panel' : 'Collapse panel'}
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          <Icon
            name="chevron"
            size={13}
            style={{ transform: collapsed ? 'rotate(180deg)' : undefined }}
          />
        </button>
      </div>

      <div className="dock__body" role="tabpanel">
        {tab === 'terminals' && <TerminalsTab />}
        {tab === 'recovery' && <RecoveryTab />}
        {tab === 'tests' && <TestsTab />}
        {tab === 'events' && <EventsTab />}
      </div>
    </section>
  );
}
