import { useEffect, useState } from "react";
import { api, type ProjectOverview } from "../api";

/** Состояние проекта (у конструктора / у агента) с опросом раз в N секунд, пока экран открыт. */
export function useProjectState(project: string, everyMs = 5000): ProjectOverview | null {
  const [st, setSt] = useState<ProjectOverview | null>(null);
  useEffect(() => {
    let alive = true;
    const tick = () =>
      api
        .projects()
        .then((r) => alive && setSt(r.projects.find((p) => p.name === project) ?? null))
        .catch(() => undefined);
    tick();
    const h = window.setInterval(tick, everyMs);
    return () => {
      alive = false;
      window.clearInterval(h);
    };
  }, [project, everyMs]);
  return st;
}
