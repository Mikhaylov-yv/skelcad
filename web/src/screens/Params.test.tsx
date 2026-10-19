import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Params } from "./Params";

vi.mock("../three/Viewer", () => ({ Viewer: () => <div data-testid="viewer" /> }));

const fields = {
  variant: "A_fork",
  file: "variants/A_fork.yaml",
  fields: [
    { path: "topology", value: "fork", type: "string", source: "variant" },
    { path: "members.gap", value: 100, type: "number", source: "variant" },
    { path: "base_plate.thickness", value: 16, type: "number", source: "project" },
  ],
};
const draft = {
  draft: "A_fork-abc",
  variant: "A_fork",
  changes: { "members.gap": 120 },
  file: "variants/A_fork.yaml",
  numbers: { mass_kg: 15.9, k_min: 1.54, errors: 0, warnings: 2 },
  diff: {
    variant: "A_fork",
    a: "x",
    b: "y",
    summary: "",
    cached: false,
    entities: {},
    geometry: {},
    deltas: { mass_kg: { a: 15.63, b: 15.9, delta: 0.27 } },
    findings: { added: [], removed: [] },
  },
  urls: { glb: "/out/bracket/_drafts/A_fork-abc/A_fork/A_fork.glb", head_glb: "/out/bracket/A_fork/A_fork.glb" },
};

describe("Параметры", () => {
  it("форма → черновик → сохранить с сообщением", async () => {
    const calls: { url: string; body?: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, body: init?.body as string });
        if (url.endsWith("/draft")) return new Response(JSON.stringify(draft), { status: 200 });
        if (url.endsWith("/params") && init?.method === "POST")
          return new Response(JSON.stringify({ commit: { commit: "abc" } }), { status: 200 });
        return new Response(JSON.stringify(fields), { status: 200 });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/p/bracket/A_fork/params"]}>
        <Routes>
          <Route path="/p/:project/:variant/params" element={<Params />} />
          <Route path="/p/:project/:variant" element={<p>экран варианта</p>} />
        </Routes>
      </MemoryRouter>,
    );
    const gap = await screen.findByLabelText(/gap/);
    expect(screen.getByRole("button", { name: "Собрать черновик" })).toBeDisabled();
    fireEvent.change(gap, { target: { value: "abc" } });
    expect(await screen.findByText("Нужно число")).toBeInTheDocument();
    fireEvent.change(gap, { target: { value: "120" } });
    expect(screen.getByText("было 100")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Собрать черновик" }));
    expect(
      await screen.findByText("Черновик собран. Ниже — что изменится по сравнению с текущим состоянием."),
    ).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.url.endsWith("/draft"))!.body!)).toEqual({
      params: { "members.gap": "120" },
    });
    const msg = screen.getByLabelText("Сообщение (что и зачем)") as HTMLInputElement;
    expect(msg.value).toBe("members.gap 100 → 120");
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(screen.getByText("экран варианта")).toBeInTheDocument());
    const saved = JSON.parse(calls.find((c) => c.url.endsWith("/params") && c.body)!.body!);
    expect(saved).toEqual({ params: { "members.gap": "120" }, message: "members.gap 100 → 120", draft: "A_fork-abc" });
  });
});
