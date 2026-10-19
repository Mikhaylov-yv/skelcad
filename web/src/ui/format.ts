import { S } from "../strings";

const AGENT_RE = /^SkelCAD agent \((.+)\)$/;

/** «SkelCAD agent (claude-code)» → «агент (claude-code)»; человек — как есть. */
export function humanAuthor(author: string): { label: string; kind: "agent" | "human" } {
  const m = AGENT_RE.exec(author.trim());
  if (m) return { label: S.author.agent(m[1]), kind: "agent" };
  return { label: author, kind: "human" };
}

export function relativeTime(iso: string, now: Date = new Date()): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const s = Math.max(0, Math.round((now.getTime() - t) / 1000));
  if (s < 90) return S.time.justNow;
  const m = Math.round(s / 60);
  if (m < 60) return S.time.minutes(m);
  const h = Math.round(m / 60);
  if (h < 36) return S.time.hours(h);
  return S.time.days(Math.round(h / 24));
}

export function fmtNum(x: number | undefined, digits = 2): string {
  if (x === undefined || x === null || Number.isNaN(x)) return "—";
  return x.toLocaleString("ru-RU", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}
