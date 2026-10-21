import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Start } from "./Start";

const next = (kind: string, short: string, stage = "design") => ({
  stage,
  kind,
  title: "t",
  hint: "h",
  label: "l",
  act: "run:design",
  short,
});
const base = {
  standards: [],
  state: "constructor",
  last_commit: { commit: "7bac9b6", author: "petrov", date: new Date().toISOString(), message: "x" },
  variants: [],
  children: [],
  aggregate: false,
  summary: null,
  stages: { brief: "done", layout: "done", design: "next", kit: "todo" },
  chosen: null,
  kit: { variant: null, files: [] },
  thumb: null,
};
const payload = {
  summary: "проектов: 3",
  templates: [{ id: "plate", title: "Планка" }],
  folders: [{ id: "krepezh", title: "Крепёж", projects: ["bolt"] }],
  loose: ["bracket"],
  trash: [{ id: "old.20261021", name: "old", title: "Старый", deleted: "20261021" }],
  task_texts: { design: "Сделай детали" },
  projects: [
    { ...base, name: "bolt", title: "Болт М16", folder: "krepezh", parent: null, children: ["frame"], next: next("agent", "дальше: детали") },
    { ...base, name: "bracket", title: "Кронштейн", folder: null, parent: null, next: next("you", "выбрать вариант") },
    { ...base, name: "frame", title: "Рама", folder: "krepezh", parent: "bolt", next: next("done", "готово") },
  ],
};

function mockFetch(calls: string[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/projects") return new Response(JSON.stringify(payload), { status: 200 });
      if (url === "/api/folders" && init?.method === "POST")
        return new Response(JSON.stringify({ id: "nasosy", title: "Насосы" }), { status: 200 });
      if (url === "/api/projects/bracket" && init?.method === "DELETE")
        return new Response(JSON.stringify({ id: "bracket.1", name: "bracket", nodes: [] }), { status: 200 });
      if (url.startsWith("/api/trash/") && init?.method === "POST")
        return new Response(JSON.stringify({ name: "bracket" }), { status: 200 });
      return new Response(JSON.stringify({ error: "нет " + url }), { status: 404 });
    }),
  );
}

describe("Стартовый экран", () => {
  it("показывает папки, проекты папки без узлов, что дальше, корзину", async () => {
    const calls: string[] = [];
    mockFetch(calls);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Start />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Крепёж")).toBeInTheDocument();
    // все проекты: корни bolt и bracket, узел frame не показан отдельной карточкой
    expect(screen.getByText("Болт М16")).toBeInTheDocument();
    expect(screen.getByText("Кронштейн")).toBeInTheDocument();
    expect(screen.queryByText("Рама")).not.toBeInTheDocument();
    expect(screen.getByText("дальше: детали")).toBeInTheDocument();
    expect(screen.getByText("выбрать вариант")).toBeInTheDocument();
    expect(screen.getByText("узлов: 1")).toBeInTheDocument();
    // папка «Крепёж» — только болт
    fireEvent.click(screen.getByText("Крепёж"));
    expect(screen.getByText("Болт М16")).toBeInTheDocument();
    expect(screen.queryByText("Кронштейн")).not.toBeInTheDocument();
    // корзина со «Старый» и кнопкой «Вернуть»
    expect(screen.getByText(/Корзина/)).toBeInTheDocument();
    expect(screen.getByText("Старый")).toBeInTheDocument();
  });

  it("создаёт папку и удаляет проект с возвратом", async () => {
    const calls: string[] = [];
    mockFetch(calls);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Start />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Крепёж")).toBeInTheDocument();
    fireEvent.click(screen.getByText("+ Папка"));
    fireEvent.change(screen.getByLabelText("Название папки"), { target: { value: "Насосы" } });
    fireEvent.click(screen.getByText("Создать"));
    expect(await screen.findByText("Крепёж")).toBeInTheDocument();
    expect(calls).toContain("POST /api/folders");
    // удалить «Кронштейн» — сообщение с «Вернуть»
    fireEvent.click(screen.getAllByText("Удалить")[1]);
    expect(await screen.findByText("«Кронштейн» в корзине")).toBeInTheDocument();
    expect(calls).toContain("DELETE /api/projects/bracket");
    fireEvent.click(within(screen.getByRole("status")).getByText("Вернуть"));
    expect(await screen.findByText("«Кронштейн» возвращён")).toBeInTheDocument();
    expect(calls.some((c) => c.startsWith("POST /api/trash/"))).toBe(true);
  });
});
