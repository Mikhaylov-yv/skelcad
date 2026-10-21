import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import { api, attachmentUrl, type Attachment, type ThreadMessage } from "../../api";
import { S } from "../../strings";

/** Задание: первое сообщение конструктора агенту (или назначение из project.yaml) и вложения — наброски, фото. */
export function BriefPane({
  project,
  purpose,
  description,
  messages,
  locked,
}: {
  project: string;
  purpose: string;
  description: string;
  messages: ThreadMessage[];
  locked: boolean;
}) {
  const first = messages.find((m) => m.who === "you");
  const [files, setFiles] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(
    () =>
      api
        .attachments(project)
        .then((r) => setFiles(r.items))
        .catch(() => undefined),
    [project],
  );
  useEffect(() => {
    load();
  }, [load]);
  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    const list = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (!list.length) return;
    setUploading(true);
    setErr(null);
    (async () => {
      for (const f of list) await api.attachmentUpload(project, f);
    })()
      .catch((e: Error) => setErr(e.message))
      .finally(() => {
        setUploading(false);
        load();
      });
  };
  const images = files.filter((f) => f.kind === "image" || f.kind === "svg");
  return (
    <div className="brief">
      <div className="brief__text">
        {first ? (
          <>
            <p className="brief__quote">{first.text}</p>
            <p className="muted small">
              {first.by} · {first.at ? new Date(first.at).toLocaleString("ru-RU") : ""}
            </p>
          </>
        ) : purpose || description ? (
          <>
            {purpose && <p className="brief__quote">{purpose}</p>}
            {description && <p>{description}</p>}
          </>
        ) : (
          <p className="empty">{S.wb.briefEmpty}</p>
        )}
      </div>
      <div className="brief__files">
        {images.map((f) => (
          <figure key={f.path} className="pic" style={{ height: 220 }}>
            <img src={attachmentUrl(project, f)} alt={f.name} />
            <figcaption className="muted small">{f.name}</figcaption>
          </figure>
        ))}
        {files
          .filter((f) => !images.includes(f))
          .map((f) => (
            <a key={f.path} className="file" href={attachmentUrl(project, f)} target="_blank" rel="noreferrer">
              <span className="file__ext">{f.kind.toUpperCase()}</span>
              <span className="file__n">{f.name}</span>
            </a>
          ))}
        <div>
          <input ref={input} type="file" multiple hidden accept="image/*,.pdf,.excalidraw,.svg" onChange={onPick} />
          <button type="button" onClick={() => input.current?.click()} disabled={locked || uploading} aria-busy={uploading}>
            {uploading ? S.agent.uploading : S.wb.briefAttach}
          </button>
          <span className="muted small"> {S.wb.briefAttachHint}</span>
        </div>
        {err && (
          <p className="level-error small" role="alert">
            {err}
          </p>
        )}
      </div>
    </div>
  );
}
