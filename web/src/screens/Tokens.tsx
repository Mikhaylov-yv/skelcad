import { useCallback, useEffect, useState } from "react";
import { api, type Me, type TokenInfo } from "../api";
import { S } from "../strings";
import { relativeTime } from "../ui/format";

export function Tokens() {
  const [me, setMe] = useState<Me | null>(null);
  const [list, setList] = useState<TokenInfo[]>([]);
  const [mcpUrl, setMcpUrl] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [made, setMade] = useState<{ name: string; command: string; token: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    api
      .tokens()
      .then((r) => {
        setList(r.tokens);
        setMcpUrl(r.mcp_url);
        setErr(null);
      })
      .catch((e: Error) => setErr(e.message));
  }, []);
  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
    load();
  }, [load]);

  const create = () => {
    setBusy(true);
    setErr(null);
    api
      .tokenCreate(name.trim())
      .then((r) => {
        setMade({ name: r.name, command: r.command, token: r.token });
        setName("");
        setCopied(false);
        load();
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(false));
  };
  const revoke = (n: string) => {
    if (!window.confirm(S.tokens.revokeConfirm(n))) return;
    api
      .tokenDelete(n)
      .then(load)
      .catch((e: Error) => setErr(e.message));
  };
  const copy = () => {
    if (!made) return;
    navigator.clipboard?.writeText(made.command).then(() => setCopied(true));
  };

  return (
    <main className="page tokens">
      <h1>{S.tokens.title}</h1>
      <p className="muted small">{S.tokens.hint}</p>
      {me && !me.admin && <p className="callout">{S.tokens.notAdmin}</p>}
      {mcpUrl && (
        <p className="small">
          {S.tokens.mcp}: <code className="mono">{mcpUrl}</code>
        </p>
      )}
      {err && (
        <p className="level-error" role="alert">
          {err}
        </p>
      )}
      {me?.admin && (
        <form
          className="commit__actions"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create();
          }}
        >
          <label className="small">
            {S.tokens.name}:{" "}
            <input value={name} placeholder={S.tokens.namePlaceholder} onChange={(e) => setName(e.target.value)} />
          </label>
          <button type="submit" disabled={!name.trim() || busy} aria-busy={busy}>
            {busy ? S.tokens.creating : S.tokens.create}
          </button>
        </form>
      )}
      {made && (
        <div className="callout tokens__made" role="status">
          <p>
            <strong>{made.name}</strong> — {S.tokens.created}
          </p>
          <pre className="mono small">{made.command}</pre>
          <button onClick={copy}>{copied ? S.tokens.copied : S.tokens.copy}</button>
        </div>
      )}
      <h3>{S.tokens.list}</h3>
      {list.length === 0 && <p className="muted small">{S.tokens.empty}</p>}
      <ul className="tokens__list">
        {list.map((t) => (
          <li key={t.name} className="tokens__item">
            <span className="mono">{t.name}</span>
            <span className="muted small">
              {t.created ? `${S.tokens.by(t.created_by ?? "")} · ${relativeTime(t.created)}` : S.tokens.static}
            </span>
            {me?.admin && t.created && (
              <button className="link small" onClick={() => revoke(t.name)}>
                {S.tokens.revoke}
              </button>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
