import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Attachment } from "../../api";
import { FilesPane } from "./FilesPane";

const files: Attachment[] = [
  { path: "attachments/20261021-1900-nabrosok.png", name: "20261021-1900-nabrosok.png", kind: "image", mime: "image/png", bytes: 2048, width: 10, height: 10, author: "petrov", date: "2026-10-21T19:00:00+00:00", note: "набросок от руки" },
  { path: "attachments/20261021-1901-analog.step", name: "20261021-1901-analog.step", kind: "cad", mime: "model/step", bytes: 300000, width: null, height: null, author: "petrov", date: "2026-10-21T19:01:00+00:00", note: null },
];

describe("FilesPane", () => {
  it("плитки: имя без штампа, заметка или вид и размер, «В сообщение», удаление — коммит", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${url}`);
        return new Response(JSON.stringify({ path: files[1].path, commit: { commit: "abc1234", author: "petrov", date: "", message: "удалено вложение" } }), { status: 200 });
      }),
    );
    const onAttach = vi.fn();
    const onDeleted = vi.fn();
    const onChanged = vi.fn();
    render(<FilesPane project="bracket" files={files} loading={false} locked={false} size="grid" onChanged={onChanged} onAttach={onAttach} onDeleted={onDeleted} />);
    expect(screen.getByText("nabrosok.png")).toBeTruthy();
    expect(screen.getByText(/набросок от руки/)).toBeTruthy();
    expect(screen.getByText(/CAD · 293 КБ/)).toBeTruthy();
    expect(screen.getByAltText("nabrosok.png").getAttribute("src")).toContain("/thumb?v=2048");
    fireEvent.click(screen.getAllByText("В сообщение")[0]);
    expect(onAttach).toHaveBeenCalledWith(files[0]);
    fireEvent.click(screen.getAllByText("Удалить")[1]);
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
    expect(calls).toContain("DELETE /api/projects/bracket/attachments/20261021-1901-analog.step");
    expect(onChanged).toHaveBeenCalled();
  });
});
