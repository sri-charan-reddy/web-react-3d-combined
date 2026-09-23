/**
 * PAT lifecycle, as a vertical stepper.
 *
 * Vertical because the horizontal version had to fit nine to eleven nodes plus
 * arrows across a card, which truncated every label. Read top-to-bottom the
 * chain is legible at a glance, and steps behind the active one are marked
 * done rather than left looking inert.
 *
 * The panel swaps to the recovery ladder automatically when the system leaves
 * nominal operation — during a fault that is the chain you actually care about.
 */
import { useCallback } from 'react';
import { Icon } from '@/components/common/Icon';
import {
  activePrimarySteps,
  activeRecoveryStep,
  PRIMARY_PIPELINE,
  RECOVERY_PIPELINE,
  type PipelineStep,
} from '@/lib/pipelines';
import { shallowEqual, useTelemetry } from '@/hooks/useTelemetry';
import type { SystemState, TelemetryFrame } from '@/types/telemetry';

interface PipelineSlice {
  state: SystemState;
  recovering: boolean;
  failed: boolean;
  mechanism: string;
}

const selectPipeline = (frame: TelemetryFrame | null): PipelineSlice => {
  const state = (frame?.telemetry.current_state ?? 'IDLE') as SystemState;
  const fsocActive =
    frame?.telemetry.fsoc_status === 'ESTABLISHED' ||
    frame?.telemetry.fsoc_status === 'ACTIVE' ||
    state === 'FSOC_ACTIVE';
  const mechanism = frame?.telemetry.recovery_mechanism || 'NONE';
  return {
    state,
    // Show the recovery ladder whenever a recovery mechanism is engaged.
    recovering: mechanism !== 'NONE' || (!fsocActive && state !== 'IDLE'),
    failed: state === 'RECOVERY_FAILED',
    mechanism,
  };
};

function Steps({
  steps,
  activeKeys,
  fault,
}: {
  steps: PipelineStep[];
  activeKeys: ReadonlySet<string>;
  fault: boolean;
}) {
  // Everything above the active node counts as completed.
  const activeIndex = steps.findIndex((s) => activeKeys.has(s.key));

  return (
    <div className="steps">
      {steps.map((step, i) => {
        const active = activeKeys.has(step.key);
        const done = activeIndex >= 0 && i < activeIndex;
        return (
          <div
            className="step"
            key={step.key}
            data-active={active}
            data-done={done}
            data-tone={fault && active ? 'fault' : undefined}
          >
            <span className="step__node">
              {done ? (
                <Icon name="check" size={9} />
              ) : fault && active ? (
                <Icon name="cross" size={9} />
              ) : step.goal ? (
                '★'
              ) : (
                step.num
              )}
            </span>
            <span className="step__label">{step.label}</span>
          </div>
        );
      })}
    </div>
  );
}

export function PipelinePanel() {
  const p = useTelemetry(useCallback(selectPipeline, []), shallowEqual);

  const recoveryKey = activeRecoveryStep(p.state);
  const recoveryActive = new Set(recoveryKey ? [recoveryKey] : []);

  return (
    <section className="card panel">
      <div className="panel__head">
        <Icon
          name={p.failed ? 'cross' : p.recovering ? 'recovery' : 'target'}
          size={14}
          className={p.failed ? 'text-fault' : p.recovering ? 'text-warn' : 'text-info'}
        />
        <h3 className="panel__title">
          {p.failed ? 'Recovery Halted' : p.recovering ? 'Recovery Ladder' : 'PAT Pipeline'}
        </h3>
        <div className="panel__tools">
          {p.failed ? (
            <span className="chip chip--fault">REJECTED</span>
          ) : p.recovering && p.mechanism !== 'NONE' ? (
            <span className="chip chip--warn">{p.mechanism.replace(/_/g, ' ')}</span>
          ) : null}
        </div>
      </div>

      <div className="panel__body">
        {p.recovering ? (
          <Steps steps={RECOVERY_PIPELINE} activeKeys={recoveryActive} fault={p.failed} />
        ) : (
          <Steps steps={PRIMARY_PIPELINE} activeKeys={activePrimarySteps(p.state)} fault={false} />
        )}
      </div>
    </section>
  );
}
