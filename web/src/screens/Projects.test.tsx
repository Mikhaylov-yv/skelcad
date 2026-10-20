import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Projects } from "./Projects";

const mount = (entry = "/") =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Projects />
    </MemoryRouter>,
  );

const payload = {
  summary: "проектов: 1",
  templates: [],
  projects: [
    {
      name: "bracket",
      title: "Кронштейн",
      standards: ["std-gost"],
      state: "constructor",
      last_commit: {
        commit: "7bac9b6",
        author: "SkelCAD agent (claude-code)",
        date: new Date().toISOString(),
        message: "анкеры M20: K_NV 1.14 → 1.74",
      },
      variants: [
        { id: "A_fork", title: "вилка", built: true, mass_kg: 15.63, k_min: 1.54, errors: 0, warnings: 2 },
        { id: "B_hub", title: "", built: false },
      ],
    },
  ],
};

describe("Проекты", () => {
  it("показывает карточку с числами, автором-агентом и несобранным вариантом", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 })),
    );
    mount();
    expect(await screen.findByText("Кронштейн", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("агент (claude-code)")).toBeInTheDocument();
    expect(screen.getByText("анкеры M20: K_NV 1.14 → 1.74")).toBeInTheDocument();
    expect(screen.getByText("не собран")).toBeInTheDocument();
    expect(screen.getByText("1,54")).toBeInTheDocument();
  });

  it("ищет по всем проектам из адреса ?q= и ведёт к сущности", async () => {
    const hits = {
      query: "wall",
      truncated: false,
      hits: [
        {
          project: "bracket",
          variant: "",
          ref: "datum:wall",
          kind: "datum",
          eid: "wall",
          name: "Плоскость стены",
          data: {},
        },
        {
          project: "bracket",
          variant: "A_fork",
          ref: "part:base_plate",
          kind: "part",
          eid: "base_plate",
          name: "Плита",
          data: {},
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async (url: string) =>
          new Response(JSON.stringify(String(url).includes("/api/graph/search") ? hits : payload), { status: 200 }),
      ),
    );
    mount("/?q=wall");
    expect(await screen.findByText("datum:wall")).toBeInTheDocument();
    expect(screen.getByText("datum:wall").closest("a")).toHaveAttribute(
      "href",
      "/p/bracket/A_fork?mode=layout&ref=datum%3Awall",
    );
    expect(screen.getByText("part:base_plate").closest("a")).toHaveAttribute(
      "href",
      "/p/bracket/A_fork?part=base_plate",
    );
    expect(screen.getByText("найдено: 2")).toBeInTheDocument();
  });

  it("показывает ошибку сервера словами и кнопку «Повторить»", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: "нет доступа" }), { status: 401 })),
    );
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("нет доступа");
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
  });
});
