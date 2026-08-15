import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import { Layout } from "./Layout";
import { Overview } from "./pages/Overview";
import { Jobs } from "./pages/Jobs";
import { JobDetail } from "./pages/JobDetail";
import { Applications } from "./pages/Applications";
import { HumanReview } from "./pages/HumanReview";
import { Analytics } from "./pages/Analytics";
import { Settings } from "./pages/Settings";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "jobs", element: <Jobs /> },
      { path: "jobs/:jobId", element: <JobDetail /> },
      { path: "applications", element: <Applications /> },
      { path: "human-review", element: <HumanReview /> },
      { path: "analytics", element: <Analytics /> },
      { path: "settings", element: <Settings /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
