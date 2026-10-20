import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Links, entityUrl } from "./Links";

const links = {
  project: "bracket",
  variant: null,
  ref: "interface:wall",
  hops: 1,
  direction: "both",
  kinds: [],
  root: {
    ref: "interface:wall",
    kind: "interface",
    eid: "wall",
    name: "Крепление к стене",
    variants: [],
    depth: 0,
    data: {},
  },
  nodes: [
    {
      ref: "interface:wall",
      kind: "interface",
      eid: "wall",
      name: "Крепление к стене",
      variants: [],
      depth: 0,
      data: {},
    },
    { ref: "datum:wall", kind: "datum", eid: "wall", name: "Плоскость стены", variants: [], depth: 1, data: {} },
    { ref: "unit:u1", kind: "unit", eid: "u1", name: "Кронштейн", variants: ["A_fork"], depth: 1, data: {} },
  ],
  edges: [
    { src: "interface:wall", dst: "datum:wall", kind: "locates", variant: "", data: {} },
    { src: "unit:u1", dst: "interface:wall", kind: "mounts", variant: "A_fork", data: {} },
  ],
  truncated: false,
  summary: "",
};

describe("Связи", () => {
  it("группирует связи по типам и отдаёт выбранную сущность наверх", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(links), { status: 200 })),
    );
    const onPick = vi.fn();
    render(
      <MemoryRouter>
        <Links project="bracket" reference="interface:wall" onPick={onPick} />
      </MemoryRouter>,
    );
    expect(await screen.findByText("привязан к базе:")).toBeInTheDocument();
    expect(screen.getByText("← ссылаются на эту сущность: крепится к интерфейсу:")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("datum:wall"));
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ ref: "datum:wall", kind: "datum" }));
    expect(screen.getByRole("button", { name: "Где используется" })).toBeInTheDocument();
  });

  it("говорит словами, если граф на сервере не настроен", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: "граф связей не настроен" }), { status: 503 })),
    );
    render(
      <MemoryRouter>
        <Links project="bracket" reference="part:base_plate" />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/не настроен/)).toBeInTheDocument();
  });

  it("строит адреса сущностей: скелет — в компоновку, деталь — в 3D", () => {
    expect(entityUrl("bracket", "A_fork", { ref: "datum:wall", kind: "datum", eid: "wall" })).toBe(
      "/p/bracket/A_fork?mode=layout&ref=datum%3Awall",
    );
    expect(entityUrl("bracket", null, { ref: "datum:wall", kind: "datum", eid: "wall" })).toBe(
      "/p/bracket/layout?ref=datum%3Awall",
    );
    expect(entityUrl("bracket", "A_fork", { ref: "part:cheek_L", kind: "part", eid: "cheek_L" })).toBe(
      "/p/bracket/A_fork?part=cheek_L",
    );
    expect(entityUrl("bracket", "A_fork", { ref: "part:cheek_L/hole:bore", kind: "hole", eid: "bore" })).toBe(
      "/p/bracket/A_fork?part=cheek_L",
    );
  });
});
