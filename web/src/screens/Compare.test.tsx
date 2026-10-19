import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Compare } from "./Compare";

vi.mock("../three/Viewer", () => ({ Viewer: (p: { url: string }) => <div data-testid="viewer">{p.url}</div> }));

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

describe("Сравнение", () => {
  it("таблица метрик с лучшим и 3D на каждый вариант", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(data), { status: 200 })));
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
