import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider, useParams, useSearchParams } from "react-router-dom";
import { App } from "./App";
import { Start } from "./screens/Start";
import { Workbench } from "./screens/Workbench";
import { Tokens } from "./screens/Tokens";
import "./index.css";

/** Старые адреса экранов (лента, сравнение, агент, вариант, параметры) ведут в рабочее место проекта (M2.5). */
function Legacy({ stage, tab, r }: { stage?: string; tab?: string; r?: string }) {
  const { project = "", variant } = useParams();
  const [params] = useSearchParams();
  const q = new URLSearchParams();
  const v = variant ?? params.get("variant");
  if (v) q.set("v", v);
  if (tab) q.set("tab", tab);
  if (r) q.set("r", r);
  const mode = params.get("mode");
  const s = mode === "layout" ? "layout" : stage;
  if (mode === "sketch") q.set("tab", "sketch");
  const qs = q.toString();
  return <Navigate to={`/p/${encodeURIComponent(project)}${s ? `/s/${s}` : ""}${qs ? `?${qs}` : ""}`} replace />;
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Start /> },
      { path: "tokens", element: <Tokens /> },
      { path: "p/:project", element: <Workbench /> },
      { path: "p/:project/s/:stage", element: <Workbench /> },
      { path: "p/:project/commits", element: <Legacy r="history" /> },
      { path: "p/:project/compare", element: <Legacy stage="design" tab="compare" /> },
      { path: "p/:project/agent", element: <Legacy /> },
      { path: "p/:project/layout", element: <Legacy stage="layout" /> },
      { path: "p/:project/:variant/params", element: <Legacy stage="design" tab="params" /> },
      { path: "p/:project/:variant", element: <Legacy stage="design" /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
