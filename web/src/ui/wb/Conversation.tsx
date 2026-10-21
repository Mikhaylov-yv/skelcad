import { useEffect, useRef, useState, type ChangeEvent, type RefObject } from "react";
import { api, attachmentUrl, type Attachment, type ProjectOverview, type ProvidersResponse, type ThreadMessage } from "../../api";
import { S } from "../../strings";
import { Markdown, firstLine } from "../Markdown";
import { relativeTime } from "../format";
import { Progress } from "../../screens/Agent";
import { NextCard } from "./NextCard";

export type ThreadLine = ThreadMessage & { project: string; projectTitle: string };

/** Разговор по узлу или по всему изделию: закреплённый следующий шаг, сообщения конструктора и агента (отчёт
 *  в три строки, картинка, кнопка решения), служебные записи из коммитов, ход живой задачи, поле «Написать агенту». */
export function Conversation({
  p,
  messages,
  loading,
  scope,
  canScope,
  onScope,
  onAct,
  busy,
  composer,
  onSend,
  onChanged,
  taskTexts,
}: {
  p: ProjectOverview;
  messages: ThreadLine[];
  loading: boolean;
  scope: "node" | "all";
  canScope: boolean;
  onScope: (s: "node" | "all") => void;
  onAct: (act: string) => void;
  busy: string | null;
  composer: RefObject<HTMLTextAreaElement | null>;
  onSend: (text: string, attachments: string[], provider?: string, model?: string) => Promise<void>;
  onChanged: () => void;
  taskTexts: Record<string, string>;
}) {
  const list = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [picked, setPicked] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [providers, setProviders] = useState<ProvidersResponse | null>(null);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  useEffect(() => {
    api
      .providers()
      .then(setProviders)
      .catch(() => setProviders(null));
  }, []);
  // новое сообщение или шаг агента — к концу ленты
  const count = messages.length + (p.task ? 1 : 0);
  useEffect(() => {
    list.current?.scrollTo?.({ top: list.current.scrollHeight });
  }, [count, p.name, p.task?.id]);

  const locked = !!p.task;
  const submit = async () => {
    const t = text.trim();
    if (!t || sending || locked) return;
    setSending(true);
    setErr(null);
    try {
      await onSend(t, picked.map((a) => a.path), provider || undefined, model.trim() || undefined);
      setText("");
      setPicked([]);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSending(false);
    }
  };
  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (!files.length) return;
    setUploading(true);
    setErr(null);
    (async () => {
      for (const f of files) {
        const r = await api.attachmentUpload(p.name, f);
        setPicked((x) => [...x, r.item]);
      }
    })()
      .catch((e: Error) => setErr(e.message))
      .finally(() => setUploading(false));
  };
  const autoText = (m: ThreadLine) =>
    m.who === "you" && Object.values(taskTexts).includes(m.text) && m.by !== undefined;
  const chosenProvider = providers?.providers.find((x) => x.id === (provider || providers.default)) ?? null;

  return (
    <aside className="chat" aria-label={S.wb.conversation}>
      <div className="chat__head">
        <h3>{S.wb.conversation}</h3>
        {canScope && (
          <div className="seg" role="tablist" aria-label={S.wb.scopeAll}>
            <button type="button" role="tab" aria-selected={scope === "node"} className={scope === "node" ? "on" : ""} onClick={() => onScope("node")} title={p.title || p.name} data-act="scope:node">
              {p.title || p.name}
            </button>
            <button type="button" role="tab" aria-selected={scope === "all"} className={scope === "all" ? "on" : ""} onClick={() => onScope("all")} data-act="scope:all">
              {S.wb.scopeAll}
            </button>
          </div>
        )}
      </div>
      <div className="chat__pin">
        <NextCard p={p} onAct={onAct} busy={busy} stack />
      </div>
      <div className="chat__list" ref={list}>
        {loading && messages.length === 0 && <p className="muted small">{S.wb.threadLoading}</p>}
        {!loading && messages.length === 0 && !p.task && <p className="muted small">{S.wb.threadEmpty}</p>}
        {messages.map((m) => (
          <Message key={m.project + m.id} m={m} showNode={scope === "all"} auto={autoText(m)} />
        ))}
        {p.task && (
          <div className="msg msg--agent msg--live">
            <div className="msg__h">
              {S.wb.agentName} · {S.wb.now}
            </div>
            <Progress id={p.task.id} project={p.name} layoutUrl={`/p/${encodeURIComponent(p.name)}/s/layout`} onChange={onChanged} compact />
          </div>
        )}
      </div>
      <form
        className="chat__composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
          ref={composer}
          data-field="say"
          aria-label={S.wb.say}
          rows={3}
          value={text}
          placeholder={p.stages.brief === "done" ? S.wb.say : S.wb.sayBrief}
          onChange={(e) => setText(e.target.value)}
          disabled={locked || sending}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") submit();
          }}
        />
        {picked.length > 0 && (
          <div className="chat__files">
            {picked.map((a) => (
              <span key={a.path} className="filechip">
                {a.kind === "image" && <img src={attachmentUrl(p.name, a)} alt="" />}
                <span>{a.name}</span>
                <button type="button" className="link small" onClick={() => setPicked((x) => x.filter((y) => y.path !== a.path))} aria-label={S.wb.unpick}>
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        {err && (
          <p className="level-error small" role="alert">
            {err}
          </p>
        )}
        <div className="chat__row">
          <input ref={fileInput} type="file" multiple hidden accept="image/*,.pdf,.excalidraw,.svg" onChange={onPick} />
          <button type="button" className="ghost small" onClick={() => fileInput.current?.click()} disabled={locked || uploading} aria-busy={uploading}>
            {uploading ? S.agent.uploading : S.wb.attach}
          </button>
          {providers && providers.providers.length > 0 && (
            <details className="chat__settings">
              <summary className="small muted">
                {S.wb.settings}
                {chosenProvider ? `: ${chosenProvider.title}` : ""}
              </summary>
              <label className="small">
                {S.agent.provider}
                <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  <option value="">{S.wb.providerDefault(providers.providers.find((x) => x.id === providers.default)?.title ?? "")}</option>
                  {providers.providers.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="small">
                {S.agent.model}
                <input value={model} placeholder={chosenProvider?.model ?? ""} onChange={(e) => setModel(e.target.value)} list="wb-models" />
                <datalist id="wb-models">{chosenProvider?.models.map((m) => <option key={m} value={m} />)}</datalist>
              </label>
            </details>
          )}
          <span className="spacer" />
          <button type="submit" className="small" disabled={!text.trim() || locked || sending} aria-busy={sending} data-act="send">
            {sending ? S.wb.sending : S.wb.send}
          </button>
        </div>
      </form>
    </aside>
  );
}

function Message({ m, showNode, auto }: { m: ThreadLine; showNode: boolean; auto: boolean }) {
  const [open, setOpen] = useState(false);
  const when = m.at ? relativeTime(m.at) : "";
  const node = showNode ? ` · ${m.projectTitle}` : "";
  if (m.who === "system" || auto)
    return (
      <div className="msg msg--sys" title={m.at ?? undefined}>
        {auto ? S.wb.autoTask(m.text) : m.text}
        {m.by && !auto ? ` · ${m.by}` : ""}
        {node}
      </div>
    );
  if (m.who === "you")
    return (
      <div className="msg msg--you">
        <div className="msg__h">
          {S.wb.you} · {when}
          {node}
        </div>
        <div className="msg__t">{m.text}</div>
        {m.attachments && m.attachments.length > 0 && (
          <div className="msg__att small muted">{m.attachments.map((a) => a.replace(/^attachments\//, "")).join(", ")}</div>
        )}
      </div>
    );
  const failed = m.status && m.status !== "done";
  const long = (m.text ?? "").length > (m.brief ?? "").length;
  return (
    <div className={"msg msg--agent" + (failed ? " msg--failed" : "")}>
      <div className="msg__h">
        {S.wb.agentName} · {when}
        {node}
        {m.status && m.status !== "done" ? ` · ${S.agent.status[m.status]}` : ""}
      </div>
      <div className="msg__t">{open ? <Markdown text={m.text} /> : <span>{m.brief || firstLine(m.text, 300)}</span>}</div>
      {m.images && m.images.length > 0 && (
        <div className="msg__imgs">
          {m.images.map((u) => (
            <a key={u} href={u} target="_blank" rel="noreferrer">
              <img src={u} alt={S.agent.imageAlt} />
            </a>
          ))}
        </div>
      )}
      {long && (
        <button type="button" className="link small" onClick={() => setOpen((v) => !v)}>
          {open ? S.agent.detailsHide : S.wb.details}
        </button>
      )}
    </div>
  );
}
