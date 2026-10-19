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

export interface ProjectOverview {
  name: string;
  title: string;
  standards: string[];
  variants: VariantOverview[];
  last_commit: Commit | null;
  state: "constructor" | "agent";
  unreviewed?: number;
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
  const r = await fetch(url, { ...init, headers: { Accept: "application/json", ...(init?.headers ?? {}) } });
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
  logout_url: string | null;
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
  urls: { glb: string | null; step: string | null; svg: Record<string, string> };
  built_at: string;
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
}

export interface CompareResponse {
  summary: string;
  variants: CompareVariant[];
  rows: CompareRow[];
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
  numbers: { mass_kg?: number; k_min?: number; k_min_item?: string; errors: number; warnings: number };
  diff: CommitDiff;
  urls: { glb: string | null; head_glb: string | null };
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
  params: (project: string, variant: string) =>
    getJson<ParamsResponse>(`/api/projects/${encodeURIComponent(project)}/variants/${encodeURIComponent(variant)}/params`),
  draft: (project: string, variant: string, params: Record<string, string | number | boolean>) =>
    getJson<DraftResponse>(`/api/projects/${encodeURIComponent(project)}/variants/${encodeURIComponent(variant)}/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params }),
    }),
  saveParams: (
    project: string,
    variant: string,
    params: Record<string, string | number | boolean>,
    message: string,
    draft: string | null,
  ) =>
    getJson<{ commit: Commit }>(`/api/projects/${encodeURIComponent(project)}/variants/${encodeURIComponent(variant)}/params`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params, message, draft }),
    }),
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
    getJson<{ reviewed: FeedCommit["reviewed"] }>(`/api/projects/${encodeURIComponent(project)}/commits/${hash}/reviewed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed }),
    }),
  revert: (project: string, commit: string, message?: string) =>
    getJson<{ commit: Commit }>(`/api/projects/${encodeURIComponent(project)}/revert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ commit, message }),
    }),
  build: (project: string, variant: string) =>
    getJson<BuildResponse>(`/api/projects/${encodeURIComponent(project)}/build?variant=${encodeURIComponent(variant)}`, {
      method: "POST",
    }),
};
