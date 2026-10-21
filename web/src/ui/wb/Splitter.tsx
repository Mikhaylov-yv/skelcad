import { useEffect, useRef, useState } from "react";
import { S } from "../../strings";

/** Ширина панели, запомненная в localStorage; за пределами [min, max] — подрезается при чтении. */
export function useStoredWidth(key: string, fallback: number): [number, (w: number) => void] {
  const [w, setW] = useState(() => {
    try {
      const v = Number(localStorage.getItem(key));
      return Number.isFinite(v) && v > 0 ? v : fallback;
    } catch {
      return fallback;
    }
  });
  const set = (v: number) => {
    setW(v);
    try {
      localStorage.setItem(key, String(Math.round(v)));
    } catch {
      /* приватный режим — ширина живёт до перезагрузки */
    }
  };
  return [w, set];
}

export function useWindowWidth(): number {
  const [w, setW] = useState(() => window.innerWidth);
  useEffect(() => {
    const on = () => setW(window.innerWidth);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return w;
}

export const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), Math.max(min, max));

/** Разделитель на краю панели: тянется мышью и пальцем, стрелками с клавиатуры, двойной щелчок — ширина по
 *  умолчанию. edge — на каком краю панели он стоит: "end" (панель слева, тянем её правый край) или "start"
 *  (панель справа, тянем левый край). */
export function Splitter({
  edge,
  value,
  min,
  max,
  fallback,
  onChange,
  label,
}: {
  edge: "start" | "end";
  value: number;
  min: number;
  max: number;
  fallback: number;
  onChange: (w: number) => void;
  label: string;
}) {
  const start = useRef<{ x: number; w: number } | null>(null);
  const apply = (dx: number) => onChange(clamp(start.current!.w + (edge === "start" ? -dx : dx), min, max));
  return (
    <div
      className={"wb__split wb__split--" + edge}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={Math.round(value)}
      aria-valuemin={min}
      aria-valuemax={Math.round(max)}
      tabIndex={0}
      title={S.wb.resizeHint}
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        start.current = { x: e.clientX, w: value };
        e.currentTarget.setPointerCapture(e.pointerId);
        e.preventDefault();
      }}
      onPointerMove={(e) => {
        if (start.current) apply(e.clientX - start.current.x);
      }}
      onPointerUp={() => {
        start.current = null;
      }}
      onPointerCancel={() => {
        start.current = null;
      }}
      onDoubleClick={() => onChange(fallback)}
      onKeyDown={(e) => {
        const step = e.shiftKey ? 48 : 16;
        const dir = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0;
        if (!dir) return;
        e.preventDefault();
        onChange(clamp(value + (edge === "start" ? -dir : dir) * step, min, max));
      }}
    />
  );
}
