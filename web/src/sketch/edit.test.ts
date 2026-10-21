import { describe, expect, it } from "vitest";
import type { LayoutEntity, LayoutView } from "../api";
import { applyDrag, changedFields, fieldsOf, handlesFor, withField, type Geom } from "./edit";

// главный вид: u = −Y, v = Z (как в geom/layout.py)
const main: LayoutView = {
  svg: "", png: null, viewBox: [0, 0, 100, 100], u: ["Y", -1], v: ["Z", 1], depth: ["X", 0], title: "главный вид",
  svg_url: "", png_url: null,
}; // prettier-ignore
const ent = (group: LayoutEntity["group"], kind: string, id = "e"): LayoutEntity => ({
  ref: `${group}:${id}`, group, id, kind, name: id, status: "", source: "", note: "",
}); // prettier-ignore

describe("Ручки компоновки", () => {
  it("короб обстановки: сдвиг и грани, привязка к сетке 5 мм, знак оси вида учтён", () => {
    const e = ent("surrounding", "box");
    const g: Geom = { min: [0, 100, 0], max: [50, 200, 80] };
    const hs = handlesFor(e, g, main, 500);
    expect(hs.map((h) => h.id)).toEqual(["move", "u-", "u+", "v-", "v+"]);
    // u = −Y: грань «u+» на виде — это min по Y в модели
    const uPlus = hs.find((h) => h.id === "u+")!;
    expect(uPlus.u).toBe(-100);
    const moved = applyDrag(e, g, main, "move", -23, 12); // влево по виду = +Y, вверх = +Z
    expect(moved.min).toEqual([0, 125, 10]);
    expect(moved.max).toEqual([50, 225, 90]);
    const grown = applyDrag(e, g, main, "u+", -30, 0); // тянем правую грань вправо? нет: du < 0 — влево, min по Y растёт
    expect(grown.min).toEqual([0, 130, 0]);
    const shrunk = applyDrag(e, g, main, "v+", 0, -200); // верх ниже низа невозможно: остаётся min+сетка
    expect(shrunk.max?.[2]).toBe(5);
  });

  it("цилиндр вдоль X (в лицо на главном виде): только сдвиг и диаметр", () => {
    const e = ent("surrounding", "cylinder");
    const g: Geom = { center: [0, 400, 0], axis: [1, 0, 0], diameter: 108, length: 500 };
    const ids = handlesFor(e, g, main, 500).map((h) => h.id);
    expect(ids).toEqual(["move", "d"]);
    expect(applyDrag(e, g, main, "d", 11, 0).diameter).toBe(130); // 108 + 22 → сетка 5
    expect(applyDrag(e, g, main, "move", 0, 50).center).toEqual([0, 400, 50]);
  });

  it("цилиндр вдоль Z: торцы меняют длину и центр", () => {
    const e = ent("surrounding", "cylinder");
    const g: Geom = { center: [0, 0, 100], axis: [0, 0, 1], diameter: 50, length: 200 };
    const ids = handlesFor(e, g, main, 500).map((h) => h.id);
    expect(ids).toEqual(["move", "v-", "v+", "d"]);
    const up = applyDrag(e, g, main, "v+", 0, 40);
    expect(up.length).toBe(240);
    expect(up.center).toEqual([0, 0, 120]);
    const down = applyDrag(e, g, main, "v-", 0, 40); // нижний торец вверх — длина меньше
    expect(down.length).toBe(160);
    expect(down.center).toEqual([0, 0, 120]);
  });

  it("плоскость обстановки (стена, нормаль +Y): толщина и протяжённость", () => {
    const e = ent("surrounding", "plane", "wall_body");
    const g: Geom = { origin: [0, 0, 0], normal: [0, 1, 0], extent: 300, thickness: 250 };
    const hs = handlesFor(e, g, main, 500);
    expect(hs.map((h) => h.id)).toEqual(["move", "v-", "v+", "t"]);
    const t = hs.find((h) => h.id === "t")!;
    expect(t.u).toBe(250); // задняя грань y = −250 → u = +250
    // тянем заднюю грань дальше от изделия (вправо по виду: du > 0 → y уменьшается) — толщина растёт
    expect(applyDrag(e, g, main, "t", 20, 0).thickness).toBe(270);
    expect(applyDrag(e, g, main, "v+", 0, 50).extent).toBe(350);
    // сдвиг стены — по нормали тоже можно (обстановка), база-плоскость — только по нормали
    expect(applyDrag(e, g, main, "move", -10, 0).origin).toEqual([0, 10, 0]);
    const d = ent("datum", "plane", "wall");
    const dg: Geom = { origin: [0, 0, 0], direction: [0, 1, 0] };
    expect(applyDrag(d, dg, main, "move", -10, 30).origin).toEqual([0, 10, 0]);
    // база-ось вдоль X: сдвиг поперёк (Y, Z), вдоль оси — нет
    const a = ent("datum", "axis", "axle_axis");
    const ag: Geom = { origin: [0, 200, 0], direction: [1, 0, 0] };
    expect(applyDrag(a, ag, main, "move", -50, 10).origin).toEqual([0, 250, 10]);
  });

  it("поля панели и разница для API", () => {
    const e = ent("surrounding", "plane", "wall_body");
    const g: Geom = { origin: [0, 0, 0], normal: [0, 1, 0], extent: 300, thickness: 250 };
    expect(fieldsOf(e, g).map((f) => f.path)).toEqual(["origin", "extent", "thickness"]);
    const g2 = withField(g, "extent", 400);
    expect(changedFields(e, g, g2)).toEqual({ extent: 400 });
    const i = ent("interface", "shaft_seat", "axle");
    const ig: Geom = { datum: "axle_axis", body: { center: [0, 200, 0], axis: [1, 0, 0], diameter: 50, length: 300 } };
    expect(changedFields(i, ig, withField(ig, "body.center", [0, 210, 0]))).toEqual({ "body.center": [0, 210, 0] });
    expect(fieldsOf(ent("interface", "mount_plane", "wall"), { datum: "wall", body: null })).toEqual([]);
  });
});
