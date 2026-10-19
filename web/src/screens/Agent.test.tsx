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
