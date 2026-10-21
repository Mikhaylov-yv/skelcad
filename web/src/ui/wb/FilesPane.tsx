import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { api, attachmentThumbUrl, attachmentUrl, type Attachment, type Commit } from "../../api";
import { S } from "../../strings";
import { relativeTime } from "../format";

export const ACCEPT = ".png,.jpg,.jpeg,.webp,.svg,.pdf,.excalidraw,.txt,.md,.csv,.yaml,.yml,.json,.step,.stp,.dxf,.iges,.igs,.docx,.xlsx,.zip";
const THUMB_KINDS = new Set(["image", "svg", "pdf"]);

/** Имя файла без штампа даты, который сервер ставит при загрузке. */
export const displayName = (a: Attachment) => a.name.replace(/^\d{8}-\d{4}-/, "");
export const fmtSize = (b: number) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} КБ` : `${(b / 1024 / 1024).toFixed(1)} МБ`);
export const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");

/** Загрузить файлы в проект по одному (каждый — коммит конструктора); onEach — для каждого сохранённого. */
export async function uploadAll(project: string, files: File[], note: string, onEach?: (a: Attachment) => void) {
  for (const f of files) {
    const r = await api.attachmentUpload(project, f, note || undefined);
    onEach?.(r.item);
  }
}

/** Зона файлов конструктора: наброски, фото, примеры, PDF, модели. Плитки с миниатюрами, перетаскивание и кнопка,
 *  «В сообщение» кладёт файл к следующему сообщению агенту, «Удалить» — коммит с возвратом из сообщения внизу. */
export function FilesPane({
  project,
  files,
  loading,
  locked,
  size,
  onChanged,
  onAttach,
  onDeleted,
  hint = true,
}: {
  project: string;
  files: Attachment[];
  loading: boolean;
  locked: boolean;
  size: "grid" | "gallery";
  onChanged: () => void;
  onAttach?: (a: Attachment) => void;
  onDeleted?: (a: Attachment, commit: Commit) => void;
  hint?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const upload = (list: File[]) => {
    if (!list.length || locked) return;
    setUploading(true);
    setErr(null);
    uploadAll(project, list, note.trim())
      .then(() => setNote(""))
      .catch((e: Error) => setErr(e.message))
      .finally(() => {
        setUploading(false);
        onChanged();
      });
  };
  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    const list = Array.from(e.target.files ?? []);
    e.target.value = "";
    upload(list);
  };
  const del = (a: Attachment) => {
    setBusy(a.path);
    setErr(null);
    api
      .attachmentDelete(project, a.name)
      .then((r) => onDeleted?.(a, r.commit))
      .catch((e: Error) => setErr(e.message))
      .finally(() => {
        setBusy(null);
        onChanged();
      });
  };
  return (
    <div
      className={"fz fz--" + size + (over ? " fz--over" : "")}
      onDragOver={(e) => {
        if (!hasFiles(e) || locked) return;
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false);
      }}
      onDrop={(e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setOver(false);
        upload(Array.from(e.dataTransfer.files));
      }}
      aria-label={S.wb.files}
      data-files={files.length}
    >
      <div className="fz__bar">
        <input ref={input} type="file" multiple hidden accept={ACCEPT} onChange={onPick} data-field="files" />
        <button type="button" onClick={() => input.current?.click()} disabled={locked || uploading} aria-busy={uploading} data-act="files-add">
          {uploading ? S.agent.uploading : S.wb.filesAdd}
        </button>
        <input className="fz__note" value={note} onChange={(e) => setNote(e.target.value)} placeholder={S.wb.fileNote} disabled={locked || uploading} aria-label={S.wb.fileNote} />
      </div>
      {hint && <p className="muted small fz__hint">{S.wb.filesHint}</p>}
      {err && (
        <p className="level-error small" role="alert">
          {err}
        </p>
      )}
      {files.length === 0 && !loading && <p className="empty fz__empty">{S.wb.filesEmpty}</p>}
      {files.length > 0 && (
        <ul className="fz__grid">
          {files.map((a) => {
            const url = attachmentUrl(project, a);
            const name = displayName(a);
            return (
              <li key={a.path} className={"ftile" + (busy === a.path ? " ftile--busy" : "")} data-file={a.name}>
                <a className="ftile__pic" href={url} target="_blank" rel="noreferrer" title={`${S.wb.fileOpen}: ${a.name}`}>
                  {THUMB_KINDS.has(a.kind) ? <img src={attachmentThumbUrl(project, a)} alt={name} loading="lazy" /> : <span className="ftile__ext">{a.name.split(".").pop()?.toUpperCase()}</span>}
                </a>
                <div className="ftile__n" title={a.name}>
                  {name}
                </div>
                <div className="ftile__meta muted small" title={a.note ?? ""}>
                  {a.note ? a.note : `${S.agent.kinds[a.kind] ?? a.kind} · ${fmtSize(a.bytes)}`}
                  {a.date ? ` · ${relativeTime(a.date)}` : ""}
                </div>
                <div className="ftile__acts">
                  {onAttach && (
                    <button type="button" className="link small" onClick={() => onAttach(a)} title={S.wb.fileToMessageHint} data-act={"file-attach:" + a.name}>
                      {S.wb.fileToMessage}
                    </button>
                  )}
                  <button type="button" className="link small" onClick={() => del(a)} disabled={locked || busy === a.path} data-act={"file-delete:" + a.name}>
                    {S.wb.fileDelete}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {over && <div className="fz__drop">{S.wb.filesDrop}</div>}
    </div>
  );
}
