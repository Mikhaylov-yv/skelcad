// Клиент /api сервера SkelCAD. Ошибки сервера приходят как {error: "..."} — превращаем в исключение с текстом.

export interface Commit {
  commit: string;
  hash?: string;
  author: string;
  date: string;
  message: string;
  files?: string[];
}

export interface VariantOverview {
  id: string;
  title: string;
  built: boolean;
  built_at?: string;
  mass_kg?: number;
  k_min?: number;
  k_min_item?: string;
  errors?: number;
  warnings?: number;
  info?: number;
}

export type LayoutStateKind = "none" | "waiting" | "approved" | "changed" | "invalid";

// --- этапы изделия и следующий шаг (M2.5, D32)
export type StageId = "brief" | "layout" | "design" | "kit";
export type StageState = "done" | "wait" | "agent" | "next" | "todo";
export type NextKind = "you" | "agent" | "running" | "done";
export interface NextStep {
  stage: StageId;
  kind: NextKind;
  title: string;
  hint: string;
  label: string;
  act: string; // say | run:layout | approve | run:design | run:fix | choose | run:kit | download | open:<проект> | stop
  short: string;
}
export interface KitFile {
  name: string;
  kind: string;
  title: string;
  size: number;
  url: string;
}
export interface NodeSummary {
  nodes: number;
  done: number;
  mass_kg: number;
  k_min: number | null;
}

export interface ProjectOverview {
  name: string;
  title: string;
  standards: string[];
  variants: VariantOverview[];
  last_commit: Commit | null;
  state: "constructor" | "agent";
  task?: { id: string; status: TaskStatus; text: string } | null;
  unreviewed?: number;
  layout?: { state: LayoutStateKind; by?: string | null; at?: string | null; error?: string | null };
  folder?: string | null;
  parent?: string | null;
  children: string[];
  aggregate: boolean;
  summary: NodeSummary | null;
  stages: Record<StageId, StageState>;
  next: NextStep;
  chosen: string | null;
  kit: { variant: string | null; files: KitFile[] };
  thumb: string | null;
  purchased?: boolean;
}

export interface Folder {
  id: string;
  title: string;
  projects: string[];
}
export interface TrashItem {
  id: string;
  name: string;
  title: string;
  deleted: string;
}
export interface FoldersResponse {
  folders: Folder[];
  loose: string[];
  children: Record<string, string[]>;
  trash: TrashItem[];
}

// --- разговор по проекту (M2.5): задачи конструктора, ответы агента, служебные записи из коммитов
export interface ThreadMessage {
  id: string;
  who: "you" | "agent" | "system";
  at: string | null;
  by?: string;
  text: string;
  brief?: string;
  status?: TaskStatus;
  images?: string[];
  steps?: number | null;
  model?: string | null;
  task?: string;
  attachments?: string[];
  commit?: string;
  kind?: CommitKind;
  reviewed?: { by: string; at: string | null } | null;
}
export interface ThreadResponse {
  messages: ThreadMessage[];
  active: AgentTask | null;
}

// --- компоновочный эскиз (M2.1, D21)
export interface LayoutView {
  svg: string;
  png: string | null;
  viewBox: number[];
  u: [string, number]; // ось модели и знак: экранная u = знак · координата
  v: [string, number];
  depth: [string, number]; // ось взгляда и её значение для точек, поставленных на эскизе
  title: string;
  svg_url: string;
  png_url: string | null;
}

export interface LayoutDim {
  id: string;
  view: string;
  kind: string;
  axis: string;
  value: number;
  text: string;
  refs: string[];
}

export interface LayoutEntity {
  ref: string;
  group: "datum" | "interface" | "envelope" | "surrounding";
  id: string;
  kind: string;
  name: string;
  status: string;
  source: string;
  note: string;
  geom?: Record<string, unknown>; // числовые поля для ручек (M2.3): origin / min / max / center / diameter / …
}

/** Правка компоновки с эскиза (M2.3): правки сущностей или размер числом; ответ — коммит конструктора. */
export interface LayoutEditRequest {
  edits?: { ref: string; set: Record<string, number | number[]> }[];
  dim?: string;
  value?: number;
  variant?: string;
  message?: string;
}

export interface LayoutEditResponse {
  summary: string;
  commit: Commit;
  applied: string[];
  approval: LayoutApproval;
}

export interface LayoutApproval {
  state: LayoutStateKind;
  hash: string | null;
  approved: { by: string; at: string; commit: string; hash: string } | null;
  diff: {
    added: string[];
    removed: string[];
    changed: string[];
    requirements: boolean;
  } | null;
  error?: string;
}

export interface LayoutResponse {
  project: string;
  variant: string | null;
  title: string;
  views: Record<string, LayoutView>;
  dims: LayoutDim[];
  entities: LayoutEntity[];
  loads: {
    name: string;
    value: number;
    source: string;
    dir: number[] | null;
  }[];
  legend: string[];
  parts: boolean;
  notes: string[];
  commit: string;
  key: string;
  approval: LayoutApproval;
}

export interface TemplateInfo {
  id: string;
  title: string;
}

export interface ProjectsResponse {
  summary: string;
  projects: ProjectOverview[];
  templates: TemplateInfo[];
  folders: Folder[];
  loose: string[];
  trash: TrashItem[];
  task_texts: Record<string, string>;
}

export interface ProjectCreated {
  summary: string;
  project: { name: string; title: string; variants: string[]; folder?: string | null; parent?: string | null };
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });
  const text = await r.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!r.ok) {
    const msg = (data as { error?: string } | null)?.error ?? `${r.status} ${r.statusText}`;
    throw new ApiError(r.status, msg);
  }
  return data as T;
}

export interface Me {
  name: string;
  kind: "agent" | "user";
  email: string | null;
  auth: "none" | "tokens" | "proxy";
  admin: boolean;
  logout_url: string | null;
}

// --- провайдеры модели встроенного агента (D29): ключи хранятся на сервере, наружу не отдаются
export interface Provider {
  id: string;
  title: string;
  kind: "openai" | "claude-code";
  base_url: string;
  model: string;
  models: string[];
  has_key: boolean;
  key_tail: string;
  default: boolean;
  created?: string | null;
  created_by?: string | null;
  updated?: string | null;
  updated_by?: string | null;
}

export interface ProviderPreset {
  id: string;
  title: string;
  base_url: string;
  model: string;
}

export interface ProvidersResponse {
  providers: Provider[];
  default: string | null;
  secure: boolean; // SKELCAD_SECRET_KEY задан — ключи шифруются
  presets: ProviderPreset[];
  env: { base_url: string; model: string; has_key: boolean; runner: string };
}

export interface ProviderModel {
  id: string;
  name?: string;
  prompt?: number; // $ за 1M токенов, если провайдер отдаёт
  completion?: number;
}

export interface ProviderTest {
  ok: boolean;
  model: string;
  reply: string;
  seconds: number;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  cost?: number | null;
}

export interface TokenInfo {
  name: string;
  created: string | null;
  created_by: string | null;
}

export type Level = "error" | "warning" | "info";

export interface Finding {
  level: Level;
  code: string;
  ref: string;
  message: string;
  source?: string;
}

export interface Part {
  id: string;
  name: string;
  role?: string;
  mass_kg?: number;
}

export interface Weld {
  id: string;
  parts: string[];
  leg?: number;
  length?: number;
  note?: string;
}

export interface Calc {
  id: string;
  title: string;
  formula?: string;
  values?: Record<string, number>;
  demand?: number;
  capacity?: number;
  unit?: string;
  K: number;
  K_req: number;
  ref?: string;
  ok: boolean;
}

export interface Assumption {
  id: string;
  text: string;
  topic?: string;
}

export interface Summary {
  mass_kg: number;
  envelope_mm?: number[];
  parts?: number;
  welds?: number;
  fasteners?: number;
  weld_length_mm?: number;
  K?: Record<string, number>;
  K_min?: number;
  K_min_item?: string;
  findings: Partial<Record<Level, number>>;
  blanks?: Record<string, number>;
}

export interface Report {
  project: string;
  project_title?: string;
  variant: string;
  title?: string;
  description?: string;
  summary: Summary;
  parts: Part[];
  welds: Weld[];
  calc: Calc[];
  findings: Finding[];
  assumptions: Assumption[];
  derived?: Record<string, string | number>;
  metrics?: { id: string; title: string; value: string | number }[];
  urls: { glb: string | null; step: string | null; svg: Record<string, string>; sketch?: Record<string, string> };
  built_at: string;
  geometry_at?: string | null; // 3D/STEP могут быть старше отчёта: сборка без экспорта переносит ссылки прошлой
  sketch?: SketchData | null; // эскиз с размерами (M2.1): виды и размеры из <v>_sketch.json
}

export interface SketchData {
  views: Record<string, LayoutView>;
  dims: LayoutDim[];
  entities: string[];
  notes: string[];
}

export type CommitKind = "agent" | "user" | "system" | "revert";

export interface FeedCommit extends Commit {
  hash: string;
  files: string[];
  kind: CommitKind;
  is_head: boolean;
  reviewed: { by: string; at: string | null } | null;
}

export interface CommitsResponse {
  commits: FeedCommit[];
  unreviewed: number;
  head: string | null;
}

export interface DeltaNum {
  a: number | null;
  b: number | null;
  delta: number | null;
}

export interface CommitDiff {
  variant: string;
  a: string | null;
  b: string;
  summary: string;
  cached: boolean;
  entities: Record<string, { added?: string[]; removed?: string[]; changed?: Record<string, unknown> }>;
  geometry: Record<string, unknown>;
  deltas: Record<string, DeltaNum | Record<string, { a: number | null; b: number | null }>>;
  findings: { added: string[]; removed: string[] };
}

export interface CommitModel {
  url: string;
  commit: string;
  built: boolean;
}

export interface CompareRow {
  metric: string;
  values: Record<string, number | string | null>;
  best: string[];
}

export interface CompareVariant extends VariantOverview {
  glb: string | null;
  sketch?: Record<string, string>; // эскизы по видам
  sketch_views?: Record<string, LayoutView>;
}

export interface CompareDimRow {
  id: string;
  axis: string;
  views: string[];
  values: Record<string, string | null>;
}

export interface CompareParamRow {
  path: string;
  values: Record<string, unknown>;
}

export interface CompareResponse {
  summary: string;
  variants: CompareVariant[];
  rows: CompareRow[];
  dim_rows?: CompareDimRow[];
  param_rows?: CompareParamRow[];
}

export interface ParamField {
  path: string;
  value: number | string | boolean | null;
  type: "number" | "string" | "boolean" | "json";
  source: "project" | "variant";
}

export interface ParamsResponse {
  variant: string;
  file: string;
  fields: ParamField[];
}

export interface DraftResponse {
  draft: string;
  variant: string;
  changes: Record<string, unknown>;
  file: string;
  numbers: {
    mass_kg?: number;
    k_min?: number;
    k_min_item?: string;
    errors: number;
    warnings: number;
  };
  diff: CommitDiff;
  urls: { glb: string | null; head_glb: string | null };
}

export interface ReviewItem {
  id: string;
  text: string;
  status: "open" | "resolved";
  author: string;
  created: string;
  variant?: string;
  part?: string;
  point?: [number, number, number];
  stroke?: ReviewStroke; // росчерк на компоновочном эскизе (M2.3): вид и точки модели
  answer?: string;
  resolved_by?: string;
  resolved_at?: string;
}

export interface ReviewStroke {
  view: string; // main | left | top
  points: [number, number, number][];
}

export type TaskStatus = "queued" | "running" | "done" | "failed" | "stopped" | "limit";

export interface AgentTask {
  id: string;
  project: string;
  variant: string | null;
  text: string;
  user: string;
  created: string;
  max_steps: number;
  status: TaskStatus;
  started?: string;
  finished?: string;
  updated?: string;
  steps?: number;
  result?: string | null;
  error?: string | null;
  stop_requested?: boolean;
  attachments?: string[]; // вложения проекта (attachments/<файл>), переданные агенту с задачей
  provider?: string | null; // провайдер модели (D29); пусто — по умолчанию
  model?: string | null;
  usage?: { prompt_tokens?: number; completion_tokens?: number; cost?: number } | null;
}

export interface TaskEvent {
  t: string;
  type:
    | "start"
    | "step"
    | "assistant"
    | "tool_call"
    | "tool_result"
    | "done"
    | "error"
    | "stopped"
    | "limit"
    | "attachment"
    | "images";
  text?: string;
  name?: string;
  args?: Record<string, unknown>;
  seconds?: number; // tool_result: длительность инструмента; step: сколько думала модель
  n?: number; // step: номер шага
  runner?: string;
  tools?: number;
  cost_usd?: number;
  path?: string; // attachment: путь вложения
  images?: number | string[]; // attachment: сколько изображений ушло модели; tool_result: файлы задачи с картинками
  count?: number; // images: сколько изображений из инструментов ушло модели
  provider?: string; // start: провайдер и модель
  model?: string;
  usage?: { prompt_tokens?: number; completion_tokens?: number; cost?: number }; // done / limit / stopped
}

// --- вложения конструктора (M2.3, D28): файлы в attachments/ репозитория проекта
export type AttachmentKind = "image" | "svg" | "pdf" | "excalidraw" | "text" | "cad" | "file";

export interface Attachment {
  path: string; // attachments/<файл>
  name: string;
  kind: AttachmentKind;
  mime: string;
  bytes: number;
  width: number | null;
  height: number | null;
  author: string | null;
  date: string | null;
  note: string | null; // заметка конструктора при загрузке (из сообщения коммита)
}

export const attachmentUrl = (project: string, a: Attachment | string) =>
  `/api/projects/${encodeURIComponent(project)}/attachments/${encodeURIComponent(
    typeof a === "string" ? a.replace(/^attachments\//, "") : a.name,
  )}`;
/** Миниатюра для галереи (картинка, SVG, первая страница PDF); у текста и моделей CAD её нет (404). */
export const attachmentThumbUrl = (project: string, a: Attachment) => `${attachmentUrl(project, a)}/thumb?v=${a.bytes}`;

// --- граф связей (M2.2, D27): производный индекс сущностей и связей в Postgres
export interface GraphNode {
  ref: string; // kind:id[/kind:id]
  kind: string;
  eid: string;
  name: string;
  variants: string[]; // варианты, где сущность есть (пусто — уровень проекта)
  depth: number;
  data: Record<string, unknown>;
}

export interface GraphEdge {
  src: string;
  dst: string;
  kind: string;
  variant: string;
  data: Record<string, unknown>;
}

export interface LinksResponse {
  project: string;
  variant: string | null;
  ref: string;
  hops: number;
  direction: "both" | "in" | "out";
  kinds: string[];
  root: GraphNode | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
  summary: string;
}

export interface SearchHit {
  project: string;
  variant: string;
  ref: string;
  kind: string;
  eid: string;
  name: string;
  data: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  truncated: boolean;
  summary: string;
}

export interface WhereUsedResponse {
  ref: string;
  project: string | null;
  uses: { project: string; variant: string; src: string; kind: string; name: string }[];
  by_project: Record<string, number>;
  truncated: boolean;
  summary: string;
}

export interface BuildResponse {
  summary: string;
  variants: { variant: string; line: string }[];
}

export const api = {
  me: () => getJson<Me>("/api/me"),
  projects: () => getJson<ProjectsResponse>("/api/projects"),
  projectCreate: (body: { name: string; title?: string; template?: string; folder?: string; parent?: string }) =>
    getJson<ProjectCreated>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  report: (project: string, variant: string) =>
    getJson<Report>(`/api/projects/${encodeURIComponent(project)}/variants/${encodeURIComponent(variant)}/report`),
  tokens: () => getJson<{ tokens: TokenInfo[]; mcp_url: string }>("/api/tokens"),
  tokenCreate: (name: string) =>
    getJson<TokenInfo & { token: string; command: string; mcp_url: string }>("/api/tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  tokenDelete: (name: string) =>
    getJson<{ ok: boolean }>(`/api/tokens/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),
  tasks: (project: string) =>
    getJson<{ tasks: AgentTask[]; active: AgentTask | null }>(`/api/projects/${encodeURIComponent(project)}/tasks`),
  taskCreate: (
    project: string,
    text: string,
    variant?: string,
    attachments?: string[],
    provider?: string,
    model?: string,
  ) =>
    getJson<AgentTask>(`/api/projects/${encodeURIComponent(project)}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        variant,
        ...(attachments?.length ? { attachments } : {}),
        ...(provider ? { provider } : {}),
        ...(model ? { model } : {}),
      }),
    }),
  providers: () => getJson<ProvidersResponse>("/api/providers"),
  providerSave: (body: Partial<Provider> & { id: string; key?: string }) =>
    getJson<Provider>("/api/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  providerDelete: (id: string) =>
    getJson<{ ok: boolean }>(`/api/providers/${encodeURIComponent(id)}`, { method: "DELETE" }),
  providerDefault: (id: string) =>
    getJson<Provider>(`/api/providers/${encodeURIComponent(id)}/default`, { method: "POST" }),
  providerTest: (id: string, model?: string) =>
    getJson<ProviderTest>(`/api/providers/${encodeURIComponent(id)}/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(model ? { model } : {}),
    }),
  providerModels: (body: { id?: string; base_url?: string; key?: string }) =>
    getJson<{ models: ProviderModel[] }>("/api/providers/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  attachments: (project: string) =>
    getJson<{ items: Attachment[] }>(`/api/projects/${encodeURIComponent(project)}/attachments`),
  attachmentUpload: (project: string, file: File, note?: string) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    if (note) fd.append("note", note);
    return getJson<{ item: Attachment; commit: Commit }>(`/api/projects/${encodeURIComponent(project)}/attachments`, {
      method: "POST",
      body: fd,
    });
  },
  attachmentDelete: (project: string, name: string) =>
    getJson<{ path: string; commit: Commit }>(
      `/api/projects/${encodeURIComponent(project)}/attachments/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ),
  taskEvents: (id: string, since: number) =>
    getJson<{
      events: TaskEvent[];
      next: number;
      total: number;
      task: AgentTask;
    }>(`/api/tasks/${encodeURIComponent(id)}/events?since=${since}`),
  /** Картинка, которую агент получил от инструмента в ходе задачи (tool_result.images). */
  taskFileUrl: (id: string, name: string) => `/api/tasks/${encodeURIComponent(id)}/files/${encodeURIComponent(name)}`,
  taskStop: (id: string) =>
    getJson<AgentTask>(`/api/tasks/${encodeURIComponent(id)}/stop`, {
      method: "POST",
    }),
  review: (project: string) =>
    getJson<{ items: ReviewItem[] }>(`/api/projects/${encodeURIComponent(project)}/review?status=all`),
  reviewAdd: (
    project: string,
    body: {
      text: string;
      variant?: string;
      part?: string | null;
      point?: number[] | null;
      stroke?: ReviewStroke | null;
    },
  ) =>
    getJson<{ item: ReviewItem }>(`/api/projects/${encodeURIComponent(project)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  reviewResolve: (project: string, id: string, answer: string) =>
    getJson<{ item: ReviewItem }>(
      `/api/projects/${encodeURIComponent(project)}/review/${encodeURIComponent(id)}/resolve`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer }),
      },
    ),
  params: (project: string, variant: string) =>
    getJson<ParamsResponse>(
      `/api/projects/${encodeURIComponent(project)}/variants/${encodeURIComponent(variant)}/params`,
    ),
  draft: (project: string, variant: string, params: Record<string, string | number | boolean>) =>
    getJson<DraftResponse>(
      `/api/projects/${encodeURIComponent(project)}/variants/${encodeURIComponent(variant)}/draft`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params }),
      },
    ),
  saveParams: (
    project: string,
    variant: string,
    params: Record<string, string | number | boolean>,
    message: string,
    draft: string | null,
  ) =>
    getJson<{ commit: Commit }>(
      `/api/projects/${encodeURIComponent(project)}/variants/${encodeURIComponent(variant)}/params`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params, message, draft }),
      },
    ),
  compare: (project: string) => getJson<CompareResponse>(`/api/projects/${encodeURIComponent(project)}/compare`),
  commits: (project: string, limit = 50) =>
    getJson<CommitsResponse>(`/api/projects/${encodeURIComponent(project)}/commits?limit=${limit}`),
  commitDiff: (project: string, hash: string, variant: string) =>
    getJson<CommitDiff>(
      `/api/projects/${encodeURIComponent(project)}/commits/${hash}/diff?variant=${encodeURIComponent(variant)}`,
    ),
  commitModel: (project: string, hash: string, variant: string) =>
    getJson<CommitModel>(
      `/api/projects/${encodeURIComponent(project)}/commits/${hash}/model?variant=${encodeURIComponent(variant)}`,
    ),
  setReviewed: (project: string, hash: string, reviewed: boolean) =>
    getJson<{ reviewed: FeedCommit["reviewed"] }>(
      `/api/projects/${encodeURIComponent(project)}/commits/${hash}/reviewed`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewed }),
      },
    ),
  revert: (project: string, commit: string, message?: string) =>
    getJson<{ commit: Commit }>(`/api/projects/${encodeURIComponent(project)}/revert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ commit, message }),
    }),
  build: (project: string, variant: string) =>
    getJson<BuildResponse>(
      `/api/projects/${encodeURIComponent(project)}/build?variant=${encodeURIComponent(variant)}`,
      {
        method: "POST",
      },
    ),
  layout: (project: string, variant?: string) =>
    getJson<LayoutResponse>(
      `/api/projects/${encodeURIComponent(project)}/layout` +
        (variant ? `?variant=${encodeURIComponent(variant)}` : ""),
    ),
  layoutEdit: (project: string, body: LayoutEditRequest) =>
    getJson<LayoutEditResponse>(`/api/projects/${encodeURIComponent(project)}/layout/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  layoutApprove: (project: string) =>
    getJson<LayoutApproval & { commit: Commit; task?: AgentTask | null }>(
      `/api/projects/${encodeURIComponent(project)}/layout/approve`,
      { method: "POST" },
    ),
  // --- папки, узлы, корзина, решения, комплект, разговор (M2.5, D32)
  folders: () => getJson<FoldersResponse>("/api/folders"),
  folderCreate: (title: string) =>
    getJson<Folder>("/api/folders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }),
  folderDelete: (id: string) => getJson<{ ok: boolean }>(`/api/folders/${encodeURIComponent(id)}`, { method: "DELETE" }),
  projectMove: (project: string, body: { folder?: string | null; parent?: string | null }) =>
    getJson<{ folder: string | null; parent: string | null }>(`/api/projects/${encodeURIComponent(project)}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  projectDelete: (project: string) =>
    getJson<{ id: string; name: string; nodes: { id: string; name: string }[] }>(
      `/api/projects/${encodeURIComponent(project)}`,
      { method: "DELETE" },
    ),
  trashRestore: (id: string) =>
    getJson<{ name: string }>(`/api/trash/${encodeURIComponent(id)}/restore`, { method: "POST" }),
  choose: (project: string, variant: string) =>
    getJson<{ variant: string | null; commit: Commit }>(`/api/projects/${encodeURIComponent(project)}/choose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ variant }),
    }),
  kit: (project: string) =>
    getJson<{ variant: string | null; files: KitFile[] }>(`/api/projects/${encodeURIComponent(project)}/kit`),
  kitBuild: (project: string) =>
    getJson<{ variant: string; files: KitFile[] }>(`/api/projects/${encodeURIComponent(project)}/kit`, {
      method: "POST",
    }),
  kitZipUrl: (project: string) => `/api/projects/${encodeURIComponent(project)}/kit.zip`,
  thread: (project: string) => getJson<ThreadResponse>(`/api/projects/${encodeURIComponent(project)}/thread`),
  projectRead: (project: string) =>
    getJson<{ spec: Record<string, unknown>; attachments: string[] }>(`/api/projects/${encodeURIComponent(project)}`),
  graphLinks: (project: string, ref: string, opts?: { variant?: string; hops?: number; direction?: string }) => {
    const q = new URLSearchParams({ ref });
    if (opts?.variant) q.set("variant", opts.variant);
    if (opts?.hops) q.set("hops", String(opts.hops));
    if (opts?.direction) q.set("direction", opts.direction);
    return getJson<LinksResponse>(`/api/projects/${encodeURIComponent(project)}/graph/links?${q}`);
  },
  graphWhereUsed: (project: string, ref: string) =>
    getJson<WhereUsedResponse>(
      `/api/projects/${encodeURIComponent(project)}/graph/where-used?ref=${encodeURIComponent(ref)}`,
    ),
  graphSearch: (q: string, opts?: { project?: string; kind?: string }) => {
    const p = new URLSearchParams({ q });
    if (opts?.project) p.set("project", opts.project);
    if (opts?.kind) p.set("kind", opts.kind);
    return getJson<SearchResponse>(`/api/graph/search?${p}`);
  },
  text: async (url: string): Promise<string> => {
    const r = await fetch(url);
    if (!r.ok) throw new ApiError(r.status, `${r.status} ${r.statusText}`);
    return r.text();
  },
};
