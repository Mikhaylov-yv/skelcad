import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown, firstLine, parseBlocks } from "./Markdown";

describe("markdown отчёта агента", () => {
  it("разбирает заголовки, списки, абзацы и код", () => {
    const blocks = parseBlocks(
      "## Отчёт\n\nПервый абзац\nпродолжение.\n\n- **A1** — раз\n- два\n  и ещё\n\n1. первый\n2. второй\n\n```\nx = 1\n```",
    );
    expect(blocks).toEqual([
      { kind: "h", text: "Отчёт" },
      { kind: "p", text: "Первый абзац продолжение." },
      { kind: "ul", items: ["**A1** — раз", "два и ещё"] },
      { kind: "ol", items: ["первый", "второй"] },
      { kind: "code", text: "x = 1" },
    ]);
  });

  it("рисует жирный и код элементами, без HTML-вставок", () => {
    render(<Markdown text={"## Итог\n\nКоммит `47af0c3` — **ось** болта <b>не html</b>"} />);
    expect(screen.getByRole("heading", { level: 4 })).toHaveTextContent("Итог");
    expect(screen.getByText("ось").tagName).toBe("STRONG");
    expect(screen.getByText("47af0c3").tagName).toBe("CODE");
    expect(screen.getByText(/не html/).textContent).toContain("<b>не html</b>");
  });

  it("первая строка без разметки — для свёрнутых реплик", () => {
    expect(firstLine("\n**Разбор ТЗ**: болт `M12`\nдалее")).toBe("Разбор ТЗ: болт M12");
    expect(firstLine("а".repeat(200), 10)).toBe("ааааааааа…");
  });
});
