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

export const api = {
  me: () => getJson<Me>("/api/me"),
  projects: () => getJson<ProjectsResponse>("/api/projects"),
};
