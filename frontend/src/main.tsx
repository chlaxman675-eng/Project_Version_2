import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import App from "./App";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import LiveConsolePage from "./pages/LiveConsolePage";
import MapPage from "./pages/MapPage";
import DispatchPage from "./pages/DispatchPage";
import TelemetryPage from "./pages/TelemetryPage";
import CitizenPage from "./pages/CitizenPage";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/citizen" element={<CitizenPage />} />
        <Route element={<App />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/live" element={<LiveConsolePage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/dispatch" element={<DispatchPage />} />
          <Route path="/telemetry" element={<TelemetryPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
