import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
// fonts are bundled with the app so it looks right offline (review rooms, firewalled networks)
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "@fontsource/geist-sans/400.css";
import "@fontsource/geist-sans/500.css";
import "@fontsource/geist-mono/400.css";
import "@fontsource/geist-mono/500.css";
import "./index.css";
import { ThemeProvider } from "./lib/theme";
import Architecture from "./pages/Architecture";
import Create from "./pages/Create";
import Evaluation from "./pages/Evaluation";
import Optimization from "./pages/Optimization";
import Overview from "./pages/Overview";
import Playground from "./pages/Playground";
import Reports from "./pages/Reports";
import RequirementsPage from "./pages/Requirements";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="create" element={<Create />} />
          <Route path="create/:wid" element={<Create />} />
          <Route path="requirements" element={<RequirementsPage />} />
          <Route path="architecture" element={<Architecture />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="optimization" element={<Optimization />} />
          <Route path="playground" element={<Playground />} />
          <Route path="reports" element={<Reports />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
);
