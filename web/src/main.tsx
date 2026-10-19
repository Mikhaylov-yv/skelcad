import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { App } from "./App";
import { Projects } from "./screens/Projects";
import { Variant } from "./screens/Variant";
import { Feed } from "./screens/Feed";
import { Compare } from "./screens/Compare";
import { Params } from "./screens/Params";
import { Agent } from "./screens/Agent";
import "./index.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Projects /> },
      { path: "p/:project/commits", element: <Feed /> },
      { path: "p/:project/compare", element: <Compare /> },
      { path: "p/:project/agent", element: <Agent /> },
      { path: "p/:project/:variant/params", element: <Params /> },
      { path: "p/:project/:variant", element: <Variant /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
