import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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

  it("создаёт проект из формы: код из названия, POST /api/projects, переход на экран «Агент»", async () => {
    const posts: { url: string; body: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          posts.push({ url: String(url), body: JSON.parse(String(init.body)) });
          const project = { name: "opora_nasosa", title: "Опора насоса", variants: [], last_commit: null };
          return new Response(JSON.stringify({ summary: "создан проект", project }), { status: 200 });
        }
        const templates = [{ id: "plate", title: "Планка с 4 резьбовыми отверстиями M10" }];
        return new Response(JSON.stringify({ ...payload, templates }), { status: 200 });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Projects />} />
          <Route path="/p/:project/agent" element={<p>экран агента</p>} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Новый проект" }));
    fireEvent.change(screen.getByLabelText("Название изделия", { exact: false }), {
      target: { value: "Опора насоса" },
    });
    const code = screen.getByLabelText("Код проекта", { exact: false });
    expect(code).toHaveValue("opora_nasosa");
    expect(screen.getByRole("option", { name: /копия примера «Планка/ })).toBeInTheDocument();
    fireEvent.change(code, { target: { value: "Bad Name" } });
    expect(screen.getByRole("button", { name: "Создать" })).toBeDisabled();
    fireEvent.change(code, { target: { value: "opora_nasosa" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать" }));
    expect(await screen.findByText("экран агента")).toBeInTheDocument();
    expect(posts).toEqual([{ url: "/api/projects", body: { name: "opora_nasosa", title: "Опора насоса" } }]);
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
