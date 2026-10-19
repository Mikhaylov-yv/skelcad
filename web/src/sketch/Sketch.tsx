// Плоский эскиз (компоновка, позже — эскиз варианта): SVG сервера встраивается в страницу, масштаб колесом,
// сдвиг перетаскиванием, наведение и клик по сущностям (data-ref), пометки замечаний в координатах модели.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type LayoutView } from "../api";
import { S } from "../strings";

export interface SketchPin {
  id: string;
  point: [number, number, number]; // мм, координаты модели
  resolved?: boolean;
}

export interface SketchProps {
  url: string; // SVG
  view: LayoutView; // оси вида: куда отображаются координаты модели
  selected: string[]; // data-ref сущностей для подсветки
  pins?: SketchPin[];
  pinMode?: boolean;
  fitNonce?: number; // «Вписать»
  onPick?: (ref: string | null, point?: [number, number, number]) => void;
  onHover?: (ref: string | null) => void;
  viewBox?: number[]; // общий viewBox (сравнение в одном масштабе, наложение)
  className?: string;
}

/** Точка модели → координаты вида (u, v): u = знак·координата по оси вида. */
export function toView(view: LayoutView, p: [number, number, number]): [number, number] {
  const idx = (axis: string) => "XYZ".indexOf(axis);
  return [view.u[1] * p[idx(view.u[0])], view.v[1] * p[idx(view.v[0])]];
}

/** Координаты вида → точка модели; координата вдоль взгляда — centre сцены (depth). */
export function fromView(view: LayoutView, u: number, v: number): [number, number, number] {
  const out: [number, number, number] = [0, 0, 0];
  const idx = (axis: string) => "XYZ".indexOf(axis);
  out[idx(view.u[0])] = u / view.u[1];
  out[idx(view.v[0])] = v / view.v[1];
  out[idx(view.depth[0])] = view.depth[1];
  return out;
}

export function Sketch({
  url,
  view,
  selected,
  pins,
  pinMode,
  fitNonce,
  onPick,
  onHover,
  viewBox,
  className,
}: SketchProps) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const host = useRef<HTMLDivElement>(null);
  const [tf, setTf] = useState({ x: 0, y: 0, k: 1 });
  const drag = useRef<{
    x: number;
    y: number;
    tx: number;
    ty: number;
    moved: boolean;
  } | null>(null);

  useEffect(() => {
    let alive = true;
    setSvg(null);
    setError(null);
    api
      .text(url)
      .then((t) => alive && setSvg(t))
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [url]);
  useEffect(() => setTf({ x: 0, y: 0, k: 1 }), [fitNonce, url]);

  // общий viewBox: одинаковый масштаб и начало координат у нескольких эскизов
  useEffect(() => {
    const root = host.current?.querySelector("svg");
    if (!root || !svg) return;
    if (viewBox && viewBox.length === 4) root.setAttribute("viewBox", viewBox.join(" "));
  }, [svg, viewBox]);

  // подсветка выбранных сущностей
  useEffect(() => {
    const root = host.current;
    if (!root || !svg) return;
    root.querySelectorAll("[data-ref].selected").forEach((el) => el.classList.remove("selected"));
    for (const ref of selected) {
      root.querySelectorAll(`[data-ref="${CSS.escape(ref)}"]`).forEach((el) => el.classList.add("selected"));
    }
  }, [selected, svg]);

  // пометки: группа кружков внутри SVG, в координатах вида
  const pinKey = useMemo(() => JSON.stringify(pins ?? []), [pins]);
  useEffect(() => {
    const root = host.current?.querySelector("svg");
    if (!root || !svg) return;
    root.querySelector("g.pins")?.remove();
    if (!pins || pins.length === 0) return;
    const vb = view.viewBox;
    const r = Math.max(vb[2], vb[3]) / 70;
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "pins");
    for (const p of pins) {
      const [u, v] = toView(view, p.point);
      const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("cx", String(u));
      c.setAttribute("cy", String(-v));
      c.setAttribute("r", String(r));
      c.setAttribute("fill", p.resolved ? "#1b7f3b" : "#f2b705");
      c.setAttribute("fill-opacity", "0.85");
      c.setAttribute("stroke", "#1b1f24");
      c.setAttribute("stroke-width", String(r / 6));
      c.setAttribute("data-pin", p.id);
      const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
      t.textContent = p.id;
      c.appendChild(t);
      g.appendChild(c);
    }
    root.appendChild(g);
  }, [pinKey, pins, svg, view]);

  const refAt = (target: EventTarget | null): string | null => {
    const el = (target as Element | null)?.closest?.("[data-ref]") as Element | null;
    return el?.getAttribute("data-ref") ?? null;
  };

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const box = host.current?.getBoundingClientRect();
    if (!box) return;
    const mx = e.clientX - box.left;
    const my = e.clientY - box.top;
    setTf((t) => {
      const k = Math.min(20, Math.max(0.2, t.k * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
      // масштаб вокруг курсора
      return {
        k,
        x: mx - ((mx - t.x) * k) / t.k,
        y: my - ((my - t.y) * k) / t.k,
      };
    });
  }, []);

  const onDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    drag.current = {
      x: e.clientX,
      y: e.clientY,
      tx: tf.x,
      ty: tf.y,
      moved: false,
    };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    if (d.moved) setTf((t) => ({ ...t, x: d.tx + dx, y: d.ty + dy }));
  };
  const onUp = (e: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d || d.moved) return;
    // клик без перетаскивания: сущность под курсором и точка модели
    const svgEl = host.current?.querySelector("svg");
    let point: [number, number, number] | undefined;
    if (svgEl) {
      const ctm = svgEl.getScreenCTM?.();
      if (ctm) {
        const pt = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
        point = fromView(view, pt.x, -pt.y);
      }
    }
    onPick?.(refAt(e.target), point);
  };

  return (
    <div
      className={"sketch" + (pinMode ? " sketch--pinning" : "") + (className ? " " + className : "")}
      ref={host}
      onWheel={onWheel}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onMouseOver={(e) => onHover?.(refAt(e.target))}
      onMouseOut={() => onHover?.(null)}
      role="img"
      aria-label={view.title}
    >
      {error && (
        <p className="canvas__note level-error" role="alert">
          {error}
        </p>
      )}
      {!svg && !error && <p className="canvas__note muted">{S.layout.loading}</p>}
      {svg && (
        <div
          className="sketch__inner"
          style={{
            transform: `translate(${tf.x}px, ${tf.y}px) scale(${tf.k})`,
            transformOrigin: "0 0",
          }}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      )}
    </div>
  );
}
