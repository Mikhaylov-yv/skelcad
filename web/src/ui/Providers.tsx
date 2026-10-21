// Провайдеры модели встроенного агента (D29): список, форма (шаблон, адрес, ключ, модель), список моделей и
// проверка по сохранённому ключу, «по умолчанию», удаление. Ключ уходит на сервер один раз и назад не приходит.
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type Provider, type ProviderModel, type ProvidersResponse, type ProviderTest } from "../api";
import { S } from "../strings";
import { relativeTime } from "../ui/format";

type Draft = {
  id: string;
  title: string;
  kind: "openai" | "claude-code";
  base_url: string;
  key: string;
  model: string;
  models: string[];
  existing: Provider | null;
};

const empty = (): Draft => ({
  id: "",
  title: "",
  kind: "openai",
  base_url: "",
  key: "",
  model: "",
  models: [],
  existing: null,
});

export function Providers({ admin }: { admin: boolean }) {
  const [data, setData] = useState<ProvidersResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // save | models | test:<id> | default:<id>
  const [note, setNote] = useState<string | null>(null);
  const [modelList, setModelList] = useState<ProviderModel[]>([]);

  const load = useCallback(() => {
    api
      .providers()
      .then((r) => {
        setData(r);
        setErr(null);
      })
      .catch((e: Error) => setErr(e.message));
  }, []);
  useEffect(load, [load]);

  const startNew = () => {
    const pre = data?.presets[0];
    setDraft({
      ...empty(),
      ...(pre ? { id: pre.id, title: pre.title, base_url: pre.base_url, model: pre.model } : {}),
    });
    setModelList([]);
    setNote(null);
  };
  const startEdit = (p: Provider) => {
    setDraft({
      id: p.id,
      title: p.title,
      kind: p.kind,
      base_url: p.base_url,
      key: "",
      model: p.model,
      models: p.models,
      existing: p,
    });
    setModelList(p.models.map((id) => ({ id })));
    setNote(null);
  };
  const applyPreset = (pid: string) => {
    if (!draft) return;
    const pre = data?.presets.find((x) => x.id === pid);
    if (!pre) {
      setDraft({ ...draft, base_url: "", kind: "openai" });
      return;
    }
    setDraft({
      ...draft,
      kind: "openai",
      id: draft.existing ? draft.id : pre.id,
      title: draft.existing ? draft.title : pre.title,
      base_url: pre.base_url,
      model: draft.model || pre.model,
    });
  };

  const save = (e: FormEvent) => {
    e.preventDefault();
    if (!draft) return;
    setBusy("save");
    setErr(null);
    api
      .providerSave({
        id: draft.id.trim(),
        title: draft.title.trim(),
        kind: draft.kind,
        base_url: draft.base_url.trim(),
        model: draft.model.trim(),
        models: modelList.length ? modelList.map((m) => m.id) : draft.models,
        ...(draft.key.trim() ? { key: draft.key.trim() } : {}),
      })
      .then(() => {
        setDraft(null);
        setNote(S.providers.saved);
        load();
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(null));
  };
  const fetchModels = () => {
    if (!draft) return;
    setBusy("models");
    setErr(null);
    const body = draft.key.trim()
      ? { base_url: draft.base_url.trim(), key: draft.key.trim() }
      : draft.existing
        ? { id: draft.existing.id, base_url: draft.base_url.trim() }
        : { base_url: draft.base_url.trim(), key: "" };
    api
      .providerModels(body)
      .then((r) => {
        setModelList(r.models);
        setNote(null);
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(null));
  };
  const test = (p: Provider, model?: string) => {
    setBusy("test:" + p.id);
    setErr(null);
    setNote(null);
    api
      .providerTest(p.id, model)
      .then((r: ProviderTest) => setNote(`${p.title}: ${S.providers.testOk(r)}`))
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(null));
  };
  const makeDefault = (p: Provider) => {
    setBusy("default:" + p.id);
    api
      .providerDefault(p.id)
      .then(load)
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(null));
  };
  const remove = (p: Provider) => {
    if (!window.confirm(S.providers.removeConfirm(p.title))) return;
    api
      .providerDelete(p.id)
      .then(load)
      .catch((e: Error) => setErr(e.message));
  };

  const presetId = draft ? (data?.presets.find((x) => x.base_url === draft.base_url)?.id ?? "") : "";
  return (
    <section className="providers" aria-label={S.providers.title}>
      <h3>{S.providers.title}</h3>
      <p className="muted small">{S.providers.hint}</p>
      {data && (
        <p className={"small " + (data.secure ? "muted" : "level-warning")} role={data.secure ? undefined : "alert"}>
          {data.secure ? S.providers.secure : S.providers.insecure}
          {data.providers.length === 0
            ? " " + S.providers.envHint(data.env.base_url, data.env.model, data.env.has_key)
            : ""}
        </p>
      )}
      {!admin && <p className="muted small">{S.providers.notAdmin}</p>}
      {err && (
        <p className="level-error small" role="alert">
          {err}
        </p>
      )}
      {note && (
        <p className="ok small" role="status">
          {note}
        </p>
      )}
      {data && data.providers.length === 0 && !draft && <p className="muted small">{S.providers.empty}</p>}
      {data && data.providers.length > 0 && (
        <ul className="providers__list">
          {data.providers.map((p) => (
            <li key={p.id} className={"providers__item" + (p.default ? " default" : "")}>
              <div className="providers__meta">
                <span>
                  <strong>{p.title}</strong> <span className="mono muted small">{p.id}</span>
                  {p.default && <span className="badge badge--ok"> {S.providers.isDefault}</span>}
                </span>
                <span className="mono small muted">
                  {p.kind === "claude-code" ? S.providers.kindClaude : `${p.base_url} · ${p.model || "—"}`}
                </span>
                <span className="muted small">
                  {p.kind === "openai" ? (p.has_key ? `${S.providers.key}: …${p.key_tail}` : S.providers.noKey) : ""}
                  {p.updated ? ` · ${p.updated_by ?? ""} ${relativeTime(p.updated)}` : ""}
                </span>
              </div>
              {admin && (
                <span className="commit__actions" style={{ margin: 0 }}>
                  {p.kind === "openai" && (
                    <button
                      className="link small"
                      onClick={() => test(p)}
                      disabled={busy !== null}
                      aria-busy={busy === "test:" + p.id}
                    >
                      {busy === "test:" + p.id ? S.providers.testing : S.providers.test}
                    </button>
                  )}
                  {!p.default && (
                    <button className="link small" onClick={() => makeDefault(p)} disabled={busy !== null}>
                      {S.providers.makeDefault}
                    </button>
                  )}
                  <button className="link small" onClick={() => startEdit(p)} disabled={busy !== null}>
                    {S.providers.edit}
                  </button>
                  <button className="link small" onClick={() => remove(p)} disabled={busy !== null}>
                    {S.providers.remove}
                  </button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {admin && !draft && (
        <div>
          <button onClick={startNew}>{S.providers.add}</button>
        </div>
      )}
      {admin && draft && (
        <form className="providers__form" onSubmit={save} aria-label={S.providers.add}>
          <div className="providers__row">
            <label>
              {S.providers.preset}
              <select value={presetId} onChange={(e) => applyPreset(e.target.value)} disabled={draft.kind !== "openai"}>
                <option value="">{S.providers.custom}</option>
                {data?.presets.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {S.providers.id}
              <input
                value={draft.id}
                placeholder={S.providers.idPlaceholder}
                onChange={(e) => setDraft({ ...draft, id: e.target.value })}
                disabled={!!draft.existing}
                required
              />
            </label>
          </div>
          <div className="providers__row">
            <label>
              {S.providers.titleLabel}
              <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
            </label>
            <label>
              {S.providers.kindOpenai}
              <select
                value={draft.kind}
                onChange={(e) => setDraft({ ...draft, kind: e.target.value as Draft["kind"] })}
                aria-label="Вид провайдера"
              >
                <option value="openai">{S.providers.kindOpenai}</option>
                <option value="claude-code">{S.providers.kindClaude}</option>
              </select>
            </label>
          </div>
          {draft.kind === "openai" && (
            <>
              <label>
                {S.providers.baseUrl}
                <input
                  value={draft.base_url}
                  placeholder="https://openrouter.ai/api/v1"
                  onChange={(e) => setDraft({ ...draft, base_url: e.target.value })}
                  required
                />
              </label>
              <label>
                {S.providers.key}
                <input
                  type="password"
                  autoComplete="off"
                  value={draft.key}
                  placeholder={
                    draft.existing?.has_key ? S.providers.keyKeep(draft.existing.key_tail) : S.providers.keyNew
                  }
                  onChange={(e) => setDraft({ ...draft, key: e.target.value })}
                />
              </label>
              <label>
                {S.providers.model}
                <input
                  list="provider-models"
                  value={draft.model}
                  placeholder={S.providers.modelPlaceholder}
                  onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                />
                <datalist id="provider-models">
                  {modelList.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.prompt != null && m.completion != null ? S.providers.price(m.prompt, m.completion) : m.name}
                    </option>
                  ))}
                </datalist>
              </label>
              <div className="commit__actions" style={{ margin: 0 }}>
                <button
                  type="button"
                  className="link"
                  onClick={fetchModels}
                  disabled={busy !== null || !draft.base_url.trim() || (!draft.key.trim() && !draft.existing?.has_key)}
                  aria-busy={busy === "models"}
                >
                  {busy === "models" ? S.providers.fetching : S.providers.fetchModels}
                </button>
                {modelList.length > 0 && <span className="muted small">{S.providers.modelsGot(modelList.length)}</span>}
              </div>
            </>
          )}
          <div className="commit__actions" style={{ margin: 0 }}>
            <button type="submit" disabled={busy !== null || !draft.id.trim()} aria-busy={busy === "save"}>
              {busy === "save" ? S.providers.saving : S.providers.save}
            </button>
            {draft.existing && draft.kind === "openai" && (
              <button
                type="button"
                className="link"
                onClick={() => test(draft.existing!, draft.model)}
                disabled={busy !== null}
              >
                {S.providers.test}
              </button>
            )}
            <button type="button" className="link" onClick={() => setDraft(null)} disabled={busy === "save"}>
              {S.providers.cancel}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
