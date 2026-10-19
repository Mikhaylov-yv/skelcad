import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Compare, unionViewBox } from "./Compare";

vi.mock("../three/Viewer", () => ({ Viewer: (p: { url: string }) => <div data-testid="viewer">{p.url}</div> }));
vi.mock("../sketch/Sketch", () => ({
  Sketch: (p: { url: string; viewBox?: number[]; className?: string }) => (
    <div data-testid="sketch" data-viewbox={(p.viewBox ?? []).join(" ")} className={p.className}>
      {p.url}
    </div>
  ),
}));

const data = {
  summary: "",
  variants: [
    { id: "A_fork", title: "вилка", built: true, mass_kg: 15.63, k_min: 1.54, glb: "/out/bracket/A_fork/A_fork.glb" },
    { id: "B_hub", title: "ступица", built: true, mass_kg: 14.35, k_min: 1.54, glb: "/out/bracket/B_hub/B_hub.glb" },
  ],
  rows: [
    { metric: "Масса, кг", values: { A_fork: 15.63, B_hub: 14.35 }, best: ["B_hub"] },
    { metric: "Число анкеров", values: { A_fork: "4 × M20", B_hub: "4 × M20" }, best: [] },
  ],
};

const view = (vb: number[]) => ({
  svg: "",
  png: null,
  viewBox: vb,
  u: ["X", 1],
  v: ["Y", 1],
  depth: ["Z", 0],
  title: "вид сверху",
  svg_url: "",
  png_url: null,
});
const withSketch = {
  ...data,
  variants: data.variants.map((v, i) => ({
    ...v,
    sketch: { top: `/out/bracket/${v.id}/${v.id}_sketch_top.svg` },
    sketch_views: { top: view(i === 0 ? [0, 0, 100, 50] : [-20, -10, 100, 100]) },
  })),
  dim_rows: [{ id: "plate.size_X", axis: "X", views: ["top"], values: { A_fork: "120", B_hub: "160" } }],
  param_rows: [{ path: "plate.length", values: { A_fork: 120, B_hub: 160 } }],
};

describe("Сравнение", () => {
  it("общий viewBox — объединение листов", () => {
    expect(
      unionViewBox([
        [0, 0, 100, 50],
        [-20, -10, 100, 100],
      ]),
    ).toEqual([-20, -10, 120, 100]);
    expect(unionViewBox([undefined])).toBeUndefined();
  });

  it("различающиеся размеры и параметры, эскизы бок о бок в одном масштабе и наложение", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(withSketch), { status: 200 })),
    );
    render(
      <MemoryRouter initialEntries={["/p/bracket/compare"]}>
        <Routes>
          <Route path="/p/:project/compare" element={<Compare />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Размеры, которые различаются")).toBeInTheDocument();
    expect(screen.getByText("plate.size_X")).toBeInTheDocument();
    expect(screen.getByText("plate.length")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Эскизы бок о бок" }));
    fireEvent.click(screen.getByRole("button", { name: "Сверху" }));
    const sketches = screen.getAllByTestId("sketch");
    expect(sketches).toHaveLength(2);
    expect(sketches[0].getAttribute("data-viewbox")).toBe("-20 -10 120 100");
    expect(sketches[1].getAttribute("data-viewbox")).toBe("-20 -10 120 100");
    fireEvent.click(screen.getByRole("tab", { name: "Наложение" }));
    const layers = screen.getAllByTestId("sketch");
    expect(layers[0].className).toContain("sketch--was");
    expect(layers[1].className).toContain("sketch--now");
  });

  it("таблица метрик с лучшим и 3D на каждый вариант", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(data), { status: 200 })),
    );
    render(
      <MemoryRouter initialEntries={["/p/bracket/compare"]}>
        <Routes>
          <Route path="/p/:project/compare" element={<Compare />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Масса, кг")).toBeInTheDocument();
    const best = screen.getByTitle("лучший");
    expect(best).toHaveTextContent("14,35");
    expect(screen.getAllByTestId("viewer")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "B_hub" })).toHaveAttribute("href", "/p/bracket/B_hub");
  });
});
