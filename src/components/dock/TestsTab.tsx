/**
 * System test suite.
 *
 * Categories and their check-lists come from `/api/tests/status`, so adding a
 * suite on the Python side surfaces here with no frontend change.
 */
import { Icon } from '@/components/common/Icon';
import { useTestRunner } from '@/hooks/useTestRunner';
import type { TestCategory } from '@/types/telemetry';

function Suite({ cat }: { cat: TestCategory }) {
  const passed = cat.status === 'PASSED';
  return (
    <div className="suite">
      <div className="suite__head">
        <span className="suite__name">{cat.title}</span>
        <span className={`chip ${passed ? 'chip--ok' : 'chip--fault'}`}>
          {cat.passed}/{cat.total}
        </span>
      </div>
      <ul className="suite__items">
        {cat.items.map((item) => {
          const ok = item.status === 'PASSED';
          return (
            <li className="suite__item" key={item.name}>
              <Icon
                name={ok ? 'check' : 'cross'}
                size={11}
                className={ok ? 'text-ok' : 'text-fault'}
              />
              {item.name}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function TestsTab() {
  const { status, error, isRunning, start } = useTestRunner();

  const total = status?.total_tests ?? 0;
  const passed = status?.passed_tests ?? 0;
  const failed = status?.failed_tests ?? 0;

  return (
    <div className="stack">
      <div className="row">
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => void start()}
          disabled={isRunning}
        >
          <Icon name={isRunning ? 'spinner' : 'play'} size={12} className={isRunning ? 'spin' : undefined} />
          {isRunning ? 'Running…' : 'Run system tests'}
        </button>

        <span className={`chip ${failed > 0 ? 'chip--fault' : 'chip--ok'}`}>
          {passed} / {total} passed
        </span>
        {failed > 0 && <span className="chip chip--fault">{failed} failed</span>}

        <span className="text-muted" style={{ fontSize: 'var(--fs-small)', marginLeft: 'auto' }}>
          {error ?? status?.current_step ?? 'Ready'}
        </span>
      </div>

      <div className="progress">
        <div
          className="progress__fill"
          style={{ width: `${status?.progress_pct ?? 0}%` }}
          data-fault={failed > 0}
        />
      </div>

      <div className="grid-2">
        {status?.categories.map((cat) => <Suite key={cat.id} cat={cat} />)}
      </div>
    </div>
  );
}
