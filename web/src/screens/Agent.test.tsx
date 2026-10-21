import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Agent } from "./Agent";

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
const task = {
  id: "20261019-1",
  project: "bracket",
  variant: "A_fork",
  text: "подними K",
  user: "ivanov",
  created: new Date().toISOString(),
  max_steps: 60,
  status: "running",
  steps: 1,
};
const events = {
  next: 2,
  total: 2,
  task,
  events: [
    { t: "", type: "start", runner: "openai", tools: 20 },
    { t: "", type: "tool_call", name: "project_read", args: { project: "bracket" } },
  ],
};

describe("Задача агенту", () => {
  it("ставит задачу, показывает ход и кнопку «Остановить»", async () => {
    const calls: string[] = [];
    let created = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push((init?.method ?? "GET") + " " + url);
        if (url.endsWith("/api/projects")) return new Response(JSON.stringify(projects), { status: 200 });
        if (url.endsWith("/tasks") && init?.method === "POST") {
          created = true;
          return new Response(JSON.stringify(task), { status: 200 });
        }
        if (url.endsWith("/tasks"))
          return new Response(JSON.stringify({ tasks: created ? [task] : [], active: created ? task : null }), {
            status: 200,
          });
        if (url.includes("/events")) return new Response(JSON.stringify(events), { status: 200 });
        if (url.endsWith("/stop")) return new Response(JSON.stringify({ ...task, status: "stopped" }), { status: 200 });
        return new Response("{}", { status: 404 });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/p/bracket/agent?variant=A_fork"]}>
        <Routes>
          <Route path="/p/:project/agent" element={<Agent />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Задач ещё не было.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Запустить" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Текст задачи"), { target: { value: "подними K" } });
    fireEvent.click(screen.getByRole("button", { name: "Запустить" }));
    await waitFor(() => expect(screen.getByText("вызов")).toBeInTheDocument());
    expect(screen.getByText("project_read")).toBeInTheDocument();
    expect(screen.getAllByText(/Проект у агента/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Запустить" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Остановить" }));
    await waitFor(() => expect(calls.some((c) => c.startsWith("POST") && c.endsWith("/stop"))).toBe(true));
    const body = JSON.parse(
      (
        vi
          .mocked(fetch)
          .mock.calls.find(
            (c) => (c[1] as RequestInit)?.method === "POST" && String(c[0]).endsWith("/tasks"),
          )?.[1] as RequestInit
      ).body as string,
    );
    expect(body).toEqual({ text: "подними K", variant: "A_fork" });
  });
});

describe("Вложения к задаче", () => {
  it("загружает файл коммитом, отмечает его к задаче и передаёт пути в задачу", async () => {
    const item = {
      path: "attachments/20261021-0900-eskiz.png",
      name: "20261021-0900-eskiz.png",
      kind: "image",
      mime: "image/png",
      bytes: 2048,
      width: 800,
      height: 600,
      author: "ivanov",
      date: "2026-10-21T09:00:00+00:00",
    };
    let uploaded = false;
    let taskBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/api/projects")) return new Response(JSON.stringify(projects), { status: 200 });
        if (url.endsWith("/attachments") && init?.method === "POST") {
          if (!(init.body instanceof FormData)) throw new Error("ожидалась форма");
          uploaded = true;
          return new Response(JSON.stringify({ item, commit: { commit: "abc", author: "ivanov" } }), { status: 200 });
        }
        if (url.endsWith("/attachments"))
          return new Response(JSON.stringify({ items: uploaded ? [item] : [] }), { status: 200 });
        if (url.endsWith("/tasks") && init?.method === "POST") {
          taskBody = JSON.parse(String(init.body));
          return new Response(JSON.stringify({ ...task, attachments: [item.path] }), { status: 200 });
        }
        if (url.endsWith("/tasks")) return new Response(JSON.stringify({ tasks: [], active: null }), { status: 200 });
        if (url.includes("/events")) return new Response(JSON.stringify(events), { status: 200 });
        return new Response("{}", { status: 404 });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/p/bracket/agent"]}>
        <Routes>
          <Route path="/p/:project/agent" element={<Agent />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Вложений пока нет.")).toBeInTheDocument();
    const file = new File([new Uint8Array([137, 80, 78, 71])], "Эскиз.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Добавить файл"), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByText(item.name)).toBeInTheDocument());
    const box = screen.getByLabelText(`Приложить ${item.name} к задаче`) as HTMLInputElement;
    expect(box.checked).toBe(true); // новый файл сразу отмечен к задаче
    expect(screen.getByText("вложений: 1")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Текст задачи"), { target: { value: "по наброску" } });
    fireEvent.click(screen.getByRole("button", { name: "Запустить" }));
    await waitFor(() => expect(taskBody).not.toBeNull());
    expect(taskBody).toEqual({ text: "по наброску", attachments: [item.path] });
  });
});

describe("Провайдер и модель задачи", () => {
  it("задача несёт выбранного провайдера и модель; по умолчанию поля не шлются", async () => {
    const bodies: Record<string, unknown>[] = [];
    const prov = {
      providers: [
        {
          id: "or",
          title: "OpenRouter",
          kind: "openai",
          base_url: "https://openrouter.ai/api/v1",
          model: "a/b",
          models: ["a/b", "c/d"],
          has_key: true,
          key_tail: "1",
          default: true,
        },
        {
          id: "cc",
          title: "Claude Code",
          kind: "claude-code",
          base_url: "",
          model: "",
          models: [],
          has_key: false,
          key_tail: "",
          default: false,
        },
      ],
      default: "or",
      secure: true,
      presets: [],
      env: { base_url: "", model: "", has_key: false, runner: "openai" },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/api/projects")) return new Response(JSON.stringify(projects), { status: 200 });
        if (url.endsWith("/api/providers")) return new Response(JSON.stringify(prov), { status: 200 });
        if (url.endsWith("/attachments")) return new Response(JSON.stringify({ items: [] }), { status: 200 });
        if (url.endsWith("/tasks") && init?.method === "POST") {
          bodies.push(JSON.parse(String(init.body)));
          return new Response(JSON.stringify({ ...task, status: "done" }), { status: 200 });
        }
        if (url.endsWith("/tasks")) return new Response(JSON.stringify({ tasks: [], active: null }), { status: 200 });
        if (url.includes("/events")) return new Response(JSON.stringify(events), { status: 200 });
        return new Response("{}", { status: 404 });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/p/bracket/agent"]}>
        <Routes>
          <Route path="/p/:project/agent" element={<Agent />} />
        </Routes>
      </MemoryRouter>,
    );
    const sel = (await screen.findByLabelText(/Провайдер/)) as HTMLSelectElement;
    expect(sel.options[0].textContent).toContain("по умолчанию (OpenRouter)");
    fireEvent.change(screen.getByLabelText("Текст задачи"), { target: { value: "раз" } });
    fireEvent.click(screen.getByRole("button", { name: "Запустить" }));
    await waitFor(() => expect(bodies.length).toBe(1));
    expect(bodies[0]).toEqual({ text: "раз" });
    fireEvent.change(sel, { target: { value: "or" } });
    fireEvent.change(screen.getByLabelText(/Модель/), { target: { value: "c/d" } });
    fireEvent.change(screen.getByLabelText("Текст задачи"), { target: { value: "два" } });
    fireEvent.click(screen.getByRole("button", { name: "Запустить" }));
    await waitFor(() => expect(bodies.length).toBe(2));
    expect(bodies[1]).toEqual({ text: "два", provider: "or", model: "c/d" });
    fireEvent.change(sel, { target: { value: "cc" } });
    expect(screen.queryByLabelText(/Модель/)).not.toBeInTheDocument(); // у Claude Code модель не выбирается
  });
});
