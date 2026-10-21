// Плоский эскиз (компоновка, позже — эскиз варианта): SVG сервера встраивается в страницу, масштаб колесом,
// сдвиг перетаскиванием, наведение и клик по сущностям (data-ref), пометки замечаний в координатах модели.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type LayoutView } from "../api";
import { S } from "../strings";
import type { Handle } from "./edit";

export interface SketchPin {
  id: string;
  point: [number, number, number]; // мм, координаты модели
  resolved?: boolean;
}

export interface SketchStroke {
  id: string;
  points: [number, number, number][]; // мм, координаты модели (вид — тот, на котором рисуется)
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
  // правка компоновки (M2.3): ручки у выбранной сущности, контур черновика, перетаскивание ручки
  handles?: Handle[];
  ghost?: [number, number, number, number] | null; // (umin, vmin, umax, vmax) в координатах вида
  onHandleDrag?: (id: string, du: number, dv: number, done: boolean) => void;
  // росчерки пометок (M2.3 шаг 3): готовые — ломаные поверх эскиза; drawMode — рисование нового
  strokes?: SketchStroke[];
  drawMode?: boolean;
  onStroke?: (points: [number, number, number][]) => void;
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
  handles,
  ghost,
  onHandleDrag,
  strokes,
  drawMode,
  onStroke,
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
    ref: string | null;
    handle: string | null; // перетаскивается ручка правки, а не лист
    su: number; // точка начала в координатах вида
    sv: number;
    draw: [number, number][] | null; // рисуется росчерк: точки в координатах вида
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

  // росчерки пометок: ломаные внутри SVG, в координатах вида
  const strokeKey = useMemo(() => JSON.stringify(strokes ?? []), [strokes]);
  useEffect(() => {
    const root = host.current?.querySelector("svg");
    if (!root || !svg) return;
    root.querySelector("g.strokes")?.remove();
    if (!strokes || strokes.length === 0) return;
    const vb = view.viewBox;
    const w = Math.max(vb[2], vb[3]) / 400;
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "strokes");
    for (const st of strokes) {
      if (st.points.length < 2) continue;
      const pts = st.points.map((p) => toView(view, p));
      const pl = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      pl.setAttribute("points", pts.map(([u, v]) => `${u},${-v}`).join(" "));
      pl.setAttribute("stroke-width", String(w));
      pl.setAttribute("class", st.resolved ? "resolved" : "");
      pl.setAttribute("data-stroke", st.id);
      const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
      t.textContent = st.id;
      pl.appendChild(t);
      g.appendChild(pl);
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", String(pts[0][0] + w * 2));
      label.setAttribute("y", String(-pts[0][1] - w * 2));
      label.textContent = st.id;
      g.appendChild(label);
    }
    root.appendChild(g);
  }, [strokeKey, strokes, svg, view]);

  /** Рисование росчерка: временная ломаная обновляется прямо в DOM, без перерисовки React. */
  const liveStroke = (pts: [number, number][] | null) => {
    const root = host.current?.querySelector("svg");
    if (!root) return;
    let g = root.querySelector("g.strokes");
    if (!g) {
      g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", "strokes");
      root.appendChild(g);
    }
    g.querySelector("polyline.live")?.remove();
    if (!pts || pts.length < 2) return;
    const vb = view.viewBox;
    const pl = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    pl.setAttribute("class", "live");
    pl.setAttribute("points", pts.map(([u, v]) => `${u},${-v}`).join(" "));
    pl.setAttribute("stroke-width", String(Math.max(vb[2], vb[3]) / 400));
    g.appendChild(pl);
  };

  // ручки правки и контур черновика: группа внутри SVG, в координатах вида
  const handleKey = useMemo(() => JSON.stringify([handles ?? [], ghost ?? null]), [handles, ghost]);
  useEffect(() => {
    const root = host.current?.querySelector("svg");
    if (!root || !svg) return;
    root.querySelector("g.handles")?.remove();
    if ((!handles || handles.length === 0) && !ghost) return;
    const vb = view.viewBox;
    const r = Math.max(vb[2], vb[3]) / 90;
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "handles");
    if (ghost) {
      const [umin, vmin, umax, vmax] = ghost;
      const rc = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rc.setAttribute("class", "ghost");
      rc.setAttribute("x", String(umin));
      rc.setAttribute("y", String(-vmax));
      rc.setAttribute("width", String(Math.max(0, umax - umin)));
      rc.setAttribute("height", String(Math.max(0, vmax - vmin)));
      g.appendChild(rc);
    }
    for (const h of handles ?? []) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", h.kind === "move" ? "circle" : "rect");
      if (h.kind === "move") {
        el.setAttribute("cx", String(h.u));
        el.setAttribute("cy", String(-h.v));
        el.setAttribute("r", String(r));
      } else {
        el.setAttribute("x", String(h.u - r * 0.8));
        el.setAttribute("y", String(-h.v - r * 0.8));
        el.setAttribute("width", String(r * 1.6));
        el.setAttribute("height", String(r * 1.6));
      }
      el.setAttribute("data-handle", h.id);
      el.setAttribute("style", `cursor: ${h.cursor}`);
      const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
      t.textContent = h.title;
      el.appendChild(t);
      g.appendChild(el);
    }
    root.appendChild(g);
  }, [handleKey, handles, ghost, svg, view]);

  const refAt = (target: EventTarget | null): string | null => {
    const el = (target as Element | null)?.closest?.("[data-ref]") as Element | null;
    return el?.getAttribute("data-ref") ?? null;
  };
  const handleAt = (target: EventTarget | null): string | null => {
    const el = (target as Element | null)?.closest?.("[data-handle]") as Element | null;
    return el?.getAttribute("data-handle") ?? null;
  };
  /** Точка указателя в координатах вида (u, v): через матрицу SVG; null, если SVG ещё нет. */
  const viewPoint = (clientX: number, clientY: number): [number, number] | null => {
    const svgEl = host.current?.querySelector("svg");
    const ctm = svgEl?.getScreenCTM?.();
    if (!ctm) return null;
    const pt = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
    return [pt.x, -pt.y];
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
    const handle = onHandleDrag ? handleAt(e.target) : null;
    const start = handle || (drawMode && onStroke) ? viewPoint(e.clientX, e.clientY) : null;
    drag.current = {
      x: e.clientX,
      y: e.clientY,
      tx: tf.x,
      ty: tf.y,
      moved: false,
      ref: refAt(e.target),
      handle: start ? handle : null,
      su: start?.[0] ?? 0,
      sv: start?.[1] ?? 0,
      draw: !handle && drawMode && onStroke && start ? [start] : null,
    };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    if (!d.moved) return;
    if (d.draw) {
      const p = viewPoint(e.clientX, e.clientY);
      const last = d.draw[d.draw.length - 1];
      if (p && Math.hypot(p[0] - last[0], p[1] - last[1]) >= Math.max(view.viewBox[2], view.viewBox[3]) / 300) {
        d.draw.push(p);
        liveStroke(d.draw);
      }
      return;
    }
    if (d.handle) {
      const p = viewPoint(e.clientX, e.clientY);
      if (p) onHandleDrag?.(d.handle, p[0] - d.su, p[1] - d.sv, false);
      return;
    }
    setTf((t) => ({ ...t, x: d.tx + dx, y: d.ty + dy }));
  };
  const onUp = (e: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (d.draw) {
      liveStroke(null);
      if (d.moved && d.draw.length >= 2) onStroke?.(d.draw.map(([u, v]) => fromView(view, u, v)));
      return;
    }
    if (d.handle) {
      const p = viewPoint(e.clientX, e.clientY);
      if (d.moved && p) onHandleDrag?.(d.handle, p[0] - d.su, p[1] - d.sv, true);
      return;
    }
    if (d.moved) return;
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
    onPick?.(d.ref, point); // при захвате указателя pointerup приходит на контейнер — сущность берём с pointerdown
  };

  return (
    <div
      className={
        "sketch" +
        (pinMode ? " sketch--pinning" : "") +
        (drawMode ? " sketch--drawing" : "") +
        (handles && handles.length ? " sketch--editing" : "") +
        (className ? " " + className : "")
      }
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
