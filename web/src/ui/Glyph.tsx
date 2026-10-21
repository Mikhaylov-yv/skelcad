// Значки шагов агента: линия 1.75, без заливки — тон как у текста. Имена — из agentSteps.Glyph плюс служебные.
import type { Glyph as Name } from "./agentSteps";

const PATHS: Record<Name | "ok" | "error" | "warn" | "spin" | "chevron", string> = {
  read: "M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5zM4 20.5V5.5M8 7h8M8 10.5h8",
  write: "M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17zM13 8l3 3",
  build: "M12 3 4 7v10l8 4 8-4V7zM4 7l8 4 8-4M12 11v10",
  check: "M12 3 4 6v6c0 4.5 3.5 8 8 9 4.5-1 8-4.5 8-9V6zM9 12l2 2 4-4",
  measure: "M3 17 17 3l4 4L7 21zM8 12l2 2M11 9l2 2M14 6l2 2",
  image: "M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15 9h.01",
  search: "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM20 20l-4.5-4.5",
  catalog: "M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17V4M8 20h11M9 8h6",
  links: "M10 13a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.5 1.5M14 11a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.5-1.5",
  revert: "M4 10h10a5 5 0 0 1 0 10h-3M4 10l4-4M4 10l4 4",
  review: "M4 5h16v11H9l-5 4zM8 9h8M8 12h5",
  note: "M5 4h14v12H10l-4 4v-4H5z",
  start: "M6 4l13 8-13 8z",
  wait: "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z",
  ok: "M5 12l4 4L19 6",
  error: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 8v5M12 16h.01",
  warn: "M12 3 2 20h20zM12 10v4M12 17h.01",
  spin: "M12 3a9 9 0 0 1 9 9",
  chevron: "M9 6l6 6-6 6",
};

export function Glyph({ name, className, title }: { name: keyof typeof PATHS; className?: string; title?: string }) {
  return (
    <svg
      className={"glyph glyph--" + name + (className ? " " + className : "")}
      viewBox="0 0 24 24"
      width="16"
      height="16"
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
      focusable="false"
    >
      {title && <title>{title}</title>}
      <path
        d={PATHS[name]}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
