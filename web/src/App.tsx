import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api, type Me } from "./api";
import { S } from "./strings";

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          {S.app}
        </NavLink>
        <nav aria-label="Разделы">
          <NavLink to="/" end>
            {S.nav.projects}
          </NavLink>
          <NavLink to="/tokens">{S.nav.tokens}</NavLink>
        </nav>
        <div id="topbar-center" className="topbar__center" />
        <span className="topbar__user">
          {me && (
            <>
              <span title={me.email ?? undefined}>{me.auth === "none" ? S.user.guest : me.name}</span>
              {me.logout_url && (
                <a className="topbar__logout" href={me.logout_url}>
                  {S.user.logout}
                </a>
              )}
            </>
          )}
        </span>
      </header>
      <Outlet />
    </div>
  );
}
