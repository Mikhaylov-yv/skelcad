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

export interface BuildResponse {
  summary: string;
  variants: { variant: string; line: string }[];
}

export const api = {
  me: () => getJson<Me>("/api/me"),
  projects: () => getJson<ProjectsResponse>("/api/projects"),
  report: (project: string, variant: string) =>
    getJson<Report>(`/api/projects/${encodeURIComponent(project)}/variants/${encodeURIComponent(variant)}/report`),
  build: (project: string, variant: string) =>
    getJson<BuildResponse>(`/api/projects/${encodeURIComponent(project)}/build?variant=${encodeURIComponent(variant)}`, {
      method: "POST",
    }),
};
