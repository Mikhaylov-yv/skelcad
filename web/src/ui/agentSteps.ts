// Ход работы агента для конструктора: события задачи (вызовы инструментов, ответы, реплики модели) →
// шаги словами: «Читаю проект bracket», «Правлю project.yaml: …» → «коммит 47af0c3», «Собираю вариант A_base».
// Сырые аргументы и ответы инструментов остаются в details — по запросу. Образец — «Ход обработки» в doc_ocr.
import type { TaskEvent } from "../api";
import { S } from "../strings";

export type Glyph =
  | "read"
  | "write"
  | "build"
  | "check"
  | "measure"
  | "image"
  | "search"
  | "catalog"
  | "links"
  | "revert"
  | "review"
  | "note"
  | "start"
  | "wait";

export interface Step {
  i: number; // индекс первого события шага
  kind: "call" | "note" | "attachment" | "start";
  glyph: Glyph;
  text: string; // фраза: что агент делает
  outcome?: string; // что получилось, одной строкой
  failed?: boolean; // инструмент ответил ошибкой
  pending?: boolean; // вызов без ответа — идёт сейчас
  seconds?: number; // длительность инструмента
  images?: string[]; // файлы задачи с картинками, на которые смотрел агент
  url?: string; // картинка вложения (шаг attachment)
  details?: string; // сырые аргументы и ответ — по запросу
  commit?: string; // хэш коммита, если шаг его создал
  paths?: string[]; // files_read: прочитанные файлы (склеиваются в один шаг)
}

const A = (v: unknown): string => (v === undefined || v === null || v === "" ? "" : String(v));

/** Фраза для вызова инструмента. */
export function describeCall(name: string, args: Record<string, unknown> = {}): { glyph: Glyph; text: string } {
  const T = S.steps;
  const project = A(args.project);
  const variant = A(args.variant);
  const pv = project + (variant ? `/${variant}` : "");
  switch (name) {
    case "project_list":
      return { glyph: "read", text: T.projectList };
    case "project_create":
      return { glyph: "write", text: T.projectCreate(A(args.name)) };
    case "project_read":
      return { glyph: "read", text: T.projectRead(project, A(args.section)) };
    case "model_query":
      return { glyph: "read", text: T.modelQuery(pv, A(args.path)) };
    case "files_read":
      return { glyph: "read", text: T.filesRead([`${project}/${A(args.path)}`]) };
    case "files_write": {
      const files = args.files && typeof args.files === "object" ? Object.keys(args.files as object) : [];
      return { glyph: "write", text: T.filesWrite(files, A(args.message)) };
    }
    case "history":
      return { glyph: "read", text: T.history(project) };
    case "revert":
      return { glyph: "revert", text: T.revert(A(args.commit)) };
    case "review_list":
      return { glyph: "review", text: T.reviewList };
    case "review_resolve":
      return { glyph: "review", text: T.reviewResolve(A(args.id), A(args.answer)) };
    case "review_add":
      return { glyph: "review", text: T.reviewAdd };
    case "attachments":
      return { glyph: "image", text: T.attachments };
    case "attachment":
      return { glyph: "image", text: T.attachment(A(args.path)) };
    case "standards_list":
      return { glyph: "catalog", text: T.standards };
    case "context_tables":
      return { glyph: "catalog", text: T.contextTables };
    case "context_lookup":
      return { glyph: "catalog", text: T.contextLookup(A(args.table), A(args.key)) };
    case "context_search":
      return { glyph: "catalog", text: T.contextSearch(A(args.query), A(args.table)) };
    case "links":
      return { glyph: "links", text: T.links(A(args.ref)) };
    case "where_used":
      return { glyph: "links", text: T.whereUsed(A(args.ref)) };
    case "search":
      return { glyph: "search", text: T.search(A(args.query)) };
    case "measure":
      return { glyph: "measure", text: T.measure(A(args.op), args.args ? short(args.args) : "") };
    case "render": {
      const view = A(args.view);
      const highlight = A(args.highlight);
      if (args.layout)
        return {
          glyph: "image",
          text: T.renderLayout(pv, view && S.variant.views[view] ? S.variant.views[view] : view, highlight),
        };
      return { glyph: "image", text: T.renderView(pv, S.variant.views[view] ?? view, highlight) };
    }
    case "check":
      return { glyph: "check", text: T.check(pv, !!args.all) };
    case "build":
      return { glyph: "build", text: T.build(pv, !!args.all, args.export === false) };
    case "diff":
      return { glyph: "read", text: T.diff(A(args.a) || "HEAD~1", A(args.b) || "HEAD") };
    case "compare":
      return { glyph: "check", text: T.compare(project) };
    default:
      return { glyph: "read", text: `${name} ${short(args)}` };
  }
}

/** Короткая запись аргументов для фразы. */
function short(v: unknown, n = 80): string {
  const s = typeof v === "string" ? v : JSON.stringify(v ?? {});
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

const COMMIT_RE = /^коммит (\w+) «([\s\S]*)»(?::\s*(.*))?$/;

/** Итог ответа инструмента одной строкой; ошибка — без служебных префиксов. */
export function describeResult(name: string, text: string): { outcome: string; failed: boolean; commit?: string } {
  const raw = (text ?? "").trim();
  if (raw.startsWith("ОШИБКА")) {
    let line = raw
      .split("\n")[0]
      .replace(/^ОШИБКА(?: вызова \w+)?:\s*/, "")
      .replace(/^Error executing tool \w+:\s*/, "");
    line = line.replace(/:\s*$/, "");
    return { outcome: clip(line || S.steps.failed, 200), failed: true };
  }
  let summary = raw;
  try {
    const d = JSON.parse(raw);
    if (d && typeof d === "object" && typeof d.summary === "string") summary = d.summary;
  } catch {
    // ответ обрезан (агент хранит до 1500 знаков) — сводку берём по полю "summary" как есть
    const m = /"summary":\s*"((?:[^"\\]|\\.)*)"/.exec(raw);
    if (m) summary = m[1].replace(/\\n/g, "\n").replace(/\\"/g, '"').replace(/\\\\/g, "\\");
  }
  let line = summary.split("\n")[0].trim();
  if (name === "render") line = line.replace(/\s+—\s+\{.*$/, "");
  const m = COMMIT_RE.exec(summary.replace(/\n/g, " "));
  if (m) return { outcome: S.steps.commit(m[1], m[3] ?? ""), failed: false, commit: m[1] };
  return { outcome: clip(line, 200), failed: false };
}

function clip(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

/** События задачи → шаги. Подряд идущие files_read склеиваются в один шаг «Читаю файлы: …». */
export function buildSteps(events: TaskEvent[]): Step[] {
  const steps: Step[] = [];
  let open: Step | null = null; // вызов, ждущий ответа
  events.forEach((e, i) => {
    if (e.type === "start") {
      steps.push({ i, kind: "start", glyph: "start", text: S.steps.start(e.model ?? "", e.tools ?? 0) });
    } else if (e.type === "assistant") {
      if (e.text?.trim()) steps.push({ i, kind: "note", glyph: "note", text: e.text.trim() });
    } else if (e.type === "attachment") {
      steps.push({
        i,
        kind: "attachment",
        glyph: "image",
        text: S.steps.attachment(e.path ?? ""),
        outcome: S.agent.sentAttachment(typeof e.images === "number" ? e.images : 0),
        url: e.path,
      });
    } else if (e.type === "tool_call") {
      const { glyph, text } = describeCall(e.name ?? "", e.args ?? {});
      const prev = steps[steps.length - 1];
      if (e.name === "files_read" && prev && prev.kind === "call" && prev.paths && !prev.pending && !prev.failed) {
        // склейка подряд идущих чтений файлов
        prev.paths.push(`${A(e.args?.project)}/${A(e.args?.path)}`);
        prev.text = S.steps.filesRead(prev.paths);
        prev.pending = true;
        prev.details = (prev.details ?? "") + `\n\n${e.name} ${JSON.stringify(e.args ?? {})}`;
        open = prev;
        return;
      }
      open = {
        i,
        kind: "call",
        glyph,
        text,
        pending: true,
        details: `${e.name} ${JSON.stringify(e.args ?? {}, null, 1)}`,
        paths: e.name === "files_read" ? [`${A(e.args?.project)}/${A(e.args?.path)}`] : undefined,
      };
      steps.push(open);
    } else if (e.type === "tool_result") {
      const s = open ?? steps[steps.length - 1];
      if (!s || s.kind !== "call") return;
      const r = describeResult(e.name ?? "", e.text ?? "");
      s.pending = false;
      s.failed = r.failed;
      s.commit = r.commit;
      s.outcome = s.paths && s.paths.length > 1 ? (r.failed ? r.outcome : undefined) : r.outcome;
      s.seconds = (s.seconds ?? 0) + (e.seconds ?? 0);
      if (Array.isArray(e.images) && e.images.length) s.images = [...(s.images ?? []), ...e.images];
      s.details = `${s.details ?? ""}\n\n→ ${e.text ?? ""}`.trim();
      open = null;
    }
    // step, images, done, error, stopped, limit — не шаги: итог и состояние показывает панель
  });
  return steps;
}

/** Коммиты, которые создала задача (по ответам инструментов). */
export function commitsOf(steps: Step[]): string[] {
  return steps.filter((s) => s.commit).map((s) => s.commit as string);
}

/** Что сейчас делает агент (для строки состояния живой задачи). */
export function nowOf(steps: Step[]): string {
  const last = steps[steps.length - 1];
  if (last && last.kind === "call" && last.pending) return last.text;
  return S.steps.thinking;
}
