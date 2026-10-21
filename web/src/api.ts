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

export type LayoutStateKind = "none" | "approved" | "changed" | "invalid";

export interface ProjectOverview {
  name: string;
  title: string;
  standards: string[];
  variants: VariantOverview[];
  last_commit: Commit | null;
  state: "constructor" | "agent";
  task?: { id: string; status: TaskStatus; text: string } | null;
  unreviewed?: number;
  layout?: { state: LayoutStateKind; by?: string | null; at?: string | null };
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

export interface ProjectsResponse {
  summary: string;
  projects: ProjectOverview[];
  templates: string[];
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
  answer?: string;
  resolved_by?: string;
  resolved_at?: string;
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
}

export interface TaskEvent {
  t: string;
  type:
    | "start"
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
  seconds?: number;
  runner?: string;
  tools?: number;
  cost_usd?: number;
  path?: string; // attachment: путь вложения
  images?: number; // attachment: сколько изображений ушло модели
  count?: number; // images: сколько изображений из инструментов ушло модели
}

// --- вложения конструктора (M2.3, D28): файлы в attachments/ репозитория проекта
export type AttachmentKind = "image" | "svg" | "pdf" | "excalidraw" | "file";

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
}

export const attachmentUrl = (project: string, a: Attachment | string) =>
  `/api/projects/${encodeURIComponent(project)}/attachments/${encodeURIComponent(
    typeof a === "string" ? a.replace(/^attachments\//, "") : a.name,
  )}`;

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
  taskCreate: (project: string, text: string, variant?: string, attachments?: string[]) =>
    getJson<AgentTask>(`/api/projects/${encodeURIComponent(project)}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, variant, ...(attachments?.length ? { attachments } : {}) }),
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
  layoutApprove: (project: string) =>
    getJson<LayoutApproval & { commit: Commit }>(`/api/projects/${encodeURIComponent(project)}/layout/approve`, {
      method: "POST",
    }),
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
