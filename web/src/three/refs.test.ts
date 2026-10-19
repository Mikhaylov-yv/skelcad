import { describe, expect, it } from "vitest";
import { indexNodes, nodesForRef } from "./refs";
import type { Report } from "../api";

const report = {
  parts: [
    { id: "base_plate", name: "Плита", role: "base_plate" },
    { id: "cheek_L", name: "Щека левая", role: "cheek" },
    { id: "cheek_R", name: "Щека правая", role: "cheek" },
  ],
  welds: [{ id: "w_cheek_L_in", parts: ["base_plate", "cheek_L"] }],
  findings: [{ level: "info", code: "X", ref: "fastener:anchor_a00", message: "" }],
} as unknown as Report;
const top = ["base_plate", "cheek_L", "cheek_R", "anchor_a00", "anchor_a01", "axle"];

describe("ссылки → узлы GLB", () => {
  const idx = indexNodes(report, top);
  it("делит верхние узлы на детали, крепёж и прочее", () => {
    expect(idx.parts).toEqual(["base_plate", "cheek_L", "cheek_R"]);
    expect(idx.fasteners).toEqual(["anchor_a00", "anchor_a01"]);
    expect(idx.other).toEqual(["axle"]);
  });
  it("разбирает ссылки замечаний и расчётов", () => {
    expect(nodesForRef("part:cheek_L/hole:bore", report, idx)).toEqual(["cheek_L"]);
    expect(nodesForRef("part:cheek", report, idx)).toEqual(["cheek_L", "cheek_R"]);
    expect(nodesForRef("weld:w_cheek_L_in", report, idx)).toEqual(["base_plate", "cheek_L"]);
    expect(nodesForRef("fastener:anchor_a01", report, idx)).toEqual(["anchor_a01"]);
    expect(nodesForRef("fasteners", report, idx)).toEqual(["anchor_a00", "anchor_a01"]);
    expect(nodesForRef("interface:axle", report, idx)).toEqual(["axle"]);
    expect(nodesForRef("section:wall", report, idx)).toEqual([]);
    expect(nodesForRef("assembly", report, idx)).toEqual([]);
  });
});
