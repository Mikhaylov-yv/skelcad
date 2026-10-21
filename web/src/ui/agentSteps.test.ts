import { describe, expect, it } from "vitest";
import type { TaskEvent } from "../api";
import { buildSteps, commitsOf, describeCall, describeResult, nowOf } from "./agentSteps";
import fixture from "./agentSteps.fixture.json";

const events = fixture as TaskEvent[];

describe("ход работы агента словами", () => {
  it("вызовы инструментов становятся фразами конструктора", () => {
    expect(describeCall("project_read", { project: "bracket" }).text).toBe("Читаю проект bracket");
    expect(describeCall("files_write", { files: { "project.yaml": "x" }, message: "компоновка болта" })).toEqual({
      glyph: "write",
      text: "Правлю project.yaml: «компоновка болта»",
    });
    expect(describeCall("render", { project: "p", variant: "A", layout: true, view: "top" }).text).toBe(
      "Смотрю компоновку p/A, вид «Сверху»",
    );
    expect(describeCall("render", { project: "p", variant: "A", view: "iso", highlight: "part:x" }).text).toBe(
      "Смотрю вид «Изометрия» p/A, подсветка part:x",
    );
    expect(describeCall("build", { project: "p", variant: "A", export: false }).text).toBe(
      "Собираю вариант p/A без геометрии",
    );
    expect(describeCall("check", { project: "p", all: true }).text).toBe("Проверяю правила всех вариантов p");
    expect(describeCall("context_search", { project: "p", query: "болт", table: "fasteners" }).text).toBe(
      "Ищу в каталоге «болт» (fasteners)",
    );
    expect(describeCall("measure", { op: "clearance", args: { a: "part:x" } }).text).toBe(
      'Измеряю clearance {"a":"part:x"}',
    );
    expect(describeCall("unknown_tool", { x: 1 }).text).toBe('unknown_tool {"x":1}');
  });

  it("итог ответа — одна строка: сводка, коммит или ошибка без служебных префиксов", () => {
    expect(describeResult("check", '{"summary": "A_base: ошибка 0, предупреждение 0\\nещё", "x": 1}')).toEqual({
      outcome: "A_base: ошибка 0, предупреждение 0",
      failed: false,
    });
    expect(
      describeResult("files_write", '{"summary": "коммит 47af0c3 «компоновка: ось»: project.yaml, variants/A.yaml"}'),
    ).toEqual({ outcome: "коммит 47af0c3 · project.yaml, variants/A.yaml", failed: false, commit: "47af0c3" });
    expect(
      describeResult(
        "build",
        "ОШИБКА: Error executing tool build: AssertionError: \nTraceback (most recent call last):",
      ),
    ).toEqual({ outcome: "AssertionError", failed: true });
    expect(describeResult("render", "p/A: вид iso — {'png': 'https://x/y.png'}").outcome).toBe("p/A: вид iso");
  });

  it("события реальной задачи «Специальный болт» → шаги; подряд идущие чтения файлов склеены", () => {
    const steps = buildSteps(events);
    const texts = steps.map((s) => s.text);
    expect(texts[0]).toBe("Получил задачу, модель deepseek-v4-flash, инструментов 24");
    expect(texts).toContain("Смотрю список проектов");
    expect(texts).toContain("Читаю проект specialnyy_bolt");
    expect(texts).toContain("Смотрю замечания конструктора");
    expect(texts).toContain("Читаю файлы: specialnyy_bolt/project.yaml, plate/project.yaml");
    expect(steps.find((s) => s.text.startsWith("Читаю файлы"))?.paths).toHaveLength(2);
    const write = steps.find((s) => s.glyph === "write");
    expect(write?.text).toMatch(/^Правлю project\.yaml, variants\/A_base\.yaml: «компоновка специального болта/);
    expect(write?.commit).toBe("47af0c3");
    expect(write?.outcome).toBe("коммит 47af0c3 · project.yaml, variants/A_base.yaml");
    expect(texts).toContain("Смотрю компоновку specialnyy_bolt/A_base, вид «Изометрия»");
    const build = steps.find((s) => s.text === "Собираю вариант specialnyy_bolt/A_base");
    expect(build?.failed).toBe(true);
    expect(build?.outcome).toBe("AssertionError");
    expect(build?.seconds).toBe(3.6);
    const check = steps.find((s) => s.text === "Проверяю правила всех вариантов specialnyy_bolt");
    expect(check?.outcome).toBe("A_base: ошибка 0, предупреждение 0, информация 3");
    // реплики модели — отдельные шаги-заметки; done и images — не шаги
    expect(steps.filter((s) => s.kind === "note").length).toBe(5);
    expect(steps.some((s) => s.text.startsWith("Проверки чистые"))).toBe(true);
    expect(commitsOf(steps)).toEqual(["47af0c3"]);
    expect(nowOf(steps)).toBe("Обдумываю следующий шаг…");
  });

  it("незавершённый вызов — pending, картинки из tool_result.images попадают в шаг", () => {
    const steps = buildSteps([
      { t: "", type: "tool_call", name: "render", args: { project: "p", layout: true } },
      { t: "", type: "tool_result", name: "render", text: "p/база: компоновка", images: ["img-001.png"] },
      { t: "", type: "tool_call", name: "build", args: { project: "p", variant: "A" } },
    ]);
    expect(steps[0].images).toEqual(["img-001.png"]);
    expect(steps[0].pending).toBe(false);
    expect(steps[1].pending).toBe(true);
    expect(nowOf(steps)).toBe("Собираю вариант p/A");
  });
});
