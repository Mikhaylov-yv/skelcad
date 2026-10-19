import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Variant } from "./Variant";

// мок вьюера: кнопка «клик по модели» вызывает onPick с деталью и точкой; показывает число пометок
vi.mock("../three/Viewer", async () => {
  const React = await import("react");
  return {
    Viewer: (p: { pins?: unknown[]; onNodes?: (n: string[]) => void; onPick?: (n: string | null, pt?: number[]) => void }) => {
      const { onNodes } = p;
      React.useEffect(() => {
        onNodes?.(["base_plate", "anchor_a00"]);
      }, [onNodes]);
      return (
        <div data-testid="viewer">
          пометок: {p.pins?.length ?? 0}
          <button onClick={() => p.onPick?.("anchor_a00", [95, 0, -100])}>клик по модели</button>
        </div>
      );
    },
  };
});

const report = {
  project: "bracket", project_title: "Кронштейн", variant: "A_fork", title: "вилка",
  summary: { mass_kg: 15.63, K_min: 1.54, findings: { error: 0, warning: 0, info: 0 } },
  parts: [{ id: "base_plate", name: "Плита", mass_kg: 10 }], welds: [], calc: [], findings: [], assumptions: [],
  urls: { glb: "/out/bracket/A_fork/A_fork.glb", step: null, svg: {} }, built_at: new Date().toISOString(),
};

describe("Замечания агенту", () => {
  it("пометка на модели → текст → review.yaml; пометка видна в 3D", async () => {
    let items: unknown[] = [];
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push((init?.method ?? "GET") + " " + url);
        if (url.endsWith("/review") && init?.method === "POST") {
          const b = JSON.parse(init.body as string);
          items = [{ id: "R1", text: b.text, status: "open", author: "ivanov", created: "", variant: b.variant, part: b.part, point: b.point }];
          return new Response(JSON.stringify({ item: items[0] }), { status: 200 });
        }
        if (url.includes("/review")) return new Response(JSON.stringify({ items }), { status: 200 });
        return new Response(JSON.stringify(report), { status: 200 });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/p/bracket/A_fork"]}>
        <Routes>
          <Route path="/p/:project/:variant" element={<Variant />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("Кронштейн · вилка");
    expect(screen.getByText(/Поставьте пометку/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Пометить на модели" }));
    expect(screen.getByText(/Кликните по детали/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "клик по модели" }));
    expect(screen.getByText("пометка: anchor_a00 · точка 95, 0, -100 мм")).toBeInTheDocument();
    expect(screen.getByTestId("viewer")).toHaveTextContent("пометок: 1");
    fireEvent.click(screen.getByRole("button", { name: "Отправить агенту" }));
    expect(await screen.findByText("Нужен текст замечания")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Текст замечания"), { target: { value: "мало места под ключ" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить агенту" }));
    await waitFor(() => expect(screen.getByText("мало места под ключ")).toBeInTheDocument());
    const body = JSON.parse((calls.find((c) => c.startsWith("POST") && c.endsWith("/review")) ? (vi.mocked(fetch).mock.calls.find((c) => (c[1] as RequestInit)?.method === "POST")![1] as RequestInit).body : "{}") as string);
    expect(body).toEqual({ text: "мало места под ключ", variant: "A_fork", part: "anchor_a00", point: [95, 0, -100] });
    expect(screen.getByTestId("viewer")).toHaveTextContent("пометок: 1");
    expect(screen.getByRole("button", { name: "Закрыть самому" })).toBeInTheDocument();
  });
});
