import type { Attachment, Commit, ThreadMessage } from "../../api";
import { S } from "../../strings";
import { FilesPane } from "./FilesPane";

/** Задание: первое сообщение конструктора агенту (или назначение из project.yaml) и зона файлов проекта —
 *  наброски, фото, примеры — крупными плитками. */
export function BriefPane({
  project,
  purpose,
  description,
  messages,
  locked,
  files,
  filesLoading,
  onFilesChanged,
  onAttach,
  onDeleted,
}: {
  project: string;
  purpose: string;
  description: string;
  messages: ThreadMessage[];
  locked: boolean;
  files: Attachment[];
  filesLoading: boolean;
  onFilesChanged: () => void;
  onAttach: (a: Attachment) => void;
  onDeleted: (a: Attachment, commit: Commit) => void;
}) {
  const first = messages.find((m) => m.who === "you");
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
      <h3 className="brief__h">{S.wb.files}</h3>
      <FilesPane project={project} files={files} loading={filesLoading} locked={locked} size="gallery" onChanged={onFilesChanged} onAttach={onAttach} onDeleted={onDeleted} />
    </div>
  );
}
