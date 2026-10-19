import type { Commit } from "../api";
import { humanAuthor, relativeTime } from "./format";

/** Строка про коммит без служебных терминов: кто, когда, что. Hash — в title. */
export function CommitLine({ c }: { c: Commit }) {
  const a = humanAuthor(c.author);
  return (
    <span className="commit-line" title={`${c.commit} · ${new Date(c.date).toLocaleString("ru-RU")}`}>
      <span className={"author author--" + a.kind}>{a.label}</span>
      <span className="muted"> · {relativeTime(c.date)} · </span>
      <span className="message">{c.message}</span>
    </span>
  );
}
