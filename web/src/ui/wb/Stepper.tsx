import { Fragment } from "react";
import type { ProjectOverview, StageId } from "../../api";
import { S } from "../../strings";

export const STAGE_IDS: StageId[] = ["brief", "layout", "design", "kit"];

/** Этапы изделия в шапке: номер или галочка, янтарный — ждёт конструктора, синий — у агента или следующий. */
export function Stepper({ p, stage, onStage }: { p: ProjectOverview; stage: StageId; onStage: (s: StageId) => void }) {
  const names = p.aggregate ? S.wb.aggStages : S.wb.stages;
  return (
    <div className="stepper" role="tablist" aria-label={S.wb.stagesLabel}>
      {STAGE_IDS.map((id, i) => {
        const st = p.stages[id];
        return (
          <Fragment key={id}>
            {i > 0 && <span className="stepper__sep" aria-hidden="true" />}
            <button
              type="button"
              role="tab"
              aria-selected={id === stage}
              className={"stepper__item" + (id === stage ? " cur" : "")}
              onClick={() => onStage(id)}
              title={S.wb.stageState[st]}
            >
              <span className={"stepper__n stepper__n--" + st}>{st === "done" ? "✓" : i + 1}</span>
              {names[id]}
            </button>
          </Fragment>
        );
      })}
    </div>
  );
}
