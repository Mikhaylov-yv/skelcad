import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Feed } from "./Feed";

vi.mock("../three/Viewer", () => ({ Viewer: () => <div data-testid="viewer" /> }));

const commits = {
  unreviewed: 1,
  head: "b".repeat(40),
  commits: [
    {
      commit: "bbbbbbb",
      hash: "b".repeat(40),
      author: "SkelCAD agent (claude-code)",
      date: new Date().toISOString(),
      message: "анкеры M20: K_NV 1.14 → 1.74",
      files: ["project.yaml"],
      kind: "agent",
      is_head: true,
      reviewed: null,
    },
    {
      commit: "aaaaaaa",
      hash: "a".repeat(40),
      author: "SkelCAD",
      date: new Date(Date.now() - 3600e3).toISOString(),
      message: "Проект bracket из шаблона bracket",
      files: ["project.yaml", "variants/A_fork.yaml"],
      kind: "system",
      is_head: false,
      reviewed: null,
    },
  ],
};
const projects = {
  summary: "",
  templates: [],
  projects: [
    {
      name: "bracket",
      title: "Кронштейн",
      standards: [],
      state: "constructor",
      last_commit: null,
      variants: [{ id: "A_fork", title: "", built: true }],
    },
  ],
};
const diff = {
  variant: "A_fork",
  a: "a".repeat(40),
  b: "b".repeat(40),
  summary: "",
  cached: true,
  entities: { fasteners: { changed: { anchor_a00: { size: ["M16", "M20"] } } } },
  geometry: {},
  deltas: { mass_kg: { a: 15.33, b: 15.63, delta: 0.3 }, K_min: { a: 1.14, b: 1.54, delta: 0.4 } },
  findings: { added: [], removed: ["[warning] K-anchor_NV fasteners: запас меньше требуемого"] },
};

function mockFetch(calls: string[]) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    calls.push((init?.method ?? "GET") + " " + url);
    if (url.includes("/commits/") && url.endsWith("/reviewed"))
      return new Response(JSON.stringify({ reviewed: { by: "ivanov", at: "2026-10-19T12:00:00+00:00" } }), {
        status: 200,
      });
    if (url.includes("/diff?")) return new Response(JSON.stringify(diff), { status: 200 });
    if (url.endsWith("/revert")) return new Response(JSON.stringify({ commit: commits.commits[0] }), { status: 200 });
    if (url.includes("/commits")) return new Response(JSON.stringify(commits), { status: 200 });
    if (url.endsWith("/api/projects")) return new Response(JSON.stringify(projects), { status: 200 });
    return new Response(JSON.stringify({ error: "нет пути " + url }), { status: 404 });
  });
}

function mount() {
  return render(
    <MemoryRouter initialEntries={["/p/bracket/commits?variant=A_fork"]}>
      <Routes>
        <Route path="/p/:project/commits" element={<Feed />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Лента", () => {
  it("показывает коммиты, счётчик непросмотренных, разницу по кнопке и отметку «Просмотрено»", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", mockFetch(calls));
    mount();
    expect(await screen.findByText("анкеры M20: K_NV 1.14 → 1.74")).toBeInTheDocument();
    expect(screen.getByText("непросмотренных изменений агента: 1")).toBeInTheDocument();
    expect(screen.getByText("текущее состояние")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Разница" })[0]);
    expect(await screen.findByText("Ушли замечания")).toBeInTheDocument();
    expect(screen.getByText("15,63")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Просмотрено" }));
    await waitFor(() => expect(screen.getByText("просмотрено · ivanov")).toBeInTheDocument());
    expect(calls.some((c) => c.startsWith("POST") && c.endsWith("/reviewed"))).toBe(true);
  });

  it("откат — через диалог с подтверждением", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", mockFetch(calls));
    mount();
    await screen.findByText("анкеры M20: K_NV 1.14 → 1.74");
    fireEvent.click(screen.getAllByRole("button", { name: "Откатить" })[0]);
    const dlg = await screen.findByRole("dialog");
    expect(dlg).toHaveTextContent("Откат — это новый коммит");
    expect(calls.some((c) => c.endsWith("/revert"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Откатить" })[0]);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Откатить" }));
    await waitFor(() => expect(calls.some((c) => c.startsWith("POST") && c.endsWith("/revert"))).toBe(true));
  });
});
