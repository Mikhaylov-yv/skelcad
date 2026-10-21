import { useState, type FormEvent } from "react";
import { api, type Folder, type TemplateInfo } from "../api";
import { S } from "../strings";
import { NAME_RE, slug } from "./translit";

/** Форма «Новый проект» / «Новый узел»: название изделия, код (подставляется транслитерацией, можно поправить),
 *  папка или родитель, основа — пустой проект или копия примера. Создаётся коммитом конструктора. */
export function NewProjectForm({
  templates,
  folders,
  folder,
  parent,
  parentTitle,
  onCancel,
  onCreated,
}: {
  templates: TemplateInfo[];
  folders: Folder[];
  folder?: string | null;
  parent?: string | null;
  parentTitle?: string;
  onCancel: () => void;
  onCreated: (name: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [name, setName] = useState<string | null>(null); // null — код ещё не правили руками
  const [template, setTemplate] = useState("");
  const [fld, setFld] = useState(folder ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const code = name ?? slug(title);
  const valid = NAME_RE.test(code);
  const node = !!parent;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setErr(null);
    api
      .projectCreate({
        name: code,
        title: title.trim() || undefined,
        template: template || undefined,
        folder: !node && fld ? fld : undefined,
        parent: parent || undefined,
      })
      .then((r) => onCreated(r.project.name))
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(false));
  };
  return (
    <form className="projects__new" onSubmit={submit} aria-label={node ? S.wb.newNode : S.projects.newProject}>
      <h3>{node ? S.wb.newNode.replace("+ ", "") : S.projects.newProject}</h3>
      <p className="muted small" style={{ margin: 0 }}>
        {node ? S.wb.newNodeHint + (parentTitle ? ` «${parentTitle}»` : "") : S.projects.newHint}
      </p>
      <label>
        {S.projects.newTitle}
        <input
          autoFocus
          value={title}
          placeholder={node ? "например, Рама" : S.projects.newTitlePlaceholder}
          onChange={(e) => setTitle(e.target.value)}
          disabled={busy}
          data-field="title"
        />
      </label>
      <label>
        {S.projects.newName}
        <input
          className="mono"
          value={code}
          placeholder={S.projects.newNamePlaceholder}
          onChange={(e) => setName(e.target.value.trim())}
          aria-invalid={code !== "" && !valid}
          disabled={busy}
        />
        <span className="small">{S.projects.newNameHint}</span>
      </label>
      {!node && folders.length > 0 && (
        <label>
          {S.start.folders}
          <select value={fld} onChange={(e) => setFld(e.target.value)} disabled={busy} data-field="folder">
            <option value="">{S.start.loose}</option>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.title}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        {S.projects.newTemplate}
        <select value={template} onChange={(e) => setTemplate(e.target.value)} disabled={busy}>
          <option value="">{S.projects.newTemplateEmpty}</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {S.projects.newTemplateFrom(t.title || t.id, t.id)}
            </option>
          ))}
        </select>
      </label>
      {err && (
        <p className="level-error" role="alert" style={{ margin: 0 }}>
          {err}
        </p>
      )}
      <div className="commit__actions" style={{ margin: 0 }}>
        <button type="submit" className="primary" disabled={!valid || busy} aria-busy={busy} data-act="create">
          {busy ? S.projects.creating : S.projects.create}
        </button>
        <button type="button" className="link" onClick={onCancel} disabled={busy}>
          {S.projects.cancel}
        </button>
      </div>
    </form>
  );
}
