import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Workbench } from "./Workbench";

const base = {
  standards: [],
  state: "constructor",
  last_commit: { commit: "7bac9b6", author: "petrov", date: "2026-10-21T10:00:00+00:00", message: "x" },
  variants: [],
  children: [],
  aggregate: false,
  summary: null,
  chosen: null,
  kit: { variant: null, files: [] },
  thumb: null,
  task: null,
  layout: { state: "approved" },
};
const projects = [
  {
    ...base,
    name: "pump",
    title: "Насосный агрегат",
    folder: "nasosy",
    parent: null,
    children: ["frame", "supports"],
    aggregate: true,
    summary: { nodes: 2, done: 1, mass_kg: 88.4, k_min: 1.8 },
    stages: { brief: "done", layout: "done", design: "wait", kit: "todo" },
    next: { stage: "design", kind: "you", title: "Ждут вас: Опоры", hint: "Опоры: сравнить и выбрать", label: "Открыть «Опоры»", act: "open:supports", short: "ждут вас: 1" },
  },
  {
    ...base,
    name: "frame",
    title: "Рама",
    folder: "nasosy",
    parent: "pump",
    variants: [{ id: "A_frame", title: "рама", built: true, mass_kg: 86.4, k_min: 1.82, errors: 0, warnings: 0 }],
    chosen: "A_frame",
    kit: { variant: "A_frame", files: [{ name: "A_frame_assembly.step", kind: "step", title: "сборка", size: 10, url: "/out/frame/A_frame/A_frame_assembly.step" }] },
    stages: { brief: "done", layout: "done", design: "done", kit: "done" },
    next: { stage: "kit", kind: "done", title: "Комплект готов", hint: "скачайте", label: "Скачать комплект", act: "download", short: "готово" },
  },
  {
    ...base,
    name: "supports",
    title: "Опоры",
    folder: "nasosy",
    parent: "pump",
    variants: [
      { id: "A_base", title: "s=6", built: true, mass_kg: 4.6, k_min: 1.9, errors: 0, warnings: 1 },
      { id: "B_wide", title: "s=8", built: true, mass_kg: 6.8, k_min: 2.4, errors: 0, warnings: 0 },
    ],
    stages: { brief: "done", layout: "done", design: "wait", kit: "todo" },
    next: { stage: "design", kind: "you", title: "2 варианта готовы — выберите", hint: "Сравните", label: "Сравнить и выбрать", act: "choose", short: "выбрать вариант" },
  },
];
const payload = { summary: "", templates: [], folders: [{ id: "nasosy", title: "Насосы", projects: ["pump"] }], loose: [], trash: [], task_texts: { design: "Сделай детали" }, projects };
const threads: Record<string, unknown> = {
  pump: { messages: [{ id: "you:1", who: "you", at: "2026-10-21T09:00:00+00:00", by: "petrov", text: "Насосный агрегат на раме" }, { id: "commit:a", who: "system", at: "2026-10-21T09:30:00+00:00", by: "petrov", text: "Компоновка согласована (petrov)" }], active: null },
  frame: { messages: [{ id: "agent:2", who: "agent", at: "2026-10-21T10:00:00+00:00", status: "done", text: "Рама из швеллера 16П. Масса 86,4 кг.", brief: "Рама из швеллера 16П. Масса 86,4 кг.", images: [], steps: 6 }], active: null },
  supports: { messages: [{ id: "agent:3", who: "agent", at: "2026-10-21T10:05:00+00:00", status: "done", text: "Два варианта подкладок.", brief: "Два варианта подкладок.", images: [] }], active: null },
};

function mockFetch(calls: string[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/projects") return new Response(JSON.stringify(payload), { status: 200 });
      const th = url.match(/^\/api\/projects\/(\w+)\/thread$/);
      if (th) return new Response(JSON.stringify(threads[th[1]] ?? { messages: [], active: null }), { status: 200 });
      if (/^\/api\/projects\/\w+$/.test(url)) return new Response(JSON.stringify({ spec: { description: "d" }, attachments: [] }), { status: 200 });
      if (url === "/api/providers") return new Response(JSON.stringify({ providers: [], default: null, secure: true }), { status: 200 });
      if (url === "/api/projects/supports/choose" && init?.method === "POST") return new Response(JSON.stringify({ variant: "B_wide", commit: {} }), { status: 200 });
      if (url.startsWith("/api/projects/supports/variants/")) return new Response(JSON.stringify({ error: "не собран" }), { status: 404 });
      if (url.includes("/review") || url.includes("/attachments")) return new Response(JSON.stringify({ items: [] }), { status: 200 });
      if (url.includes("/layout")) return new Response(JSON.stringify({ error: "нет" }), { status: 404 });
      return new Response(JSON.stringify({ error: "нет " + url }), { status: 404 });
    }),
  );
}

const mount = (entry: string) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <div id="topbar-center" />
      <Routes>
        <Route path="/p/:project" element={<Workbench />} />
        <Route path="/p/:project/s/:stage" element={<Workbench />} />
      </Routes>
    </MemoryRouter>,
  );

describe("Рабочее место", () => {
  it("изделие: состав с узлами и строкой «что дальше», сводка, этапы, разговор по всему изделию", async () => {
    const calls: string[] = [];
    mockFetch(calls);
    mount("/p/pump");
    const tree = await screen.findByLabelText("Состав изделия");
    expect(within(tree).getByText("Насосный агрегат")).toBeInTheDocument();
    expect(within(tree).getByText("Рама")).toBeInTheDocument();
    expect(within(tree).getByText("готово")).toBeInTheDocument();
    expect(within(tree).getByText("выбрать вариант")).toBeInTheDocument();
    // этапы сводного узла и сводка
    expect(screen.getByRole("tab", { name: /Узлы/ })).toBeInTheDocument();
    expect(screen.getByText("88,4")).toBeInTheDocument();
    // закреплённый следующий шаг
    expect(screen.getByText("Ждут вас: Опоры")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Открыть «Опоры»" })).toBeInTheDocument();
    // разговор по всему изделию: сообщения узлов с подписью узла
    expect(await screen.findByText("Рама из швеллера 16П. Масса 86,4 кг.")).toBeInTheDocument();
    expect(screen.getByText(/Насосный агрегат на раме/)).toBeInTheDocument();
    expect(calls).toContain("GET /api/projects/frame/thread");
  });

  it("узел: варианты в полосе, выбор кнопкой — запрос к серверу", async () => {
    const calls: string[] = [];
    mockFetch(calls);
    mount("/p/supports");
    expect(await screen.findByText("2 варианта готовы — выберите")).toBeInTheDocument();
    const strip = await screen.findByLabelText("Варианты");
    expect(within(strip).getByText("A_base")).toBeInTheDocument();
    const choose = within(strip).getAllByRole("button", { name: "Выбрать" });
    expect(choose).toHaveLength(2);
    fireEvent.click(choose[1]);
    await screen.findByText("2 варианта готовы — выберите");
    expect(calls).toContain("POST /api/projects/supports/choose");
    // разговор по умолчанию у узла — только узел
    expect(screen.queryByText(/Насосный агрегат на раме/)).not.toBeInTheDocument();
    expect(await screen.findByText("Два варианта подкладок.")).toBeInTheDocument();
  });
});
