import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { LayoutEntity } from "../api";
import { LayoutEditPanel } from "./LayoutEdit";
import type { Geom } from "./edit";

const wall: LayoutEntity = {
  ref: "surrounding:wall_body", group: "surrounding", id: "wall_body", kind: "plane", name: "Стена",
  status: "", source: "", note: "",
}; // prettier-ignore
const base: Geom = { origin: [0, 0, 0], normal: [0, 1, 0], extent: 300, thickness: 250 };

describe("Панель правки компоновки", () => {
  it("меняет поле, показывает число изменений и шлёт правку коммитом", async () => {
    let body: unknown = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/layout/edit")) {
          body = JSON.parse(String(init?.body));
          return new Response(
            JSON.stringify({
              summary: "коммит abc",
              commit: { commit: "abc" },
              applied: ["x"],
              approval: { state: "changed" },
            }),
            { status: 200 },
          );
        }
        return new Response("{}", { status: 404 });
      }),
    );
    let draft: Geom | null = null;
    const applied: string[] = [];
    const ui = (d: Geom | null) =>
      render(
        <LayoutEditPanel
          project="bracket"
          entity={wall}
          base={base}
          draft={d}
          onDraft={(g) => {
            draft = g;
          }}
          dim={null}
          onDimDone={() => undefined}
          onApplied={(s) => applied.push(s)}
          locked={false}
        />,
      );
    const r = ui(null);
    expect(screen.getByRole("button", { name: "Применить" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("протяжённость (полуразмер)"), { target: { value: "350" } });
    expect(draft).toEqual({ ...base, extent: 350 });
    r.unmount();
    ui(draft);
    expect(screen.getByText("изменено поле: 1")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Сообщение коммита (необязательно)"), { target: { value: "шире" } });
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    await waitFor(() => expect(applied).toEqual(["коммит abc"]));
    expect(body).toEqual({ edits: [{ ref: "surrounding:wall_body", set: { extent: 350 } }], message: "шире" });
  });

  it("интерфейс без тела: объясняет, что положение задаёт база; размер — отдельная форма", async () => {
    const iface: LayoutEntity = { ...wall, ref: "interface:wall", group: "interface", id: "wall", kind: "mount_plane" };
    const pick: string[] = [];
    const { rerender } = render(
      <LayoutEditPanel
        project="bracket"
        entity={iface}
        base={{ datum: "wall", body: null }}
        draft={null}
        onDraft={() => undefined}
        dim={null}
        onDimDone={() => undefined}
        onApplied={() => undefined}
        onSelectRef={(r) => pick.push(r)}
        locked={false}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "datum:wall" }));
    expect(pick).toEqual(["datum:wall"]);
    rerender(
      <LayoutEditPanel
        project="bracket"
        entity={null}
        base={null}
        draft={null}
        onDraft={() => undefined}
        dim={{
          id: "wall-axle_axis",
          view: "main",
          kind: "linear",
          axis: "Y",
          value: 200,
          text: "200",
          refs: ["datum:wall", "datum:axle_axis"],
        }}
        onDimDone={() => undefined}
        onApplied={() => undefined}
        locked={false}
      />,
    );
    expect(screen.getByText("Размер wall-axle_axis")).toBeInTheDocument();
    expect((screen.getByLabelText("Новое значение, мм") as HTMLInputElement).value).toBe("200");
  });
});
