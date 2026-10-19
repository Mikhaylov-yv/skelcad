import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Variant } from "./Variant";

vi.mock("../three/Viewer", async () => {
  const React = await import("react");
  return {
    Viewer: (p: { selected: string[]; onNodes?: (n: string[]) => void }) => {
      const { onNodes } = p;
      React.useEffect(() => {
        onNodes?.(["base_plate", "cheek_L", "anchor_a00"]);
      }, [onNodes]);
      return <div data-testid="viewer">выделено: {p.selected.join(",")}</div>;
    },
  };
});

const report = {
  project: "bracket",
  project_title: "Кронштейн",
  variant: "A_fork",
  title: "вилка",
  summary: { mass_kg: 15.63, K_min: 1.54, K_min_item: "Плита", findings: { error: 0, warning: 1, info: 2 } },
  parts: [
    { id: "base_plate", name: "Плита опорная", mass_kg: 10 },
    { id: "cheek_L", name: "Щека левая", mass_kg: 2.82 },
  ],
  welds: [{ id: "w1", parts: ["base_plate", "cheek_L"], leg: 8, length: 200 }],
  calc: [{ id: "plate_bend", title: "Изгиб плиты", K: 1.54, K_req: 1.5, ok: true, ref: "part:base_plate" }],
  findings: [
    { level: "warning", code: "R-WELD-ACCESS", ref: "weld:w1", message: "Шов на дне щели", source: "rules.gost" },
    { level: "info", code: "R-BORE", ref: "part:cheek_L/hole:bore", message: "Кольцо 25 мм" },
    { level: "info", code: "R-BORE", ref: "part:cheek_R/hole:bore", message: "Кольцо 25 мм" },
  ],
  assumptions: [{ id: "G1", text: "Нагрузка на один кронштейн" }],
  urls: { glb: "/out/bracket/A_fork/A_fork.glb", step: "/out/bracket/A_fork/A_fork_assembly.step", svg: {} },
  built_at: new Date().toISOString(),
};

function mount(path = "/p/bracket/A_fork") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/p/:project/:variant" element={<Variant />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Вариант", () => {
  it("показывает числа, замечания и подсвечивает детали шва по клику", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(report), { status: 200 })),
    );
    mount();
    expect(await screen.findByText("Кронштейн · вилка")).toBeInTheDocument();
    expect(screen.getByText("Шов на дне щели")).toBeInTheDocument();
    expect(screen.queryByText("Кольцо 25 мм")).not.toBeInTheDocument(); // info свёрнуты
    fireEvent.click(screen.getByRole("button", { name: "weld:w1" }));
    expect(screen.getByTestId("viewer")).toHaveTextContent("выделено: base_plate,cheek_L");
    fireEvent.click(screen.getByRole("button", { name: "Показать" }));
    expect(screen.getAllByText("Кольцо 25 мм")).toHaveLength(2);
  });

  it("берёт выделение из адреса ?part=", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(report), { status: 200 })),
    );
    mount("/p/bracket/A_fork?part=cheek_L");
    expect(await screen.findByTestId("viewer")).toHaveTextContent("выделено: cheek_L");
  });

  it("нет 3D в комплекте: объясняет причину и предлагает собрать заново прямо в окне 3D", async () => {
    const noGlb = { ...report, urls: { ...report.urls, glb: null } };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(noGlb), { status: 200 })),
    );
    mount();
    expect(await screen.findByText("3D-модели в комплекте сборки нет.")).toBeInTheDocument();
    expect(screen.getByText(/build с export=false/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Собрать заново" })).toHaveLength(2); // шапка и окно 3D
    expect(screen.queryByTestId("viewer")).not.toBeInTheDocument();
  });

  it("геометрия старше отчёта: предупреждает, что 3D от прошлой сборки", async () => {
    const stale = { ...report, geometry_at: new Date(Date.now() - 3 * 3600_000).toISOString() };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(stale), { status: 200 })),
    );
    mount();
    expect(await screen.findByRole("status")).toHaveTextContent(/3D от сборки .*пересобирали без геометрии/);
  });

  it("несобранный вариант: объясняет и предлагает собрать", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: "вариант «A_fork» ещё не собран" }), { status: 404 })),
    );
    mount();
    expect(await screen.findByText("Вариант ещё не собран.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Собрать" })).toBeInTheDocument();
  });
});
