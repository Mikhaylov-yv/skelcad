import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Projects } from "./Projects";

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
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 })));
    render(<Projects />);
    expect(await screen.findByText("Кронштейн", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("агент (claude-code)")).toBeInTheDocument();
    expect(screen.getByText("анкеры M20: K_NV 1.14 → 1.74")).toBeInTheDocument();
    expect(screen.getByText("не собран")).toBeInTheDocument();
    expect(screen.getByText("1,54")).toBeInTheDocument();
  });

  it("показывает ошибку сервера словами и кнопку «Повторить»", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "нет доступа" }), { status: 401 })));
    render(<Projects />);
    expect(await screen.findByRole("alert")).toHaveTextContent("нет доступа");
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
  });
});
