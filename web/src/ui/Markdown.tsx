// Отчёт агента и его реплики приходят в markdown: заголовки, списки, **жирный**, `код`.
// Небольшой разбор в элементы React — без HTML-вставок и внешних библиотек.
import { Fragment, type ReactNode } from "react";

type Block =
  | { kind: "h"; text: string }
  | { kind: "p"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "code"; text: string };

export function parseBlocks(src: string): Block[] {
  const out: Block[] = [];
  const lines = src.replace(/\r/g, "").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      out.push({ kind: "code", text: buf.join("\n") });
      continue;
    }
    const h = /^#{1,6}\s+(.*)$/.exec(line);
    if (h) {
      out.push({ kind: "h", text: h[1].trim() });
      i++;
      continue;
    }
    const ul = /^\s*[-*•]\s+/;
    const ol = /^\s*\d+[.)]\s+/;
    if (ul.test(line) || ol.test(line)) {
      const ordered = ol.test(line);
      const re = ordered ? ol : ul;
      const items: string[] = [];
      while (i < lines.length && re.test(lines[i])) {
        let item = lines[i].replace(re, "");
        i++;
        // продолжение пункта с отступом
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !re.test(lines[i])) item += " " + lines[i++].trim();
        items.push(item);
      }
      out.push({ kind: ordered ? "ol" : "ul", items });
      continue;
    }
    const buf: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^#{1,6}\s/.test(lines[i]) &&
      !ul.test(lines[i]) &&
      !ol.test(lines[i]) &&
      !lines[i].startsWith("```")
    )
      buf.push(lines[i++].trim());
    out.push({ kind: "p", text: buf.join(" ") });
  }
  return out;
}

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;

/** Строка с **жирным**, *курсивом* и `кодом`. */
export function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, k) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={k}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`"))
      return (
        <code key={k} className="mono">
          {part.slice(1, -1)}
        </code>
      );
    if (part.length > 2 && part.startsWith("*") && part.endsWith("*")) return <em key={k}>{part.slice(1, -1)}</em>;
    return <Fragment key={k}>{part}</Fragment>;
  });
}

export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = parseBlocks(text);
  return (
    <div className={"md" + (className ? " " + className : "")}>
      {blocks.map((b, k) => {
        switch (b.kind) {
          case "h":
            return <h4 key={k}>{inline(b.text)}</h4>;
          case "ul":
            return (
              <ul key={k}>
                {b.items.map((it, j) => (
                  <li key={j}>{inline(it)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={k}>
                {b.items.map((it, j) => (
                  <li key={j}>{inline(it)}</li>
                ))}
              </ol>
            );
          case "code":
            return (
              <pre key={k} className="mono small">
                {b.text}
              </pre>
            );
          default:
            return <p key={k}>{inline(b.text)}</p>;
        }
      })}
    </div>
  );
}

/** Первая строка текста без разметки — для свёрнутых реплик и заголовков. */
export function firstLine(text: string, n = 140): string {
  const line =
    text
      .split("\n")
      .map((l) =>
        l
          .replace(/^#{1,6}\s+/, "")
          .replace(/\*\*|`/g, "")
          .trim(),
      )
      .find((l) => l) ?? "";
  return line.length > n ? line.slice(0, n - 1) + "…" : line;
}
