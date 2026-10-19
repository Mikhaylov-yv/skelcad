import { NavLink, Outlet } from "react-router-dom";
import { S } from "./strings";

export function App() {
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
        </nav>
        <span className="topbar__user" id="user-slot" />
      </header>
      <Outlet />
    </div>
  );
}
