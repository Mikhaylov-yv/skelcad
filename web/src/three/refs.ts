// Связь ссылок из замечаний и расчётов (`part:cheek_L/hole:bore`, `weld:w_x`, `fastener:anchor_a00`,
// `fasteners`, `interface:axle`, `section:wall`) с узлами GLB. Узлы GLB названы по id сущностей модели.
import type { Report } from "../api";

export interface NodeIndex {
  parts: string[]; // id деталей из отчёта
  fasteners: string[]; // верхние узлы GLB, которых нет среди деталей и которые похожи на крепёж
  other: string[]; // остальные верхние узлы (оси, интерфейсы)
}

export function indexNodes(report: Report, topLevel: string[]): NodeIndex {
  const parts = report.parts.map((p) => p.id);
  const rest = topLevel.filter((n) => !parts.includes(n));
  const fastRefs = new Set(
    report.findings.filter((f) => f.ref.startsWith("fastener:")).map((f) => f.ref.slice("fastener:".length)),
  );
  const fasteners = rest.filter((n) => fastRefs.has(n) || /^(anchor|bolt|fastener)/.test(n));
  const other = rest.filter((n) => !fasteners.includes(n));
  return { parts, fasteners, other };
}

/** Какие узлы подсветить по ссылке. Пустой список — подсвечивать нечего (сечение, сборка целиком). */
export function nodesForRef(ref: string, report: Report, idx: NodeIndex): string[] {
  const [kind, restRaw] = ref.split(":", 2);
  const rest = (restRaw ?? "").split("/")[0];
  switch (kind) {
    case "part": {
      if (idx.parts.includes(rest)) return [rest];
      // «part:cheek» — роль или префикс: все детали с таким role или id, начинающимся на него
      const byRole = report.parts.filter((p) => p.role === rest || p.id.startsWith(rest)).map((p) => p.id);
      return byRole;
    }
    case "weld": {
      const w = report.welds.find((w) => w.id === rest);
      return w ? w.parts.filter((p) => idx.parts.includes(p)) : [];
    }
    case "welds":
      return [];
    case "fastener":
      return idx.fasteners.includes(rest) ? [rest] : [];
    case "fasteners":
      return idx.fasteners;
    case "interface":
      return idx.other.includes(rest) ? [rest] : [];
    default:
      return [];
  }
}
