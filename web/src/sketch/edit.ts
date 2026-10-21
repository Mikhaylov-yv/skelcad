// Правка компоновки на эскизе (M2.3 шаг 2): ручки у выбранной сущности и перевод перетаскивания в новые числа.
// Чистые функции без DOM: геометрия сущности (layout.json → entities[].geom) ↔ координаты вида (u, v, мм; v вверх).
import type { LayoutEntity, LayoutView } from "../api";

export type Vec3 = [number, number, number];

/** Числовые поля сущности компоновки (как отдаёт сервер в entities[].geom). */
export interface Geom {
  origin?: Vec3;
  direction?: Vec3 | null;
  normal?: Vec3;
  axis?: Vec3;
  min?: Vec3;
  max?: Vec3;
  center?: Vec3;
  diameter?: number;
  length?: number;
  extent?: number;
  thickness?: number;
  datum?: string | null;
  body?: { center: Vec3; axis: Vec3; diameter: number; length: number } | null;
}

export interface Handle {
  id: string; // move | u- | u+ | v- | v+ | d (диаметр) | t (толщина)
  u: number;
  v: number;
  kind: "move" | "size";
  cursor: string;
  title: string;
}

/** Поле, которое правится с эскиза, и его текущее значение — для панели полей. */
export interface Field {
  path: string; // origin | min | max | center | diameter | length | extent | thickness | body.center | …
  value: number | Vec3;
  label: string;
}

export const GRID = 5; // мм: сетка привязки ручек

const AX = (axis: string) => "XYZ".indexOf(axis);
const snap = (x: number, step = GRID) => Math.round(x / step) * step;
const axisIndex = (v: Vec3 | null | undefined): number | null => {
  if (!v) return null;
  const nz = v.map((c, i) => [Math.abs(c), i] as const).filter(([a]) => a > 1e-9);
  return nz.length === 1 ? nz[0][1] : null;
};
const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));

/** Вид сущности для правки: datum | interface | envelope | plane | box | cylinder. */
export function geomKind(e: LayoutEntity): string {
  return e.group === "surrounding" ? e.kind : e.group;
}

function cylBox(c: Vec3, axis: Vec3, d: number, l: number): [Vec3, Vec3] {
  const n = Math.hypot(...axis) || 1;
  const a = axis.map((x) => x / n);
  const half = a.map((ai) => (l / 2) * Math.abs(ai) + (d / 2) * Math.sqrt(Math.max(0, 1 - ai * ai)));
  return [
    [c[0] - half[0], c[1] - half[1], c[2] - half[2]],
    [c[0] + half[0], c[1] + half[1], c[2] + half[2]],
  ];
}

/** Описывающий бокс сущности в модели (мм): база — точка или отрезок длиной сцены, интерфейс — его тело. */
export function bbox3(e: LayoutEntity, g: Geom, sceneHalf: number): [Vec3, Vec3] | null {
  const k = geomKind(e);
  if (k === "datum" && g.origin) {
    const lo: Vec3 = [...g.origin];
    const hi: Vec3 = [...g.origin];
    const ax = axisIndex(g.direction);
    if (e.kind === "axis" && ax !== null) {
      lo[ax] -= sceneHalf;
      hi[ax] += sceneHalf;
    } else if (e.kind === "plane" && ax !== null) {
      for (let i = 0; i < 3; i++) {
        if (i === ax) continue;
        lo[i] -= sceneHalf;
        hi[i] += sceneHalf;
      }
    }
    return [lo, hi];
  }
  if (k === "interface") return g.body ? cylBox(g.body.center, g.body.axis, g.body.diameter, g.body.length) : null;
  if ((k === "envelope" || k === "box") && g.min && g.max) return [g.min, g.max];
  if (k === "cylinder" && g.center && g.axis && g.diameter && g.length) {
    return cylBox(g.center, g.axis, g.diameter, g.length);
  }
  if (k === "plane" && g.origin && g.normal) {
    const ext = g.extent ?? 500;
    const lo: Vec3 = [g.origin[0] - ext, g.origin[1] - ext, g.origin[2] - ext];
    const hi: Vec3 = [g.origin[0] + ext, g.origin[1] + ext, g.origin[2] + ext];
    const ax = axisIndex(g.normal);
    if (ax !== null) {
      const t = g.thickness ?? 0;
      if (g.normal[ax] > 0) {
        lo[ax] = g.origin[ax] - t;
        hi[ax] = g.origin[ax];
      } else {
        lo[ax] = g.origin[ax];
        hi[ax] = g.origin[ax] + t;
      }
    }
    return [lo, hi];
  }
  return null;
}

/** Бокс модели → бокс вида (umin, vmin, umax, vmax). */
export function viewBox(view: LayoutView, lo: Vec3, hi: Vec3): [number, number, number, number] {
  const iu = AX(view.u[0]);
  const iv = AX(view.v[0]);
  const us = [view.u[1] * lo[iu], view.u[1] * hi[iu]];
  const vs = [view.v[1] * lo[iv], view.v[1] * hi[iv]];
  return [Math.min(...us), Math.min(...vs), Math.max(...us), Math.max(...vs)];
}

const H = (id: string, u: number, v: number, cursor: string, title: string): Handle => ({
  id,
  u,
  v,
  kind: id === "move" ? "move" : "size",
  cursor,
  title,
});

/** Ручки у сущности на виде: сдвиг — у всех, грани — у коробов и зон, торцы и диаметр — у цилиндров,
 * протяжённость и толщина — у плоскостей обстановки. База-плоскость «в лицо» не правится. */
export function handlesFor(e: LayoutEntity, g: Geom, view: LayoutView, sceneHalf: number): Handle[] {
  const bb = bbox3(e, g, sceneHalf);
  if (!bb) return [];
  const [umin, vmin, umax, vmax] = viewBox(view, bb[0], bb[1]);
  const cu = (umin + umax) / 2;
  const cv = (vmin + vmax) / 2;
  const k = geomKind(e);
  const iu = AX(view.u[0]);
  const iv = AX(view.v[0]);
  const move = H("move", cu, cv, "move", "сдвинуть");
  if (k === "datum") {
    const ax = axisIndex(g.direction);
    if (e.kind === "plane" && ax !== null && ax !== iu && ax !== iv) return [];
    return [move];
  }
  const sides = (title: string): Handle[] => [
    H("u-", umin, cv, "ew-resize", title),
    H("u+", umax, cv, "ew-resize", title),
    H("v-", cu, vmin, "ns-resize", title),
    H("v+", cu, vmax, "ns-resize", title),
  ];
  if (k === "envelope" || k === "box") return [move, ...sides("грань")];
  if (k === "cylinder" || k === "interface") {
    const axis = k === "interface" ? g.body?.axis : g.axis;
    const ax = axisIndex(axis);
    if (ax === iu) {
      return [
        move,
        H("u-", umin, cv, "ew-resize", "торец"),
        H("u+", umax, cv, "ew-resize", "торец"),
        H("d", cu, vmax, "ns-resize", "диаметр"),
      ];
    }
    if (ax === iv) {
      return [
        move,
        H("v-", cu, vmin, "ns-resize", "торец"),
        H("v+", cu, vmax, "ns-resize", "торец"),
        H("d", umax, cv, "ew-resize", "диаметр"),
      ];
    }
    return [move, H("d", umax, cv, "ew-resize", "диаметр")];
  }
  if (k === "plane" && g.normal && g.origin) {
    const ax = axisIndex(g.normal);
    const t = g.thickness ?? 0;
    if (ax === iu || ax === iv) {
      const sign = ax === iu ? view.u[1] : view.v[1];
      const back = sign * (g.origin[ax] - Math.sign(g.normal[ax]) * t); // задняя грань на виде
      const ext =
        ax === iu
          ? [H("v-", cu, vmin, "ns-resize", "протяжённость"), H("v+", cu, vmax, "ns-resize", "протяжённость")]
          : [H("u-", umin, cv, "ew-resize", "протяжённость"), H("u+", umax, cv, "ew-resize", "протяжённость")];
      const thick = ax === iu ? H("t", back, cv, "ew-resize", "толщина") : H("t", cu, back, "ns-resize", "толщина");
      return [move, ...ext, thick];
    }
    return [move, ...sides("протяжённость")];
  }
  return [move];
}

/** Перетаскивание ручки (du, dv — сдвиг в мм вида, v вверх) → новая геометрия с привязкой к сетке GRID. */
export function applyDrag(e: LayoutEntity, g: Geom, view: LayoutView, handle: string, du: number, dv: number): Geom {
  const k = geomKind(e);
  const iu = AX(view.u[0]);
  const iv = AX(view.v[0]);
  const dm: Vec3 = [0, 0, 0]; // сдвиг в модели
  dm[iu] = du / view.u[1];
  dm[iv] = dv / view.v[1];
  const out = clone(g);
  const shift = (p: Vec3, only?: number[]): Vec3 =>
    p.map((c, i) => (only && !only.includes(i) ? c : snap(c + dm[i]))) as Vec3;
  if (handle === "move") {
    if (k === "datum" && out.origin) {
      const ax = axisIndex(g.direction);
      // плоскость — только по нормали; ось — поперёк оси; точка — свободно
      let only: number[] | undefined;
      if (e.kind === "plane" && ax !== null) only = [ax];
      if (e.kind === "axis" && ax !== null) only = [0, 1, 2].filter((i) => i !== ax);
      out.origin = shift(out.origin, only);
    } else if (k === "interface" && out.body) {
      out.body = { ...out.body, center: shift(out.body.center) };
    } else if ((k === "envelope" || k === "box") && out.min && out.max) {
      out.min = shift(out.min);
      out.max = shift(out.max);
    } else if (k === "cylinder" && out.center) {
      out.center = shift(out.center);
    } else if (k === "plane" && out.origin) {
      out.origin = shift(out.origin);
    }
    return out;
  }
  const i = handle.startsWith("u") ? iu : iv; // ось модели, вдоль которой стоит ручка
  const sign = handle.startsWith("u") ? view.u[1] : view.v[1];
  const plus = handle.endsWith("+");
  const end = plus === sign > 0 ? 1 : -1; // какой торец модели двигаем: +1 — max, −1 — min
  const outward = dm[i] * end; // на сколько грань ушла наружу (рост размера)
  if ((k === "envelope" || k === "box") && out.min && out.max) {
    if (end > 0) out.max[i] = Math.max(snap(out.max[i] + dm[i]), out.min[i] + GRID);
    else out.min[i] = Math.min(snap(out.min[i] + dm[i]), out.max[i] - GRID);
    return out;
  }
  if (k === "cylinder" || k === "interface") {
    const body =
      k === "interface" ? out.body : (out as { center?: Vec3; axis?: Vec3; diameter?: number; length?: number });
    if (!body || !body.center || !body.axis) return out;
    if (handle === "d") {
      // ручка стоит на «+» краю вида поперёк оси: тянем наружу — диаметр растёт
      const grow = axisIndex(body.axis) === iu ? dv : du;
      body.diameter = Math.max(GRID, snap((body.diameter ?? 0) + 2 * grow));
    } else {
      const len0 = body.length ?? 0;
      const len = Math.max(GRID, snap(len0 + outward));
      const c: Vec3 = [...body.center];
      c[i] = snap(c[i] + (end * (len - len0)) / 2);
      body.length = len;
      body.center = c;
    }
    return out;
  }
  if (k === "plane" && out.origin && out.normal) {
    const ax = axisIndex(out.normal);
    if (handle === "t" && ax !== null) {
      // задняя грань лежит против нормали: сдвиг против нормали — толщина растёт
      out.thickness = Math.max(0, snap((g.thickness ?? 0) - Math.sign(out.normal[ax]) * dm[ax]));
    } else {
      out.extent = Math.max(GRID, snap((g.extent ?? 500) + outward));
    }
    return out;
  }
  return out;
}

/** Поля для панели: что правится и текущие значения. */
export function fieldsOf(e: LayoutEntity, g: Geom): Field[] {
  const k = geomKind(e);
  if (k === "datum" && g.origin) return [{ path: "origin", value: g.origin, label: "начало (x, y, z)" }];
  if (k === "interface" && g.body) {
    return [
      { path: "body.center", value: g.body.center, label: "центр тела (x, y, z)" },
      { path: "body.diameter", value: g.body.diameter, label: "диаметр" },
      { path: "body.length", value: g.body.length, label: "длина" },
    ];
  }
  if ((k === "envelope" || k === "box") && g.min && g.max) {
    return [
      { path: "min", value: g.min, label: "min (x, y, z)" },
      { path: "max", value: g.max, label: "max (x, y, z)" },
    ];
  }
  if (k === "cylinder" && g.center) {
    return [
      { path: "center", value: g.center, label: "центр (x, y, z)" },
      { path: "diameter", value: g.diameter ?? 0, label: "диаметр" },
      { path: "length", value: g.length ?? 0, label: "длина" },
    ];
  }
  if (k === "plane" && g.origin) {
    return [
      { path: "origin", value: g.origin, label: "начало (x, y, z)" },
      { path: "extent", value: g.extent ?? 500, label: "протяжённость (полуразмер)" },
      { path: "thickness", value: g.thickness ?? 0, label: "толщина" },
    ];
  }
  return [];
}

/** Значение поля геометрии по пути (`body.center`, `extent`). */
export function fieldValue(g: Geom, path: string): number | Vec3 | undefined {
  let cur: unknown = g;
  for (const p of path.split(".")) {
    if (!cur || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur as number | Vec3 | undefined;
}

/** Геометрия с одним изменённым полем (для панели полей). */
export function withField(g: Geom, path: string, value: number | Vec3): Geom {
  const out = clone(g);
  const parts = path.split(".");
  let cur = out as unknown as Record<string, unknown>;
  for (const p of parts.slice(0, -1)) cur = (cur[p] ??= {}) as Record<string, unknown>;
  cur[parts[parts.length - 1]] = value;
  return out;
}

/** Что изменилось: {путь: значение} для API — только поля из fieldsOf с другим значением. */
export function changedFields(e: LayoutEntity, before: Geom, after: Geom): Record<string, number | Vec3> {
  const out: Record<string, number | Vec3> = {};
  for (const f of fieldsOf(e, after)) {
    const a = fieldValue(before, f.path);
    const b = fieldValue(after, f.path);
    if (b !== undefined && JSON.stringify(a) !== JSON.stringify(b)) out[f.path] = b;
  }
  return out;
}
